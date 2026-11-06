"""A lista de prioridade do WhatsApp (ADR 0055): quem o Zé vigia em tempo real."""

import asyncio
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from zervis.avisos import falas_whatsapp as f
from zervis.avisos import pendentes as pd
from zervis.avisos import prioridade as pr
from zervis.avisos.caixa import Caixa
from zervis.cerebro.ferramentas import whatsapp as w
from zervis.nucleo import estados as e
from zervis.nucleo.servicos.atendimento import ServicoAtendimento

T = 1_000_000.0
FUSO = ZoneInfo("America/Sao_Paulo")
ANA = "100000000000001@lid"


class Relogio:
    t = T

    def __call__(self) -> float:
        return self.t


def test_o_mesmo_numero_escrito_de_jeitos_diferentes() -> None:
    assert pr.mesmo_numero("5581987650000", "558187650000")  # o nono dígito
    assert pr.mesmo_numero("81 98765-0000", "5581987650000")  # sem o código do país
    assert pr.mesmo_numero("+1 (415) 555-0100", "14155550100")
    assert not pr.mesmo_numero("5581987650000", "5511987650000")  # outro DDD
    assert not pr.mesmo_numero("5581987650000", "5581987650001")
    assert not pr.mesmo_numero("0000", "5581987650000")


def _lista(tmp_path: Path) -> tuple[pr.Prioridade, Relogio]:
    relogio = Relogio()
    return pr.Prioridade(tmp_path / "prioridade.json", relogio), relogio


def test_monitorar_fica_ate_tirar_e_aprende_a_conversa(tmp_path: Path) -> None:
    lista, relogio = _lista(tmp_path)
    lista.monitorar("Ana", telefone="81 98765-0000")
    assert stat.S_IMODE(lista.arquivo.stat().st_mode) == 0o600
    v = lista.chegou("558187650000@s.whatsapp.net", "558187650000")  # o WhatsApp sem o nono
    assert v is not None and v.motivo == "pedido"
    relogio.t += 30 * 24 * 3600
    depois = pr.Prioridade(tmp_path / "prioridade.json", relogio)  # reiniciou, um mês depois
    assert depois.chegou("558187650000@s.whatsapp.net", "") is not None  # pela conversa aprendida
    assert depois.remover("a Ana") is not None
    assert depois.todos() == []


def test_esperar_resposta_vale_uma_vez_e_por_24_horas(tmp_path: Path) -> None:
    lista, relogio = _lista(tmp_path)
    lista.esperar_resposta("Ana", ANA)
    assert lista.chegou(ANA, "") is not None
    assert lista.chegou(ANA, "") is None  # respondeu: a espera acabou
    lista.esperar_resposta("Ana", ANA)
    relogio.t += pr.ESPERA_S + 1
    assert lista.chegou(ANA, "") is None  # passou um dia sem resposta


def test_esperar_resposta_nao_tira_quem_esta_de_vez(tmp_path: Path) -> None:
    lista, _ = _lista(tmp_path)
    lista.monitorar("Ana", chat=ANA)
    lista.esperar_resposta("Ana", ANA)
    assert [v.motivo for v in lista.todos()] == ["pedido"]
    lista.chegou(ANA, "")
    assert len(lista.todos()) == 1


def test_tirar_pelo_numero_e_pelo_id(tmp_path: Path) -> None:
    lista, _ = _lista(tmp_path)
    v = lista.monitorar("Bia", telefone="5581999990000")
    lista.monitorar("Caio", chat="2@lid")
    assert lista.remover("81 99999-0000") is not None
    assert lista.remover("ninguém") is None
    assert [x.nome for x in lista.todos()] == ["Caio"]
    assert lista.remover(lista.todos()[0].id) is not None
    assert v.nome == "Bia"


