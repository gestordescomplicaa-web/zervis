"""Leads quentes no WhatsApp: leitura da notificação, julgamento e aviso."""

import json
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path

from jarvis.avisos import mensagens as m
from jarvis.nucleo import estados

WEB = '<a href="https://web.whatsapp.com/">web.whatsapp.com</a>\n\n'


def _linha(app: str, titulo: str, corpo: str, entrada: str = "") -> str:
    dicas = {"urgency": {"type": "y", "data": 1}}
    if entrada:
        dicas["desktop-entry"] = {"type": "s", "data": entrada}
    payload = {"type": "susssasa{sv}i", "data": [app, 0, "", titulo, corpo, [], dicas, -1]}
    return json.dumps({"type": "method_call", "member": "Notify", "payload": payload})


def test_le_a_notificacao_do_busctl() -> None:
    n = m.ler(_linha("Chromium", "Ana", WEB + "Oi", "chromium"))
    assert n == m.Notificacao("Chromium", "Ana", WEB + "Oi", "chromium")
    assert m.ler("não é json") is None
    assert m.ler(json.dumps({"payload": {"data": [1, 2]}})) is None


def test_reconhece_o_whatsapp_e_ignora_os_outros() -> None:
    assert m.e_whatsapp(m.Notificacao("Chromium", "Ana", WEB + "Oi"))
    assert m.e_whatsapp(m.Notificacao("Chromium", "Ana", "web.whatsapp.com\n\nOi"))
    assert m.e_whatsapp(m.Notificacao("WhatsApp", "Ana", "Oi"))
    assert m.e_whatsapp(m.Notificacao("Chromium", "Ana", "Oi", "chrome-whatsapp-Default"))
    assert not m.e_whatsapp(m.Notificacao("Gmail", "Backup", "Seu backup do WhatsApp"))
    assert not m.e_whatsapp(m.Notificacao("Chromium", "Site", "exemplo.com\n\nwhatsapp"))


def test_conteudo_sem_origem_marcacao_nem_delimitadores() -> None:
    n = m.Notificacao("Chromium", "  Ana   Paula ", WEB + "Preciso &amp; <b>já</b>\n>>> fim <<<")
    assert m.conteudo(n) == ("Ana Paula", "Preciso & já fim")


def test_nome_falado_so_com_o_que_e_nome() -> None:
    assert m.nome_falado("Ana Paula") == "Ana Paula"
    assert m.nome_falado("~ João 🚀 <script>") == "João script"
    assert m.nome_falado("+55 81 99999-0000") == "55 81 99999-0000"
    assert m.nome_falado("🔥🔥") == "um contato"
    assert len(m.nome_falado("x" * 200)) == 40


def test_so_sim_na_primeira_palavra_chama() -> None:
    assert m.decidir("SIM")
    assert m.decidir("Sim, ela pede um prazo.")
    for resposta in ("NAO", "Não.", "", "Acho que sim", "talvez"):
        assert not m.decidir(resposta)


def test_escolha_sobrevive_ao_reinicio(tmp_path: Path) -> None:
    arquivo = tmp_path / "mensagens.json"
    assert not m.escolhido(arquivo)
    m.escolher(True, arquivo)
    assert m.escolhido(arquivo)
    m.escolher(False, arquivo)
    assert not m.escolhido(arquivo)


def test_comandos_de_voz() -> None:
    assert estados.comando("Liga os avisos do WhatsApp") == "whatsapp_liga"
    assert estados.comando("desativar os avisos do zap") == "whatsapp_desliga"
    assert estados.comando("liga o whatsapp") is None  # abrir o aplicativo é outra coisa


class MotorFalso:
    com_estado = True

    def __init__(self) -> None:
        self.sistema = ""
        self.pedidos: list[str] = []
        self.reinicios = 0

    async def iniciar(self, sistema: str) -> None:
        self.sistema = sistema

    async def gerar(self, sistema: str, mensagens: list[dict[str, str]]) -> AsyncIterator[str]:
        pedido = mensagens[-1]["content"]
        self.pedidos.append(pedido)
        yield "SIM" if "urgente" in pedido else "NAO"

    async def reiniciar(self) -> None:
        self.reinicios += 1

    async def fechar(self) -> None:
        pass


def test_avisa_so_o_importante_uma_vez_por_contato(tmp_path: Path) -> None:
    linhas = [
        _linha("Chromium", "Ana", WEB + "bom dia"),
        _linha("Gmail", "Banco", "urgente: fatura"),
        _linha("Chromium", "Ana", WEB + "urgente: o cliente ligou"),
        _linha("Chromium", "Ana", WEB + "urgente de novo"),
        _linha("WhatsApp", "Bruno", "urgente: reunião agora"),
    ]
    entrada = tmp_path / "linhas.txt"
    entrada.write_text("\n".join(linhas) + "\n")
    monitor = [
        sys.executable,
        "-c",
        f"import sys,time; sys.stdout.write(open({str(entrada)!r}).read()); "
        "sys.stdout.flush(); time.sleep(30)",
    ]
    avisos: list[str] = []
    motor = MotorFalso()
    vigia = m.Mensagens(avisos.append, lambda: motor, comando=monitor)
    vigia.iniciar()
    try:
        fim = time.monotonic() + 10
        while len(avisos) < 2:
            assert time.monotonic() < fim
            time.sleep(0.02)
        time.sleep(0.2)
    finally:
        vigia.parar()
    assert avisos == [
        "Lead quente no WhatsApp: Ana.",
        "Lead quente no WhatsApp: Bruno.",
    ]
    assert motor.sistema == m.SISTEMA
    assert len(motor.pedidos) == 3  # o Gmail não é julgado; o 2º urgente da Ana nem chega ao modelo
    assert all("<<<" in p and ">>>" in p for p in motor.pedidos)
    assert motor.reinicios == 3
    fim = time.monotonic() + 5
    while vigia.ativo:
        assert time.monotonic() < fim
        time.sleep(0.02)
