"""A conversa com o Zé pelo WhatsApp (ADR 0102): a mensagem do seu número, autorizado no painel,
ao número do Zé é um pedido, respondido na mesma conversa por um cérebro próprio, sem confirmação
de nada com efeito."""

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.atendimento import central as c
from zervis.atendimento import whatsapp as w
from zervis.atendimento.whatsapp import Recebida
from zervis.cerebro import por_mensagem as pm
from zervis.cerebro.base import Espera, EventoCerebro, Fim, Texto
from zervis.nucleo.servicos import atendimento as sa

EU = "5511999990000@s.whatsapp.net"


def test_numero_autorizado_com_ou_sem_o_nono_digito_e_nunca_sem_numero(tmp_path: Path) -> None:
    arquivo = tmp_path / "whatsapp-conversa.json"
    assert w.conversa(arquivo) == (False, [])
    w.configurar_conversa(True, ["5511999990000"], arquivo)
    ligada, numeros = w.conversa(arquivo)
    assert ligada and numeros == ["5511999990000"]
    assert w.autorizado("5511999990000", numeros)
    assert w.autorizado("551199990000", numeros)  # o mesmo celular, sem o nono dígito
    assert not w.autorizado("5511988887777", numeros)
    assert not w.autorizado("", numeros)  # só o LID: na dúvida, é de fora
    arquivo.write_text('{"ativo": true, "numeros": ["abc", 5511]}')
    assert w.conversa(arquivo) == (True, [])  # lixo no arquivo não autoriza ninguém
    arquivo.write_text('{"ativo": true}')  # o arquivo da versão do chat "Você"
    assert w.conversa(arquivo) == (True, [])


# --- a Central ------------------------------------------------------------------------------


class WhatsAppFalso:
    def __init__(self) -> None:
        self.enviadas: list[tuple[str, str]] = []

    def enviar(self, telefone: str, texto: str, chave: str, chat: str = "") -> str:
        self.enviadas.append((chat, texto))
        return f"s:{len(self.enviadas)}"

    def parar(self) -> None:
        pass


class AtendenteFalso:
    def __init__(self, pasta: Path) -> None:
        from zervis.atendimento.agente import Registros

        self.registros = Registros(pasta)
        self.recebidas: list[Recebida] = []

    def receber(self, r: Recebida) -> None:
        self.recebidas.append(r)


def _central(tmp_path: Path) -> tuple[c.Central, WhatsAppFalso, AtendenteFalso]:
    wa, at = WhatsAppFalso(), AtendenteFalso(tmp_path)
    return c.Central(lambda: None, wa, at), wa, at  # type: ignore[arg-type, return-value]


DONO = "5511999990000"
OUTRO = "5511988887777@s.whatsapp.net"


def _ligar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ativo: bool = True) -> None:
    monkeypatch.setattr(w, "CONVERSA", tmp_path / "whatsapp-conversa.json")
    w.configurar_conversa(ativo, [DONO])


def test_central_faz_da_mensagem_do_seu_numero_um_pedido_fora_do_arquivo_e_do_agente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ligar(monkeypatch, tmp_path)
    central, _, at = _central(tmp_path)
    central._recebida(Recebida("s:1", "Gabriel", "551199990000", "que horas são?", chat=EU))
    eventos, _ = central.eventos.depois(0)
    assert [(e["tipo"], e["texto"], e["chat"]) for e in eventos] == [
        ("pedido", "que horas são?", EU)
    ]
    # A resposta do Zé nessa conversa volta como mensagem do número do Zé: não vai a lugar algum.
    central._recebida(Recebida("s:2", "Zé", DONO, "São dez horas.", de_mim=True, chat=EU))
    assert central.eventos.depois(1)[0] == [] and at.recebidas == []


def test_outros_numeros_grupo_e_conversa_desligada_seguem_como_antes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ligar(monkeypatch, tmp_path)
    central, _, at = _central(tmp_path)
    central._recebida(Recebida("s:1", "Ana", "5511988887777", "quanto custa?", chat=OUTRO))
    grupo = "120363000000000000@g.us"
    central._recebida(Recebida("s:2", "Gabriel", DONO, "bom dia", chat=grupo, grupo=True))
    assert [e["tipo"] for e in central.eventos.depois(0)[0]] == ["mensagem", "mensagem"]
    assert [r.id for r in at.recebidas] == ["s:1"]  # o grupo nunca vai ao agente

    w.configurar_conversa(False, [DONO])  # desligada: o seu número é um contato como outro
    central._recebida(Recebida("s:3", "Gabriel", DONO, "oi", chat=EU))
    assert [e["tipo"] for e in central.eventos.depois(2)[0]] == ["mensagem"]
    assert [r.id for r in at.recebidas] == ["s:1", "s:3"]


