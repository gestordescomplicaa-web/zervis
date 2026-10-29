"""Via rápida: conversa no motor rápido, ferramenta no completo, a mesma conversa nos dois."""

import asyncio
import json
import threading
from collections.abc import AsyncIterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from zervis import config
from zervis.cerebro import rapido
from zervis.cerebro.base import Aprovar, EventoCerebro, Fim, Texto


class MotorFalso:
    nome = "falso"
    modelo = "rapido-1"
    com_estado = False
    uso = None

    def __init__(self, respostas: list[list[str]], atraso_s: float = 0.0) -> None:
        self.respostas = respostas
        self.atraso_s = atraso_s
        self.pedidos: list[list[dict[str, str]]] = []
        self.interrompido = 0

    async def iniciar(self, sistema: str) -> None:
        self.sistema = sistema

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        self.pedidos.append(mensagens)
        await asyncio.sleep(self.atraso_s)
        for pedaco in self.respostas.pop(0):
            yield pedaco

    async def interromper(self) -> None:
        self.interrompido += 1

    async def reiniciar(self) -> None:
        return None

    async def fechar(self) -> None:
        return None


class CompletoFalso:
    modelo = "claude-sonnet-5-5"

    def __init__(self) -> None:
        self.pedidos: list[str] = []
        self.uso = {"input_tokens": 10}
        self.ferramentas_usadas = ["mcp__jarvis__tela_agir"]

    async def start(self, persona: str, aprovar: Aprovar | None = None) -> None:
        return None

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        self.pedidos.append(texto)
        yield Texto("Abri o Mapa.")
        yield Fim()

    async def interrupt(self) -> None:
        return None

    async def reset(self) -> None:
        return None

    async def close(self) -> None:
        return None


def falar(roteado: rapido.Roteado, texto: str) -> str:
    async def juntar() -> str:
        partes = []
        async for evento in roteado.ask(texto):
            if isinstance(evento, Texto):
                partes.append(evento.texto)
        return "".join(partes)

    return asyncio.run(juntar())


def roteado(motor: MotorFalso, espera_s: float = 1.0) -> tuple[rapido.Roteado, CompletoFalso]:
    completo = CompletoFalso()
    r = rapido.Roteado(completo, motor, "PERSONA RÁPIDA", lambda: "MEMÓRIA", espera_s)
    asyncio.run(r.start("PERSONA COMPLETA"))
    return r, completo


def test_conversa_simples_fica_na_via_rapida_com_o_historico() -> None:
    motor = MotorFalso([["Oi, Ana", "! Tudo certo."], ["Às três da tarde."]])
    r, completo = roteado(motor)
    assert falar(r, "Oi Zé") == "Oi, Ana! Tudo certo."
    assert r.via == "rapida" and r.ferramentas_usadas == [] and completo.pedidos == []
    assert falar(r, "Que horas são?") == "Às três da tarde."
    assert motor.pedidos[-1] == [
        {"role": "user", "content": "Oi Zé"},
        {"role": "assistant", "content": "Oi, Ana! Tudo certo."},
        {"role": "user", "content": "Que horas são?"},
    ]
    assert motor.sistema == "PERSONA RÁPIDA\n\nMEMÓRIA"


def test_pedido_de_acao_passa_ao_completo_com_aviso_e_a_conversa_anterior() -> None:
    motor = MotorFalso([["Oi!"], ["[comp", "leto]"], ["Beleza."]])
    r, completo = roteado(motor)
    falar(r, "Oi Zé")
    assert falar(r, "Me ajuda numa coisa") == "Deixa eu ver. Abri o Mapa."  # o motor passou
    assert r.via == "completo" and r.ferramentas_usadas == ["mcp__jarvis__tela_agir"]
    assert completo.pedidos == [
        "(Antes disto, na mesma conversa: Usuário: «Oi Zé» Zé: «Oi!»)\nMe ajuda numa coisa"
    ]
    # Ação clara vai direto, sem perguntar ao motor; o aviso varia.
    assert falar(r, "[09/10, 11:30] (Janela: aberta) Abre o mapa") == "Um instante. Abri o Mapa."
    assert len(motor.pedidos) == 2 and len(completo.pedidos) == 2
    assert falar(r, "Valeu") == "Beleza."  # a via rápida vê o que o completo respondeu
    assert {"role": "assistant", "content": "Abri o Mapa."} in motor.pedidos[-1]


