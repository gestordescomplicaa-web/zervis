"""A bateria de avaliação do cérebro: o motor com um cérebro falso (o de verdade gasta a conta
de quem usa e roda em `zervis avaliar`)."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, ClassVar

import pytest

from zervis import avaliacao
from zervis.avaliacao import Cenario, Rodada
from zervis.cerebro.base import Aprovar, EventoCerebro, Fim, Texto


class Roteiro:
    """Um cérebro falso que chama as ferramentas do roteiro e responde o texto dado."""

    def __init__(
        self, ferramentas: list[Any], passos: list[tuple[str, dict[str, Any]]], texto: str
    ):
        self.ferramentas = {f.name: f for f in ferramentas}
        self.passos, self.texto = passos, texto
        self.aprovar: Aprovar | None = None
        self.persona = ""
        self.fechado = False

    async def start(self, persona: str, aprovar: Aprovar | None = None) -> None:
        self.persona, self.aprovar = persona, aprovar

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        for nome, entrada in self.passos:
            if nome == "sessao_enviar" and self.aprovar is not None:
                await self.aprovar("Estou enviando sua solicitação, confirma?")
            await self.ferramentas[nome].handler(entrada)
        yield Texto(self.texto)
        yield Fim()

    async def close(self) -> None:
        self.fechado = True


def _criar(passos: list[tuple[str, dict[str, Any]]], texto: str) -> Callable[[list[Any]], Roteiro]:
    return lambda ferramentas: Roteiro(ferramentas, passos, texto)


def _cenario(**espera: Any) -> Cenario:
    return Cenario(
        "teste", "teste", "o que tem no meu n8n?",
        {"sessoes_listar": json.dumps([{"id": "s1", "nome": "Loja"}])}, espera,
    )  # fmt: skip


def test_os_cenarios_da_bateria_carregam_e_citam_ferramentas_reais() -> None:
    cenarios = avaliacao.carregar()
    assert len(cenarios) >= 10
    for c in cenarios:
        avaliacao.simuladas(c, Rodada())  # recusa ferramenta que não existe
        assert c.espera, c.arquivo


def test_as_ferramentas_simuladas_tem_as_descricoes_reais_e_nao_executam_nada() -> None:
    rodada = Rodada()
    c = _cenario()
    ferramentas = {f.name: f for f in avaliacao.simuladas(c, rodada)}
    reais = {f.name: f for f in avaliacao.definicoes()}
    assert ferramentas.keys() == reais.keys()
    assert ferramentas["sessoes_listar"].description == reais["sessoes_listar"].description

    async def chamar(nome: str, entrada: dict[str, Any]) -> dict[str, Any]:
        return await ferramentas[nome].handler(entrada)

    saida = asyncio.run(chamar("sessoes_listar", {}))
    assert json.loads(saida["content"][0]["text"]) == [{"id": "s1", "nome": "Loja"}]
    asyncio.run(chamar("sessao_criar", {"nome": "x"}))  # sem resposta: o padrão
    assert [ch.ferramenta for ch in rodada.chamadas] == ["sessoes_listar", "sessao_criar"]


def test_julga_ferramentas_argumentos_resposta_e_formato_de_voz() -> None:
    c = _cenario(
        usa=["sessoes_listar"],
        nao_usa=["sessao_criar"],
        entrada_em_alguma={"sessao_ler": "s1", "sessao_enviar": "s1"},
        resposta_alguma=["fluxo"],
        pergunta=False,
    )
    passos = [
        ("sessoes_listar", {}),
        ("sessao_enviar", {"sessao": "s1", "texto": "liste os fluxos"}),
    ]
    rodada = asyncio.run(avaliacao.rodar(c, _criar(passos, "Pedi à Loja a lista de fluxos."), "p"))
    regras = avaliacao.julgar(c, rodada)
    assert avaliacao.nota(regras), [r for r in regras if not r.ok]
    assert rodada.aprovacoes  # o pedido de aprovação foi respondido pelo cenário

    errado = asyncio.run(
        avaliacao.rodar(c, _criar([("sessao_criar", {"nome": "n8n"})], "**Pronto!**\n- feito"), "p")
    )
    falhas = {r.regra for r in avaliacao.julgar(c, errado) if not r.ok}
    assert {"usa sessoes_listar", "não usa sessao_criar", "sem Markdown"} <= falhas
    assert any("alvo certo" in f for f in falhas) and any("fluxo" in f for f in falhas)


def test_resposta_longa_ou_erro_do_cerebro_reprovam() -> None:
    c = _cenario()
    longa = asyncio.run(avaliacao.rodar(c, _criar([], "palavra " * 120), "p"))
    assert not avaliacao.nota(avaliacao.julgar(c, longa))

    class Quebrado(Roteiro):
        async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
            yield Fim("limite")

    quebrado = asyncio.run(avaliacao.rodar(c, lambda f: Quebrado(f, [], ""), "p"))
    assert quebrado.erro == "limite" and not avaliacao.nota(avaliacao.julgar(c, quebrado))


def test_aprovacao_negada_chega_ao_cerebro() -> None:
    c = Cenario("negado", "negado", "publica", {}, {}, aprovar=False)
    respostas: list[bool] = []

    class Pergunta(Roteiro):
        async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
            assert self.aprovar is not None
            respostas.append(bool(await self.aprovar("Posso publicar?")))
            yield Texto("Tudo bem, não publiquei.")
            yield Fim()

    asyncio.run(avaliacao.rodar(c, lambda f: Pergunta(f, [], ""), "p"))
    assert respostas == [False]


def test_cenario_invalido_e_recusado(tmp_path: Path) -> None:
    (tmp_path / "sem-pedido.toml").write_text('nome = "x"\n')
    with pytest.raises(avaliacao.AvaliacaoErro, match="pedido"):
        avaliacao.carregar(tmp_path)
    (tmp_path / "sem-pedido.toml").write_text('pedido = "oi"\n[ferramentas]\nnao_existe = "x"\n')
    (cenario,) = avaliacao.carregar(tmp_path)
    with pytest.raises(avaliacao.AvaliacaoErro, match="desconhecida"):
        avaliacao.simuladas(cenario, Rodada())


def test_resumo_compara_com_a_rodada_anterior() -> None:
    from zervis.avaliacao.__main__ import resumo

    def rel(**taxas: list[bool]) -> dict[str, Any]:
        return {"cenarios": [{"arquivo": a, "rodadas": [{"passou": p} for p in v]}
                             for a, v in taxas.items()]}  # fmt: skip

    texto = resumo(rel(a=[True, True], b=[True, False]), rel(a=[True, False], b=[True, False]))
    assert "Nota: 75%" in texto and "1 de 2" in texto
    assert "melhorou: a (50% → 100%)" in texto and "b" not in texto.split("melhorou")[1]


def test_a_persona_da_avaliacao_nao_leva_dados_de_ninguem() -> None:
    from zervis.avaliacao.__main__ import persona

    texto = persona()
    assert "Você atende Ana." in texto and "Omarchy" in texto


def test_cerebro_sem_responder_fica_sem_nota_e_para_no_limite(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from zervis.avaliacao.__main__ import avaliar, resumo

    class Limite(Roteiro):
        async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
            yield Fim("limite_de_uso")

    cenarios = [_cenario(), _cenario()]
    relatorio = asyncio.run(avaliar(cenarios, lambda f: Limite(f, [], ""), 3))
    assert relatorio["parou"] == "limite_de_uso"
    assert [len(c["rodadas"]) for c in relatorio["cenarios"]] == [1, 0]  # parou na primeira
    assert resumo(relatorio, {}) == "Sem nota: o cérebro não respondeu em nenhum cenário."


def test_a_referencia_e_a_ultima_rodada_de_cada_cenario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zervis.avaliacao import __main__ as executor

    monkeypatch.setattr(executor, "HISTORICO", tmp_path)

    def rel(**taxas: bool | None) -> str:
        return json.dumps({"cenarios": [{"arquivo": a, "rodadas": [{"passou": p}]}
                                        for a, p in taxas.items()]})  # fmt: skip

    (tmp_path / "1.json").write_text(rel(a=False, b=True))
    (tmp_path / "2.json").write_text(rel(a=True))  # só o "a" rodou de novo
    (tmp_path / "3.json").write_text(rel(b=None))  # o "b" sem nota não conta
    anterior = {c["arquivo"]: c["rodadas"][0]["passou"] for c in executor._anterior()["cenarios"]}
    assert anterior == {"a": True, "b": True}


def test_cada_rodada_anota_os_tokens_por_parte() -> None:
    """Pedido de 28/10/2026: medir qualidade e custo juntos, antes e depois de cada corte."""

    class ComUso(Roteiro):
        uso: ClassVar[dict[str, int]] = {
            "input_tokens": 300,
            "cache_read_input_tokens": 15000,
            "output_tokens": 20,
        }
        modelo = "gpt-5.6-luna"

    rodada = asyncio.run(avaliacao.rodar(_cenario(), lambda f: ComUso(f, [], "Oi."), "P"))
    assert rodada.tokens == 15320 and rodada.via == "completo"
    assert rodada.gastos[0]["modelo"] == "gpt-5.6-luna"

    class Roteado(Roteiro):
        gastos: ClassVar[list[dict[str, Any]]] = [
            {"rotulo": "rapida", "modelo": "s", "entrada": 4, "cache_lido": 1400,
             "cache_criado": 0, "saida": 20},
        ]  # fmt: skip

    rodada = asyncio.run(avaliacao.rodar(_cenario(), lambda f: Roteado(f, [], "Oi."), "P"))
    assert rodada.tokens == 1424 and rodada.via == "rapida"


def test_resumo_mostra_os_tokens_e_compara_os_mesmos_cenarios() -> None:
    from zervis.avaliacao.__main__ import resumo

    def rel(**tokens: int) -> dict[str, Any]:
        return {"cenarios": [{"arquivo": a, "rodadas": [{"passou": True, "tokens": t}]}
                             for a, t in tokens.items()]}  # fmt: skip

    texto = resumo(rel(a=1500, b=30000), rel(a=16000, c=99000))
    assert "Tokens: 15,8 mil por cenário, em média (antes 16,0 mil → agora 1,5 mil nos mesmos)" in (
        texto
    )


def test_a_referencia_e_do_mesmo_cerebro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from zervis.avaliacao import __main__ as executor

    monkeypatch.setattr(executor, "HISTORICO", tmp_path)

    def rel(rotulo: str, passou: bool) -> str:
        return json.dumps(
            {"rotulo": rotulo, "cenarios": [{"arquivo": "a", "rodadas": [{"passou": passou}]}]}
        )

    (tmp_path / "1.json").write_text(rel("codex:gpt", True))
    (tmp_path / "2.json").write_text(rel("claude:sonnet", False))
    assert executor._anterior("codex:gpt")["cenarios"][0]["rodadas"][0]["passou"] is True
    assert executor._anterior("claude:sonnet")["cenarios"][0]["rodadas"][0]["passou"] is False
