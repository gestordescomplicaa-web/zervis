"""Comandos locais de voz (sem o cérebro): o que cada um faz na tela e o que o JARVIS fala."""

import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jarvis.foco.frentes import Foco
from jarvis.memoria.linha import LinhaDoTempo
from jarvis.nucleo import estados as e
from jarvis.nucleo.laco import Nucleo, Status


@dataclass
class Registro:
    """Faz o papel do HUD, da tela, da ponte e da fila de eventos, anotando tudo."""

    janela_aberta: bool = True
    feito: list[tuple[str, Any]] = field(default_factory=list)
    provas: list[tuple[str, str]] = field(default_factory=list)  # evidências da rodada
    pasta: Path = Path("/nao-existe")

    def registrar(self, tipo: str, detalhe: str = "") -> None:
        self.provas.append((tipo, detalhe))

    def abrir_mapa(self) -> None:
        self.feito.append(("mapa", None))

    def pedir_maos(self, acao: str) -> None:
        self.feito.append(("maos", acao))

    def aberto(self) -> bool:
        return self.janela_aberta

    def enviar(self, acoes: list[dict[str, Any]]) -> None:
        self.feito.append(("tela", acoes))

    def trazer(self) -> None:
        self.feito.append(("trazer", None))

    def abrir(self) -> None:
        self.feito.append(("abrir", None))

    def fechar(self) -> None:
        self.feito.append(("fechar", None))

    def agir(self, acoes: list[dict[str, Any]]) -> dict[str, Any]:
        self.feito.append(("agir", acoes))
        achou = acoes[0]["alvo"] == "burrinho"
        return {"resultados": [{"ok": achou, "abriu": "burrinho"} if achou else {"ok": False}]}

    def reiniciar(self) -> None:
        self.feito.append(("reiniciar", None))

    def somar_local(self) -> None:
        pass

    def put(self, evento: object) -> None:
        self.feito.append(("evento", evento))

    def resumo(self, agora: float = 0.0) -> str:
        return "Janela do JARVIS: aberta."


class ManutencaoFalsa:
    """O modo manutenção sem Orca: anota o que pediram e responde frases fixas."""

    ligado = True
    nome_do_agente = "Claude"

    def __init__(self, r: Registro) -> None:
        self.r = r

    def entrar(self, agente: str = "") -> str:
        self.r.feito.append(("entrar", agente))
        return "Modo manutenção ligado."

    def sair(self) -> str:
        return "Saí do modo manutenção."

    def situacao(self, agora: float) -> str:
        return "Nenhum pedido em andamento."

    def encaminhar(self, texto: str, contexto: str, agora: float, rodada: str = "") -> str:
        self.r.feito.append(("encaminhar", texto if not rodada else "rodada"))
        return "Mandei para o Claude."

    def mudancas(self) -> dict[str, Any]:
        return {"copia": False}  # sem melhorias na cópia: "reinicia" só reinicia

    def reiniciar(self, revisado: bool = False) -> tuple[bool, str]:
        self.r.feito.append(("reiniciar", revisado))
        return True, "Vou me reiniciar."


def rodar(nome: str, janela_aberta: bool = True) -> tuple[str, list[tuple[str, Any]]]:
    r = Registro(janela_aberta)
    n = Nucleo.__new__(Nucleo)
    n.hud = n.tela = n.ponte = n.eventos = n.consumo = r  # type: ignore[assignment]
    n.marca = 0
    n.maquina = e.Maquina(orbes={"orca": "Orca", "guia": "Guia"})
    n.manutencao = ManutencaoFalsa(r)  # type: ignore[assignment]
    n.evidencias = r  # type: ignore[assignment]
    n.linha = LinhaDoTempo(Path(tempfile.mkdtemp()) / "linha.jsonl")
    n.foco = Foco(Path(tempfile.mkdtemp()) / "frentes.json")
    n.status = Status()
    n.trocar_cerebro = lambda id_: f"trocado para {id_}"  # type: ignore[method-assign]
    n.relatorio_de_baterias = lambda: "baterias"  # type: ignore[method-assign]
    n.ligar_mensagens = lambda ativo: f"whatsapp {ativo}"  # type: ignore[method-assign]
    n.voz = SimpleNamespace(muda=False, parar=lambda: None)  # type: ignore[assignment]
    n._ligar_ativacao = lambda: None  # type: ignore[method-assign]
    n._comando(nome)
    time.sleep(0.1)  # trazer, abrir, fechar e a busca correm numa linha de execução própria
    frases = [ev.texto for tipo, ev in r.feito if tipo == "evento" and isinstance(ev, e.Frase)]
    assert ("evento", e.RespostaFim()) in r.feito and n.marca == 1
    acoes = [(t, v) for t, v in r.feito if t != "evento"]
    return frases[0], acoes


NUCLEO = [{"acao": "nucleo", "valor": "abrir"}]


