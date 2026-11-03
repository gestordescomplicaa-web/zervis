"""O vigia das fontes de fora (ADR 0059): o que o Zé consome e não depende de nós.

O buscador, o leitor de páginas, o Chromium, as fontes do CNPJ, a Wikimedia, o WhatsApp e o
token do Instagram mudam sem avisar: uma versão nova, uma API que sai do ar, um token que vence.
Uma vez por semana (e quando o usuário pergunta "está tudo funcionando?"), cada fonte é testada
de verdade, com um pedido pequeno. O resultado fica em `ESTADO/fontes.json`; o Zé fala quando
uma fonte quebra ou volta, não toda semana a mesma coisa.

Cada verificação é uma função que devolve um detalhe curto quando está tudo certo e levanta
quando não está; quem monta a lista (o núcleo) decide o que se aplica nesta máquina.
"""

import concurrent.futures
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from zervis import lugares

log = logging.getLogger(__name__)

ARQUIVO = lugares.ESTADO / "fontes.json"
SEMANA_S = 7 * 86400
TEMPO_S = 90.0  # o teto da rodada inteira
Verificacao = Callable[[], str]


def _ler(arquivo: Path) -> dict[str, Any]:
    try:
        dados = json.loads(arquivo.read_text())
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


class Vigia:
    def __init__(
        self,
        verificacoes: Callable[[], dict[str, Verificacao]],
        arquivo: Path = ARQUIVO,
        agora: Callable[[], float] = time.time,
    ) -> None:
        self.verificacoes = verificacoes  # montadas a cada rodada: o que está em uso muda
        self.arquivo = arquivo
        self.agora = agora
        self.rodando = False
        self._em: float | None = None  # a última checagem, sem ler o disco a cada segundo

    @property
    def ultimo(self) -> dict[str, Any]:
        return _ler(self.arquivo)

    def vencido(self) -> bool:
        if self._em is None:
            self._em = float(self.ultimo.get("em", 0) or 0)
        return self.agora() - self._em > SEMANA_S

    def checar(self) -> dict[str, Any]:
        """Testa todas as fontes ao mesmo tempo e grava. Fonte que estoura o tempo é falha."""
        self.rodando = True
        try:
            lista = self.verificacoes()
            ex = concurrent.futures.ThreadPoolExecutor(len(lista) or 1, "vigia")
            futuros = {nome: ex.submit(f) for nome, f in lista.items()}
            concurrent.futures.wait(futuros.values(), timeout=TEMPO_S)
            ex.shutdown(wait=False, cancel_futures=True)
            fontes = {}
            for nome, futuro in futuros.items():
                if not futuro.done():
                    fontes[nome] = {"ok": False, "detalhe": "não respondeu a tempo"}
                elif (erro := futuro.exception()) is not None:
                    detalhe = " ".join(str(erro).split())[:160] or type(erro).__name__
                    fontes[nome] = {"ok": False, "detalhe": detalhe}
                else:
                    fontes[nome] = {"ok": True, "detalhe": str(futuro.result())[:160]}
            self._em = self.agora()
            resultado = {"em": self._em, "fontes": fontes}
            try:
                self.arquivo.parent.mkdir(parents=True, exist_ok=True)
                self.arquivo.write_text(json.dumps(resultado, ensure_ascii=False, indent=1))
            except OSError as erro:
                log.warning("vigia: não gravou %s: %s", self.arquivo, erro)
            return resultado
        finally:
            self.rodando = False

    def checar_e_contar(self) -> str | None:
        """Checa e devolve a fala sobre o que mudou desde a última vez (None se nada mudou)."""
        antes = self.ultimo.get("fontes") or {}
        agora = self.checar()["fontes"]
        quebrou = [n for n, f in agora.items() if not f["ok"] and antes.get(n, {}).get("ok", True)]
        voltou = [n for n, f in agora.items() if f["ok"] and antes.get(n, {}).get("ok") is False]
        partes = []
        if quebrou:
            detalhes = "; ".join(f"{n}: {agora[n]['detalhe']}" for n in quebrou)
            partes.append(f"Parou de funcionar: {detalhes}.")
        if voltou:
            partes.append(f"Voltou a funcionar: {', '.join(voltou)}.")
        return " ".join(partes) or None