def _nucleo(tmp_path: Path, mensagens_ativo: bool = True) -> Any:
    relogio = Relogio()
    falados: list[e.Aviso] = []
    julgadas: list[tuple[str, ...]] = []
    n: Any = SimpleNamespace(
        leads=pd.Pendentes(tmp_path / "pendentes.json", relogio),
        caixa=Caixa(tmp_path / "caixa.json", relogio),
        prioridade=pr.Prioridade(tmp_path / "prioridade.json", relogio),
        relogio=relogio,
        modo_fala="avisos",
        avisos_lidos={},
        mensagens=SimpleNamespace(
            ativo=mensagens_ativo, receber=lambda *dados: julgadas.append(dados)
        ),
        eventos=SimpleNamespace(put=falados.append),
        _na_linha=lambda tipo, texto: None,
        _fonte=None,
        falados=falados,
        julgadas=julgadas,
        central=SimpleNamespace(
            enviar=lambda *a, **k: None, para_tela=lambda: {"estado": "conectado"}
        ),
    )
    servico = ServicoAtendimento(n)
    n.servico = servico
    n.responder_whatsapp = servico.responder_whatsapp
    n.dispensar_lead = servico.dispensar_lead
    n.estado_whatsapp = servico.estado_whatsapp
    return n


def _chega(n: Any, nome: str, texto: str, chat: str, telefone: str = "", midia: str = "") -> None:
    n.relogio.t += 1
    n.servico._evento_da_central(
        {"tipo": "mensagem", "nome": nome, "texto": texto, "telefone": telefone, "chat": chat,
         "midia": midia, "quando": n.relogio.t}
    )  # fmt: skip


def _ferramenta(n: Any, args: dict[str, Any]) -> dict[str, Any]:
    f: dict[str, Any] = {t.name: t.handler for t in w.ferramentas(n)}
    resposta: dict[str, Any] = asyncio.run(f["whatsapp_prioridade"](args))
    return resposta


def test_quem_esta_na_lista_avisa_na_hora_sem_julgar_e_lembra(tmp_path: Path) -> None:
    n = _nucleo(tmp_path, mensagens_ativo=False)  # sem os avisos de lead: a lista vale igual
    r = _ferramenta(n, {"acao": "adicionar", "contato": "Ana", "numero": "81 98765-0000"})
    assert r["content"][0]["text"] == "Monitorando Ana: aviso qualquer mensagem, na hora."
    _chega(n, "Ana Souza", "", "558187650000@s.whatsapp.net", "558187650000", midia="audio")
    [aviso] = n.falados
    assert "Ana Souza, da sua lista de prioridade, mandou: [um áudio]" in aviso.texto
    assert n.julgadas == []  # não passa pelo julgamento de lead
    _chega(n, "Ana Souza", "me liga", "558187650000@s.whatsapp.net", "558187650000")
    assert len(n.falados) == 1  # junta na mesma pendência
    n.relogio.t += pd.INTERVALO_S
    n.servico._lembrar_leads()
    assert n.falados[-1].texto.endswith("Ana Souza ainda espera sua resposta no WhatsApp.")
    assert pd.para_o_celular(n.leads.abertas()[0])["motivo"] == "Prioridade"


def test_depois_que_o_ze_responde_ele_escuta_a_resposta(tmp_path: Path) -> None:
    n = _nucleo(tmp_path)
    _chega(n, "Ana", "quanto custa?", ANA)
    assert n.servico.responder_whatsapp(ANA, "Ana", "Custa 200.") == (
        "Enviado para Ana. Aviso quando responder."
    )
    n.servico._evento_da_central(
        {"tipo": "respondida", "chat": ANA, "texto": "Custa 200.", "quando": n.relogio.t}
    )
    _chega(n, "Ana", "fechado, pode mandar o link", ANA)
    assert n.falados[-1].texto.endswith("Ana respondeu: fechado, pode mandar o link.")
    assert len(n.julgadas) == 1  # só a primeira mensagem dela foi julgada
    _chega(n, "Bia", "oi", "2@lid")
    _chega(n, "Ana", "e o prazo?", ANA)
    assert len(n.julgadas) == 3  # a espera acabou: a próxima volta ao normal (junta na pendência)


