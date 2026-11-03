"""A pesquisa profunda (ADR 0059): o SearXNG próprio, o leitor de páginas atrás da trava, o
CNPJ com reserva, a pesquisa que junta e lê, o vigia das fontes e as ferramentas. Sem rede."""

import asyncio
import contextlib
import hashlib
import io
import json
import shutil
import tarfile
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from zervis.cerebro.ferramentas import LIVRES
from zervis.cerebro.ferramentas import profunda as ferramentas_profunda
from zervis.cerebro.pesquisa import PesquisaErro
from zervis.imersivo import capturas
from zervis.pesquisa import buscador as bu
from zervis.pesquisa import cnpj, leitor, profunda, saude
from zervis.pesquisa.buscador import Resultado
from zervis.pesquisa.guardadas import Guardadas

ARTIGO = (
    "<html><head><title>Loja X abre filial</title></head><body><nav>Menu Entrar Carrinho</nav>"
    "<article><h1>Loja X abre filial em Campinas</h1>"
    + "<p>A Loja X anunciou uma nova filial em Campinas, com 200 vagas e foco em móveis.</p>" * 8
    + "</article><footer>Todos os direitos reservados</footer></body></html>"
)


# --- o buscador (SearXNG) ---------------------------------------------------------------------


def _pacote(arquivos: dict[str, bytes]) -> bytes:
    dados = io.BytesIO()
    with tarfile.open(fileobj=dados, mode="w:gz") as tar:
        for nome, conteudo in arquivos.items():
            info = tarfile.TarInfo(nome)
            info.size = len(conteudo)
            tar.addfile(info, io.BytesIO(conteudo))
    return dados.getvalue()


def test_configuracao_so_local_com_json_e_sem_motores_da_rede_tor() -> None:
    texto = bu.configuracao(8123, "segredo")
    assert "bind_address: 127.0.0.1" in texto and "port: 8123" in texto
    assert "secret_key: segredo" in texto and "formats: [html, json]" in texto
    assert "remove: [ahmia, torch]" in texto and "limiter: false" in texto


def test_extrair_tira_a_pasta_de_cima_e_recusa_caminho_para_fora(tmp_path: Path) -> None:
    bu._extrair(
        _pacote({"searxng-abc/searx/webapp.py": b"x", "searxng-abc/req.txt": b"y"}), tmp_path
    )
    assert (tmp_path / "searx/webapp.py").read_bytes() == b"x"
    with pytest.raises(bu.BuscadorErro, match="fora da pasta"):
        bu._extrair(_pacote({"topo/../../fora.txt": b"z"}), tmp_path / "outro")
    assert not (tmp_path / "fora.txt").exists()


def test_preparar_confere_o_pacote_antes_de_instalar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/uv")
    b = bu.Buscador(tmp_path)
    comandos: list[list[str]] = []
    with pytest.raises(bu.BuscadorErro, match="não confere"):
        b.preparar(lambda _: b"outro pacote", lambda c, **_: comandos.append(c))
    assert comandos == []  # nada instalado de um pacote que não confere
    pacote = _pacote({"s/searx/webapp.py": b"", "s/requirements.txt": b"flask\n"})
    monkeypatch.setattr(bu, "SHA256", hashlib.sha256(pacote).hexdigest())
    (tmp_path / "versao-velha").mkdir()

    def executar(comando: list[str], **_: Any) -> SimpleNamespace:
        comandos.append(comando)
        if comando[1] == "venv":
            b.python.parent.mkdir(parents=True)
            b.python.write_text("")
        return SimpleNamespace(returncode=0, stderr="")

    b.preparar(lambda _: pacote, executar)
    assert b.preparado and [c[1] for c in comandos] == ["venv", "pip"]
    assert "--python" in comandos[0] and bu.PYTHON in comandos[0]
    assert not (tmp_path / "versao-velha").exists()  # a versão anterior sai


