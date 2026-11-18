"""O Zé nos grupos das empresas (ADR 0108): responde quando chamado, só no grupo de uma empresa
ligada, só com a vitrine, e encaminha pedidos de ação a quem usa."""

import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from zervis import empresas as emp
from zervis.atendimento import grupos as g
from zervis.atendimento import whatsapp as w
from zervis.atendimento.agente import Motor
from zervis.atendimento.whatsapp import Recebida

LIGADO, DESLIGADO = "120363000000000001@g.us", "120363000000000002@g.us"


def _cadastro(tmp_path: Path) -> emp.Empresas:
    cadastro = emp.Empresas(tmp_path / "config" / "empresas.json", tmp_path / "dados")
    padaria = cadastro.salvar("Padaria", LIGADO, "Padaria · equipe", ligada=True)
    cadastro.salvar("Academia", DESLIGADO, "Academia", ligada=False)
    cadastro.guardar_sobre(padaria.id, "Abrimos das 6h às 20h. Entrega até 3 km.")
    (cadastro.vitrine(padaria.id) / "relatorio-novembro.md").write_text("Vendas: 1.200 pães/dia.")
    return cadastro


def _msg(texto: str, chat: str = LIGADO, **campos: Any) -> Recebida:
    padrao: dict[str, Any] = {"grupo": True, "grupo_nome": "Padaria", "quando": time.time()}
    return Recebida(
        f"s:{abs(hash((texto, time.monotonic())))}", "Ana", "5511999990000", texto,
        chat=chat, **{**padrao, **campos},
    )  # fmt: skip


class MotorFalso:
    def __init__(self, resposta: str) -> None:
        self.resposta = resposta
        self.sistemas: list[str] = []
        self.pedidos: list[str] = []

    async def iniciar(self, sistema: str) -> None:
        self.sistemas.append(sistema)

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        self.pedidos.append(mensagens[-1]["content"])
        yield self.resposta

    async def fechar(self) -> None:
        pass


def _esperar(condicao: Any, prazo: float = 5.0) -> None:
    fim = time.monotonic() + prazo
    while not condicao():
        assert time.monotonic() < fim, "não aconteceu a tempo"
        time.sleep(0.01)


def _grupos(
    tmp_path: Path, resposta: str = "Abrimos às 6h.", **opcoes: Any
) -> tuple[g.Grupos, MotorFalso, list[tuple[str, str]], list[tuple[str, dict[str, Any]]]]:
    motor = MotorFalso(resposta)
    enviadas: list[tuple[str, str]] = []
    eventos: list[tuple[str, dict[str, Any]]] = []

    def enviar(chat: str, texto: str, chave: str) -> str:
        enviadas.append((chat, texto))
        return f"s:enviada{len(enviadas)}"

    grupos = g.Grupos(
        lambda: cast(Motor, motor),
        enviar,
        lambda tipo, **dados: eventos.append((tipo, dados)),
        cadastro=_cadastro(tmp_path),
        agrupar_s=0.05,
        intervalo_s=0,
        **opcoes,
    )
    return grupos, motor, enviadas, eventos


def test_quem_chama_o_ze() -> None:
    for texto in ("Zé, que horas abre?", "@Zé abre amanhã?", "ei zé tudo bem", "Oi, Zérvis!"):
        assert g.chamado(_msg(texto)), texto
    for texto in ("bom dia pessoal", "o zé da padaria chegou", "Zezinho?"):
        assert not g.chamado(_msg(texto)), texto
    assert g.chamado(_msg("e aí?", chama=True))  # menção ou resposta, vinda do WhatsApp


def test_responde_so_quando_chamado_e_so_com_a_vitrine(tmp_path: Path) -> None:
    grupos, motor, enviadas, eventos = _grupos(tmp_path)
    try:
        grupos.receber(_msg("bom dia pessoal"))  # conversa: vai ao histórico, sem resposta
        grupos.receber(_msg("Zé, que horas abre?"))
        _esperar(lambda: enviadas)
    finally:
        grupos.parar()
    assert enviadas == [(LIGADO, "Abrimos às 6h.")]
    sistema = motor.sistemas[0]
    assert "Padaria" in sistema and "Abrimos das 6h às 20h" in sistema
    assert "relatorio-novembro.md" in sistema and "1.200 pães" in sistema
    assert "Academia" not in sistema  # nada de outra empresa
    assert "<<<bom dia pessoal>>>" in motor.pedidos[0] and "Ana chamou você" in motor.pedidos[0]
    [(tipo, dados)] = eventos
    assert tipo == "grupo_resposta" and dados["empresa"] == "Padaria" and dados["quem"] == "Ana"
    [linha] = g.registro("padaria", grupos.cadastro)
    assert linha["pergunta"] == "Zé, que horas abre?" and linha["encaminhado"] == ""


def test_grupo_sem_empresa_ligada_midia_e_eco_nao_respondem(tmp_path: Path) -> None:
    grupos, _, enviadas, _ = _grupos(tmp_path)
    try:
        grupos.receber(_msg("Zé, oi?", chat=DESLIGADO))  # empresa desligada
        grupos.receber(_msg("Zé, oi?", chat="120363000000000009@g.us"))  # grupo sem empresa
        grupos.receber(_msg("Zé", midia="audio"))
        grupos.receber(_msg("Zé, eu mesmo", de_mim=True))
        grupos.receber(_msg("Zé, privado", chat="5511999990000@s.whatsapp.net", grupo=False))
        time.sleep(0.3)
    finally:
        grupos.parar()
    assert enviadas == []


