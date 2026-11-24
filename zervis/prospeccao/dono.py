"""Quem decide na empresa e por onde chegar a ele (ADR 0127).

Ligar para o número da empresa cai no vendedor ou na recepção. O cadastro da Receita é público e
traz o quadro de sócios (o sócio-administrador é quem decide) e o telefone que a empresa deu ao
abrir o CNPJ, que na empresa pequena costuma ser o celular do dono; às vezes, o do contador.

1. O CNPJ: a busca do Zé pelo nome e pela cidade; os CNPJs que aparecem nos resultados são
   conferidos na Receita (ativo, na cidade, com uma palavra do nome em comum).
2. O decisor: o sócio-administrador; sem quadro de sócios (empresário individual, MEI), o nome
   da razão social.
3. Os telefones, na ordem: o celular da Receita (se não parece do contador) e o do Google Maps.
"""

import logging
import re
import unicodedata
from collections.abc import Callable, Iterable
from typing import Any

log = logging.getLogger(__name__)

CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
CANDIDATOS = 4  # CNPJs conferidos por empresa: cada um é uma consulta à Receita
# O e-mail do cadastro diz quando quem abriu o CNPJ foi o escritório de contabilidade: o telefone
# do lado é o dele, não o do dono.
CONTADOR = re.compile(r"contab|contador|contabil|escritorio|assessoria|fiscal", re.IGNORECASE)
VAZIAS = frozenset(
    [
        "ltda",
        "me",
        "epp",
        "eireli",
        "sa",
        "s/a",
        "cia",
        "comercio",
        "servicos",
        "industria",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "em",
        "the",
        "and",
        "loja",
        "clinica",
    ]
)  # palavras que não identificam uma empresa

Buscar = Callable[[str], Iterable[Any]]  # resultados com titulo, url e trecho
Consultar = Callable[[str], dict[str, Any]]  # o resumo de zervis.pesquisa.cnpj


def sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )


def palavras(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z0-9]{3,}", sem_acento(texto)) if p not in VAZIAS}


def cnpjs(texto: str) -> list[str]:
    vistos: list[str] = []
    for achado in CNPJ.findall(texto):
        numero = re.sub(r"\D", "", achado)
        if numero not in vistos:
            vistos.append(numero)
    return vistos


def confere(cadastro: dict[str, Any], nome: str, cidade: str) -> bool:
    """O cadastro é desta empresa? Ativo, na cidade e com uma palavra do nome em comum."""
    if sem_acento(str(cadastro.get("situacao", ""))) != "ativa":
        return False
    cidade_ = sem_acento(cidade.split(",")[0].split(" - ")[0]).strip()
    if cidade_ and cidade_ not in sem_acento(str(cadastro.get("endereco", ""))):
        return False
    nomes = f"{cadastro.get('nome_fantasia', '')} {cadastro.get('razao_social', '')}"
    return bool(palavras(nome) & palavras(nomes))


def achar_cnpj(
    nome: str, cidade: str, buscar: Buscar, consultar: Consultar
) -> dict[str, Any] | None:
    """O cadastro da Receita desta empresa, ou None se a busca não achou um que confira."""
    resultados = list(buscar(f'"{nome}" {cidade.split(",")[0]} CNPJ'))
    candidatos: list[str] = []
    for r in resultados:
        texto = f"{getattr(r, 'titulo', '')} {getattr(r, 'trecho', '')} {getattr(r, 'url', '')}"
        candidatos += [c for c in cnpjs(texto) if c not in candidatos]
    for numero in candidatos[:CANDIDATOS]:
        try:
            cadastro = consultar(numero)
        except Exception as erro:  # fora do ar ou inexistente: o próximo
            log.info("prospecção: CNPJ não conferido (%s)", type(erro).__name__)
            continue
        if confere(cadastro, nome, cidade):
            return cadastro
    return None


def _titulo(nome: str) -> str:
    return " ".join(p.capitalize() for p in nome.split())


def decisor(cadastro: dict[str, Any]) -> tuple[str, str]:
    """O nome de quem decide e o porquê ("Sócio-Administrador"); vazio se não dá para saber."""
    socios = [s for s in cadastro.get("socios") or [] if isinstance(s, dict) and s.get("nome")]
    if socios:
        admin = next(
            (s for s in socios if "administrador" in sem_acento(s.get("qualificacao", ""))), None
        )
        escolhido = admin or socios[0]
        if admin is None and len(socios) > 1:
            return "", ""  # vários sócios e nenhum administrador: não chuta
        return _titulo(str(escolhido["nome"])), str(escolhido.get("qualificacao", "")) or "Sócio"
    natureza = sem_acento(str(cadastro.get("natureza_juridica", "")))
    if "individual" in natureza or cadastro.get("mei"):
        nome = re.sub(r"[\d.\-/]+", " ", str(cadastro.get("razao_social", ""))).strip()
        if len(nome.split()) >= 2:
            return _titulo(nome), "Titular"
    return "", ""


def primeiro_nome(nome: str) -> str:
    return nome.split()[0] if nome.split() else ""


def _com_pais(digitos: str) -> str:
    if len(digitos) in (10, 11):
        return f"55{digitos}"
    return digitos if digitos.startswith("55") and len(digitos) in (12, 13) else ""


def celular(telefone: str) -> bool:
    """55 + DDD + 9 dígitos começando por 9, ou o antigo de 8 dígitos começando por 6 a 9."""
    numero = telefone[4:]
    return (len(numero) == 9 and numero[0] == "9") or (len(numero) == 8 and numero[0] in "6789")


def chave_do_telefone(telefone: str) -> str:
    """DDD e os 8 últimos dígitos: o mesmo número com e sem o nono dígito dá a mesma chave."""
    d = re.sub(r"\D", "", telefone)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    return f"{d[:2]}{d[-8:]}" if len(d) >= 10 else d


def telefones(cadastro: dict[str, Any], do_maps: str) -> list[dict[str, str]]:
    """Os números para tentar, o melhor primeiro, cada um com a origem."""
    saida: list[dict[str, str]] = []
    receita = _com_pais(re.sub(r"\D", "", str(cadastro.get("telefone", ""))))
    do_contador = bool(CONTADOR.search(str(cadastro.get("email", ""))))
    if receita and celular(receita) and not do_contador:
        saida.append({"numero": receita, "origem": "Receita"})
    maps = _com_pais(do_maps)
    if maps and all(chave_do_telefone(maps) != chave_do_telefone(t["numero"]) for t in saida):
        saida.append({"numero": maps, "origem": "Google"})
    # O fixo da Receita por último: há empresa com o WhatsApp Business num fixo.
    repetido = any(chave_do_telefone(receita) == chave_do_telefone(t["numero"]) for t in saida)
    if receita and not celular(receita) and not do_contador and not repetido:
        saida.append({"numero": receita, "origem": "Receita"})
    return saida
