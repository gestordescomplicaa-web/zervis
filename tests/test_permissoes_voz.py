"""A pergunta de permissão das sessões pela voz (ADR 0039, E2): o Zé pergunta, o "sim" e o "não"
logo depois respondem sem passar pelo cérebro, e nada é aprovado por engano."""

import queue
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.avisos.fila import Fila
from zervis.nucleo import estados as e
from zervis.nucleo.servicos.avisos import ServicoAvisos
from zervis.nucleo.servicos.oficina import ServicoOficina
from zervis.oficina.permissoes import Pedido, Permissoes
from zervis.oficina.sessoes import Sessao, SessaoErro

PUBLICAR: dict[str, Any] = {
    "tool_name": "mcp__n8n-loja__publish_workflow",
    "tool_input": {"workflowName": "Pedido novo"},
    "prompt_id": "t1",
}


@pytest.mark.parametrize(
    ("fala", "decisao"),
    [
        ("Sim.", "permissao_sim"),
        ("Pode publicar", "permissao_sim"),
        ("Ei Zé, sim", "permissao_sim"),
        ("Ok, manda ver", "permissao_sim"),
        ("beleza", "permissao_sim"),
        ("Não, deixa pra depois", "permissao_nao"),
        ("espera", "permissao_nao"),
        ("sim, mas troca o fluxo", "permissao_nao"),  # a correção ganha
        # Nada disto decide: segue como pedido (ou pede a pergunta de novo).
        ("Vai chover amanhã em Recife?", None),
        ("vai chover amanhã", None),
        ("faz um resumo do dia", None),
        ("valeu Zé", None),
        ("não entendi", None),
        ("repete", None),
        ("sim, e me diz também quanto falta para terminar", None),  # longa demais
        ("Aprovo", "permissao_sim"),
        ("Sim, aprova tudo", "permissao_tudo"),
        ("Pode aprovar tudo.", "permissao_tudo"),
        ("não aprova tudo", "permissao_nao"),
    ],
)
def test_so_uma_resposta_curta_e_clara_decide(fala: str, decisao: str | None) -> None:
    assert e.resposta_a_permissao(fala) == decisao


def ouvindo(permissao: bool) -> e.Maquina:
    m = e.Maquina(estado=e.Estado.OUVINDO, autorizado=True, em_conversa=True)
    m.permissao = lambda: permissao
    return m


def test_logo_depois_da_pergunta_o_ok_responde_a_sessao_e_nao_encerra() -> None:
    m = ouvindo(True)
    assert m.tratar(e.FimDeFala("Ok, pode"), 0) == [e.Comando("permissao_sim")]
    assert m.estado is e.Estado.PENSANDO  # a resposta do Zé ("Aprovado.") vem a seguir
    # Fora da janela, o mesmo "ok, pode" só encerra a conversa, como sempre.
    m = ouvindo(False)
    assert m.tratar(e.FimDeFala("Ok, pode"), 0) == [e.Bip()] and m.estado is e.Estado.ATIVO
    # E a pergunta qualquer, mesmo na janela, vai ao cérebro.
    m = ouvindo(True)
    assert m.tratar(e.FimDeFala("Vai chover amanhã?"), 0) == [
        e.EnviarAoCerebro("Vai chover amanhã?")
    ]


def test_aprova_e_nega_a_qualquer_momento_sao_comandos() -> None:
    assert e.comando("Ei Zé, aprova") == "permissao_sim"
    assert e.comando("pode aprovar") == "permissao_sim"
    assert e.comando("nega a sessão") == "permissao_nao"
    assert e.comando("não aprova") == "permissao_nao"
    assert e.comando("Aprovo.") == "permissao_sim"
    # O caso real de 27/10/2026: estes iam ao cérebro, que dizia "aprovado" sem aprovar.
    assert e.comando("Pode aprovar tudo.") == "permissao_tudo"
    assert e.comando("Ei Zé, aprova tudo") == "permissao_tudo"
    assert e.comando("aprova todos") == "permissao_tudo"


class Sessoes:
    def __init__(self) -> None:
        self.permissoes = Permissoes()
        self.nomes = {"s1": "Loja", "s2": "Site"}

    def ler(self, id_: str) -> Any:
        if id_ not in self.nomes:
            raise SessaoErro(id_)
        return SimpleNamespace(nome=self.nomes[id_])


