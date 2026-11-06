"""Estado só em SQLite (plano de maturidade, Frente 1): avisos, pendências, leads, a lista de
prioridade e as ligações saem do JSON regravado inteiro, sem perder o que já estava guardado."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from zervis.avisos.fila import Fila
from zervis.avisos.ligacoes import Ligacoes
from zervis.avisos.pendentes import Pendentes
from zervis.avisos.prioridade import Prioridade
from zervis.habilidades.revisao import Pendencias, Proposta


def test_o_json_de_antes_entra_uma_vez_e_fica_guardado_ao_lado(tmp_path: Path) -> None:
    antigo = tmp_path / "avisos.json"
    antigo.write_text(json.dumps([{"texto": "A sessão Loja terminou.", "id": "a1", "sessao": "s"}]))
    fila = Fila(antigo)
    assert [a.texto for a in fila.validos()] == ["A sessão Loja terminou."]
    assert not antigo.exists() and (tmp_path / ".antes-do-sqlite" / "avisos.json").is_file()
    assert fila.arquivo == tmp_path / "avisos.db"
    fila.guardar("Lembrete: reunião.")
    assert len(Fila(antigo).validos()) == 2  # reaberta: nada importado de novo, nada perdido


def test_json_cortado_nao_impede_o_ze_de_subir(tmp_path: Path) -> None:
    antigo = tmp_path / "pendencias.json"
    antigo.write_text('[{"id": "p1", "tipo": "memoria"')  # cortado no meio de uma gravação
    assert Pendencias(antigo).listar() == []
    assert (tmp_path / ".antes-do-sqlite" / "pendencias.json").read_text().startswith("[{")


def test_os_cinco_registros_estao_em_sqlite_e_privados(tmp_path: Path) -> None:
    fila = Fila(tmp_path / "avisos.json")
    fila.guardar("Oi.")
    leads = Pendentes(tmp_path / "pendentes.json")
    leads.novo("Ana", "quanto custa?", "1@s.whatsapp.net", "5581999990000")
    vigiados = Prioridade(tmp_path / "prioridade.json")
    vigiados.monitorar("Ana", telefone="81 98765-0000")
    ligacoes = Ligacoes(tmp_path / "ligacoes.json")
    ligacoes.registrar({"telefone": "5581999990000", "nome": "Ana", "quando": 1.0})
    pendencias = Pendencias(tmp_path / "pendencias.json")
    pendencias.adicionar([Proposta("memoria", {"acao": "add"}, "Lembrar do café.")])
    for registro in (fila, leads, vigiados, ligacoes, pendencias):
        assert registro.arquivo.suffix == ".db"
        assert registro.arquivo.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.glob("*.json")) == []
    assert len(Pendencias(tmp_path / "pendencias.json").listar()) == 1
    assert [x.nome for x in Ligacoes(tmp_path / "ligacoes.json").recentes()] == ["Ana"]


ESCREVER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from zervis.avisos.fila import Fila
    fila = Fila(Path(sys.argv[1]))
    for i in range(40):
        fila.guardar(f"{sys.argv[2]} {i}", sessao=f"{sys.argv[2]}{i}")
    """
)


def test_dois_processos_escrevendo_juntos_nao_perdem_avisos(tmp_path: Path) -> None:
    """Com o JSON, quem gravava por último apagava o que o outro tinha acabado de gravar."""
    arquivo = tmp_path / "avisos.json"
    Fila(arquivo)  # cria o banco antes da disputa
    processos = [
        subprocess.Popen([sys.executable, "-c", ESCREVER, str(arquivo), nome])  # noqa: S603
        for nome in ("painel", "nucleo")
    ]
    assert [p.wait(30) for p in processos] == [0, 0]
    assert len(Fila(arquivo).validos()) == 80