@pytest.mark.parametrize(
    ("pedido", "completo"),
    [
        ("[sexta, 09/10/2026, 11:30] (Janela do Zé: aberta) Abre o mapa.", True),
        ("[x] Zé, pesquisa o preço do dólar", True),
        ("[x] Qual é o meu foco agora?", True),
        ("[x] Lembra que eu prefiro café sem açúcar", True),
        ("[x] O que conversamos ontem?", True),
        ("[x] Oi Zé, tudo bem?", False),
        ("[x] Quanto é dezessete vezes três?", False),
        ("[x] Me conta uma curiosidade sobre polvos", False),
        ("[x] Valeu", False),
        # Explicar com a janela aberta é uma cena na tela (ADR 0047); fechada, fica falado.
        ("[x] (Janela do Zé: aberta, é a janela ativa) Zé, me explica o que é MCP", True),
        ("[x] (Janela do Zé: aberta, em segundo plano) Se apresenta", True),
        ("[x] (Janela do Zé: fechada (não há Núcleo na tela).) Me explica o que é MCP", False),
    ],
)
def test_acao_clara_vai_direto_ao_completo(pedido: str, completo: bool) -> None:
    assert rapido.precisa_do_completo(pedido) is completo


def test_marca_de_emocao_antes_nao_esconde_o_passar_nem_a_resposta() -> None:
    assert rapido.Roteado._decidir("[duvida] [completo]") == "passar"
    assert rapido.Roteado._decidir("[alegria] Boa") == "falar"
    assert rapido.Roteado._decidir("[aleg") == "esperar"
    assert rapido.Roteado._decidir("  ") == "esperar"
    assert rapido.Roteado._decidir("[alegria]", fim=True) == "falar"
    motor = MotorFalso([["[alegria]", " Que", " bom!"]])
    r, _ = roteado(motor)
    assert falar(r, "Fechei o contrato") == "[alegria] Que bom!"


def test_motor_lento_ou_quebrado_vai_ao_completo() -> None:
    lento = MotorFalso([["Oi"]], atraso_s=0.5)
    r, completo = roteado(lento, espera_s=0.1)
    assert falar(r, "Oi") == "Deixa eu ver. Abri o Mapa."
    assert lento.interrompido == 1 and len(completo.pedidos) == 1

    class Quebrado(MotorFalso):
        async def gerar(self, s: str, m: list[dict[str, str]]) -> AsyncIterator[str]:
            raise rapido.MotorErro("HTTP 401")
            yield ""  # pragma: no cover

    r, completo = roteado(Quebrado([]))
    assert falar(r, "Oi") == "Deixa eu ver. Abri o Mapa."


# --- HTTP de verdade, num servidor local --------------------------------------------------


class Servidor:
    def __init__(self, linhas: list[str]) -> None:
        self.pedidos: list[dict[str, Any]] = []
        self.conexoes: set[tuple[str, int]] = set()
        dono = self

        class Tratador(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:
                corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                dono.pedidos.append(
                    {"caminho": self.path, "corpo": corpo, "cabecalhos": dict(self.headers)}
                )
                dono.conexoes.add(self.client_address)
                dados = "".join(f"{linha}\n\n" for linha in linhas).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def log_message(self, *args: object) -> None:
                return None

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Tratador)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.endereco = f"http://127.0.0.1:{self.http.server_port}/v1"

    def parar(self) -> None:
        self.http.shutdown()
        self.http.server_close()


def gerar_tudo(motor: rapido.Motor, vezes: int = 1) -> list[str]:
    async def rodar() -> list[str]:
        await motor.iniciar("SIS")
        saida = []
        for _ in range(vezes):
            saida.append(
                "".join([p async for p in motor.gerar("SIS", [{"role": "user", "content": "oi"}])])
            )
        return saida

    return asyncio.run(rodar())