def contexto(tmp_path: Path, travado: bool = False, chamado: str = "voz") -> Any:
    return SimpleNamespace(
        sessoes=Sessoes(),
        eventos=queue.Queue(),
        fila=Fila(tmp_path / "avisos.json"),
        _meta={},
        _perguntas_permissao={},
        _permissao_falada=None,
        _permissao_ate=0.0,
        _oferta_ate=0.0,
        chamado=chamado,
        microfone_travado=travado,
        _na_linha=lambda tipo, texto: None,
        _aviso_da_oficina=lambda *a: avisos_genericos.append(a),
    )


avisos_genericos: list[Any] = []


def pedir(n: Any, sessao: str, entrada: dict[str, Any]) -> tuple[Pedido, dict[str, Any]]:
    """O gancho de uma sessão esperando, numa thread; o Zé já perguntou (`ao_pedir`)."""
    permissoes = n.sessoes.permissoes
    chegou: list[Pedido] = []

    def ao_pedir(p: Pedido) -> None:
        chegou.append(p)
        ServicoOficina(n)._permissao_pedida(p)

    permissoes.ao_pedir = ao_pedir
    permissoes.ao_decidir = ServicoOficina(n)._permissao_decidida
    saida: dict[str, Any] = {}
    chave = permissoes.chave(sessao)
    threading.Thread(
        target=lambda: saida.update(volta=permissoes.pedir(chave, entrada)), daemon=True
    ).start()
    fim = time.monotonic() + 3
    while not chegou:
        assert time.monotonic() < fim
        time.sleep(0.01)
    return chegou[0], saida


def esperar(cond: Any) -> None:
    fim = time.monotonic() + 3
    while not cond():
        assert time.monotonic() < fim
        time.sleep(0.01)


def test_o_ze_pergunta_com_o_que_acontece_e_ouve_a_resposta(tmp_path: Path) -> None:
    n = contexto(tmp_path)
    pedido, saida = pedir(n, "s1", PUBLICAR)
    aviso = n.eventos.get_nowait()
    texto = (
        'A sessão Loja quer publicar o fluxo "Pedido novo": ele passa a rodar de verdade. Aprovo?'
    )
    assert aviso == e.Aviso(texto, escutar=True, sequencial=True)
    assert n._perguntas_permissao[texto] == ("s1", pedido.id)
    assert n._meta[texto]["origem"] == "permissao" and n._meta[texto]["prioridade"] == 0
    # O Zé falou a pergunta (o laço marca) e a pessoa disse "sim".
    n._permissao_falada, n._permissao_ate = ("s1", pedido.id), time.monotonic() + 45
    assert ServicoOficina(n)._responder_permissao(True) == "Aprovado. A sessão Loja segue."
    esperar(lambda: "volta" in saida)
    assert saida["volta"]["hookSpecificOutput"]["decision"]["behavior"] == "allow"
    assert n._permissao_ate == 0.0 and not n._perguntas_permissao  # a janela fechou


def test_no_silencioso_sem_app_so_a_tela(tmp_path: Path) -> None:
    n = contexto(tmp_path, travado=True)
    pedir(n, "s1", PUBLICAR)
    assert n.eventos.empty() and n._perguntas_permissao  # na Conversa e no painel, sem voz
    n.sessoes.permissoes.retirar("s1")


def test_o_que_nao_cabe_numa_frase_nao_se_aprova_de_ouvido(tmp_path: Path) -> None:
    n = contexto(tmp_path)
    pedir(n, "s1", {"tool_name": "Bash", "tool_input": {"command": "cat > /etc/hosts"}})
    aviso = n.eventos.get_nowait()
    assert aviso.texto.endswith("Veja no painel ou no terminal.") and not aviso.escutar
    n.sessoes.permissoes.retirar("s1")


def test_sem_pergunta_feita_vale_o_unico_pedido_e_com_varios_pede_o_painel(tmp_path: Path) -> None:
    n = contexto(tmp_path)
    oficina = ServicoOficina(n)
    assert oficina._responder_permissao(True) == "Não há nenhum pedido esperando aprovação."
    _, a = pedir(n, "s1", PUBLICAR)
    _, b = pedir(n, "s2", {**PUBLICAR, "prompt_id": "t2"})
    assert "mais de uma sessão" in oficina._responder_permissao(True)
    n.sessoes.permissoes.retirar("s2")
    esperar(lambda: "volta" in b)
    assert oficina._responder_permissao(False) == "Negado. Avisei a sessão Loja."
    esperar(lambda: "volta" in a)
    assert a["volta"]["hookSpecificOutput"]["decision"]["behavior"] == "deny"


