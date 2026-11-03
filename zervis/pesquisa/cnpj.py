"""O cadastro de uma empresa na Receita Federal pelo CNPJ (ADR 0059): razão social, situação,
atividade, endereço, capital, porte e quadro de sócios, que são dados públicos.

Vem da BrasilAPI (MIT, comunitária) e, se ela falhar, do minhareceita.org (o mesmo formato, que é
de onde a BrasilAPI tira esse dado). Os dois são gratuitos e sem chave. Aceita o CNPJ numérico e o
alfanumérico (Receita, julho de 2026), conferindo os dígitos antes de perguntar.
"""

import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

FONTES = (
    ("BrasilAPI", "https://brasilapi.com.br/api/cnpj/v1/{}"),
    ("minhareceita.org", "https://minhareceita.org/{}"),
)
TEMPO_S = 12.0
SOCIOS_MAX = 20
Abrir = Callable[[str], Any]  # devolve o JSON da fonte; None = não existe


class CnpjErro(RuntimeError):
    pass


def _digito(base: str) -> str:
    pesos = list(range(len(base) - 7, 1, -1)) + list(range(9, 1, -1))
    soma = sum((ord(c) - 48) * p for c, p in zip(base, pesos, strict=True))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def normalizar(cnpj: str) -> str:
    """Os 14 caracteres do CNPJ, conferidos; CnpjErro se não for um CNPJ."""
    limpo = re.sub(r"[\s./-]", "", cnpj).upper()
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", limpo) or len(set(limpo)) == 1:
        raise CnpjErro("isso não é um CNPJ (são 14 caracteres)")
    if _digito(limpo[:12]) + _digito(limpo[:12] + _digito(limpo[:12])) != limpo[12:]:
        raise CnpjErro("esse CNPJ não confere (algum número está errado)")
    return limpo


def formatado(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def _abrir(url: str) -> Any:
    pedido = urllib.request.Request(url, headers={"User-Agent": "Zervis"})  # noqa: S310 (https fixo)
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_S) as r:  # noqa: S310
            return json.loads(r.read(2 * 1024 * 1024))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            return None
        raise


def _texto(valor: Any) -> str:
    return " ".join(str(valor or "").split())


def resumo(d: dict[str, Any], fonte: str) -> dict[str, Any]:
    """O que interessa do cadastro, sem campo vazio e sem CPF (que já vem mascarado)."""
    endereco = ", ".join(
        p
        for p in (
            _texto(f"{d.get('descricao_tipo_de_logradouro') or ''} {d.get('logradouro') or ''}"),
            _texto(d.get("numero")),
            _texto(d.get("complemento")),
            _texto(d.get("bairro")),
            _texto(f"{d.get('municipio') or ''} - {d.get('uf') or ''}").strip(" -"),
            _texto(d.get("cep")),
        )
        if p
    )
    socios = [
        {
            "nome": _texto(s.get("nome_socio")),
            "qualificacao": _texto(s.get("qualificacao_socio")),
            "desde": _texto(s.get("data_entrada_sociedade")),
        }
        for s in (d.get("qsa") or [])[:SOCIOS_MAX]
        if isinstance(s, dict) and s.get("nome_socio")
    ]
    secundarias = [
        _texto(c.get("descricao"))
        for c in (d.get("cnaes_secundarios") or [])[:8]
        if isinstance(c, dict) and c.get("descricao")
    ]
    campos = {
        "cnpj": formatado(str(d.get("cnpj") or "")),
        "razao_social": _texto(d.get("razao_social")),
        "nome_fantasia": _texto(d.get("nome_fantasia")),
        "situacao": _texto(d.get("descricao_situacao_cadastral")),
        "desde_a_situacao": _texto(d.get("data_situacao_cadastral")),
        "matriz_ou_filial": _texto(d.get("descricao_identificador_matriz_filial")),
        "abertura": _texto(d.get("data_inicio_atividade")),
        "atividade": _texto(d.get("cnae_fiscal_descricao")),
        "outras_atividades": secundarias,
        "natureza_juridica": _texto(d.get("natureza_juridica")),
        "porte": _texto(d.get("porte")),
        "capital_social": d.get("capital_social") or "",
        "simples": "sim" if d.get("opcao_pelo_simples") else "",
        "mei": "sim" if d.get("opcao_pelo_mei") else "",
        "endereco": endereco,
        "telefone": _texto(d.get("ddd_telefone_1")),
        "email": _texto(d.get("email")).lower(),
        "socios": socios,
        "fonte": f"{fonte} (dados públicos da Receita Federal)",
    }
    return {k: v for k, v in campos.items() if v}


def consultar(cnpj: str, abrir: Abrir = _abrir) -> dict[str, Any]:
    """O cadastro pela primeira fonte que responder; CnpjErro se nenhuma achar."""
    numero = normalizar(cnpj)
    nao_achou = 0
    for nome, modelo in FONTES:
        try:
            dados = abrir(modelo.format(numero))
        except (urllib.error.URLError, OSError, ValueError) as erro:
            log.info("cnpj: %s falhou (%s)", nome, type(erro).__name__)
            continue
        if dados is None:
            nao_achou += 1
            continue
        if isinstance(dados, dict) and dados.get("razao_social"):
            return resumo(dados, nome)
    if nao_achou:
        raise CnpjErro(f"o CNPJ {formatado(numero)} não está no cadastro da Receita")
    raise CnpjErro("as fontes do CNPJ não responderam agora")