def test_motor_openai_em_fluxo_reusa_a_conexao_e_pede_pouco_raciocinio() -> None:
    sse = [
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        'data: {"choices":[{"delta":{"content":"Oi, "}}]}',
        'data: {"choices":[{"delta":{"content":"Ana."}}]}',
        "data: [DONE]",
    ]
    servidor = Servidor(sse)
    try:
        motor = rapido.MotorOpenAI("ponte", servidor.endereco, "k1", "gpt-5.4-mini", "low", 200)
        assert gerar_tudo(motor, vezes=2) == ["Oi, Ana.", "Oi, Ana."]
        pedido = servidor.pedidos[0]
        assert pedido["caminho"] == "/v1/chat/completions"
        assert pedido["cabecalhos"]["Authorization"] == "Bearer k1"
        assert pedido["corpo"]["messages"][0] == {"role": "system", "content": "SIS"}
        assert pedido["corpo"]["reasoning_effort"] == "low"
        assert pedido["corpo"]["max_tokens"] == 200 and pedido["corpo"]["stream"] is True
        assert len(servidor.conexoes) == 1  # o aperto de mão uma vez só
        sem = rapido.MotorOpenAI("ponte", servidor.endereco, None, "claude-haiku", "low")
        assert "reasoning_effort" not in sem.corpo("S", [])
    finally:
        servidor.parar()


def test_motor_anthropic_em_fluxo() -> None:
    sse = [
        "event: message_start",
        'data: {"type":"message_start","message":{}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Tudo "}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"certo."}}',
        'data: {"type":"message_stop"}',
    ]
    servidor = Servidor(sse)
    try:
        motor = rapido.MotorAnthropic("k2", "claude-haiku-4-5", servidor.endereco, 150)
        assert gerar_tudo(motor) == ["Tudo certo."]
        pedido = servidor.pedidos[0]
        assert pedido["caminho"] == "/v1/messages"
        assert pedido["cabecalhos"]["x-api-key"] == "k2"
        assert pedido["corpo"]["system"] == "SIS" and pedido["corpo"]["max_tokens"] == 150
    finally:
        servidor.parar()


def test_erro_http_vira_motor_erro() -> None:
    motor = rapido.MotorOpenAI("ponte", "http://127.0.0.1:9/v1", None, "x")
    with pytest.raises(rapido.MotorErro):
        gerar_tudo(motor)


def test_criar_motor_e_a_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    via = dict(config.PADRAO["via_rapida"])
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(rapido, "CHAVES", tmp_path / "chaves-vazia")  # nunca a pasta real
    assert isinstance(rapido.criar_motor(via, tmp_path), rapido.MotorPlano)
    assert rapido.criar_motor({**via, "motor": "openai"}, tmp_path) is None  # sem chave
    chave = tmp_path / "openai.key"
    chave.write_text("sk-teste\n")
    motor = rapido.criar_motor(
        {**via, "motor": "openai", "arquivo_chave": str(chave), "modelo": "gpt-5.4-mini"}, tmp_path
    )
    assert isinstance(motor, rapido.MotorOpenAI) and motor.chave == "sk-teste"
    assert motor.http.host == "api.openai.com"
    with pytest.raises(config.ConfigInvalida, match="endereco"):
        config.validar({"via_rapida": {"motor": "ponte"}}, "t")
    with pytest.raises(config.ConfigInvalida, match=r"via_rapida\.motor"):
        config.validar({"via_rapida": {"motor": "groq"}}, "t")
    desligado = CompletoFalso()
    assert rapido.envolver(desligado, {**via, "ligada": False}, tmp_path, "P") is desligado


def test_religar_troca_o_motor_sem_reiniciar_o_completo() -> None:
    async def rodar() -> None:
        completo = CompletoFalso()
        um, dois = MotorFalso([["Oi do um."]]), MotorFalso([["Oi do dois."]])
        ligado = await rapido.religar(completo, um, "P")
        assert isinstance(ligado, rapido.Roteado) and ligado.completo is completo
        trocado = await rapido.religar(ligado, dois, "P")
        assert trocado is ligado and ligado.motor is dois
        desligado = await rapido.religar(trocado, None, "P")
        assert desligado is completo

    asyncio.run(rodar())