def test_respondido_em_outro_lugar_a_pergunta_sai_da_fila(tmp_path: Path) -> None:
    n = contexto(tmp_path)
    pedido, saida = pedir(n, "s1", PUBLICAR)
    texto = next(iter(n._perguntas_permissao))
    ServicoAvisos(n)._guardar(texto)  # o Zé estava ocupado: a pergunta esperou na fila
    assert [a.origem for a in n.fila.validos()] == ["permissao"]
    n.sessoes.permissoes.decidir("s1", pedido.id, True, "painel")
    esperar(lambda: "volta" in saida)
    assert not n.fila.validos() and not n._perguntas_permissao
    # Uma pergunta que sobrou de antes de um reinício não é feita.
    n.fila.guardar(texto, origem="permissao", sessao="s1")
    while not n.eventos.empty():
        n.eventos.get_nowait()
    ServicoAvisos(n)._sair_da_fila()
    assert n.eventos.empty() and not n.fila.validos()


def test_sem_aviso_repetido_quando_a_pergunta_ja_foi_feita(tmp_path: Path) -> None:
    n = contexto(tmp_path)
    avisos_genericos.clear()
    pedir(n, "s1", PUBLICAR)
    ServicoOficina(n)._sessao_pede(Sessao(id="s1", nome="Loja", pasta="/x"), "permission")
    assert avisos_genericos == []
    n.sessoes.permissoes.retirar("s1")
    ServicoOficina(n)._sessao_pede(Sessao(id="s1", nome="Loja", pasta="/x"), "permission")
    assert len(avisos_genericos) == 1  # sem pedido na fila (Codex, painel fora): o de sempre


def test_a_janela_abre_quando_o_ze_fala_a_pergunta() -> None:
    from zervis.nucleo.laco import JANELA_PERMISSAO_S, Nucleo

    pergunta = "A sessão Loja quer publicar um fluxo no n8n-loja. Aprovo?"
    n = SimpleNamespace(
        marca=1,
        maquina=SimpleNamespace(aviso_falando=None, estado=e.Estado.FALANDO),
        teclado=SimpleNamespace(falou=lambda t: None),
        voz=SimpleNamespace(falar=lambda t, ao_iniciar=None: None),
        _turno_atual=None,
        _perguntas_permissao={pergunta: ("s1", "p1")},
        _permissao_falada=None,
        _permissao_ate=0.0,
    )
    Nucleo._executar(n, e.Falar("Outra coisa."))  # type: ignore[arg-type]
    assert n._permissao_ate == 0.0
    antes = time.monotonic()
    Nucleo._executar(n, e.Falar(pergunta))  # type: ignore[arg-type]
    assert n._permissao_falada == ("s1", "p1")
    assert (
        antes + JANELA_PERMISSAO_S - 1 < n._permissao_ate <= time.monotonic() + JANELA_PERMISSAO_S
    )


def test_aprova_tudo_aprova_os_pedidos_da_sessao_que_cabem_na_voz(tmp_path: Path) -> None:
    """Uma sessão de pesquisa pedia uma página por vez e a pessoa dizia "aprova tudo"."""
    n = contexto(tmp_path)
    oficina = ServicoOficina(n)
    saidas = [
        pedir(n, "s1", {**PUBLICAR, "tool_input": {"workflowName": nome}})[1]
        for nome in ("Pedido novo", "Boleto", "Estoque")
    ]
    _, longo = pedir(n, "s1", {"tool_name": "Bash", "tool_input": {"command": "cat > /etc/x"}})
    resposta = oficina._responder_permissao(True, tudo=True)
    assert resposta == "Aprovei os 3 pedidos da sessão Loja. Um ficou na tela."
    for saida in saidas:
        esperar(lambda saida=saida: "volta" in saida)
        assert saida["volta"]["hookSpecificOutput"]["decision"]["behavior"] == "allow"
    assert "volta" not in longo  # o comando fica para o painel ou o terminal
    assert [p["ferramenta"] for p in n.sessoes.permissoes.pendentes()] == ["Bash"]
    assert oficina._responder_permissao(True, tudo=True) == (
        "Os pedidos que esperam estão na tela; aprove no painel."
    )
    n.sessoes.permissoes.retirar("s1")
    assert oficina._responder_permissao(True, tudo=True) == (
        "Não há nenhum pedido esperando aprovação."
    )


def test_o_cerebro_nao_aprova_pedido_de_sessao() -> None:
    persona = (Path(__file__).parents[1] / "zervis/persona/ZE.md").read_text()
    persona = " ".join(persona.split())
    assert 'basta dizer "aprova tudo". Nunca diga "aprovado".' in persona
