"""O cérebro local (ADR 0063): o laço de ferramentas do Ollama com as ferramentas e a aprovação do
Zé, a conversa que cabe no contexto, a data que não vira fala, e o catálogo, a config e a voz.
Um Ollama falso responde roteiros prontos; nada sai da máquina."""

import asyncio
import contextlib
import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import tool

from zervis.cerebro import catalogo, ferramentas, local
from zervis.cerebro.base import Fim, Resposta, Texto
from zervis.config import ConfigInvalida, validar
from zervis.nucleo import estados as e


class OllamaFalso:
    """Responde /api/chat com o próximo roteiro (uma lista de pedaços em NDJSON)."""

    def __init__(self, roteiros: list[list[dict[str, Any]]], modelos: list[str]) -> None:
        self.roteiros, self.modelos = roteiros, modelos
        self.pedidos: list[dict[str, Any]] = []
        self.lento = False
        self.lendo = threading.Event()
        self.caiu_em: float | None = None
        falso = self

        class Tratador(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                corpo = json.dumps({"models": [{"name": m} for m in falso.modelos]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def do_POST(self) -> None:
                pedido = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                falso.pedidos.append(pedido)
                if self.path == "/api/generate":  # carregar o modelo, sem pergunta
                    corpo = json.dumps({"done": True, "done_reason": "load"}).encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(corpo)))
                    self.end_headers()
                    self.wfile.write(corpo)
                    return
                if falso.lento:  # lendo um prompt longo: só termina quando o cliente cai
                    falso.lendo.set()
                    self.connection.settimeout(10)
                    inicio = time.monotonic()
                    with contextlib.suppress(OSError):
                        self.connection.recv(1)
                    falso.caiu_em = time.monotonic() - inicio
                    return
                if pedido["messages"][-1].get("content") == "ok":  # o aquecimento
                    roteiro = [{"done": True, "prompt_eval_count": 1, "eval_count": 1}]
                else:
                    roteiro = falso.roteiros.pop(0)
                corpo = b"".join(json.dumps(p).encode() + b"\n" for p in roteiro)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Tratador)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.endereco = f"http://127.0.0.1:{self.servidor.server_address[1]}"

    def chats(self) -> list[dict[str, Any]]:
        return [
            p
            for p in self.pedidos
            if p.get("messages") and p["messages"][-1].get("content") != "ok"
        ]


@pytest.fixture
def ollama() -> Iterator[OllamaFalso]:
    falso = OllamaFalso([], ["gemma4:e4b", "qwen3:8b"])
    yield falso
    falso.servidor.shutdown()


def _fala(texto: str) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": texto}}


def _fim(entrada: int = 100, saida: int = 10) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": ""}, "done": True,
            "prompt_eval_count": entrada, "eval_count": saida}  # fmt: skip


def _pede(nome: str, argumentos: dict[str, Any]) -> dict[str, Any]:
    chamada = {"function": {"name": nome, "arguments": argumentos}}
    return {"message": {"role": "assistant", "content": "", "tool_calls": [chamada]}}


def _cerebro(tmp_path: Path, ollama: OllamaFalso, feitos: list[str]) -> local.LocalBrain:
    @tool("cnpj_ler", "Lê o cadastro de uma empresa.", {"cnpj": str})
    async def cnpj_ler(args: dict[str, Any]) -> dict[str, Any]:
        feitos.append(f"ler {args['cnpj']}")
        return {"content": [{"type": "text", "text": "MAGAZINE LUIZA S/A, ativa"}]}

    @tool("whatsapp_mandar", "Manda uma mensagem.", {"texto": str})
    async def whatsapp_mandar(args: dict[str, Any]) -> dict[str, Any]:
        feitos.append(f"mandar {args['texto']}")
        return {"content": [{"type": "text", "text": "Enviado."}]}

    return local.LocalBrain(
        "gemma4:e4b",
        tmp_path,
        endereco=ollama.endereco,
        mcp={"jarvis": ferramentas.servidor([cnpj_ler, whatsapp_mandar])},
        livres=["mcp__jarvis__cnpj_ler"],
    )


async def _perguntar(b: local.LocalBrain, texto: str) -> tuple[str, str | None]:
    falado, erro = "", None
    async for ev in b.ask(texto):
        if isinstance(ev, Texto):
            falado += ev.texto
        elif isinstance(ev, Fim):
            erro = ev.erro
    return falado, erro