class MotorComFalha(MotorFalso):
    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        self.pedidos.append(mensagens)
        for pedaco in self.respostas.pop(0):
            yield pedaco
        raise rapido.MotorErro("limite_de_uso")


def test_falha_depois_da_primeira_palavra_nao_repete_no_completo() -> None:
    motor = MotorComFalha([["Já comecei."]])
    r, completo = roteado(motor)
    assert falar(r, "Oi") == "Já comecei."
    assert completo.pedidos == []


def test_motor_automatico_usa_proxima_conta() -> None:
    primeira = MotorComFalha([[]])
    segunda = MotorFalso([["Oi!"], ["Sim."]])
    motor = rapido.MotorContas([primeira, segunda])

    async def rodar() -> None:
        await motor.iniciar("persona")
        assert [p async for p in motor.gerar("persona", [{"role": "user", "content": "Olá"}])] == [
            "Oi!"
        ]
        assert [
            p async for p in motor.gerar("persona", [{"role": "user", "content": "Tudo bem?"}])
        ] == ["Sim."]
        assert len(primeira.pedidos) == 1
        await motor.fechar()

    asyncio.run(rodar())


def test_so_no_live_por_padrao(tmp_path: Path) -> None:
    """ADR 0042, etapa 2: a via rápida responde na conversa em tempo real; no Normal e no
    teclado, tudo vai ao cérebro completo, a menos que a pessoa escolha "sempre"."""
    via = {**config.PADRAO["via_rapida"], "motor": "ponte", "endereco": "http://127.0.0.1:9/v1"}
    assert via["quando"] == "live"
    assert not rapido.vale_agora(via, live=False) and rapido.vale_agora(via, live=True)
    assert rapido.vale_agora({**via, "quando": "sempre"}, live=False)
    assert not rapido.vale_agora({**via, "ligada": False}, live=True)
    completo = CompletoFalso()
    assert rapido.envolver(completo, via, tmp_path, "P") is completo
    assert isinstance(rapido.envolver(completo, via, tmp_path, "P", live=True), rapido.Roteado)
    assert rapido.validar_escolha({"quando": "sempre"}) == {"quando": "sempre"}
    with pytest.raises(rapido.MotorErro, match="quando"):
        rapido.validar_escolha({"quando": "as vezes"})
    with pytest.raises(config.ConfigInvalida, match=r"via_rapida\.quando"):
        config.validar({"via_rapida": {"quando": "nunca"}}, "t")


class MotorQueFalha(MotorFalso):
    """O motor da assinatura que recusa (a chave sem crédito) e leva 5 s para parar."""

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        raise rapido.MotorErro("acesso_invalido")
        yield ""  # pragma: no cover (só para ser gerador)

    async def interromper(self) -> None:
        await asyncio.sleep(5)


def test_motor_que_falha_nao_atrasa_o_completo() -> None:
    """Teste de 27/10/2026: cada falha da via rápida esperava 5 s o motor parar antes de o
    cérebro completo começar."""
    import time

    async def rodar() -> float:
        roteado = rapido.Roteado(CompletoFalso(), MotorQueFalha([]), "P")
        roteado.motor_ok = True
        inicio = time.monotonic()
        async for evento in roteado.ask("oi, tudo bem?"):
            if isinstance(evento, Fim):
                break
        return time.monotonic() - inicio

    assert asyncio.run(rodar()) < 1.0


def test_o_motor_da_assinatura_nao_usa_a_chave_do_painel(tmp_path: Path) -> None:
    """Com o login do Claude feito, a chave de API (que tem a vez sobre o login) não entra no
    motor "plano"; sem login, fica o que houver."""
    from zervis.cerebro import contas

    conta = contas.Conta("claude:principal", "claude", "Principal", pasta=str(tmp_path))
    assert rapido.pela_assinatura(conta) == {}
    conta.login.parent.mkdir(parents=True, exist_ok=True)
    conta.login.write_text("{}")
    assert rapido.pela_assinatura(conta) == {"ANTHROPIC_API_KEY": ""}