def test_sem_preparo_a_busca_avisa_e_prepara_em_segundo_plano(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    b = bu.Buscador(tmp_path)
    chamadas: list[int] = []
    monkeypatch.setattr(b, "preparar_em_segundo_plano", lambda: chamadas.append(1))
    with pytest.raises(bu.BuscadorErro, match="sendo preparado"):
        b.buscar("loja x")
    assert chamadas == [1]


def test_buscar_le_o_json_do_searxng_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos: list[str] = []
    corpo = {
        "results": [
            {
                "title": " Loja  X ",
                "url": "https://lojax.com.br/",
                "content": "Móveis",
                "engines": ["brave", "duckduckgo"],
            },
            {"title": "sem endereço", "url": "javascript:alert(1)"},
            {
                "title": "Notícia",
                "url": "https://g1.globo.com/x",
                "engine": "bing",
                "publishedDate": "2026-10-01T10:00:00",
            },
        ]
    }

    def abrir(url: str, timeout: float) -> Any:
        pedidos.append(url)
        return contextlib.nullcontext(io.BytesIO(json.dumps(corpo).encode()))

    b = bu.Buscador(tmp_path, abrir)
    b.filho, b.porta = SimpleNamespace(), 8123  # type: ignore[assignment]
    monkeypatch.setattr(bu.Buscador, "preparado", True)
    monkeypatch.setattr(bu, "porta_ocupada", lambda porta: porta == 8123)
    achados = b.buscar("loja x móveis")
    assert pedidos[0].startswith("http://127.0.0.1:8123/search?q=loja+x+m%C3%B3veis&format=json")
    assert [a.titulo for a in achados] == ["Loja X", "Notícia"]
    assert (
        achados[0].motores == ("brave", "duckduckgo") and achados[1].data == "2026-10-01T10:00:00"
    )


# --- o leitor ---------------------------------------------------------------------------------


def test_extrai_o_texto_principal_sem_menu_nem_rodape() -> None:
    p = leitor.extrair(ARTIGO, "https://lojax.com.br/noticia")
    assert p is not None and p.titulo == "Loja X abre filial em Campinas"
    assert "200 vagas" in p.texto and "Carrinho" not in p.texto and "reservados" not in p.texto


def test_pagina_que_monta_com_javascript_abre_no_chromium() -> None:
    vazia = b"<html><body><div id=app></div><script src=app.js></script></body></html>"
    abertas: list[str] = []

    def renderizar(url: str) -> str:
        abertas.append(url)
        return ARTIGO

    p = leitor.ler(
        "https://app.exemplo/x", baixar=lambda u: (vazia, u + "?final"), renderizar=renderizar
    )
    assert p.por == "chromium" and "200 vagas" in p.texto
    assert abertas == ["https://app.exemplo/x?final"]  # o endereço depois dos redirecionamentos
    sem_js = leitor.ler("https://app.exemplo/x", js=False, baixar=lambda u: (ARTIGO.encode(), u))
    assert sem_js.por == "direto"


def test_pagina_de_bloqueio_nao_vira_fonte_e_segredo_sai_mascarado() -> None:
    bloqueio = (
        "<html><head><title>Just a moment...</title></head>"
        "<body>Checking your browser</body></html>"
    )
    with pytest.raises(leitor.LeitorErro, match="bloqueou"):
        leitor.ler("https://x.exemplo", js=False, baixar=lambda u: (bloqueio.encode(), u))
    cartao = ARTIGO.replace("foco em móveis", "cartão 4111 1111 1111 1111")
    p = leitor.ler("https://x.exemplo", js=False, baixar=lambda u: (cartao.encode(), u))
    assert "4111" not in p.texto and "[cartão oculto]" in p.texto


def test_o_leitor_passa_pela_trava_e_nao_segue_para_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capturas, "conferir_url", lambda url, resolve=None: "interno.exemplo")
    usadas: list[capturas.Trava] = []
    original = capturas.trava

    @contextlib.contextmanager
    def trava_que_ve_a_rede_local() -> Iterator[capturas.Trava]:
        # O nome passou na conferência, mas na hora aponta para a rede local: a trava barra.
        with original(resolve=lambda h, p: ["192.168.0.10"]) as t:
            usadas.append(t)
            yield t

    monkeypatch.setattr(capturas, "trava", trava_que_ve_a_rede_local)
    with pytest.raises(leitor.LeitorErro, match="não abriu"):
        leitor.baixar("https://interno.exemplo/painel")
    assert usadas[0].recusados == ["interno.exemplo"]
    pedido = urllib.request.Request("https://a.exemplo/")
    with pytest.raises(leitor.LeitorErro, match="fora do https"):
        leitor._SoHttps().redirect_request(pedido, io.BytesIO(), 302, "", None, "http://a.exemplo/")  # type: ignore[arg-type]


