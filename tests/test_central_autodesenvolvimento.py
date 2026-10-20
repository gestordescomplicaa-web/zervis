"""Três cópias legadas e uma central, com Git e SQLite reais e nenhuma conta real."""

import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.cerebro import contas
from zervis.oficina.central import Central
from zervis.oficina.manutencao import Manutencao
from zervis.oficina.sessoes import Sessao, SessaoErro, Sessoes
from zervis.portal.acoes import Acoes
from zervis.portal.senha import SO_NO_PC
from zervis.portal.servidor import PedidoInvalido


def git(pasta: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 (repositórios sintéticos, argumentos fixos)
        ["/usr/bin/git", "-C", str(pasta), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.strip()


def commit(pasta: Path, nome: str, texto: str) -> str:
    (pasta / nome).write_text(texto)
    git(pasta, "add", nome)
    git(pasta, "commit", "-qm", nome)
    return git(pasta, "rev-parse", "HEAD")


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Sessoes, Manutencao]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Teste")
    git(repo, "config", "user.email", "teste@localhost")
    commit(repo, "comum.txt", "base\n")
    cs = contas.Contas(tmp_path / "contas.json", tmp_path / "contas")
    monkeypatch.setattr(contas, "Contas", lambda: cs)
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,), rodar=lambda *_: "ok")
    m = Manutencao(sessoes, tmp_path / "manutencao", repo)
    return repo, sessoes, m


def legadas(repo: Path, sessoes: Sessoes, m: Manutencao) -> list[Sessao]:
    # As versões antigas permitiam criar uma por agente. A API atual proíbe a duplicação;
    # a fixture reproduz os registros existentes antes da instalação desta versão.
    criadas = [
        sessoes.criar("Autodesenvolvimento", str(repo), motor=motor, isolada=True)
        for motor in ("claude", "codex", "codex")
    ]
    for s in criadas:
        sessoes._mudar(s.id, origem="manutencao")
    m.estado.sessao = criadas[0].id
    m._gravar()
    return [sessoes.ler(s.id) for s in criadas]


def esperar(m: Manutencao) -> dict[str, Any]:
    fim = time.monotonic() + 15
    while m.central.em_andamento() and time.monotonic() < fim:
        time.sleep(0.01)
    assert not m.central.em_andamento(), "a migração não terminou"
    return m.central.situacao(m.estado.sessao)