def test_ver_e_tirar_da_lista_pela_voz(tmp_path: Path) -> None:
    n = _nucleo(tmp_path)
    _chega(n, "João Silva", "oi", "9@lid")
    assert "vazia" in _ferramenta(n, {"acao": "ver"})["content"][0]["text"]
    _ferramenta(n, {"acao": "adicionar", "contato": "João"})
    assert "João Silva (id " in _ferramenta(n, {"acao": "ver"})["content"][0]["text"]
    r = _ferramenta(n, {"acao": "remover", "contato": "o João"})
    assert r["content"][0]["text"] == "João Silva saiu da lista de prioridade."
    assert _ferramenta(n, {"acao": "adicionar", "contato": "Carla"})["is_error"]
    assert _ferramenta(n, {"acao": "remover", "contato": "Carla"})["is_error"]


ACOUGUE = "558133334444@s.whatsapp.net"
PEDIDO = "PRODUTO(S): Acém sem osso, 6 kg x R$ 30,49 = R$ 182,94. Valor após a pesagem."


def test_ja_vi_segura_o_contato_por_6_horas_sem_julgar_de_novo(tmp_path: Path) -> None:
    """Caso de 03/11/2026: a loja que mandava o resumo do pedido virou lead três vezes, e o "já
    vi" só calava a mensagem daquele momento."""
    n = _nucleo(tmp_path)
    _chega(n, "Oi", PEDIDO, ACOUGUE)
    assert len(n.julgadas) == 1
    n.servico._lead_qualificado("Oi", PEDIDO, "", ACOUGUE)  # o filtro tinha dito que era lead
    assert n.servico.dispensar_lead(ACOUGUE) == "Certo, não lembro mais de Oi."
    _chega(n, "Oi", "Chã de dentro: 2 peças, R$ 160", ACOUGUE)
    assert len(n.julgadas) == 1  # nem julgou: "já vi" há pouco
    assert n.leads.abertas() == []
    n.relogio.t += pd.SEGURAR_S + 60
    _chega(n, "Oi", "Seu pedido saiu para entrega", ACOUGUE)
    assert len(n.julgadas) == 2  # passou o tempo: volta ao normal
    assert [m["texto"] for m in n.caixa.mensagens(ACOUGUE)][-1] == "Seu pedido saiu para entrega"


def test_silenciar_cala_de_vez_ate_voltar_a_avisar(tmp_path: Path) -> None:
    n = _nucleo(tmp_path)
    _chega(n, "Oi", PEDIDO, ACOUGUE)
    n.servico._lead_qualificado("Oi", PEDIDO, "", ACOUGUE)
    falados = len(n.falados)
    r = _ferramenta(n, {"acao": "silenciar", "contato": "Oi"})
    assert r["content"][0]["text"] == (
        "Certo, não aviso mais de Oi. As mensagens continuam no arquivo."
    )
    assert n.leads.abertas() == []  # o aviso aberto também parou
    n.relogio.t += pd.SEGURAR_S + 60
    _chega(n, "Oi", "Seu pedido saiu para entrega", ACOUGUE)
    assert len(n.julgadas) == 1 and len(n.falados) == falados  # nada: nem julga, nem fala
    assert len(n.caixa.mensagens(ACOUGUE)) == 2  # mas guarda
    assert "Ninguém esperando" in f.esperando(n.caixa, FUSO, n.prioridade.calado)
    assert "silenciado" in _ferramenta(n, {"acao": "ver"})["content"][0]["text"]
    n.servico.responder_whatsapp(ACOUGUE, "Oi", "Obrigado!")
    assert [v.motivo for v in n.prioridade.todos()] == ["silencio"]  # responder não descala
    r = _ferramenta(n, {"acao": "remover", "contato": "Oi"})
    assert r["content"][0]["text"] == "Voltei a avisar de Oi."
    _chega(n, "Oi", "Chegou?", ACOUGUE)
    assert len(n.julgadas) == 2


def test_o_filtro_sabe_que_a_loja_do_seu_pedido_nao_e_lead() -> None:
    from zervis.avisos.mensagens import SISTEMA

    assert "pedido, uma compra ou um serviço que o próprio usuário contratou" in SISTEMA