# --- o CNPJ -----------------------------------------------------------------------------------

MAGALU = {
    "cnpj": "47960950000121",
    "razao_social": "MAGAZINE LUIZA S/A",
    "nome_fantasia": "MAGAZINE LUIZA",
    "descricao_situacao_cadastral": "ATIVA",
    "data_inicio_atividade": "1966-10-24",
    "cnae_fiscal_descricao": "Lojas de departamentos",
    "descricao_tipo_de_logradouro": "RUA",
    "logradouro": "VOLUNTARIOS DA FRANCA",
    "numero": "1465",
    "municipio": "FRANCA",
    "uf": "SP",
    "capital_social": 14202162000,
    "opcao_pelo_simples": False,
    "qsa": [
        {
            "nome_socio": "FULANO DE TAL",
            "qualificacao_socio": "Diretor",
            "cnpj_cpf_do_socio": "***571038**",
            "data_entrada_sociedade": "2019-09-11",
        },
    ],
}


def test_cnpj_numerico_e_alfanumerico_com_os_digitos_conferidos() -> None:
    assert cnpj.normalizar("47.960.950/0001-21") == "47960950000121"
    assert cnpj.normalizar("12.abc.345/01de-35") == "12ABC34501DE35"  # o novo formato
    for errado in ("47.960.950/0001-22", "11111111111111", "1234"):
        with pytest.raises(cnpj.CnpjErro):
            cnpj.normalizar(errado)


def test_cnpj_usa_a_reserva_e_resume_sem_cpf() -> None:
    pedidos: list[str] = []

    def abrir(url: str) -> Any:
        pedidos.append(url)
        if "brasilapi" in url:
            raise urllib.error.URLError("fora do ar")
        return MAGALU

    r = cnpj.consultar("47.960.950/0001-21", abrir)
    assert pedidos == [
        "https://brasilapi.com.br/api/cnpj/v1/47960950000121",
        "https://minhareceita.org/47960950000121",
    ]
    assert r["cnpj"] == "47.960.950/0001-21" and r["situacao"] == "ATIVA"
    assert r["endereco"] == "RUA VOLUNTARIOS DA FRANCA, 1465, FRANCA - SP"
    assert r["socios"] == [
        {"nome": "FULANO DE TAL", "qualificacao": "Diretor", "desde": "2019-09-11"}
    ]
    assert "571038" not in json.dumps(r) and "simples" not in r
    assert r["fonte"].startswith("minhareceita.org")


def test_cnpj_que_nao_existe_e_fontes_fora_do_ar() -> None:
    with pytest.raises(cnpj.CnpjErro, match="não está no cadastro"):
        cnpj.consultar("47960950000121", lambda url: None)

    def fora(url: str) -> Any:
        raise OSError("sem rede")

    with pytest.raises(cnpj.CnpjErro, match="não responderam"):
        cnpj.consultar("47960950000121", fora)


# --- a pesquisa profunda ----------------------------------------------------------------------


def _r(url: str, motores: tuple[str, ...] = ("brave",)) -> Resultado:
    return Resultado(titulo=url.split("/")[2], url=url, trecho="trecho", motores=motores)


class BuscadorFalso:
    def __init__(self, respostas: dict[str, list[Resultado] | Exception]) -> None:
        self.respostas = respostas
        self.consultas: list[str] = []

    def buscar(self, consulta: str) -> list[Resultado]:
        self.consultas.append(consulta)
        r = self.respostas.get(consulta, [])
        if isinstance(r, Exception):
            raise r
        return r


def test_chave_junta_o_mesmo_endereco_escrito_diferente() -> None:
    assert profunda.chave("https://www.loja.com/a/?utm_source=x&id=2#topo") == "loja.com/a?id=2"
    assert profunda.chave("https://loja.com/a?id=2") == "loja.com/a?id=2"


def test_juntar_sobe_quem_aparece_em_mais_consultas() -> None:
    a, b, c = _r("https://a.com/1"), _r("https://b.com/1"), _r("https://c.com/1")
    juntos = profunda.juntar([[a, b], [c, _r("https://www.b.com/1/")]])
    assert [r.url for r in juntos] == ["https://b.com/1", "https://a.com/1", "https://c.com/1"]