# --- o cérebro do WhatsApp ------------------------------------------------------------------


class CerebroFalso:
    def __init__(self, aprovar_em: str = "") -> None:
        self.persona = ""
        self.pedidos: list[str] = []
        self.fechado = False
        self.aprovar_em = aprovar_em
        self.respostas_da_aprovacao: list[Any] = []
        self.uso = {"input_tokens": 10}

    async def start(self, persona: str, aprovar: Any = None) -> None:
        self.persona, self.aprovar = persona, aprovar

    async def ask(self, texto: str) -> AsyncIterator[EventoCerebro]:
        self.pedidos.append(texto)
        yield Espera("Só um momento. ")
        if texto == self.aprovar_em:
            self.respostas_da_aprovacao.append(await self.aprovar("Enviar a mensagem?"))
        await asyncio.sleep(0.05)  # o segundo pedido chega enquanto este responde
        yield Texto(f"Resposta a {texto}.\n")
        yield Texto("- item")
        yield Fim()

    async def interrupt(self) -> None:
        pass

    async def reset(self) -> None:
        pass

    async def close(self) -> None:
        self.fechado = True


def _esperar(condicao: Any, prazo: float = 5.0) -> None:
    fim = time.monotonic() + prazo
    while not condicao():
        assert time.monotonic() < fim, "não aconteceu a tempo"
        time.sleep(0.01)


def test_um_pedido_por_vez_na_ordem_sem_a_frase_de_espera_e_sem_confirmacao() -> None:
    cerebro = CerebroFalso(aprovar_em="manda oi para a Ana")
    feitos: list[pm.Feito] = []
    conversa = pm.ConversaPorMensagem(lambda: cerebro, lambda: "PERSONA", feitos.append)
    try:
        assert conversa.pedir("que horas são?", EU)
        assert conversa.pedir("manda oi para a Ana", EU)
        _esperar(lambda: len(feitos) == 2)
    finally:
        conversa.fechar()
    assert cerebro.pedidos == ["que horas são?", "manda oi para a Ana"]
    assert feitos[0] == pm.Feito(
        "que horas são?", "Resposta a que horas são?.\n- item", None, EU, {"input_tokens": 10}
    )
    assert cerebro.persona.startswith("PERSONA") and "WhatsApp" in cerebro.persona
    [negada] = cerebro.respostas_da_aprovacao
    assert not negada and negada.fala == pm.SEM_CONFIRMACAO
    assert cerebro.fechado


def test_cerebro_sobe_sob_demanda_e_fecha_quando_fica_parado() -> None:
    criados: list[CerebroFalso] = []

    def criar() -> CerebroFalso:
        criados.append(CerebroFalso())
        return criados[-1]

    feitos: list[pm.Feito] = []
    conversa = pm.ConversaPorMensagem(criar, lambda: "", feitos.append, ocioso_s=0.2)
    try:
        assert criados == []
        conversa.pedir("oi")
        _esperar(lambda: len(criados) == 1 and criados[0].fechado)
        conversa.pedir("oi de novo")
        _esperar(lambda: len(feitos) == 2)
        assert len(criados) == 2  # a sessão nova começa sem o histórico da anterior
    finally:
        conversa.fechar()


def test_cerebro_que_nao_sobe_vira_resposta_de_falha() -> None:
    def criar() -> Any:
        raise RuntimeError("sem conta")

    feitos: list[pm.Feito] = []
    conversa = pm.ConversaPorMensagem(criar, lambda: "", feitos.append)
    try:
        conversa.pedir("oi", EU)
        _esperar(lambda: len(feitos) == 1)
    finally:
        conversa.fechar()
    assert feitos == [pm.Feito("oi", "", "RuntimeError", EU)]


# --- o serviço no Zé ------------------------------------------------------------------------


class CentralFalsa:
    def __init__(self) -> None:
        self.enviadas: list[tuple[str, str]] = []

    def enviar(self, texto: str, chave: str, chat: str = "") -> None:
        self.enviadas.append((chat, texto))


class ConversaFalsa:
    def __init__(self, aceita: bool = True) -> None:
        self.pedidos: list[tuple[str, str]] = []
        self.aceita = aceita

    def pedir(self, texto: str, destino: str = "") -> bool:
        self.pedidos.append((texto, destino))
        return self.aceita


