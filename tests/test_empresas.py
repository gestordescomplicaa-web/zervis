"""As empresas que quem usa gere e o grupo de WhatsApp de cada uma (ADR 0105): só o cadastro,
nada é enviado nem lido nos grupos."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis import empresas as emp
from zervis.atendimento import cliente
from zervis.atendimento import whatsapp as w
from zervis.portal.acoes.empresas import AcoesEmpresas
from zervis.portal.servidor import PedidoInvalido

PADARIA = "120363000000000001@g.us"
ACADEMIA = "120363000000000002@g.us"


def _cadastro(tmp_path: Path) -> emp.Empresas:
    return emp.Empresas(tmp_path / "config" / "empresas.json", tmp_path / "dados")


def test_identificador_sem_acento() -> None:
    assert emp.identificador("Padaria São João") == "padaria-sao-joao"
    assert emp.identificador("  ### ") == "empresa"


def test_criar_editar_e_remover(tmp_path: Path) -> None:
    cadastro = _cadastro(tmp_path)
    assert cadastro.listar() == []
    padaria = cadastro.salvar(
        "Padaria  São João", PADARIA, "Padaria — equipe", "~/projetos/p", True
    )
    assert padaria.id == "padaria-sao-joao" and padaria.nome == "Padaria São João"
    assert cadastro.vitrine(padaria.id).is_dir()  # a vitrine nasce com a empresa
    assert cadastro.do_grupo(PADARIA) == padaria

    editada = cadastro.salvar("Padaria São João", "", ligada=False, ident=padaria.id)
    assert editada.grupo == "" and editada.grupo_nome == "" and editada.criada == padaria.criada
    assert cadastro.do_grupo(PADARIA) is None
    assert (tmp_path / "config" / "empresas.json").stat().st_mode & 0o777 == 0o600

    cadastro.salvar("Academia", ACADEMIA)
    assert [e.nome for e in cadastro.listar()] == ["Academia", "Padaria São João"]
    assert cadastro.remover(padaria.id).nome == "Padaria São João"
    assert [e.id for e in cadastro.listar()] == ["academia"]
    assert cadastro.vitrine(padaria.id).is_dir()  # o publicado não se perde
    with pytest.raises(emp.EmpresaErro, match="não encontrada"):
        cadastro.remover(padaria.id)


def test_regras_do_cadastro(tmp_path: Path) -> None:
    cadastro = _cadastro(tmp_path)
    cadastro.salvar("Padaria", PADARIA)
    with pytest.raises(emp.EmpresaErro, match="nome"):
        cadastro.salvar("   ")
    with pytest.raises(emp.EmpresaErro, match="longo"):
        cadastro.salvar("x" * 61)
    with pytest.raises(emp.EmpresaErro, match="Grupo inválido"):
        cadastro.salvar("Academia", "5511999990000@s.whatsapp.net")  # uma pessoa, não um grupo
    with pytest.raises(emp.EmpresaErro, match="antes de ligar"):
        cadastro.salvar("Academia", ligada=True)
    with pytest.raises(emp.EmpresaErro, match="já está ligado a Padaria"):
        cadastro.salvar("Academia", PADARIA)  # um grupo nunca em duas empresas
    with pytest.raises(emp.EmpresaErro, match="Já existe"):
        cadastro.salvar("padaria")
    with pytest.raises(emp.EmpresaErro, match="não encontrada"):
        cadastro.salvar("Academia", ident="outra")


def test_cadastro_ilegivel_nao_derruba(tmp_path: Path) -> None:
    cadastro = _cadastro(tmp_path)
    cadastro.arquivo.parent.mkdir(parents=True)
    cadastro.arquivo.write_text("{quebrado")
    assert cadastro.listar() == []
    cadastro.arquivo.write_text(
        json.dumps({"empresas": [{"id": "a"}, "x", {"id": "b", "nome": "B"}]})
    )
    assert [e.nome for e in cadastro.listar()] == ["B"]


# --- o WhatsApp -----------------------------------------------------------------------------


def test_wacalls_lista_so_os_grupos(tmp_path: Path) -> None:
    wa = w.WhatsApp(lambda r: None, lambda: True, tmp_path, tmp_path)
    pedidos: list[str] = []

    def api(metodo: str, caminho: str, corpo: Any = None, espera: float = 0) -> Any:
        pedidos.append(caminho)
        return {
            "groups": [
                {"chat": PADARIA, "name": " Padaria ", "participants": 5},
                {"chat": "5511999990000@s.whatsapp.net", "name": "pessoa"},
                "lixo",
            ]
        }

    wa._api = api  # type: ignore[method-assign]
    wa.sessoes = lambda: [{"id": "s", "paired": True, "state": "open"}]  # type: ignore[method-assign]
    assert wa.grupos() == [{"chat": PADARIA, "nome": "Padaria", "participantes": 5}]
    assert pedidos == ["/api/sessions/s/groups"]
    wa.sessoes = lambda: []  # type: ignore[method-assign]
    with pytest.raises(w.WhatsAppErro, match="não conectado"):
        wa.grupos()


# --- o painel -------------------------------------------------------------------------------


class CentralFalsa:
    def __init__(self, falha: str = "") -> None:
        self.falha = falha

    def grupos(self) -> list[dict[str, Any]]:
        if self.falha:
            raise cliente.CentralErro(self.falha)
        return [
            {"chat": PADARIA, "nome": "Padaria", "participantes": 5},
            {"chat": ACADEMIA, "nome": "Academia", "participantes": 9},
        ]


def _pagina(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, central: Any) -> AcoesEmpresas:
    monkeypatch.setattr(emp, "PADRAO", _cadastro(tmp_path))
    painel = SimpleNamespace(pastas=lambda: ["~/projetos/padaria"])
    return AcoesEmpresas(painel, SimpleNamespace(central=central))  # type: ignore[arg-type]


def test_painel_salva_lista_e_marca_o_grupo_ja_ligado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pagina = _pagina(tmp_path, monkeypatch, CentralFalsa())
    r = pagina.salvar_empresa(
        {"nome": "Padaria", "grupo": PADARIA, "grupo_nome": "Padaria", "ligada": True}
    )
    assert r["aviso"] == "Salvo." and r["pastas"] == ["~/projetos/padaria"]
    [padaria] = r["empresas"]
    assert (
        padaria["ligada"] and padaria["publicados"] == 0 and padaria["vitrine"].endswith("vitrine")
    )
    grupos = pagina.grupos_whatsapp({})["grupos"]
    assert [(g["nome"], g["empresa"]) for g in grupos] == [("Padaria", "Padaria"), ("Academia", "")]
    with pytest.raises(PedidoInvalido, match="já está ligado"):
        pagina.salvar_empresa({"nome": "Outra", "grupo": PADARIA})
    assert pagina.remover_empresa({"id": "padaria"})["empresas"] == []


def test_painel_sem_whatsapp_mostra_o_motivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pagina = _pagina(tmp_path, monkeypatch, CentralFalsa("WhatsApp não conectado."))
    with pytest.raises(PedidoInvalido, match="não conectado"):
        pagina.grupos_whatsapp({})