def test_trechos_com_as_palavras_da_pergunta_na_ordem_da_pagina() -> None:
    texto = "\n".join(
        [
            "Receita de bolo de cenoura." * 30,
            "A Loja X tem 200 vagas em Campinas.",
            "Clima ameno.",
            "Vagas na Loja X: inscrição até sexta.",
        ]
    )
    achados = profunda.trechos(texto, profunda.termos("vagas da Loja X em Campinas"), 2)
    assert achados[0].startswith("A Loja X tem 200 vagas") and "inscrição" in achados[0]
    assert len(achados) == 1  # as linhas curtas viram um bloco só; o do bolo fica de fora
    assert profunda.termos("Qual é o CNPJ da Magazine Luiza em 2026?") == {
        "cnpj",
        "magazine",
        "luiza",
        "2026",
    }


def test_pesquisa_le_as_melhores_no_maximo_duas_por_site_e_grava_o_relatorio(
    tmp_path: Path,
) -> None:
    buscador = BuscadorFalso(
        {
            "loja x vagas": [
                _r("https://g1.com/1"),
                _r("https://g1.com/2"),
                _r("https://g1.com/3"),
                _r("https://quebrado.com/x"),
            ],
            "loja x campinas": [_r("https://jornal.com/a"), _r("https://g1.com/1", ("bing",))],
            "Quantas vagas a Loja X abriu?": bu.BuscadorErro("um motor caiu"),
        }
    )
    lidas: list[str] = []
    guardadas: list[str] = []

    def ler(url: str) -> leitor.Pagina:
        lidas.append(url)
        if "quebrado" in url:
            raise leitor.LeitorErro("a página respondeu 500")
        return leitor.Pagina(
            url=url,
            titulo=f"Título {url[-1]}",
            texto="A Loja X abriu 200 vagas.",
            site=profunda.site(url),
        )

    def guardar(texto: str) -> str:
        guardadas.append(texto)
        return f"{len(guardadas):010x}"

    r = profunda.pesquisar(
        "Quantas vagas a Loja X abriu?",
        ["loja x vagas", "loja x campinas", "LOJA X VAGAS"],
        buscador,
        paginas=3,
        ler=ler,
        guardadas=Guardadas(tmp_path),
        guardar=guardar,
    )
    assert buscador.consultas.count("loja x vagas") == 1  # a repetida não roda de novo
    assert "https://g1.com/3" not in lidas  # no máximo duas por site
    assert [f["url"] for f in r["fontes"]] == [
        "https://g1.com/1",
        "https://jornal.com/a",
        "https://g1.com/2",
    ]
    assert (
        r["fontes"][0]["trechos"] == ["A Loja X abriu 200 vagas."]
        and r["fontes"][0]["leitura"] == "0000000001"
    )
    assert {o["url"] for o in r["outros_resultados"]} == {
        "https://g1.com/3",
        "https://quebrado.com/x",
    }
    guardada = Guardadas(tmp_path).ler(r["guardada"])
    assert (
        guardada["pergunta"] == "Quantas vagas a Loja X abriu?" and guardada["tipo"] == "profunda"
    )
    assert guardada["fontes"][1]["url"] == "https://jornal.com/a"


def test_sem_buscador_a_pesquisa_falha_e_a_ferramenta_usa_a_reserva(tmp_path: Path) -> None:
    caido = BuscadorFalso(
        {"x": bu.BuscadorErro("o SearXNG não respondeu"), "pergunta x": bu.BuscadorErro("idem")}
    )
    with pytest.raises(profunda.ProfundaErro, match="não respondeu"):
        profunda.pesquisar("pergunta x", ["x"], caido, guardadas=Guardadas(tmp_path))
    pedidos: list[str] = []

    async def pesquisar(pedido: str) -> str:
        pedidos.append(pedido)
        return "Resumo. Fontes: https://a.com"

    f: dict[str, Any] = {
        t.name: t.handler for t in ferramentas_profunda.ferramentas(caido, None, pesquisar)
    }
    r = json.loads(
        asyncio.run(f["pesquisa_profunda"]({"pergunta": "pergunta x", "consultas": ["x"]}))[
            "content"
        ][0]["text"]
    )
    assert (
        r["reserva"].startswith("Resumo")
        and "não respondeu" in r["aviso"]
        and pedidos == ["pergunta x"]
    )

    async def tambem_caiu(pedido: str) -> str:
        raise PesquisaErro("sem conta")

    f = {t.name: t.handler for t in ferramentas_profunda.ferramentas(caido, None, tambem_caiu)}
    erro = asyncio.run(f["pesquisa_profunda"]({"pergunta": "pergunta x", "consultas": ["x"]}))
    assert erro["is_error"] and "reserva também falhou" in erro["content"][0]["text"]