def _servico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ligada: bool = True
) -> tuple[sa.ServicoAtendimento, Any]:
    monkeypatch.setattr(w, "CONVERSA", tmp_path / "whatsapp-conversa.json")
    if ligada:
        w.configurar_conversa(True, [DONO])
    registradas: list[tuple[str, str]] = []
    n = SimpleNamespace(
        central=CentralFalsa(),
        conversa_whatsapp=ConversaFalsa(),
        conversas=SimpleNamespace(registrar=lambda p, r: registradas.append((p, r))),
        consumo=SimpleNamespace(somar=lambda uso, provedor: None),
        provedor="claude",
        registradas=registradas,
    )
    return sa.ServicoAtendimento(n), n


def _pedido(**campos: Any) -> dict[str, Any]:
    return {"tipo": "pedido", "chat": EU, "texto": "que horas são?", "hora": time.time(), **campos}


def test_pedido_so_com_a_conversa_ligada_no_painel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servico, n = _servico(tmp_path, monkeypatch, ligada=False)
    servico._evento_da_central(_pedido())
    assert n.conversa_whatsapp.pedidos == [] and n.central.enviadas == []
    assert servico.configurar_conversa_whatsapp(True, "") == "Informe o seu número."
    assert servico.configurar_conversa_whatsapp(True, "12 34") == "Número inválido."
    assert servico.configurar_conversa_whatsapp(True, "+55 (11) 99999-0000") == (
        "Conversa com o Zé ligada."
    )
    assert servico.conversa_pelo_whatsapp() == {"ligado": True, "numero": DONO}
    servico._evento_da_central(_pedido())
    assert n.conversa_whatsapp.pedidos == [("que horas são?", EU)]
    assert servico.configurar_conversa_whatsapp(False, "") == "Conversa com o Zé desligada."
    assert servico.conversa_pelo_whatsapp() == {"ligado": False, "numero": ""}


def test_pedido_atrasado_grupo_e_midia_nao_vao_ao_cerebro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servico, n = _servico(tmp_path, monkeypatch)
    servico._evento_da_central(_pedido(hora=time.time() - sa.PEDIDO_VALIDO_S - 5))
    servico._evento_da_central(_pedido(chat="120363000000000000@g.us"))
    servico._evento_da_central(_pedido(texto="", midia="audio", evento="s:9"))
    assert n.conversa_whatsapp.pedidos == []
    assert n.central.enviadas == [(EU, sa.SO_TEXTO)]


def test_fila_cheia_avisa_no_chat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    servico, n = _servico(tmp_path, monkeypatch)
    n.conversa_whatsapp.aceita = False
    servico._evento_da_central(_pedido())
    assert n.central.enviadas == [(EU, sa.FILA_CHEIA)]


def test_resposta_vai_ao_chat_em_partes_e_entra_na_conversa_do_dia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servico, n = _servico(tmp_path, monkeypatch)
    longa = ("Uma frase de resposta. " * 100).strip()
    servico.resposta_do_whatsapp(pm.Feito("resuma", longa, None, EU))
    partes = [t for _, t in n.central.enviadas]
    assert len(partes) == 2 and all(len(p) <= sa.PARTE_MAXIMA for p in partes)
    assert " ".join(partes) == longa
    assert all(chat == EU for chat, _ in n.central.enviadas)
    assert n.registradas == [("resuma", longa)]

    servico.resposta_do_whatsapp(pm.Feito("oi", "", "TimeoutError", EU))
    assert n.central.enviadas[-1] == (EU, sa.SEM_RESPOSTA)
    assert len(n.registradas) == 1  # a falha não entra na conversa do dia


def test_partes_quebram_no_paragrafo() -> None:
    texto = "a" * 10 + "\n\n" + "b" * 10
    assert sa._partes(texto, limite=15) == ["a" * 10, "b" * 10]
    assert sa._partes("x" * 30, limite=15) == ["x" * 15, "x" * 15]
    assert sa._partes("  ") == []


def test_conversa_do_nucleo_existe_e_fecha_sem_ter_subido() -> None:
    conversa = pm.ConversaPorMensagem(lambda: CerebroFalso(), lambda: "", lambda f: None)
    conversa.fechar()  # nunca subiu: nada a fechar, e não trava


def test_ao_desligar_o_ze_para_de_ouvir_a_central_e_fecha_o_chat_voce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servico, n = _servico(tmp_path, monkeypatch)
    fechou: list[str] = []
    n.central.parar = lambda: fechou.append("central")
    n.conversa_whatsapp.fechar = lambda: fechou.append("conversa")
    servico.parar_atendimento()
    assert fechou == ["central", "conversa"]
    del n.conversa_whatsapp  # nunca houve pedido: nada a fechar
    servico.parar_atendimento()
    assert fechou == ["central", "conversa", "central"]