def fala(resultado: dict[str, Any]) -> str:
    """O resumo para responder "está tudo funcionando?"."""
    fontes = resultado.get("fontes") or {}
    if not fontes:
        return "Ainda não chequei as fontes."
    ruins = {n: f for n, f in fontes.items() if not f.get("ok")}
    quando = time.strftime("%d/%m às %H:%M", time.localtime(float(resultado.get("em", 0))))
    if not ruins:
        return f"Tudo funcionando: {', '.join(fontes)} (checado em {quando})."
    bons = [n for n in fontes if n not in ruins]
    ruim = "; ".join(f"{n}: {f.get('detalhe', '')}" for n, f in ruins.items())
    return f"Com problema: {ruim}. Funcionando: {', '.join(bons) or 'nenhuma'} ({quando})."


def verificacoes(
    buscador: Any,
    central: Callable[[], Any] = lambda: None,
    instagram: Callable[[], Any] = lambda: None,
) -> dict[str, Verificacao]:
    """As verificações desta máquina, com o nome falado de cada fonte. WhatsApp e Instagram só
    entram quando estão em uso (escolhido no painel, token guardado)."""
    from zervis.atendimento import whatsapp
    from zervis.imersivo import capturas, imagens
    from zervis.pesquisa import cnpj, leitor

    def o_buscador() -> str:
        if not buscador.preparado:
            if buscador.falha:
                raise RuntimeError(f"não preparou: {buscador.falha}")
            buscador.preparar_em_segundo_plano()
            return "ainda preparando"
        achados = buscador.buscar("Wikipédia Brasil")
        if not achados:
            raise RuntimeError("a busca voltou vazia (os buscadores podem ter bloqueado)")
        motores = sorted({m for r in achados for m in r.motores})
        return f"{len(achados)} resultados ({', '.join(motores)})"

    def o_leitor() -> str:
        p = leitor.ler("https://pt.wikipedia.org/wiki/Brasil", js=False)
        if len(p.texto) < leitor.POUCO:
            raise RuntimeError("o texto da página veio vazio")
        return f"{len(p.texto)} caracteres lidos"

    def o_chromium() -> str:
        if capturas.navegador() is None:
            raise RuntimeError("o Chromium não está instalado")
        if "Example Domain" not in capturas.renderizar("https://example.com"):
            raise RuntimeError("o Chromium não abriu a página de teste")
        return "abre páginas"

    def fonte_cnpj(modelo: str) -> Verificacao:
        def checar() -> str:
            dados = cnpj._abrir(modelo.format("00000000000191"))  # o Banco do Brasil
            if not isinstance(dados, dict) or not dados.get("razao_social"):
                raise RuntimeError("o formato da resposta mudou")
            return "responde"

        return checar

    def a_wikimedia() -> str:
        if not imagens.buscar_wikipedia("Brasil"):
            raise RuntimeError("a busca de imagens voltou vazia")
        return "responde"

    lista: dict[str, Verificacao] = {
        "o buscador": o_buscador,
        "o leitor de páginas": o_leitor,
        "o Chromium": o_chromium,
        **{nome: fonte_cnpj(modelo) for nome, modelo in cnpj.FONTES},
        "a Wikimedia": a_wikimedia,
    }
    if whatsapp.escolhido() and central() is not None:

        def o_whatsapp() -> str:
            estado = str(central().para_tela().get("estado", ""))
            if estado != "conectado":
                raise RuntimeError(f"está {estado or 'sem resposta'}: reconecte em Redes sociais")
            return "conectado"

        lista["o WhatsApp"] = o_whatsapp
    conta = instagram()
    if conta is not None and conta.conectado:

        def o_instagram() -> str:
            dados = conta.perfil()
            if not dados.get("username"):
                raise RuntimeError("o perfil veio vazio")
            return f"@{dados['username']}"

        lista["o Instagram"] = o_instagram
    return lista
