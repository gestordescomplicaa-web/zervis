"""O mapa de contratos do painel (docs/plano-design.md): cada botão, pelo nome que aparece na
tela, e o que ele pede ao Zé (a escrita e os campos dela).

O redesenho muda a aparência, não as funções. Se um botão sumir, mudar de nome ou passar a pedir
outra coisa, este teste diz qual, em qual página. Mudança de propósito (um botão novo, um nome
melhor): `ZE_ATUALIZAR_CONTRATOS=1 uv run pytest tests/test_painel_contratos.py` regrava o mapa,
e a diferença fica à vista no PR. A Imersão é outro servidor e fica de fora (ADR 0100); o que
protege ela é `tests/test_imersao_protegida.py`.
"""

import asyncio
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import websockets

from tests.test_painel_no_navegador import (
    CHROMIUM,
    RESPOSTAS,
    _carregar,
    _Navegador,
    _paginas,
    _painel,
)
from zervis.portal.acoes import Acoes
from zervis.portal.servidor import Escrita

MAPA = Path(__file__).with_name("painel_contratos.json")
# Leituras feitas por POST que se repetem sozinhas (o terminal e a cópia da sessão abertos, a
# sessão central que a página Melhorias acompanha): o número delas depende do relógio, não do botão.
REPETIDAS = {"terminal/ler", "sessao/ler", "terminal/tamanho", "ze/central"}
# Nada de janela de verdade: confirmar diz sim, perguntar devolve o padrão, links não abrem.
PREPARO = (
    "window.confirm = () => true; window.prompt = (_m, d) => d || 'Exemplo';"
    " window.alert = () => {}; window.open = () => null;"
)
# Fora do mapa: o aviso de terminal fechado das sessões, que aparece quando o terminal (outro
# canal, com testes próprios) cai, e isso depende do relógio, não do painel.
BOTOES = (
    "[...document.querySelectorAll('#conteudo button, #conteudo input[type=submit],"
    " #conteudo [role=button]')].filter((b) => b.offsetParent !== null"
    " && !b.closest('#terminal-fechado'))"
)
ABRIR_DETALHES = (
    "document.querySelectorAll('#conteudo details').forEach((d) => { d.open = true; });"
)
LISTAR = f"""(() => {{
  {ABRIR_DETALHES}
  const nome = (b) => (b.getAttribute('aria-label') || b.innerText || b.value || b.title || '')
    .trim().replace(/\\s+/g, ' ');
  const vistos = {{}};
  return {BOTOES}.map((b) => {{
    const n = nome(b) || '(sem nome)';
    vistos[n] = (vistos[n] || 0) + 1;
    return {{nome: vistos[n] > 1 ? `${{n}} (${{vistos[n]}})` : n, desligado: !!b.disabled}};
  }});
}})()"""
# A casca: o menu e os controles de voz de toda página (o redesenho os muda de lugar).
CASCA = """(() => [...document.querySelectorAll(
    'nav a[data-secao], .lateral button, .lateral select')]
  .map((e) => (e.getAttribute('aria-label') || e.dataset.secao || e.innerText || '').trim()
  .replace(/\\s+/g, ' ')).filter(Boolean))()"""


class Gravador:
    """As escritas que o painel faz, com os campos (os valores mudam, os nomes não)."""

    def __init__(self) -> None:
        self.trava = threading.Lock()
        self.feitas: list[tuple[str, tuple[str, ...]]] = []
        self.respostas = json.loads(RESPOSTAS.read_text())["escritas"]

    def escrita(self, nome: str) -> Escrita:
        def escrever(dados: dict[str, Any]) -> Any:
            with self.trava:
                self.feitas.append((nome, tuple(sorted(dados))))
            return json.loads(json.dumps(self.respostas.get(nome, {})))

        return escrever

    def limpar(self) -> None:
        with self.trava:
            self.feitas.clear()

    def quantas(self) -> int:
        with self.trava:
            return len(self.feitas)

    def chamadas(self) -> list[str]:
        with self.trava:
            feitas = list(self.feitas)
        return sorted({f"{n}({','.join(c)})" for n, c in feitas if n not in REPETIDAS})


async def _abrir(nav: _Navegador, pagina: str) -> list[dict[str, Any]]:
    await nav.avaliar(f'(async () => {{ location.hash = "#{pagina}"; await abrir(); }})()')
    await asyncio.sleep(0.2)
    return await nav.avaliar(LISTAR) or []


