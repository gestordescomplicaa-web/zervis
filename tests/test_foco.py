"""O Foco: frentes com próximo passo, limite de três ativas, falas curtas e captura pela oficina."""

import json
from pathlib import Path

import pytest

from jarvis.foco import ferramentas
from jarvis.foco.frentes import LIMITE, Foco, FocoErro, Frente
from jarvis.nucleo import estados
from jarvis.oficina.oficina import Oficina


def atual(foco: Foco) -> Frente:
    f = foco.atual()
    assert f is not None
    return f


def novo(tmp_path: Path, eventos: list[tuple[str, str]] | None = None) -> Foco:
    def ao_mudar(o_que: str, f: Frente) -> None:
        if eventos is not None:
            eventos.append((o_que, f.titulo))

    return Foco(tmp_path / "frentes.json", ao_mudar)


def test_a_primeira_vira_a_atual_e_a_quarta_espera_pausada(tmp_path: Path) -> None:
    eventos: list[tuple[str, str]] = []
    foco = novo(tmp_path, eventos)
    a = foco.criar("Lançar o Ligatia", "comparar provedores SIP", "Ligatia")
    foco.criar("Site novo")
    foco.criar("Vídeo do Zé")
    quarta = foco.criar("Planilha de custos")
    assert foco.atual() is a and a.atual
    assert quarta.estado == "pausada" and len(foco.com_estado("ativa")) == LIMITE
    assert eventos[-1] == ("fila", "Planilha de custos")
    assert foco.onde_estava() == (
        "Você estava em Lançar o Ligatia — próximo passo: comparar provedores SIP."
    )


def test_pendentes_fala_no_maximo_tres(tmp_path: Path) -> None:
    foco = novo(tmp_path)
    for t in ("A", "B", "C", "D", "E"):
        foco.criar(t)
    fala = foco.falar_pendentes()
    assert fala.startswith("1. A.") and "3." in fala and "4." not in fala
    assert fala.endswith("E mais 2 paradas; peça se quiser ver.")


def test_achar_tolera_a_transcricao_e_atualizar_trava(tmp_path: Path) -> None:
    foco = novo(tmp_path)
    foco.criar("Lançar o Ligatia", projeto="Ligatia")
    f = foco.atualizar("ligacia", bloqueio="esperando o contrato do provedor")
    assert f.estado == "bloqueada" and foco.atual() is None
    assert "travada: esperando o contrato do provedor" in f.resumo()
    with pytest.raises(FocoErro):
        foco.achar("planilha")


def test_focar_respeita_o_limite_e_concluir_passa_a_vez(tmp_path: Path) -> None:
    eventos: list[tuple[str, str]] = []
    foco = novo(tmp_path, eventos)
    for t in ("A", "B", "C", "D"):
        foco.criar(t)
    with pytest.raises(FocoErro, match="pause uma antes"):
        foco.focar("D")
    foco.atualizar("C", estado="pausada")
    assert foco.focar("D").atual
    foco.concluir("D")
    assert ("concluida", "D") in eventos
    assert foco.atual() is not None and atual(foco).titulo in ("A", "B")
    assert foco.achar("D", ("concluida",)).concluida_em


def test_ideia_nao_tira_o_foco_e_repetir_nao_duplica(tmp_path: Path) -> None:
    foco = novo(tmp_path)
    foco.criar("Ligatia", "comparar provedores")
    foco.criar("App de receitas com IA", ideia=True)
    assert atual(foco).titulo == "Ligatia"
    foco.criar("Ligatia", "fechar o provedor")
    assert len(foco.frentes) == 2 and atual(foco).proximo_passo == "fechar o provedor"
    assert atual(Foco(tmp_path / "frentes.json")).titulo == "Ligatia"


def test_o_projeto_avanca_quando_o_agente_termina(tmp_path: Path) -> None:
    foco = novo(tmp_path)
    foco.criar("Loja Virtual", "acompanhar o Claude", "Loja Virtual", origem="orca")
    f = foco.anotar_projeto("loja virtual", "o Claude terminou: testes", "revisar a entrega")
    assert f is not None and f.proximo_passo == "revisar a entrega"
    assert f.notas[-1].endswith("o Claude terminou: testes")
    assert foco.anotar_projeto("Outro", "x") is None


def test_a_oficina_avisa_o_que_mudou(tmp_path: Path) -> None:
    oficina = Oficina(tmp_path / "oficina.json")
    vistos: list[tuple[str, dict[str, str]]] = []
    oficina.ao_mudar = lambda o_que, d: vistos.append((o_que, d))
    oficina.tarefas["d1"] = {"agente": "claude", "projeto": "Loja", "tarefa": "testes"}
    oficina.concluir("d1")
    assert vistos == [("concluido", {"agente": "claude", "projeto": "Loja", "tarefa": "testes"})]

    def quebra(o_que: str, d: dict[str, str]) -> None:
        raise RuntimeError("quem escuta nunca derruba a oficina")

    oficina.ao_mudar = quebra
    oficina.tarefas["d2"] = {"projeto": "Loja"}
    assert oficina.concluir("d2") == {"projeto": "Loja"}