def test_pedido_de_acao_vira_encaminhamento(tmp_path: Path) -> None:
    resposta = "Encaminhei para o gestor, Ana.\n[[ENCAMINHAR: pausar a campanha de Natal]]"
    grupos, _, enviadas, eventos = _grupos(tmp_path, resposta)
    try:
        grupos.receber(_msg("Zé, pausa a campanha de Natal"))
        _esperar(lambda: len(eventos) == 2)
    finally:
        grupos.parar()
    assert enviadas == [(LIGADO, "Encaminhei para o gestor, Ana.")]  # a marca não vai ao grupo
    pedido = {"empresa": "Padaria", "quem": "Ana", "pedido": "pausar a campanha de Natal"}
    assert eventos[1] == ("grupo_pedido", pedido)
    assert g.separar("[[ENCAMINHAR: x]]") == (g.ENCAMINHADO, "x")


def test_limite_por_hora(tmp_path: Path) -> None:
    grupos, _, enviadas, _ = _grupos(tmp_path, limite_hora=1)
    try:
        grupos.receber(_msg("Zé, um?"))
        _esperar(lambda: enviadas)
        grupos.receber(_msg("Zé, dois?"))
        time.sleep(0.3)
    finally:
        grupos.parar()
    assert len(enviadas) == 1


# --- o cadastro e o WhatsApp ------------------------------------------------------------------


def test_lista_dos_grupos_ligados_e_a_vitrine(tmp_path: Path) -> None:
    cadastro = _cadastro(tmp_path)
    assert json.loads(cadastro.grupos.read_text()) == {"grupos": [LIGADO]}
    assert cadastro.grupos.stat().st_mode & 0o777 == 0o600
    cadastro.salvar("Padaria", LIGADO, ligada=False, ident="padaria")
    assert json.loads(cadastro.grupos.read_text()) == {"grupos": []}  # desligou: sai na hora
    conhecimento = cadastro.conhecimento("padaria")
    assert conhecimento.index("sobre.md") < conhecimento.index("relatorio-novembro.md")
    with pytest.raises(emp.EmpresaErro, match="não encontrada"):
        cadastro.guardar_sobre("outra", "x")


def test_mensagem_de_grupo_traz_o_chamado_e_o_envio_so_vai_a_grupo_ligado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lote = {"mensagens": [{
        "type": "text", "direction": "inbound", "chat_jid": LIGADO, "content": "e aí?",
        "event_id": "s:1", "phone": "5511999990000", "calls_me": True,
    }]}  # fmt: skip
    [r] = w.recebidas(lote)
    assert r.grupo and r.chama
    monkeypatch.setattr(emp, "PADRAO", _cadastro(tmp_path))
    wa = w.WhatsApp(lambda r: None, lambda: True, tmp_path, tmp_path)
    pedidos: list[Any] = []

    def mandar(destino: dict[str, Any], texto: str, chave: str) -> str:
        pedidos.append(destino)
        return "s:x"

    wa._mandar = mandar  # type: ignore[method-assign]
    assert wa.enviar_ao_grupo(LIGADO, "oi", "k") == "s:x" and pedidos == [{"chat_jid": LIGADO}]
    for chat in (DESLIGADO, "5511999990000@s.whatsapp.net"):
        with pytest.raises(w.WhatsAppErro, match="não ligado"):
            wa.enviar_ao_grupo(chat, "oi", "k")
    with pytest.raises(w.WhatsAppErro, match="inválido"):
        wa.enviar("", "oi", "k", chat=LIGADO)  # o envio comum continua sem grupo


# --- no Zé ------------------------------------------------------------------------------------


def test_pedido_encaminhado_chega_a_voce(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from zervis import atividade
    from zervis.nucleo.servicos import atendimento as sa

    monkeypatch.setattr(w, "CONVERSA", tmp_path / "whatsapp-conversa.json")
    w.configurar_conversa(True, ["5511988887777"])
    registradas: list[tuple[str, str]] = []
    monkeypatch.setattr(
        atividade.PADRAO, "registrar", lambda tipo, titulo, **_: registradas.append((tipo, titulo))
    )
    enviadas: list[tuple[str, str]] = []
    linha: list[str] = []
    n = SimpleNamespace(
        central=SimpleNamespace(
            enviar=lambda texto, chave, telefone="": enviadas.append((telefone, texto))
        ),
        _na_linha=lambda tipo, texto: linha.append(texto),
        modo_fala="silencioso",
        maquina=SimpleNamespace(estado=None),
    )
    servico = sa.ServicoAtendimento(n)
    resposta = {"empresa": "Padaria", "quem": "Ana", "pergunta": "a", "resposta": "b"}
    servico._evento_da_central({"tipo": "grupo_resposta", **resposta})
    assert enviadas == [] and registradas == [("execucao", "Grupo Padaria: respondeu a Ana")]
    servico._evento_da_central(
        {"tipo": "grupo_pedido", "empresa": "Padaria", "quem": "Ana", "pedido": "pausar a campanha"}
    )  # fmt: skip
    texto = "Padaria: Ana pediu no grupo: pausar a campanha."
    assert enviadas == [("5511988887777", texto)] and linha == [texto]