async def _do_zero(nav: _Navegador, pagina: str) -> list[dict[str, Any]]:
    """O painel recarregado de verdade, sem o que as páginas guardaram (aba, filtro, rascunho):
    mudar só o endereço não recarrega, e o estado de um clique vazava para o seguinte."""
    await nav.avaliar("localStorage.clear(); sessionStorage.clear()")
    await nav.comando("Page.reload", {})
    await asyncio.sleep(0.3)
    for _ in range(100):
        if await nav.avaliar("window.__atalhos === true && !!document.querySelector('#conteudo')"):
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.3)
    return await _abrir(nav, pagina)


async def _quieto(gravador: Gravador) -> None:
    """Espera as escritas do clique pararem de chegar (até ~2 s)."""
    antes, iguais = -1, 0
    for _ in range(14):
        await asyncio.sleep(0.15)
        agora = gravador.quantas()
        iguais = iguais + 1 if agora == antes else 0
        antes = agora
        if iguais >= 2:
            return


async def _mapear(depuracao: str, endereco: str, gravador: Gravador) -> dict[str, Any]:
    mapa: dict[str, Any] = {}
    async with websockets.connect(depuracao, max_size=None) as ws:
        nav = _Navegador(ws)
        await _carregar(nav, endereco)
        await nav.comando("Page.addScriptToEvaluateOnNewDocument", {"source": PREPARO})
        await nav.avaliar(PREPARO)
        await nav.comando("Page.setInterceptFileChooserDialog", {"enabled": True})
        mapa["(casca)"] = await nav.avaliar(CASCA)
        for pagina in _paginas():
            base = await _do_zero(nav, pagina)
            atual = base
            botoes: dict[str, Any] = {}
            for i, botao in enumerate(base):
                if botao["desligado"]:
                    botoes[botao["nome"]] = "desligado"
                    continue
                if atual != base:  # o clique anterior mudou a página: de novo, do zero
                    atual = await _abrir(nav, pagina)
                    if atual != base:
                        atual = await _do_zero(nav, pagina)
                if atual != base:
                    botoes[botao["nome"]] = "instável"
                    continue
                gravador.limpar()
                await nav.avaliar(f"(() => {{ {ABRIR_DETALHES} {BOTOES}[{i}].click(); }})()")
                await _quieto(gravador)
                botoes[botao["nome"]] = gravador.chamadas()
                atual = await nav.avaliar(LISTAR) or []
            mapa[pagina] = botoes
    return mapa


def _diferencas(antes: dict[str, Any], agora: dict[str, Any]) -> list[str]:
    linhas = []
    for pagina in sorted(set(antes) | set(agora)):
        a, b = antes.get(pagina), agora.get(pagina)
        if a is None or b is None:
            linhas.append(f"{pagina}: página {'nova' if a is None else 'sumiu'}")
            continue
        if pagina == "(casca)":
            if a != b:
                linhas.append(f"menu e controles de voz: {a} → {b}")
            continue
        for nome in sorted(set(a) | set(b)):
            if nome not in b:
                linhas.append(f"{pagina}: o botão “{nome}” sumiu (pedia {a[nome]})")
            elif nome not in a:
                linhas.append(f"{pagina}: botão novo “{nome}” ({b[nome]})")
            elif a[nome] != b[nome]:
                linhas.append(f"{pagina}: “{nome}” pedia {a[nome]}, agora pede {b[nome]}")
    return linhas


@pytest.mark.skipif(CHROMIUM is None, reason="sem Chromium na máquina")
def test_cada_botao_continua_pedindo_o_mesmo_ao_ze(tmp_path: Path) -> None:
    gravador = Gravador()
    nomes = Acoes(SimpleNamespace(), tmp_path, tmp_path).escritas()
    extras = {nome: gravador.escrita(nome) for nome in nomes}
    with _painel(tmp_path, extras=extras) as (depuracao, endereco):
        agora = asyncio.run(_mapear(depuracao, endereco, gravador))
    if os.environ.get("ZE_ATUALIZAR_CONTRATOS") == "1":
        MAPA.write_text(json.dumps(agora, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    instaveis = [
        f"{p}: {n}" for p, bs in agora.items() if p != "(casca)" for n, v in bs.items()
        if v == "instável"
    ]  # fmt: skip
    assert not instaveis, f"botões que não dá para clicar do mesmo jeito: {instaveis}"
    diferencas = _diferencas(json.loads(MAPA.read_text()), agora)
    assert not diferencas, "\n".join(diferencas)