@pytest.mark.parametrize(
    ("fala", "nome"),
    [
        ("No que eu estava?", "foco_onde"),
        ("Zé, onde eu parei?", "foco_onde"),
        ("Qual é o meu foco agora?", "foco_onde"),
        ("O que está pendente?", "foco_pendentes"),
        ("Ei Zé, quais são as minhas frentes?", "foco_pendentes"),
        ("O que falta?", "foco_pendentes"),
        ("Abra o modo foco para eu ver.", "foco_mostrar"),
        ("Aba o modo foco.", "foco_mostrar"),
        ("Mostra o meu foco", "foco_mostrar"),
    ],
)
def test_comandos_locais_do_foco(fala: str, nome: str) -> None:
    assert estados.comando(fala) == nome


def test_a_ferramenta_ver_resume_para_falar(tmp_path: Path) -> None:
    foco = novo(tmp_path)
    foco.criar("Ligatia", "comparar provedores")
    foco.criar("Ideia solta", ideia=True)
    visto = ferramentas.ver(foco)
    assert visto["atual"]["frente"] == "Ligatia" and visto["ideias"] == ["Ideia solta"]
    assert len(ferramentas.LIVRES) == 7


def test_o_quadro_da_tela_e_as_marcacoes_do_v(tmp_path: Path) -> None:
    from jarvis.foco import tela

    foco = novo(tmp_path)
    a = foco.criar("Ligatia", "comparar provedores SIP", "Ligatia")
    b = foco.criar("Site novo", "escolher o tema")
    foco.atualizar("Site novo", bloqueio="esperando as fotos")
    foco.criar("Ideia solta", ideia=True)
    q = foco.quadro()
    assert q["atual"]["id"] == a.id and q["atual"]["proximo_passo"] == "comparar provedores SIP"
    assert [c["id"] for c in q["travadas"]] == [b.id] and len(q["ideias"]) == 1

    arquivo = tmp_path / "foco-acoes.jsonl"
    arquivo.write_text(
        json.dumps({"id": a.id, "acao": "passo"})
        + "\n"
        + '{"id": "x", "acao": "apagar"}\n{"id": "meia'
    )
    acoes, pos = tela.ler_acoes(arquivo, 0)
    assert acoes == [{"id": a.id, "acao": "passo"}]  # a desconhecida e a linha pela metade, fora
    assert tela.aplicar(foco, acoes[0]) == (
        "Boa! Comparar provedores SIP: feito. Qual é o próximo passo de Ligatia?"
    )
    assert atual(foco).proximo_passo == "" and "passo feito" in atual(foco).notas[-1]
    assert tela.ler_acoes(arquivo, pos) == ([], pos)
    with arquivo.open("a") as f:
        f.write('"}\n' + json.dumps({"id": a.id, "acao": "concluir"}) + "\n")
    acoes, pos = tela.ler_acoes(arquivo, pos)
    assert [x["acao"] for x in acoes] == ["concluir"]
    assert tela.aplicar(foco, acoes[0]) == "Ligatia: concluída!"
    assert tela.aplicar(foco, {"id": "nada", "acao": "focar"}).startswith("Não deu:")
    assert tela.aplicar(foco, {"id": b.id, "acao": "focar"}) == (
        "Foco agora: Site novo — próximo passo: escolher o tema."
    )


def test_a_correcao_muda_a_mesma_ideia_e_as_repetidas_se_juntam(tmp_path: Path) -> None:
    """08/10/2026: "academia mês que vem", "meta ganhar dez quilos", "na verdade é perder"
    viraram três ideias, e o Zé disse que não conseguia apagar a errada."""
    foco = novo(tmp_path)
    a = foco.criar("Começar a academia em novembro", ideia=True)
    b = foco.criar("Meta: ganhar 10 quilos", ideia=True)
    c = foco.criar("Correção: perder 10 quilos", ideia=True)
    foco.atualizar("Meta: ganhar 10 quilos", titulo="Meta: perder 10 quilos")
    assert b.titulo == "Meta: perder 10 quilos" and "antes: Meta: ganhar" in b.notas[-1]
    f = foco.juntar(a.id, [b.id, c.id], "Academia em novembro, meta perder 10 quilos")
    assert f is a and f.titulo == "Academia em novembro, meta perder 10 quilos"
    assert (b.estado, c.estado) == ("descartada", "descartada")
    assert [x["id"] for x in foco.quadro()["ideias"]] == [a.id]
    foco.atualizar(a.id, estado="descartada")
    assert foco.quadro()["ideias"] == [] and len(foco.frentes) == 3  # nada é apagado
    with pytest.raises(FocoErro):
        foco.juntar("Nada", ["Outra"])


def test_ao_abrir_o_quadro_o_ze_diz_o_que_esta_nele(tmp_path: Path) -> None:
    foco = novo(tmp_path)
    assert foco.fala_do_quadro().startswith("Seu quadro está vazio.")
    foco.criar("Academia", ideia=True)
    foco.criar("Planilha", ideia=True)
    assert foco.fala_do_quadro() == (
        "Nenhuma frente em andamento. Na tela: 2 ideias; toque em Virar frente na que quiser "
        "começar."
    )
    foco.criar("Ligatia", "comparar provedores")
    assert foco.fala_do_quadro() == (
        "Seu foco na tela: Ligatia, próximo passo: comparar provedores. Marque o V quando fizer."
    )
