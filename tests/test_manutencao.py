"""O modo manutenção: encaminhar à sessão de código, ler a resposta e guardar a zona protegida."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from jarvis.nucleo import estados as e
from jarvis.oficina import manutencao as mod
from jarvis.oficina.manutencao import Manutencao
from jarvis.oficina.oficina import Projeto
from jarvis.oficina.orca import OrcaErro


@dataclass
class OficinaFalsa:
    sessoes_abertas: list[str] = field(default_factory=lambda: ["claude"])
    enviados: list[tuple[str, str]] = field(default_factory=list)

    def achar_projeto(self, nome: str) -> Projeto:
        return Projeto("JARVIS", nome, ())

    def sessoes(self, projeto: Projeto) -> list[dict[str, str]]:
        return [{"handle": "t", "titulo": "sessão", "agente": a} for a in self.sessoes_abertas]

    def mandar_texto(
        self, projeto: str, texto: str, sessao: str = "", agente: str = ""
    ) -> dict[str, str]:
        if sessao or agente not in self.sessoes_abertas:  # a manutenção escolhe pelo agente
            raise OrcaErro("não há sessão")
        self.enviados.append((agente, texto))
        return {}


def git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 (git num repositório temporário do teste)
        ["/usr/bin/git", "-C", str(repo), *args], check=True, capture_output=True
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = tmp_path / "repo"
    (r / "jarvis/cerebro/ferramentas").mkdir(parents=True)
    (r / "docs").mkdir()
    (r / "jarvis/cerebro/ferramentas/__init__.py").write_text("LEITURA = []\n")
    (r / "docs/x.md").write_text("x\n")
    git(r, "init", "-q")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "base", "--allow-empty")
    git(r, "add", "-A")
    git(r, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "inicial")
    monkeypatch.setattr(mod, "CONFIG_DO_USUARIO", tmp_path / "config.toml")
    return r


def nova(repo: Path, oficina: OficinaFalsa) -> Manutencao:
    return Manutencao(oficina, repo.parent / "manutencao", repo=repo, projeto=str(repo))  # type: ignore[arg-type]


def test_entrar_exige_a_sessao_aberta_e_sobrevive_ao_reinicio(repo: Path) -> None:
    oficina = OficinaFalsa(sessoes_abertas=["claude"])
    m = nova(repo, oficina)
    assert m.entrar("codex").startswith("Não entrei no modo manutenção: não há sessão do Codex")
    assert not m.ligado
    assert m.entrar("claude").startswith("Modo manutenção ligado, com o Claude.")
    assert nova(repo, oficina).ligado  # o estado fica gravado: o reinício faz parte
    assert m.sair() == "Saí do modo manutenção."
    assert not nova(repo, oficina).ligado


def test_pedido_vai_com_contexto_e_o_combinado_dos_arquivos(repo: Path) -> None:
    oficina = OficinaFalsa()
    m = nova(repo, oficina)
    m.entrar("claude")
    assert m.encaminhar("melhora o teclado", "Janela aberta.", 100.0) == (
        "Mandei para o Claude. Aviso quando terminar."
    )
    agente, texto = oficina.enviados[0]
    pedido = m.estado.pendentes[0].id
    assert agente == "claude"
    assert f"pedido {pedido}]" in texto and '"melhora o teclado"' in texto
    assert "Contexto agora: Janela aberta." in texto
    assert str(m.pasta / f"resposta-{pedido}.md") in texto
    assert str(m.pasta / f"pergunta-{pedido}.md") in texto
    assert "jarvis/cerebro/claude.py" in texto  # a zona protegida vai escrita no pedido


def test_pergunta_e_resposta_chegam_uma_vez_e_a_resposta_fica_no_mesmo_pedido(
    repo: Path,
) -> None:
    oficina = OficinaFalsa()
    m = nova(repo, oficina)
    m.entrar()
    m.encaminhar("muda a cor do anel", "", 100.0)
    pedido = m.estado.pendentes[0].id
    (m.pasta / f"pergunta-{pedido}.md").write_text("Roxo ou azul?\n")
    assert m.verificar(101.0) == [mod.Chegada("pergunta", pedido, "Roxo ou azul?")]
    assert m.verificar(102.0) == []
    assert m.encaminhar("roxo", "", 103.0) == "Respondi ao Claude."
    assert len(m.estado.pendentes) == 1 and f"pedido {pedido}]" in oficina.enviados[-1][1]
    assert 'Resposta do usuário à sua pergunta: "roxo"' in oficina.enviados[-1][1]
    (m.pasta / f"resposta-{pedido}.md").write_text("Pronto,\n o anel ficou roxo.")
    [chegou] = m.verificar(104.0)
    assert (chegou.tipo, chegou.texto, chegou.protegidos) == (
        "resposta",
        "Pronto, o anel ficou roxo.",
        (),
    )
    assert not m.estado.pendentes


def test_a_guarda_ve_codigo_novo_e_a_zona_protegida(repo: Path) -> None:
    m = nova(repo, OficinaFalsa())
    m.entrar()
    m.encaminhar("x", "", 1.0)
    inicio = m.estado.pendentes[0].inicio
    assert m.guarda(inicio) == (False, ())
    (repo / "docs/x.md").write_text("y\n")
    assert m.guarda(inicio) == (False, ())  # documento: nem reinício nem alarme
    (repo / "jarvis/novo.py").write_text("")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "codigo")
    assert m.guarda(inicio) == (True, ())
    (repo / "jarvis/cerebro/ferramentas/__init__.py").write_text("LEITURA = ['tudo']\n")
    assert m.guarda(inicio) == (True, ("jarvis/cerebro/ferramentas/__init__.py",))
    mod.CONFIG_DO_USUARIO.write_text("[sistema]\n")
    assert str(mod.CONFIG_DO_USUARIO) in m.guarda(inicio)[1]


def test_reiniciar_recusa_com_zona_protegida_sem_eu_revisei(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rodou: list[Any] = []

    def rodar(*a: Any, **k: Any) -> subprocess.CompletedProcess[str]:
        rodou.append(a)
        return subprocess.CompletedProcess(a, 0)

    m = nova(repo, OficinaFalsa())
    m.rodando = "abc"
    monkeypatch.setattr(subprocess, "run", rodar)
    monkeypatch.setattr(m, "guarda", lambda inicio: (True, ("jarvis/cerebro/claude.py",)))
    ok, fala = m.reiniciar()
    assert not ok and "eu revisei" in fala and not rodou
    ok, fala = m.reiniciar(revisado=True)
    assert ok and "Vou me reiniciar" in fala
    assert rodou[0][0][:2] == ["/usr/bin/make", "-s"]  # os testes antes
    assert "deploy/reinicio-seguro.sh" in rodou[1][0][4] and rodou[1][0][6] == "abc"


def test_resultado_do_reinicio_e_dito_uma_vez(repo: Path) -> None:
    m = nova(repo, OficinaFalsa())
    (m.pasta / "reinicio.json").write_text('{"resultado": "voltou"}')
    assert "voltei sozinho para a anterior" in (m.resultado_do_reinicio() or "")
    assert m.resultado_do_reinicio() is None


@pytest.mark.parametrize(
    ("fala", "nome"),
    [
        ("Jarvis, entre no modo manutenção.", "manutencao_entrar"),
        ("Entra no modo de manutenção com o Codex.", "manutencao_entrar:codex"),
        ("Modo manutenção.", "manutencao_entrar"),
        ("Sai do modo manutenção.", "manutencao_sair"),
        ("Como está a manutenção?", "manutencao_situacao"),
        ("Reinicia o JARVIS.", "reiniciar"),
        ("Reinicia o JARVIS, eu revisei.", "reiniciar:revisado"),
        ("Faz uma rodada de melhoria.", "rodada_melhoria"),
        # A frase real de 07/10/2026 que foi ao cérebro e virou o menu de configurações:
        ("Coloque no modo manutenção.", "manutencao_entrar"),
        ("Ative o modo manutenção, por favor.", "manutencao_entrar"),
        ("Ative o modo manuntenção.", "manutencao_entrar"),  # o Whisper erra a palavra
        ("Jarvis, bota em manutenção com o Codex.", "manutencao_entrar:codex"),
        ("Vamos para o modo de manutenção.", "manutencao_entrar"),
        ("Desliga a manutenção.", "manutencao_sair"),
        ("Saia do teu modo manutenção.", "manutencao_sair"),
        ("Sai do seu modo de manutenção.", "manutencao_sair"),
        ("Como anda a manutenção?", "manutencao_situacao"),
        # As de 08/10/2026 que foram à sessão: a hesitação e o "Ei Zé" mal transcrito.
        ("Um Desative o modo manutenção.", "manutencao_sair"),
        ("Eis é saia do modo manutenção.", "manutencao_sair"),
        # Perguntas, negações e pedidos com a palavra não são o comando:
        ("O que é o modo manutenção?", None),
        ("Não entra no modo manutenção.", None),
        ("Coloque um botão de manutenção no menu.", None),
    ],
)
def test_comandos_da_manutencao(fala: str, nome: str | None) -> None:
    assert e.comando(fala) == nome


def test_no_modo_manutencao_o_pedido_vai_para_a_sessao_e_comandos_seguem_locais() -> None:
    m = e.Maquina(manutencao=lambda: True)
    m.tratar(e.Presenca(True), 0)
    m.tratar(e.Ativacao(), 1)
    assert m.tratar(e.FimDeFala("melhora o teclado"), 2) == [
        e.Comando("manutencao_pedido:melhora o teclado")
    ]
    assert m.tratar(e.Digitado("Hey Zé"), 2.5)[-1] == e.EnviarAoCerebro("Hey Zé")  # só o chamado
    assert m.tratar(e.Digitado("abre o guia"), 3) == [
        e.CortarFala(),
        e.InterromperCerebro(),
        e.Comando("abrir_orbe:Guia"),
    ]


def test_a_guarda_do_reinicio_ve_commits_feitos_fora_de_um_pedido(repo: Path) -> None:
    m = nova(repo, OficinaFalsa())  # o processo subiu nesta versão
    (repo / "jarvis/cerebro/ferramentas/__init__.py").write_text("LEITURA = ['tudo']\n")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "direto, sem pedido")
    assert m.guarda(m.rodando) == (True, ("jarvis/cerebro/ferramentas/__init__.py",))


def test_o_cerebro_tem_a_ferramenta_e_ela_pede_aprovacao(repo: Path) -> None:
    from jarvis.cerebro import ferramentas
    from jarvis.nucleo.laco import Nucleo

    m = nova(repo, OficinaFalsa())
    nomes = [t.name for t in ferramentas.g_manutencao.ferramentas(m)]
    assert nomes == ["modo_manutencao"] and "modo_manutencao" not in ferramentas.LEITURA
    descrever = Nucleo._descrever_manutencao
    nome = "mcp__jarvis__modo_manutencao"
    assert descrever(nome, {"acao": "entrar", "agente": "codex"}) == (
        "Vou ligar o modo manutenção com o Codex; seus pedidos vão para a sessão de código."
    )
    assert descrever(nome, {"acao": "sair"}) == "Vou desligar o modo manutenção."
    assert descrever("mcp__jarvis__tela_agir", {}) is None