@pytest.mark.parametrize(
    ("nome", "fala", "acoes"),
    [
        ("nova_conversa", "Certo, começando uma conversa nova.", [("reiniciar", None)]),
        ("modo_maos_livres", "Modo mãos livres.", []),
        ("modo_avisos", "Modo normal.", []),
        ("mostrar_mapa", "Está no Núcleo.", [("mapa", None), ("trazer", None)]),
        ("calibrar_maos", "Vamos calibrar. Siga as instruções na tela.", [("maos", "calibrar")]),
        ("maos_padrao", "Pronto, voltei à calibração e à câmera originais.", [("maos", "padrao")]),
        ("nucleo_abrir", "Núcleo aberto.", [("tela", NUCLEO), ("trazer", None)]),
        (
            "teclado_abrir",
            "Teclado aberto; pode escrever.",
            [("tela", [{"acao": "teclado", "valor": "abrir"}]), ("trazer", None)],
        ),
        (
            "nucleo_fechar",
            "Núcleo recolhido.",
            [("tela", [{"acao": "nucleo", "valor": "fechar"}])],
        ),
        ("janela_fechar", "Fechei a minha janela; a câmera apagou.", [("fechar", None)]),
        (
            "abrir_orbe:Guia",
            "Guia na tela.",
            [("tela", [{"acao": "abrir", "alvo": "Guia"}]), ("trazer", None)],
        ),
        ("fechar_alvo:Guia", "Fechado.", [("tela", [{"acao": "fechar", "alvo": "Guia"}])]),
        ("mapa_fechar", "Fechado.", [("tela", [{"acao": "fechar_mapa"}])]),
        (
            "mostrar_sessoes",
            "Está no Mapa.",
            [
                ("tela", [{"acao": "abrir_mapa"}, {"acao": "focar", "alvo": "sessoes"}]),
                ("trazer", None),
            ],
        ),
        (
            "visual_anel",
            "Pronto, o anel de volta.",
            [("tela", [{"acao": "visual", "valor": "anel"}]), ("trazer", None)],
        ),
        (
            "mostrar_automacoes",
            "Está no Mapa.",
            [
                ("tela", [{"acao": "abrir_mapa"}, {"acao": "focar", "alvo": "automacoes"}]),
                ("trazer", None),
            ],
        ),
        ("brilho_mais", "Brilho da câmera aumentado.", [("maos", "brilho:+")]),
        ("tema_roxo", "Pronto, tema roxo.", [("maos", "tema:roxo")]),
        ("configuracoes", "Configurações na tela.", [("maos", "config")]),
        ("trocar:gpt", "trocado para gpt", []),
        ("relatorio_de_uso", "baterias", []),
        ("manutencao_entrar:codex", "Modo manutenção ligado.", [("entrar", "codex")]),
        ("manutencao_sair", "Saí do modo manutenção.", []),
        ("manutencao_situacao", "Nenhum pedido em andamento.", []),
        (
            "manutencao_pedido:melhora o teclado",
            "Mandei para o Claude.",
            [("encaminhar", "melhora o teclado")],
        ),
        ("reiniciar", "Vou me reiniciar.", [("reiniciar", False)]),
        (
            "reiniciar:revisado",
            "Vou me reiniciar.",
            [("reiniciar", False)],
        ),  # "eu revisei" pela voz não vale (ADR 0028)
        ("rodada_melhoria", "Mandei para o Claude.", [("encaminhar", "rodada")]),
    ],
)
def test_cada_comando_faz_e_fala_o_certo(
    nome: str, fala: str, acoes: list[tuple[str, Any]]
) -> None:
    assert rodar(nome) == (fala, acoes)


def test_todo_comando_da_tabela_tem_quem_o_execute() -> None:
    for nome in e.COMANDOS:
        fala, _ = rodar(nome)
        assert fala and (fala != "baterias" or nome == "relatorio_de_uso"), nome


def test_pedido_enfileirado_nao_entra_na_sessao_depois_de_sair_da_manutencao() -> None:
    registro = Registro()
    n = Nucleo.__new__(Nucleo)
    manutencao = ManutencaoFalsa(registro)
    manutencao.ligado = False
    n.manutencao = manutencao  # type: ignore[assignment]
    n.eventos = registro  # type: ignore[assignment]
    n._responder_depois("manutencao_pedido", "Diminua o brilho em cinquenta por cento")
    assert not any(tipo == "encaminhar" for tipo, _ in registro.feito)
    assert ("evento", e.Frase("Manutenção desligada. Faça o pedido na conversa.")) in registro.feito


def test_com_a_janela_fechada_mostrar_abre_e_fechar_nao_faz_nada() -> None:
    assert rodar("abrir_orbe:Guia", janela_aberta=False) == (
        "Abrindo a minha janela.",
        [("abrir", None), ("tela", [{"acao": "abrir", "alvo": "Guia"}])],
    )
    assert rodar("fechar_alvo:Guia", janela_aberta=False) == ("A minha janela já está fechada.", [])
    assert rodar("nucleo_fechar", janela_aberta=False) == ("A minha janela já está fechada.", [])


@pytest.mark.parametrize(
    ("nome", "fala", "acao"),
    [
        (
            "abrir_item:Acervo:burrinho",
            "Burrinho na tela.",
            {"acao": "abrir", "alvo": "burrinho", "orbe": "Acervo"},
        ),
        ("abrir_item::burrinho", "Burrinho na tela.", {"acao": "abrir", "alvo": "burrinho"}),
        (
            "abrir_item:Guia:planilha",
            "Não achei planilha no Guia.",
            {"acao": "abrir", "alvo": "planilha", "orbe": "Guia"},
        ),
    ],
)
def test_item_do_nucleo_espera_a_busca_e_diz_se_achou(
    nome: str, fala: str, acao: dict[str, Any]
) -> None:
    assert rodar(nome) == (fala, [("agir", [acao])])