def test_usa_a_ferramenta_e_responde_com_o_resultado(tmp_path: Path, ollama: OllamaFalso) -> None:
    feitos: list[str] = []
    ollama.roteiros = [
        [_pede("cnpj_ler", {"cnpj": "47960950000121"}), _fim(17000, 20)],
        [_fala("É a Magazine Luiza,"), _fala(" ativa."), _fim(17100, 12)],
    ]
    b = _cerebro(tmp_path, ollama, feitos)

    async def rodar() -> tuple[str, str | None]:
        await b.start("Você é o Zé.", None)
        try:
            return await _perguntar(b, "consulta o CNPJ 47960950000121")
        finally:
            await b.close()

    falado, erro = asyncio.run(rodar())
    assert (falado, erro) == ("É a Magazine Luiza, ativa.", None)
    assert feitos == ["ler 47960950000121"]  # livre: sem pergunta
    assert b.ferramentas_usadas == ["mcp__jarvis__cnpj_ler"]
    assert b.uso == {"input_tokens": 34100, "output_tokens": 32}
    segundo = ollama.chats()[1]
    assert segundo["messages"][-1] == {
        "role": "tool",
        "tool_name": "cnpj_ler",
        "content": "MAGAZINE LUIZA S/A, ativa",
    }
    assert segundo["think"] is False and segundo["keep_alive"] == local.MANTER
    assert segundo["options"]["num_ctx"] == local.CONTEXTO
    nomes = [f["function"]["name"] for f in segundo["tools"]]
    assert nomes == ["cnpj_ler", "whatsapp_mandar"]  # o nome curto, sem mcp__jarvis__
    sistema = segundo["messages"][0]["content"]
    assert sistema.startswith("Você é o Zé.") and "nunca invente" in sistema
    assert segundo["messages"][1]["content"].startswith("[")  # a data, como nos outros cérebros


def test_acao_com_efeito_pede_o_sim_e_o_nao_cancela(tmp_path: Path, ollama: OllamaFalso) -> None:
    feitos: list[str] = []
    perguntas: list[str] = []
    respostas = [Resposta(False), Resposta(True)]

    async def aprovar(descricao: str) -> Resposta:
        perguntas.append(descricao)
        return respostas.pop(0)

    ollama.roteiros = [
        [_pede("whatsapp_mandar", {"texto": "oi"}), _fim()],
        [_fala("Não mandei."), _fim()],
        [_pede("whatsapp_mandar", {"texto": "oi"}), _fim()],
        [_fala("Mandei."), _fim()],
    ]
    b = _cerebro(tmp_path, ollama, feitos)

    async def rodar() -> list[tuple[str, str | None]]:
        await b.start("Zé", aprovar)
        try:
            return [await _perguntar(b, "manda oi"), await _perguntar(b, "manda oi de novo")]
        finally:
            await b.close()

    assert asyncio.run(rodar()) == [("Não mandei.", None), ("Mandei.", None)]
    assert len(perguntas) == 2 and feitos == ["mandar oi"]  # o "não" não mandou
    recusa = ollama.chats()[1]["messages"][-1]
    assert recusa["role"] == "tool" and recusa["content"]  # o motivo volta ao modelo


def test_ferramenta_inexistente_e_data_repetida_nao_viram_fala(
    tmp_path: Path, ollama: OllamaFalso
) -> None:
    ollama.roteiros = [
        [_pede("apagar_tudo", {}), _fim()],
        [_fala("[quarta-feira, 04/11"), _fala("/2026, 08:05] Não"), _fala(" posso."), _fim()],
    ]
    b = _cerebro(tmp_path, ollama, [])

    async def rodar() -> tuple[str, str | None]:
        await b.start("Zé", None)
        try:
            return await _perguntar(b, "apaga tudo")
        finally:
            await b.close()

    assert asyncio.run(rodar()) == ("Não posso.", None)
    assert "não existe" in ollama.chats()[1]["messages"][-1]["content"]


def test_ollama_fora_do_ar_falha_com_codigo(tmp_path: Path) -> None:
    b = local.LocalBrain("gemma4:e4b", tmp_path, endereco="http://127.0.0.1:9")

    async def rodar() -> tuple[str, str | None]:
        await b.start("Zé", None)
        try:
            return await _perguntar(b, "oi")
        finally:
            await b.close()

    assert asyncio.run(rodar()) == ("", "falha_local")


def test_a_conversa_corta_sempre_num_pedido() -> None:
    sistema: dict[str, Any] = {"role": "system", "content": "Zé"}
    conversa: list[dict[str, Any]] = [sistema]
    for i in range(6):
        conversa += [
            {"role": "user", "content": f"p{i}"},
            {"role": "assistant", "content": "", "tool_calls": [{}]},
            {"role": "tool", "content": "r"},
            {"role": "assistant", "content": f"r{i}"},
        ]
    aparada = local.aparar(conversa, 10)
    assert aparada[0] == sistema and aparada[1] == {"role": "user", "content": "p4"}
    assert len(aparada) == 9


