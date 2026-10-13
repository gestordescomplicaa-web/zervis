"""O modo manutenção: encaminhar à sessão de código, ler a resposta e guardar a zona protegida."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from jarvis.nucleo import estados as e
from jarvis.oficina import manutencao as mod
from jarvis.oficina.manutencao import Manutencao
from jarvis.oficina.sessoes import Sessao, SessaoErro


@dataclass
class SessoesFalsas:
    """As sessões próprias do Zé, sem agente de verdade: guardam o que foi criado e enviado."""

    criadas: list[Sessao] = field(default_factory=list)
    enviados: list[tuple[str, str]] = field(default_factory=list)
    ocupada: bool = False
    gravadas: list[str] = field(default_factory=list)

    def listar(self) -> list[Sessao]:
        return list(self.criadas)

    def criar(
        self,
        nome: str,
        pasta: str,
        motor: str = "claude",
        origem: str = "",
        isolada: bool = False,
    ) -> Sessao:
        s = Sessao(
            id=f"{len(self.criadas):08x}",
            nome=nome,
            pasta=pasta,
            motor=motor,
            origem=origem,
            isolada=isolada,
        )
        if isolada:  # a cópia isolada de verdade, como as sessões fazem
            s.branch, s.worktree = f"ze/{s.id}", str(Path(pasta).parent / f"copia-{s.id}")
            git(Path(pasta), "worktree", "add", "-q", "-b", s.branch, s.worktree, "HEAD")
        self.criadas.append(s)
        return s

    def _gravar(self, s: Sessao) -> None:
        self.gravadas.append(s.nome)

    def ler(self, id_: str) -> Sessao:
        for s in self.criadas:
            if s.id == id_:
                return s
        raise SessaoErro("sessão desconhecida")

    def enviar(self, id_: str, texto: str, quem: str = "usuario") -> Sessao:
        if self.ocupada:
            raise SessaoErro("essa sessão ainda está trabalhando; espere ou pare")
        self.enviados.append((id_, texto))
        return next(s for s in self.criadas if s.id == id_)


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


def nova(repo: Path, sessoes: SessoesFalsas) -> Manutencao:
    return Manutencao(sessoes, repo.parent / "manutencao", repo=repo)  # type: ignore[arg-type]


def test_entrar_abre_a_sessao_do_ze_uma_vez_e_sobrevive_ao_reinicio(repo: Path) -> None:
    sessoes = SessoesFalsas()
    m = nova(repo, sessoes)
    assert m.entrar("gemini").startswith("Modo manutenção ligado, com o Claude.")  # desconhecido
    m.sair()
    assert m.entrar("codex").startswith("Modo manutenção ligado, com o Codex.")
    assert [s.motor for s in sessoes.criadas] == ["claude", "codex"]  # uma sessão por agente
    assert m.entrar("claude").startswith("Modo manutenção ligado, com o Claude.")
    sessao = sessoes.criadas[0]
    assert (sessao.nome, sessao.pasta, sessao.origem) == (
        "Zé · autodesenvolvimento",
        str(repo),
        "manutencao",
    )
    assert nova(repo, sessoes).ligado  # o estado fica gravado: o reinício faz parte
    assert m.sair() == "Saí do modo manutenção."
    m.entrar("claude")
    assert len(sessoes.criadas) == 2  # a mesma sessão de cada agente: a conversa continua
    m.sair()
    assert not nova(repo, sessoes).ligado


def test_pedido_vai_com_contexto_e_o_combinado_dos_arquivos(repo: Path) -> None:
    oficina = SessoesFalsas()
    m = nova(repo, oficina)
    m.entrar("claude")
    assert m.encaminhar("melhora o teclado", "Janela aberta.", 100.0) == (
        "Mandei para o Claude. Aviso quando terminar."
    )
    sessao, texto = oficina.enviados[0]
    pedido = m.estado.pendentes[0].id
    assert sessao == m.estado.sessao
    assert f"pedido {pedido}]" in texto and '"melhora o teclado"' in texto
    assert "Contexto agora: Janela aberta." in texto
    assert str(m.pasta / f"resposta-{pedido}.md") in texto
    assert str(m.pasta / f"pergunta-{pedido}.md") in texto
    assert "jarvis/cerebro/claude.py" in texto  # a zona protegida vai escrita no pedido
    assert "docs/essencia.md" in texto and "Escopo: só trabalho sobre o próprio Zérvis" in texto


def test_essencia_e_seguranca_na_zona_protegida() -> None:
    from jarvis.oficina.manutencao import PROTEGIDOS

    raiz = Path(__file__).resolve().parents[1]
    for arquivo in (
        "docs/essencia.md",
        "jarvis/portal/senha.py",
        "jarvis/portal/servidor.py",
        "jarvis/portal/tunel.py",
        "jarvis/atividade.py",
        "jarvis/transporte/websocket.py",
        "jarvis/cerebro/codex_rpc.py",
    ):
        assert arquivo in PROTEGIDOS and (raiz / arquivo).is_file(), arquivo
    for pasta in ("jarvis/persona/", "systemd/"):
        assert pasta in PROTEGIDOS and (raiz / pasta).is_dir(), pasta


def test_sessao_ocupada_nao_perde_o_pedido_em_silencio(repo: Path) -> None:
    sessoes = SessoesFalsas()
    m = nova(repo, sessoes)
    m.entrar("claude")
    sessoes.ocupada = True
    assert m.encaminhar("x", "", 1.0).startswith("Não consegui mandar para o Claude: essa sessão")
    assert not m.estado.pendentes


def test_pergunta_e_resposta_chegam_uma_vez_e_a_resposta_fica_no_mesmo_pedido(
    repo: Path,
) -> None:
    oficina = SessoesFalsas()
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
    m = nova(repo, SessoesFalsas())
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

    m = nova(repo, SessoesFalsas())
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
    m = nova(repo, SessoesFalsas())
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
    m = nova(repo, SessoesFalsas())  # o processo subiu nesta versão
    (repo / "jarvis/cerebro/ferramentas/__init__.py").write_text("LEITURA = ['tudo']\n")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "direto, sem pedido")
    assert m.guarda(m.rodando) == (True, ("jarvis/cerebro/ferramentas/__init__.py",))


def test_o_cerebro_tem_a_ferramenta_e_ela_pede_aprovacao(repo: Path) -> None:
    from jarvis.cerebro import ferramentas
    from jarvis.nucleo.laco import Nucleo

    m = nova(repo, SessoesFalsas())
    nomes = [t.name for t in ferramentas.g_manutencao.ferramentas(m)]
    assert nomes == ["modo_manutencao"] and "modo_manutencao" not in ferramentas.LEITURA
    descrever = Nucleo._descrever_manutencao
    nome = "mcp__jarvis__modo_manutencao"
    assert descrever(nome, {"acao": "entrar", "agente": "codex"}) == (
        "Vou ligar o modo manutenção com o Codex; seus pedidos vão para a sessão de código."
    )
    assert descrever(nome, {"acao": "sair"}) == "Vou desligar o modo manutenção."
    assert descrever("mcp__jarvis__tela_agir", {}) is None


def _commit(pasta: Path, arquivo: str, texto: str) -> None:
    (pasta / arquivo).parent.mkdir(parents=True, exist_ok=True)
    (pasta / arquivo).write_text(texto)
    git(pasta, "add", "-A")
    git(pasta, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", f"muda {arquivo}")


def test_melhorias_numa_copia_isolada_aplicar_e_descartar(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m = nova(repo, SessoesFalsas())
    m.entrar()
    m.encaminhar("melhora o guia", "", 1.0)
    copia = Path(m.copia().worktree)  # type: ignore[union-attr]
    assert m.copia().nome == "Zé · autodesenvolvimento"  # type: ignore[union-attr]
    m.copia().nome = "Zé · melhorias"  # type: ignore[union-attr]  # criada com o nome antigo
    assert m.copia().nome == "Zé · autodesenvolvimento"  # type: ignore[union-attr]
    assert m.mudancas()["commits"] == [] and m.aplicar() == (
        False,
        "Não há melhorias para aplicar.",
    )
    _commit(copia, "docs/guia.md", "guia novo\n")
    _commit(copia, "jarvis/cerebro/ferramentas/__init__.py", "LEITURA = ['tudo']\n")
    mud = m.mudancas()
    assert len(mud["commits"]) == 2 and not (repo / "docs/guia.md").exists()  # o Zé em uso intacto
    assert mud["protegidos"] == ["jarvis/cerebro/ferramentas/__init__.py"]
    ok, texto = m.aplicar()
    assert not ok and "zona protegida" in texto
    m.testar = lambda pasta: False
    assert m.aplicar(revisado=True) == (
        False,
        "Os testes falharam na cópia. Peça para a sessão corrigir antes.",
    )
    reinicios: list[bool] = []
    m.testar = lambda pasta: True

    def reiniciar(revisado: bool = False) -> tuple[bool, str]:
        reinicios.append(revisado)
        return True, "ok"

    monkeypatch.setattr(m, "reiniciar", reiniciar)
    assert m.aplicar(revisado=True) == (True, "ok") and reinicios == [True]
    assert (repo / "docs/guia.md").read_text() == "guia novo\n" and m.mudancas()["commits"] == []
    _commit(copia, "docs/rascunho.md", "descartável\n")
    (copia / "solto.txt").write_text("sem commit")
    assert m.mudancas()["sem_commit"]
    assert m.descartar() == "Mudanças descartadas."
    assert m.mudancas()["commits"] == [] and not (copia / "docs/rascunho.md").exists()
    assert not (copia / "solto.txt").exists()