def test_habilidade_nativa_e_livre() -> None:
    for nome in ("pesquisa_profunda", "pagina_ler", "empresa_cnpj", "fontes_saude"):
        assert f"mcp__jarvis__{nome}" in LIVRES
    vigia = saude.Vigia(dict)
    nomes = [t.name for t in ferramentas_profunda.ferramentas(BuscadorFalso({}), vigia)]
    assert nomes == [
        "pesquisa_profunda", "pagina_ler", "empresa_cnpj", "pesquisas_guardadas",
        "pesquisa_guardada", "fontes_saude",
    ]  # fmt: skip
    assert ferramentas_profunda.ferramentas(None) == []


# --- o vigia das fontes -----------------------------------------------------------------------


def test_vigia_fala_so_o_que_quebrou_ou_voltou(tmp_path: Path) -> None:
    relogio = SimpleNamespace(t=1_000_000.0)
    estado = {"cnpj": True}

    def o_cnpj() -> str:
        if not estado["cnpj"]:
            raise RuntimeError("o formato da resposta mudou")
        return "responde"

    vigia = saude.Vigia(
        lambda: {"o buscador": lambda: "10 resultados", "a BrasilAPI": o_cnpj},
        tmp_path / "fontes.json",
        lambda: relogio.t,
    )
    assert vigia.vencido()
    assert vigia.checar_e_contar() is None  # tudo funcionando: nada a dizer
    assert not vigia.vencido()
    relogio.t += saude.SEMANA_S + 1
    assert vigia.vencido()
    estado["cnpj"] = False
    assert (
        vigia.checar_e_contar() == "Parou de funcionar: a BrasilAPI: o formato da resposta mudou."
    )
    assert vigia.checar_e_contar() is None  # a mesma quebra não se repete toda semana
    assert "Com problema: a BrasilAPI" in saude.fala(vigia.ultimo)
    estado["cnpj"] = True
    assert vigia.checar_e_contar() == "Voltou a funcionar: a BrasilAPI."
    assert saude.fala(vigia.ultimo).startswith("Tudo funcionando: o buscador, a BrasilAPI")
    assert saude.fala({}) == "Ainda não chequei as fontes."


def test_vigia_conta_quem_nao_responde_a_tempo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    monkeypatch.setattr(saude, "TEMPO_S", 0.2)
    solta = threading.Event()
    vigia = saude.Vigia(lambda: {"o leitor": lambda: str(solta.wait(5))}, tmp_path / "f.json")
    try:
        r = vigia.checar()
    finally:
        solta.set()
    assert r["fontes"]["o leitor"] == {"ok": False, "detalhe": "não respondeu a tempo"}
    assert not vigia.rodando


def test_whatsapp_e_instagram_so_entram_em_uso(monkeypatch: pytest.MonkeyPatch) -> None:
    from zervis.atendimento import whatsapp

    b = SimpleNamespace(preparado=True, falha="")
    monkeypatch.setattr(whatsapp, "escolhido", lambda: False)
    base = saude.verificacoes(b)
    assert "o WhatsApp" not in base and "o Instagram" not in base
    assert {
        "o buscador",
        "o leitor de páginas",
        "o Chromium",
        "BrasilAPI",
        "minhareceita.org",
        "a Wikimedia",
    } <= set(base)
    monkeypatch.setattr(whatsapp, "escolhido", lambda: True)
    central = SimpleNamespace(para_tela=lambda: {"estado": "pareando"})
    insta = SimpleNamespace(conectado=True, perfil=lambda: {"username": "gabriel"})
    todas = saude.verificacoes(b, lambda: central, lambda: insta)
    with pytest.raises(RuntimeError, match="está pareando"):
        todas["o WhatsApp"]()
    assert todas["o Instagram"]() == "@gabriel"