def test_catalogo_config_e_voz(tmp_path: Path, ollama: OllamaFalso) -> None:
    cfg = validar({"cerebro": {"local_endereco": ollama.endereco}}, "teste")
    extras = catalogo.Extras(mcp={"jarvis": {}, "tempo": {}, "navegador": {}, "drive": {}})
    b = catalogo.criar("local", cfg, tmp_path, extras)
    assert isinstance(b, local.LocalBrain) and b.modelo == "gemma4:e4b"
    assert set(b.mcp) == {"jarvis", "tempo"}  # o navegador e os conectores ficam para a nuvem
    assert not b.pronto  # ainda não leu a persona e as ferramentas
    cfg["cerebro"]["modelo_local"] = "llama9:70b"
    with pytest.raises(catalogo.Indisponivel, match="não está instalado"):
        catalogo.criar("local", cfg, tmp_path)
    cfg["cerebro"]["local_endereco"] = "http://127.0.0.1:9"
    with pytest.raises(catalogo.Indisponivel, match="fora do ar"):
        catalogo.criar("local", cfg, tmp_path)
    with pytest.raises(ConfigInvalida, match="loopback"):
        validar({"cerebro": {"local_endereco": "http://192.168.0.5:11434"}}, "teste")
    assert local.modelos(ollama.endereco) == ["gemma4:e4b", "qwen3:8b"]
    assert local.modelos("http://127.0.0.1:9") == []
    for frase in ("muda para o local", "usa o modelo local", "troca pro gemma", "usa o ollama"):
        assert e.troca(frase) == "local", frase
    assert asyncio.run(local.testar("http://127.0.0.1:9", "gemma4:e4b")) == (
        False,
        "O Ollama está fora do ar.",
    )


def test_fechar_corta_a_leitura_em_curso(tmp_path: Path, ollama: OllamaFalso) -> None:
    """Caso de 04/11/2026: trocar de modelo no meio da leitura inicial deixava o Ollama lendo o
    prompt antigo por minutos, com a GPU em 99%, e os pedidos novos na fila."""
    ollama.lento = True
    b = _cerebro(tmp_path, ollama, [])

    async def rodar() -> None:
        await b.start("Zé", None)  # o aquecimento começa a ler
        await asyncio.to_thread(ollama.lendo.wait, 5)
        await b.close()

    asyncio.run(rodar())
    deadline = time.monotonic() + 3
    while ollama.caiu_em is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ollama.caiu_em is not None and ollama.caiu_em < 2  # a conexão caiu na hora


def test_testar_carrega_o_modelo_sem_perguntar(ollama: OllamaFalso) -> None:
    ok, mensagem = asyncio.run(local.testar(ollama.endereco, "gemma4:e4b"))
    assert (ok, mensagem) == (True, "Conectado: gemma4:e4b carregado.")
    assert ollama.pedidos == [{"model": "gemma4:e4b", "keep_alive": local.MANTER}]
    ok, mensagem = asyncio.run(local.testar(ollama.endereco, "llama9:70b"))
    assert not ok and "não está instalado" in mensagem


def test_so_aparecem_os_que_funcionam_o_recomendado_primeiro() -> None:
    """Pedido de 04/11/2026: a lista mostrava tudo o que estava instalado no Ollama, inclusive o
    functiongemma, que não funciona como cérebro."""
    falso = OllamaFalso([], ["functiongemma:270m", "qwen3:8b", "gemma2:2b", "gemma4:e4b"])
    try:
        assert local.que_funcionam(falso.endereco) == [
            {"id": "gemma4:e4b", "nome": "gemma4:e4b · recomendado"},
        ]  # o qwen3:8b não cabe na RAM livre desta máquina com o contexto do Zé
    finally:
        falso.servidor.shutdown()
    assert local.que_funcionam("http://127.0.0.1:9") == []
    for fora in ("functiongemma:270m", "gemma2:2b", "qwen3:8b"):
        assert fora not in local.FUNCIONAM


def test_sair_do_local_tira_o_modelo_da_memoria(tmp_path: Path, ollama: OllamaFalso) -> None:
    """Caso de 04/11/2026: depois de sair do local, o qwen3:8b seguia ocupando 9,8 GB por horas."""
    b = _cerebro(tmp_path, ollama, [])

    async def rodar() -> None:
        await b.start("Zé", None)
        await b.close()

    asyncio.run(rodar())
    assert {"model": "gemma4:e4b", "keep_alive": 0} in ollama.pedidos


def test_resultado_grande_chega_curto_ao_modelo_local() -> None:
    """Teste real de 04/11/2026: ler a pesquisa inteira (~4 mil tokens) deixava a primeira palavra
    em 50 a 67 s; com as fontes compactas, 20 s."""
    pesquisa = {
        "pergunta": "concorrentes",
        "fontes": [
            {
                "titulo": f"Fonte {i}",
                "site": f"s{i}.com",
                "data": "2026-10-01",
                "trechos": ["x" * 900, "y" * 900],
            }
            for i in range(5)
        ],
        "outros_resultados": [{"url": "https://a.com", "trecho": "z" * 2000}],
        "dica": 'Feche com "Fontes:".',
    }
    curto = local.encurtar(json.dumps(pesquisa))
    assert curto.startswith("Fontes lidas:\n- Fonte 0 (s0.com, 2026-10-01): x")
    assert curto.count("\n- ") == 5 and "y" not in curto and "z" not in curto
    assert curto.endswith('Feche com "Fontes:".')
    longo = local.encurtar("a" * 10_000)
    assert len(longo) < local.RESULTADO_MAX + 100 and longo.endswith("peça]")
    assert local.encurtar("pouco") == "pouco"