def test_tres_copias_unificam_commits_rascunhos_historicos_e_preservam_origens(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    central, a, b = legadas(repo, sessoes, m)
    commit(central.onde, "atual.txt", "central\n")
    commit(a.onde, "claude.txt", "concluído\n")
    commit(b.onde, "codex.txt", "em revisão\n")
    (a.onde / "rascunho.txt").write_text("ainda sem commit\n")
    (b.onde / "codex.txt").write_text("alteração sem commit\n")
    # O índice original pode diferir do arquivo; fotografar não o altera.
    git(b.onde, "add", "codex.txt")
    (b.onde / "codex.txt").write_text("alteração posterior ao stage\n")
    commit(a.onde, ".gitignore", "privado.local\n")
    (a.onde / "privado.local").write_text("preservado na origem\n")
    sessoes.anotar(a.id, "usuario", "Preparar a agenda")
    sessoes.anotar(a.id, "agente", "Agenda preparada; falta conferir horários.")
    sessoes.anotar(b.id, "usuario", "Revisar o painel")
    sessoes._mudar(b.id, interrompida="Falta conferir a tela", ultimo_pedido="Revisar o painel")
    originais = {
        s.id: (git(s.onde, "status", "--porcelain"), git(s.onde, "rev-parse", "HEAD"))
        for s in (a, b)
    }
    assert "iniciada" in m.unificar_sessoes()
    estado = esperar(m)
    assert estado["estado"] == "concluida", estado
    assert (central.onde / "rascunho.txt").read_text() == "ainda sem commit\n"
    assert (central.onde / "codex.txt").read_text() == "alteração posterior ao stage\n"
    assert (central.onde / "claude.txt").read_text() == "concluído\n"
    assert not (central.onde / "privado.local").exists()
    assert not (repo / "codex.txt").exists()  # ainda depende de Aplicar no painel
    for s in (a, b):
        assert originais[s.id] == (
            git(s.onde, "status", "--porcelain"),
            git(s.onde, "rev-parse", "HEAD"),
        )
        assert sessoes.arquivada_em(s.id) == central.id
        assert s.onde.is_dir()
    mensagens = sessoes.mensagens(central.id)
    assert any(
        x.get("origem_sessao") == a.id and "Agenda preparada" in x["texto"] for x in mensagens
    )
    assert "Falta conferir a tela" in sessoes.ler(central.id).passagem
    assert "Preparar a agenda" in sessoes.ler(central.id).passagem
    backups = list(m.central.pasta.glob("*.db"))
    assert len(backups) == 1 and backups[0].stat().st_mode & 0o777 == 0o600
    assert "já estão centralizadas" in m.unificar_sessoes()
    assert sessoes.mensagens(central.id) == mensagens


def test_conflito_na_ultima_origem_nao_altera_nenhuma_copia(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    central, a, b = legadas(repo, sessoes, m)
    commit(central.onde, "comum.txt", "central\n")
    commit(a.onde, "a.txt", "a\n")
    commit(b.onde, "comum.txt", "outra escolha\n")
    antes = git(central.onde, "rev-parse", "HEAD")
    m.unificar_sessoes()
    estado = esperar(m)
    assert estado["estado"] == "erro" and "conflitos" in estado["aviso"], estado
    assert git(central.onde, "rev-parse", "HEAD") == antes
    assert not (central.onde / "a.txt").exists()
    assert all(not sessoes.arquivada_em(s.id) for s in (a, b))
    assert git(repo, "for-each-ref", "--format=%(refname)", "refs/zervis/arquivo")


def test_recupera_a_mesma_sessao_sem_estado_json_e_sem_filtrar_agente(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    id_ = m.abrir_sessao("codex")
    pasta = sessoes.ler(id_).worktree
    (m.pasta / "estado.json").unlink()
    outra = Manutencao(sessoes, m.pasta, repo)
    assert outra.abrir_sessao() == id_
    assert sessoes.ler(id_).motor == "codex"
    assert len(sessoes.listar()) == 1 and sessoes.ler(id_).worktree == pasta


def test_sem_vinculo_recupera_unica_candidata_de_outro_agente(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    s = sessoes.criar("Legada", str(repo), motor="codex", origem="manutencao", isolada=True)
    assert m.abrir_sessao() == s.id
    assert sessoes.ler(s.id).motor == "codex" and m.estado.agente == "codex"
    assert len(sessoes.listar()) == 1


def test_varias_candidatas_sem_referencia_exigem_escolha_explicita(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    _, escolhida, _ = legadas(repo, sessoes, m)
    m.estado.sessao = ""
    with pytest.raises(SessaoErro, match="Escolha a sessão central"):
        m.abrir_sessao()
    assert len(sessoes.listar()) == 3
    m.unificar_sessoes(escolhida.id)
    assert esperar(m)["estado"] == "concluida"
    assert m.estado.sessao == escolhida.id


@pytest.mark.parametrize("faltando", ["pasta", "registro"])
def test_central_ausente_nao_cria_substituta_silenciosa(
    ambiente: tuple[Path, Sessoes, Manutencao],
    faltando: str,
) -> None:
    _, sessoes, m = ambiente
    id_ = m.abrir_sessao()
    if faltando == "pasta":
        shutil.rmtree(sessoes.ler(id_).worktree)
    else:
        sessoes._dados.remover("sessoes", id_)
    with pytest.raises(SessaoErro, match=r"ausente|indisponível"):
        m.abrir_sessao("codex")
    assert m.central.registro()["sessao"] == id_
    assert len(sessoes.listar()) == (1 if faltando == "pasta" else 0)


def test_aberturas_concorrentes_em_duas_instancias_criam_uma_unica_central(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    outra = Manutencao(sessoes, m.pasta, repo)
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda n: (m if n % 2 else outra).abrir_sessao(), range(6)))
    assert len(set(resultados)) == 1 and len(sessoes.listar()) == 1


def test_migracao_reserva_comandos_e_nao_bloqueia_leituras(
    ambiente: tuple[Path, Sessoes, Manutencao],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, sessoes, m = ambiente
    central, a, _ = legadas(repo, sessoes, m)
    liberada = threading.Event()
    original = Central._unificar

    def pausar(self: Central, id_: str, ids: set[str]) -> None:
        assert liberada.wait(5)
        original(self, id_, ids)

    monkeypatch.setattr(Central, "_unificar", pausar)
    m.unificar_sessoes()
    try:
        assert sessoes.ler(a.id).id == a.id
        for operacao in (
            lambda: sessoes.enviar(central.id, "novo pedido"),
            lambda: sessoes.escrever_terminal(a.id, b"teclas"),
            lambda: sessoes.criar_arquivo(central.id, "novo.md", "novo"),
            lambda: sessoes.trocar(central.id, "codex"),
            lambda: sessoes.ajustar_modelo(central.id, ""),
            lambda: sessoes.excluir(central.id),
            lambda: sessoes.abrir_terminal(central.id),
            lambda: m.unificar_sessoes(),
        ):
            with pytest.raises(SessaoErro, match=r"[Uu]nificação"):
                operacao()
        assert m.aplicar()[0] is False
    finally:
        liberada.set()
        esperar(m)


@pytest.mark.parametrize("condicao", ["atualizando", "trabalhando", "rascunho"])
def test_migracao_recusa_atualizacao_trabalho_ativo_e_rascunho_central(
    ambiente: tuple[Path, Sessoes, Manutencao],
    monkeypatch: pytest.MonkeyPatch,
    condicao: str,
) -> None:
    repo, sessoes, m = ambiente
    central, a, _ = legadas(repo, sessoes, m)
    if condicao == "atualizando":
        m.atualizando = lambda: True
    elif condicao == "trabalhando":
        monkeypatch.setattr(sessoes, "trabalhando", lambda: [a.id])
    else:
        (central.onde / "rascunho.txt").write_text("não perder")
    with pytest.raises(SessaoErro):
        m.unificar_sessoes()
    assert not m.central.em_andamento()


def test_origens_arquivadas_recusam_envio_mas_continuam_consultaveis(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    central, a, _ = legadas(repo, sessoes, m)
    m.unificar_sessoes()
    assert esperar(m)["estado"] == "concluida"
    for operacao in (
        lambda: sessoes.enviar(a.id, "pedido"),
        lambda: sessoes.trocar(a.id, "claude"),
        lambda: sessoes.excluir(a.id),
    ):
        with pytest.raises(SessaoErro, match="substituída"):
            operacao()
    assert sessoes.mensagens(a.id)
    with pytest.raises(SessaoErro, match="preservada"):
        sessoes.excluir(central.id)


def test_queda_apos_git_retoma_sem_duplicar_historico(
    ambiente: tuple[Path, Sessoes, Manutencao],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, sessoes, m = ambiente
    central, a, _ = legadas(repo, sessoes, m)
    commit(a.onde, "trabalho.txt", "feito\n")
    sessoes.anotar(a.id, "agente", "Trabalho terminado.")
    original = sessoes._dados.guardar
    falhar = True

    def guardar(colecao: str, dados: dict[str, Any], chave: str = "") -> None:
        if colecao == "mensagens-" + central.id and falhar:
            raise OSError("queda após a integração do Git")
        original(colecao, dados, chave)

    monkeypatch.setattr(sessoes._dados, "guardar", guardar)
    m.unificar_sessoes()
    assert esperar(m)["estado"] == "erro"
    assert (central.onde / "trabalho.txt").read_text() == "feito\n"
    assert not sessoes.arquivada_em(a.id)
    falhar = False
    m.unificar_sessoes()
    assert esperar(m)["estado"] == "concluida"
    assert sum(x["texto"] == "Trabalho terminado." for x in sessoes.mensagens(central.id)) == 1


def test_rotas_exigem_confirmacao_e_pc_local(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    legadas(repo, sessoes, m)
    acoes = Acoes(SimpleNamespace(sessoes=sessoes, manutencao=m), repo.parent, repo.parent)
    assert {"ze/central", "ze/unificar"} <= SO_NO_PC
    assert len(acoes.central_de_melhorias({})["candidatas"]) == 3
    with pytest.raises(PedidoInvalido, match="Confirme"):
        acoes.unificar_melhorias({})
    assert m.central.registro() == {}


def test_trocas_entre_claude_duas_contas_codex_e_modelos_mantem_central_e_contexto(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    central, a, b = legadas(repo, sessoes, m)
    sessoes.anotar(a.id, "usuario", "Conferir agenda")
    sessoes.anotar(b.id, "agente", "O painel está pronto; falta testar no celular.")
    m.unificar_sessoes()
    assert esperar(m)["estado"] == "concluida"
    cs = contas.Contas()
    uma = cs.adicionar("codex", "Primeira")
    outra = cs.adicionar("codex", "Segunda")
    s, _ = m.trocar(central.id, "codex", uma.id)
    assert "Conferir agenda" in s.passagem and "falta testar no celular" in s.passagem
    sessoes.ajustar_modelo(central.id, "")
    assert sessoes.ler(central.id).passagem == s.passagem
    # Conversa nativa sintética já existente; a passagem da unificação ainda será entregue.
    nativa = uma.onde / "sessions" / "fio-central.jsonl"
    nativa.parent.mkdir(parents=True)
    nativa.write_text("{}\n")
    sessoes._mudar(central.id, sdk_sessao="fio-central")
    depois, _ = m.trocar(central.id, "codex", outra.id)
    assert depois.passagem == s.passagem  # trocar de conta não perde contexto ainda pendente
    assert (outra.onde / "sessions" / nativa.name).read_text() == "{}\n"
    m.trocar(central.id, "claude")
    assert m.abrir_sessao() == central.id
    assert sessoes.ler(central.id).worktree == central.worktree
    assert sessoes.ler(central.id).branch == central.branch
    assert len(m.central.candidatas()) == 1 and len(sessoes.listar()) == 1
    assert len(sessoes.listar(incluir_arquivadas=True)) == 3


def test_arquivo_ignorado_na_central_nao_e_substituido_pela_unificacao(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    central, a, _ = legadas(repo, sessoes, m)
    commit(central.onde, ".gitignore", "local.txt\n")
    (central.onde / "local.txt").write_text("preservar\n")
    commit(a.onde, "local.txt", "versionado em outra cópia\n")
    m.unificar_sessoes()
    estado = esperar(m)
    assert estado["estado"] == "erro" and "ignorado" in estado["aviso"]
    assert (central.onde / "local.txt").read_text() == "preservar\n"
    assert not sessoes.arquivada_em(a.id)


def test_registro_de_migracao_interrompida_pode_ser_retomado(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    central, _, _ = legadas(repo, sessoes, m)
    m.central.resolver(central.id, "claude")
    m.central._gravar(estado="em_andamento", aviso="Unificando sessões.")
    reiniciada = Manutencao(sessoes, m.pasta, repo)
    assert reiniciada.central.situacao()["estado"] == "interrompida"
    reiniciada.unificar_sessoes()
    assert esperar(reiniciada)["estado"] == "concluida"


def test_instalacao_vincula_a_atual_e_bloqueia_terminal_antigo_antes_de_abrir_pagina(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    central, antiga, _ = legadas(repo, sessoes, m)
    reiniciada = Manutencao(sessoes, m.pasta, repo)
    assert reiniciada.central.registro()["sessao"] == central.id
    with pytest.raises(SessaoErro, match="substituída"):
        sessoes.enviar(antiga.id, "novo pedido")


def test_copia_orfa_sem_registros_nao_provoca_outra_criacao(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    _, sessoes, m = ambiente
    id_ = m.abrir_sessao()
    sessoes._dados.remover("sessoes", id_)
    sessoes._dados.remover("autodesenvolvimento", m.central.chave)
    m.estado.sessao = ""
    with pytest.raises(SessaoErro, match="sem registro"):
        m.abrir_sessao("codex")
    assert not sessoes.listar()
    assert len(list(sessoes.pasta.glob("*/copia"))) == 1


def test_sessao_comum_no_projeto_nao_impede_primeira_central(
    ambiente: tuple[Path, Sessoes, Manutencao],
) -> None:
    repo, sessoes, m = ambiente
    comum = sessoes.criar("Revisão", str(repo), isolada=True)
    id_ = m.abrir_sessao()
    assert id_ != comum.id
    assert sessoes.ler(comum.id).origem == "painel"
    assert len(m.central.candidatas()) == 1


def test_resolucao_manual_na_central_nao_reaplica_renomeacao_ao_tentar_novamente(
    ambiente: tuple[Path, Sessoes, Manutencao],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, sessoes, m = ambiente
    central, origem, _ = legadas(repo, sessoes, m)
    m.central.resolver(central.id, central.motor)
    (origem.onde / "comum.txt").rename(origem.onde / "renomeado.txt")
    with monkeypatch.context() as datas:
        datas.setenv("GIT_AUTHOR_DATE", "2025-01-01T00:00:00+00:00")
        datas.setenv("GIT_COMMITTER_DATE", "2025-01-01T00:00:00+00:00")
        foto, arvore = m.central._fotografar(origem, tmp_path / "indice")
    git(repo, "update-ref", f"refs/zervis/arquivo/z_aceita/{origem.id}", foto)
    # Tentativas antigas criavam outro commit para a mesma árvore e mesmo pai. Este vem
    # antes na ordenação: a busca precisa preferir o que realmente foi reconciliado.
    repetida = git(
        repo,
        "commit-tree",
        arvore,
        "-p",
        git(origem.onde, "rev-parse", "HEAD"),
        "-m",
        "Fotografia com outra data ou mensagem",
    )
    assert repetida != foto
    git(repo, "update-ref", f"refs/zervis/arquivo/a_repetida/{origem.id}", repetida)
    commit(central.onde, "correcao.txt", "correção mais recente\n")
    resolvida = git(
        repo,
        "commit-tree",
        git(central.onde, "rev-parse", "HEAD^{tree}"),
        "-p",
        git(central.onde, "rev-parse", "HEAD"),
        "-p",
        foto,
        "-m",
        "Preserva a estrutura atual e registra a resolução",
    )
    git(central.onde, "merge", "--ff-only", resolvida)
    m.unificar_sessoes()
    estado = esperar(m)
    assert estado["estado"] == "concluida", estado
    assert (central.onde / "comum.txt").read_text() == "base\n"
    assert not (central.onde / "renomeado.txt").exists()
    assert git(central.onde, "rev-parse", "HEAD") == resolvida
    assert m.central.registro()["origens"][origem.id]["commit"] == foto
    assert sessoes.arquivada_em(origem.id) == central.id
    assert (origem.onde / "renomeado.txt").read_text() == "base\n"


def test_fotografia_reutilizada_exige_mesma_arvore_e_mesmo_pai(
    ambiente: tuple[Path, Sessoes, Manutencao],
    tmp_path: Path,
) -> None:
    repo, sessoes, m = ambiente
    central, origem, _ = legadas(repo, sessoes, m)
    m.central.resolver(central.id, central.motor)
    (origem.onde / "rascunho.txt").write_text("primeira versão\n")
    foto, _ = m.central._fotografar(origem, tmp_path / "primeiro")
    git(repo, "update-ref", f"refs/zervis/arquivo/salva/{origem.id}", foto)
    assert m.central._fotografar(origem, tmp_path / "repetido")[0] == foto
    (origem.onde / "rascunho.txt").write_text("nova alteração\n")
    assert m.central._fotografar(origem, tmp_path / "alterado")[0] != foto
    commit(origem.onde, "outro.txt", "outro commit\n")
    assert m.central._fotografar(origem, tmp_path / "novo-pai")[0] != foto


def test_instalacao_sem_historico_git_diz_o_que_fazer(tmp_path: Path) -> None:
    """A VPS recebeu o código por `git archive`, sem o .git: o painel dizia só "não foi possível
    unificar pelo Git". Agora diz o que falta e não cria cópia nenhuma."""
    repo = tmp_path / "zervis"
    repo.mkdir()
    (repo / "a.txt").write_text("x")
    sessoes = Sessoes(tmp_path / "sessoes", (tmp_path,))
    central = Central(sessoes, repo, tmp_path / "manutencao")
    with pytest.raises(SessaoErro, match=r"não tem histórico Git.*instalar-servidor"):
        central.resolver("", "codex")
    assert sessoes.listar() == []
