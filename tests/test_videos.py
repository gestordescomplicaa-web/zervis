"""Os vídeos de Marketing (ADR 0106): estilos, roteiro, voz, trilha, a página no Chromium e o
caminho inteiro com o modelo, a voz, a captura e o FFmpeg trocados por falsos."""

import json
import math
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from zervis.marca import Marca
from zervis.video import captura, estilos, narracao, roteiro, trilha, videos
from zervis.video.fotos import Fotos

EMBUTIDOS = estilos.EMBUTIDOS

ROTEIRO: dict[str, Any] = {
    "titulo": "Sua recepção perde pacientes no WhatsApp",
    "legenda": "Legenda do Instagram.",
    "cenas": [
        {"tipo": "gancho", "fala": "Sua recepção perde pacientes no WhatsApp.",
         "destaque": "perde pacientes", "composicao": "esquerda", "camera": "voa"},
        {"tipo": "passos", "fala": "O paciente chama, o agente agenda.", "titulo": "Como funciona",
         "passos": [{"texto": "Paciente chama", "quando": "chama,"}, "Agente agenda",
                    {"texto": "Recepção confirma", "quando": "inexistente"}]},
        {"tipo": "antes_depois", "fala": "Antes no dia seguinte, agora em segundos.",
         "antes": "Resposta no dia seguinte", "depois": "Resposta em segundos", "quando": "agora",
         "composicao": "dividido", "transicao": "mascara"},
        {"tipo": "conversa", "fala": "Assim, a qualquer hora.", "mensagens": [
            {"de": "cliente", "texto": "Tem horário amanhã?"},
            {"de": "empresa", "texto": "Tenho às 9h e às 10h30."}]},
        {"tipo": "lista", "fala": "Agenda cheia e menos faltas.", "titulo": "Você ganha",
         "itens": ["Agenda cheia", "Menos faltas"]},
        {"tipo": "fecho", "fala": "Fala comigo.", "chamada": "Fale comigo no WhatsApp"},
    ],
}  # fmt: skip


def _estilo() -> estilos.Estilo:
    return estilos.achar(estilos.PADRAO, EMBUTIDOS, Path("/nao-existe"))


# --- estilos ----------------------------------------------------------------------------------


def test_estilo_embutido_e_o_de_quem_usa_no_lugar(tmp_path: Path) -> None:
    zervis, editorial = estilos.listar(EMBUTIDOS, tmp_path)
    assert editorial.id == "editorial" and not editorial.proprio
    assert zervis.id == "zervis" and zervis.css is not None and not zervis.proprio
    assert "Inter+Tight" in zervis.fontes_url() and "Poppins" in zervis.fontes_url("Poppins")

    meu = tmp_path / "zervis"
    meu.mkdir()
    (meu / "estilo.json").write_text(
        json.dumps({"nome": "Meu", "trilha": {"bpm": 999, "energia": "alta"}, "onda": False,
                    "cenas": {"citacao": "{\"tipo\": \"citacao\", \"texto\": \"...\"}", "X!": "y"}})
    )  # fmt: skip
    (meu / "cenas.js").write_text("Ze.cena('citacao', {montar() {}, render() {}});")
    (tmp_path / "quebrado").mkdir()
    (tmp_path / "quebrado" / "estilo.json").write_text("{")
    (tmp_path / "Maiusculo").mkdir()
    (tmp_path / "Maiusculo" / "estilo.json").write_text("{}")
    proprio, _ = estilos.listar(EMBUTIDOS, tmp_path)  # o de quem usa vale no lugar do embutido
    assert proprio.nome == "Meu" and proprio.proprio and proprio.js is not None
    assert proprio.bpm == 160 and proprio.energia == "alta" and not proprio.onda
    assert list(proprio.cenas_extras) == ["citacao"]
    assert estilos.achar("nao-existe", EMBUTIDOS, tmp_path).id == "zervis"


# --- roteiro ----------------------------------------------------------------------------------


def test_plano_de_direcao_conferido_e_cortado() -> None:
    bruto = json.loads(json.dumps(ROTEIRO))
    bruto["cenas"][1]["titulo"] = "x" * 200
    bruto["cenas"][1]["passos"].append("<b>quarto</b>")
    bruto["objetivo"] = "Fazer o dono de clínica pedir uma conversa"
    resposta = "Aqui está:\n```json\n" + json.dumps(bruto) + "\n```"
    r = roteiro.interpretar(resposta, _estilo())
    assert [c["tipo"] for c in r.cenas] == [c["tipo"] for c in ROTEIRO["cenas"]]
    gancho, passos, antes_depois = r.cenas[:3]
    assert gancho["composicao"] == "esquerda" and gancho["camera"] == "empurra"  # "voa" não existe
    assert gancho["transicao"] == "zoom" and "texto" not in gancho  # a fala é a tipografia
    assert len(passos["titulo"]) == 32 and passos["titulo"].endswith("…")
    assert passos["passos"][-1] == {"texto": "<b>quarto</b>", "quando": ""}  # texto puro
    # o "quando" só vale com uma palavra da fala (sem pontuação nem maiúscula)
    assert [p["quando"] for p in passos["passos"][:3]] == ["chama", "", ""]
    assert antes_depois["quando"] == "agora" and antes_depois["composicao"] == "dividido"
    assert r.falas[0] == "Sua recepção perde pacientes no WhatsApp."
    assert r.titulo == ROTEIRO["titulo"] and r.objetivo.startswith("Fazer")


def test_duracao_muda_o_tamanho_do_plano() -> None:
    assert roteiro.limites(15) == (4, 6, 26, 44) and roteiro.limites(60)[1] == 16
    sete = json.loads(json.dumps(ROTEIRO))
    sete["cenas"].insert(1, dict(sete["cenas"][1]))
    with pytest.raises(roteiro.RoteiroErro, match="4 a 6 cenas"):
        roteiro.interpretar(json.dumps(sete), _estilo(), 15)
    prompt = roteiro.montar_prompt("Marca", "Tema: x", "", _estilo(), 45)
    assert "cerca de 45 segundos" in prompt and "78 a 130 palavras" in prompt


def test_alinhamento_casa_as_palavras_e_preenche_as_que_faltam() -> None:
    ouvidas = [("Em", 0.0, 0.2), ("treze", 0.2, 0.6), ("de", 0.6, 0.7), ("novembro", 0.7, 1.2),
               ("tudo", 1.3, 1.5), ("parou.", 1.5, 2.0)]  # fmt: skip
    alinhadas = narracao.alinhar("Em 13 de novembro, tudo parou.", ouvidas, 2.0)
    assert [p for p, _, _ in alinhadas] == ["Em", "13", "de", "novembro,", "tudo", "parou."]
    assert alinhadas[0][1:] == (0.0, 0.2) and alinhadas[3][1:] == (0.7, 1.2)
    assert alinhadas[1][1:] == (0.2, 0.6)  # "13" não casa com "treze": entre as vizinhas
    sem = narracao.alinhar("duas palavras", [], 1.0)
    assert sem[0][1] == 0 and sem[-1][2] == pytest.approx(1.0)


def test_gatilhos_viram_segundos_desde_o_comeco_da_cena() -> None:
    passos = [{"texto": "a", "quando": "agenda"}, {"texto": "b", "quando": ""}]
    cena = {"inicio": 10.0, "passos": passos, "quando": "agora"}
    palavras = [
        {"p": "O", "i": 10.2, "f": 10.3},
        {"p": "agente", "i": 10.3, "f": 10.7},
        {"p": "agenda.", "i": 10.8, "f": 11.3},
        {"p": "Agora", "i": 11.5, "f": 11.9},
    ]
    assert roteiro.tempos_dos_gatilhos(cena, palavras) == {
        "tempos_passos": [0.8, None], "tempo": 1.5,
    }  # fmt: skip


@pytest.mark.parametrize(
    ("mudar", "erro"),
    [
        (lambda r: r["cenas"].reverse(), "abrir"),
        (lambda r: r["cenas"][1].update(tipo="slide"), "desconhecido"),
        (lambda r: r["cenas"][1].update(passos=["só um"]), "pelo menos 2"),
        (lambda r: r["cenas"].insert(1, {"tipo": "numero", "fala": "x", "valor": "muito",
                                         "rotulo": "a", "fonte": "b"}), "não tem número"),
        (lambda r: r["cenas"].insert(1, {"tipo": "numero", "fala": "x", "valor": "9%",
                                         "rotulo": "a"}), "sem fonte"),
        (lambda r: r["cenas"][2].update(fala="ab " * 40), "longa"),
        (lambda r: r["cenas"][2].update(fala=""), "sem fala"),
        (lambda r: r.update(cenas=r["cenas"][:2]), "6 a 10"),
        (lambda r: r["cenas"][2].update(depois=""), "depois"),
    ],
)  # fmt: skip
def test_roteiro_fora_do_formato_e_recusado(mudar: Any, erro: str) -> None:
    bruto = json.loads(json.dumps(ROTEIRO))
    mudar(bruto)
    with pytest.raises(roteiro.RoteiroErro, match=erro):
        roteiro.interpretar(json.dumps(bruto), _estilo())
    with pytest.raises(roteiro.RoteiroErro, match="não devolveu"):
        roteiro.interpretar("sem json", _estilo())


def test_cena_de_um_estilo_entra_so_com_texto(tmp_path: Path) -> None:
    pasta = tmp_path / "meu"
    pasta.mkdir()
    (pasta / "estilo.json").write_text(json.dumps({"cenas": {"citacao": "formato"}}))
    estilo = estilos.achar("meu", EMBUTIDOS, tmp_path)
    bruto = json.loads(json.dumps(ROTEIRO))
    bruto["cenas"].insert(1, {"tipo": "citacao", "fala": "Uma frase.", "texto": "y" * 300,
                              "autor": {"nome": "objeto"}, "Ruim": "x"})  # fmt: skip
    r = roteiro.interpretar(json.dumps(bruto), estilo)
    assert r.cenas[1] == {
        "tipo": "citacao", "fala": "Uma frase.", "camera": "empurra", "transicao": "zoom",
        "fundo": "escuro",
        "texto": "y" * 199 + "…",
    }  # fmt: skip
    assert "citacao" in roteiro.montar_prompt("Marca", "Tema: x", "", estilo)


# --- voz e trilha -----------------------------------------------------------------------------


def _fala(taxa: int = 24000) -> narracao.Sintetizar:
    """Uma "fala" de 1 s de tom, com 0,5 s de silêncio em cada ponta."""

    def sintetizar(texto: str) -> tuple[int, bytes]:
        t = np.arange(taxa) / taxa
        tom = 0.5 * np.sin(2 * np.pi * 220 * t)
        x = np.concatenate([np.zeros(taxa // 2), tom, np.zeros(taxa // 2)])
        return taxa, (x * 32767).astype("<i2").tobytes()

    return sintetizar


def test_falas_sem_silencio_cada_uma_numa_batida() -> None:
    ouvidos: list[bytes] = []

    def ouvir(wav: bytes) -> list[tuple[str, float, float]]:
        ouvidos.append(wav)
        return [("um", 0.1, 0.5)]

    n = narracao.narrar(["um", "dois", "três"], _fala(), minimos=[0, 3.0, 0], ouvir=ouvir)
    assert len(ouvidos) == 3 and ouvidos[0][:4] == b"RIFF"
    assert n.falas[0]["palavras"] == [{"p": "um", "i": 0.6, "f": 1.0}]  # o tempo real, no vídeo
    inicios = [f["inicio"] for f in n.falas]
    assert inicios[0] == narracao.INICIO_S
    assert all(math.isclose(i / 0.5, round(i / 0.5)) for i in inicios)  # 120 BPM
    assert all(1.0 <= f["dur"] <= 1.1 for f in n.falas)  # o silêncio das pontas saiu
    assert inicios[2] - inicios[1] >= 3.0  # o mínimo da cena 2 segura a fala 3
    assert n.cenas[0][0] == 0 and n.cenas[-1][1] == n.duracao
    assert len(n.volume) == round(n.duracao * narracao.FPS) and max(n.volume) == 1.0

    sem_voz = narracao.narrar(["uma fala com cinco palavras", "fim"], None, ouvir=ouvir)
    assert len(ouvidos) == 3  # sem voz, nada a ouvir
    assert not sem_voz.voz.any() and sem_voz.falas[0]["dur"] == pytest.approx(0.4 + 0.36 * 5)


def test_trilha_normalizada_e_abaixa_sob_a_voz() -> None:
    sem = trilha.compor(4.0, [1.0, 3.0])
    assert len(sem) == 4 * trilha.SR and np.max(np.abs(sem)) == pytest.approx(0.89)
    voz = np.zeros(4 * trilha.SR)
    voz[trilha.SR : 2 * trilha.SR] = 0.3 * np.sin(np.arange(trilha.SR) / 7)
    com = trilha.compor(4.0, [1.0, 3.0], voz, bpm=100, energia="calma")
    assert np.max(np.abs(com)) == pytest.approx(0.89)


# --- a página no Chromium ---------------------------------------------------------------------


def _dados(pasta: Path, video: dict[str, Any] | None = None) -> Path:
    cenas, t = [], 0.0
    estilo = _estilo()
    for c in roteiro.interpretar(json.dumps(ROTEIRO), estilo).cenas:
        cenas.append({**c, "inicio": t, "fim": t + 2.0})
        t += 2.0
    falas = [{"texto": c["fala"], "inicio": c["inicio"] + 0.3, "dur": 1.2} for c in cenas]
    dados = video or {
        "largura": 1080, "altura": 1920, "formato": "vertical", "fps": 30, "duracao": t,
        "cenas": cenas, "falas": falas, "volume": [0.5] * int(t * 30),
        "marca": {"nome": "Clínica Sorriso", "instagram": "clinica", "logo": "", "cores": {}},
        "estilo": {"id": estilo.id, "css": estilo.css.as_uri() if estilo.css else "", "js": "",
                   "onda": True, "fontes": {}, "fontes_url": ""},
    }  # fmt: skip
    arquivo = pasta / "dados.js"
    arquivo.write_text(f"window.VIDEO = {json.dumps(dados, ensure_ascii=False)};")
    return arquivo


@pytest.mark.skipif(captura.navegador() is None, reason="sem Chromium")
def test_cada_cena_desenha_sem_erro_no_chromium(tmp_path: Path) -> None:
    url = captura.url_da_pagina(_dados(tmp_path))
    tempos = [1.0 + 2.0 * i for i in range(len(ROTEIRO["cenas"]))]
    feitos = captura.capturar(url, tmp_path / "q", 1080, 1920, tempos=tempos)
    assert len(feitos) == len(tempos) and all(f.stat().st_size > 10_000 for f in feitos)


@pytest.mark.skipif(captura.navegador() is None, reason="sem Chromium")
def test_erro_na_pagina_derruba_a_captura(tmp_path: Path) -> None:
    url = captura.url_da_pagina(_dados(tmp_path, video={"estilo": {"id": "x"}}))
    with pytest.raises(captura.CapturaErro, match="falhou"):
        captura.capturar(url, tmp_path / "q", 1080, 1920, tempos=[0.5])


# --- o caminho inteiro ------------------------------------------------------------------------


class SiteFalso:
    def __init__(self) -> None:
        self.avisos: list[str] = []
        self.avisar = self.avisos.append

    def marca(self) -> Marca:
        return Marca(nome="Clínica Sorriso", instagram="clinica")

    def logo(self) -> bytes:
        return b"<svg xmlns='http://www.w3.org/2000/svg'/>"

    def manual(self) -> str:
        return "Fale com donos de clínica."

    def artigo(self, slug: str) -> str:
        return "Texto do artigo." if slug == "existe" else ""

    def artigos(self) -> list[dict[str, Any]]:
        return [
            {"slug": "rascunho", "estado": "Rascunho"},
            {"slug": "existe", "estado": "Publicado"},
        ]


def _videos(tmp_path: Path, resposta: str, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    monkeypatch.setattr(videos.Videos, "disponivel", staticmethod(lambda: ""))
    site = SiteFalso()
    pedidos: list[str] = []

    def perguntar(prompt: str, modelo: str) -> str:
        pedidos.append(f"[{modelo}] {prompt}")
        return resposta

    def capturar(url: str, pasta: Path, largura: int, altura: int, **_: Any) -> list[Path]:
        pasta.mkdir(parents=True)
        quadros = [pasta / f"{i:04d}.jpg" for i in range(3)]
        for q in quadros:
            q.write_bytes(b"jpg")
        return quadros

    def montar(quadros: list[Path], trilha_: Path, saida: Path, capa: int) -> Path:
        assert trilha_.is_file() and capa > 0
        saida.write_bytes(b"mp4")
        saida.with_name("capa.jpg").write_bytes(b"jpg")
        return saida

    v = videos.Videos(
        tmp_path,
        site,  # type: ignore[arg-type]
        perguntar,
        lambda: _fala(),
        lambda: None,
        capturar,
        montar,
        fotos=Fotos(da_marca=lambda: [], buscar=lambda b: []),  # sem o painel nem a rede
    )
    v.pedidos = pedidos  # type: ignore[attr-defined]
    return v, site


def test_do_pedido_ao_mp4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    v, site = _videos(tmp_path, json.dumps(ROTEIRO), monkeypatch)
    feito = v.criar(tema="Atendimento fora do horário", esperar=True)
    assert feito.estado == "rascunho" and feito.erro == "" and feito.etapa == ""
    assert feito.titulo == ROTEIRO["titulo"] and feito.duracao > 6
    assert v.pedidos[0].startswith("[claude-opus-5-5]")  # o Opus dirige por padrão
    assert "Clínica Sorriso (@clinica)" in v.pedidos[0] and "Fale com donos" in v.pedidos[0]
    pasta = tmp_path / feito.id
    assert v.arquivo(feito.id).read_bytes() == b"mp4" and v.arquivo(feito.id, "capa").is_file()
    assert not (pasta / "quadros").exists() and not (pasta / "trilha.wav").exists()
    dados = json.loads(
        (pasta / "dados.js").read_text().removeprefix("window.VIDEO = ").rstrip(";\n")
    )
    assert [c["tipo"] for c in dados["cenas"]] == [c["tipo"] for c in ROTEIRO["cenas"]]
    assert dados["marca"]["logo"].startswith("data:image/svg+xml;base64,")
    assert dados["cenas"][0]["inicio"] == 0 and dados["cenas"][-1]["fim"] == dados["duracao"]
    gancho, passos = dados["cenas"][:2]
    assert gancho["legenda"] == "cinetica" and passos["legenda"] == "rodape"
    assert [p["p"] for p in gancho["palavras"]][:2] == ["Sua", "recepção"]
    assert passos["tempos_passos"][1] is None and isinstance(passos["tempos_passos"][0], float)
    assert site.avisos == [f"O vídeo {feito.titulo} está pronto para assistir em Marketing."]
    assert v.para_tela(feito)["pronto"] and v.para_tela(feito)["cenas"] == 6

    refeito = v.refazer(feito.id, "gancho mais curto", esperar=True)
    assert refeito.estado == "rascunho" and "Ajuste pedido: gancho mais curto" in v.pedidos[1]
    v.descartar(feito.id)
    assert v.listar() == []


def test_roteiro_ruim_vira_erro_com_aviso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    v, site = _videos(tmp_path, "não sei", monkeypatch)
    feito = v.criar(tema="x", esperar=True)
    assert feito.estado == "erro" and "roteiro" in feito.erro
    assert site.avisos == [f"Não consegui criar o vídeo: {feito.erro}"]
    with pytest.raises(videos.VideoErro, match="não está pronto"):
        v.arquivo(feito.id)


def test_pedido_invalido_e_video_interrompido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    v, _ = _videos(tmp_path, json.dumps(ROTEIRO), monkeypatch)
    with pytest.raises(videos.VideoErro, match="tema"):
        v.criar()
    with pytest.raises(videos.VideoErro, match="Artigo"):
        v.criar(artigo="nao-existe")
    with pytest.raises(videos.VideoErro, match="Duração"):
        v.criar(tema="x", duracao=20)
    with pytest.raises(videos.VideoErro, match="Modelo"):
        v.criar(tema="x", modelo="gpt")
    with pytest.raises(videos.VideoErro, match="Vídeo"):
        v.ler("../x")
    preso = videos.Video("abcdef12", tema="x")  # criando, de antes de um reinício
    v._gravar(preso)
    assert v.ler("abcdef12").estado == "erro"
    monkeypatch.setattr(videos.Videos, "disponivel", staticmethod(lambda: "Falta o FFmpeg."))
    with pytest.raises(videos.VideoErro, match="indisponíveis"):
        v.criar(tema="x")


def test_deepgram_devolve_cada_palavra_com_o_tempo() -> None:
    import io

    from zervis.voz import deepgram

    pedidos: list[Any] = []

    class Resposta(io.BytesIO):
        def __enter__(self) -> "Resposta":
            return self

        def __exit__(self, *_: object) -> None:
            pass

    def abrir(pedido: Any, timeout: float) -> Resposta:
        pedidos.append(pedido)
        corpo = {"results": {"channels": [{"alternatives": [{"transcript": "oi zé", "words": [
            {"word": "oi", "start": 0.1, "end": 0.3}, {"word": "zé", "start": 0.3, "end": 0.6},
            {"word": "quebrada"}]}]}]}}  # fmt: skip
        return Resposta(json.dumps(corpo).encode())

    assert deepgram.palavras("chave", b"RIFF", abrir=abrir) == [("oi", 0.1, 0.3), ("zé", 0.3, 0.6)]
    assert pedidos[0].get_header("Content-type") == "audio/wav"
    assert deepgram.transcrever("chave", b"x", "audio/ogg", abrir) == "oi zé"


# --- publicar como Reels (ADR 0109) ------------------------------------------------------------


def test_reels_vai_a_api_com_o_video_e_a_legenda() -> None:
    from test_marketing_posts import Meta, _ig  # type: ignore[import-not-found]

    from zervis.redes import instagram_publicar

    meta = Meta(["IN_PROGRESS", "IN_PROGRESS", "FINISHED"])
    esperas: list[float] = []
    url = "https://ze.exemplo.com/publico/s/video.mp4"
    link = instagram_publicar.publicar_reels(_ig(meta), url, "Legenda", dormir=esperas.append)
    assert link == "https://www.instagram.com/p/xyz/"
    criar = next(d for m, c, d in meta.pedidos if d.get("media_type") == ["REELS"])
    assert criar["video_url"] == [url] and criar["caption"] == ["Legenda"]
    assert criar["share_to_feed"] == ["true"] and criar["thumb_offset"] == ["0"]
    assert esperas == [instagram_publicar.INTERVALO_VIDEO_S] * 2  # o vídeo leva mais
    publicar = next(d for m, c, d in meta.pedidos if c.endswith("/media_publish"))
    assert publicar["creation_id"] == ["c1"]


def test_link_publico_entrega_o_mp4_e_responde_head(tmp_path: Path) -> None:
    from zervis.portal import publico

    mp4 = tmp_path / "video.mp4"
    mp4.write_bytes(b"\x00\x00\x00 ftypisom")
    links = publico.Publicos()
    segredo = links.abrir([mp4])
    assert links.arquivo(f"/publico/{segredo}/video.mp4") == (mp4.read_bytes(), "video/mp4")

    class Pedido:
        def __init__(self, path: str) -> None:
            self.path, self.status = path, 0
            self.cabecalhos: dict[str, str] = {}

        def _host_local(self) -> bool:
            return True

        def send_response(self, status: int) -> None:
            self.status = status

        def send_header(self, nome: str, valor: str) -> None:
            self.cabecalhos[nome] = valor

        def end_headers(self) -> None:
            pass

    original, publico.PADRAO = publico.PADRAO, links
    try:
        certo, errado = Pedido(f"/publico/{segredo}/video.mp4"), Pedido("/api/estado")
        publico.responder_head(certo)
        publico.responder_head(errado)
    finally:
        publico.PADRAO = original
    assert certo.status == 200 and certo.cabecalhos["Content-Type"] == "video/mp4"
    assert certo.cabecalhos["Content-Length"] == str(len(mp4.read_bytes()))
    assert errado.status == 404  # o resto do painel não responde HEAD


class LinksFalsos:
    def __init__(self) -> None:
        self.abertos: dict[str, list[Path]] = {}
        self.prazos: list[float] = []

    def abrir(self, arquivos: list[Path], prazo_s: float = 0) -> str:
        self.abertos["seg"] = arquivos
        self.prazos.append(prazo_s)
        return "seg"

    def fechar(self, segredo: str) -> None:
        self.abertos.pop(segredo, None)


def _publicaveis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, publicar: Any, conectado: bool = True
) -> tuple[Any, Any, LinksFalsos]:
    v, site = _videos(tmp_path, json.dumps(ROTEIRO), monkeypatch)
    links = LinksFalsos()
    v.links = links
    v._instagram = SimpleNamespace(conectado=conectado)
    v._endereco = lambda: "https://ze.exemplo.com"
    v._publicar_reels = publicar
    return v, site, links


def test_publicar_um_video_pronto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[tuple[str, str]] = []

    def publicar(ig: Any, url: str, legenda: str) -> str:
        chamadas.append((url, legenda))
        return "https://www.instagram.com/reel/abc/"

    v, site, links = _publicaveis(tmp_path, monkeypatch, publicar)
    feito = v.criar(tema="x", esperar=True)
    publicado = v.publicar(feito.id, esperar=True)
    assert publicado.estado == "publicado" and publicado.permalink.endswith("/reel/abc/")
    assert chamadas == [("https://ze.exemplo.com/publico/seg/video.mp4", ROTEIRO["legenda"])]
    assert links.abertos == {} and links.prazos == [videos.LINK_DO_VIDEO_S]  # fechado depois
    assert site.avisos[-1] == f"O vídeo {feito.titulo} foi publicado no Instagram."
    tela = v.para_tela(publicado)
    assert tela["permalink"] and tela["publicado"]
    with pytest.raises(videos.VideoErro, match="pronto"):
        v.publicar(feito.id)  # publicado não publica de novo


def test_publicar_exige_instagram_endereco_e_duracao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zervis.redes.instagram import InstagramErro

    def recusa(ig: Any, url: str, legenda: str) -> str:
        raise InstagramErro("O Instagram não conseguiu buscar o vídeo.")

    v, _, links = _publicaveis(tmp_path, monkeypatch, recusa, conectado=False)
    feito = v.criar(tema="x", esperar=True)
    with pytest.raises(videos.VideoErro, match="Conecte o Instagram"):
        v.publicar(feito.id)
    v._instagram = SimpleNamespace(conectado=True)
    v._endereco = lambda: ""
    with pytest.raises(videos.VideoErro, match="endereço fixo"):
        v.publicar(feito.id)
    v._endereco = lambda: "https://ze.exemplo.com"
    voltou = v.publicar(feito.id, esperar=True)  # a Meta recusou: volta a rascunho, com o motivo
    assert voltou.estado == "rascunho" and "buscar o vídeo" in voltou.erro and links.abertos == {}
    longo = v.ler(feito.id)
    longo.duracao = 120
    v._gravar(longo)
    with pytest.raises(videos.VideoErro, match="3 a 90"):
        v.publicar(feito.id)


def test_reinicio_no_meio_da_publicacao_confere_no_perfil(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    v, _, _ = _publicaveis(tmp_path, monkeypatch, lambda *a: "")
    achados: list[str] = ["https://www.instagram.com/reel/saiu/"]
    v._procurar = lambda ig, legenda, desde: achados.pop(0) if achados else ""
    feito = v.criar(tema="x", esperar=True)

    def preso(desde: float) -> None:
        video = v.ler(feito.id)
        video.estado, video.publicando_desde = "publicando", desde
        v._gravar(video)

    preso(time.time())  # recente: ainda pode estar no ar daqui a pouco
    assert v.ler(feito.id).estado == "publicando"
    preso(time.time() - videos.CONFERIR_APOS_S - 1)
    saiu = v.ler(feito.id)
    assert saiu.estado == "publicado" and saiu.permalink.endswith("/reel/saiu/")
    preso(time.time() - videos.CONFERIR_APOS_S - 1)
    nao_saiu = v.ler(feito.id)
    assert nao_saiu.estado == "rascunho" and "Confira no Instagram" in nao_saiu.erro


def test_pergunta_de_aprovacao_diz_qual_video() -> None:
    from zervis.cerebro.claude import descrever

    criar = descrever(
        "mcp__jarvis__marketing_video_criar", {"tema": "agentes de IA", "duracao": 45}
    )
    assert criar == "Vou criar um vídeo de 45 segundos sobre agentes de IA."
    assert descrever("mcp__jarvis__marketing_video_publicar", {"video": "nao-existe"}) == (
        "Vou publicar no Instagram o vídeo nao-existe."
    )


def test_edicao_nova_no_plano() -> None:
    bruto = json.loads(json.dumps(ROTEIRO))
    bruto["cenas"][0].update(composicao="gigante", transicao="cor")  # 7 palavras: cabe
    bruto["cenas"][3].update(transicao="cor")
    r = roteiro.interpretar(json.dumps(bruto), _estilo())
    assert r.cenas[0]["composicao"] == "gigante" and r.cenas[3]["transicao"] == "cor"
    bruto["cenas"][0]["fala"] = "Sua recepção perde pacientes no WhatsApp toda santa noite."
    longa = roteiro.interpretar(json.dumps(bruto), _estilo())
    assert longa.cenas[0]["composicao"] == "centro"  # uma palavra por linha não cabe
    bruto["cenas"].insert(1, {"tipo": "frase", "fala": "Quem responde primeiro, marca.",
                              "composicao": "cheia"})  # fmt: skip
    assert roteiro.interpretar(json.dumps(bruto), _estilo()).cenas[1]["composicao"] == "cheia"


def test_biblioteca_acha_o_objeto_da_fala() -> None:
    from zervis.video import biblioteca

    assert len(biblioteca.todos()) > 1500
    assert biblioteca.achar("pizza") == "pizza"
    assert biblioteca.achar("Delivery Trucks") == "truck"  # parte do nome, plural
    assert biblioteca.achar("invoice") == "receipt"  # sinônimo
    assert biblioteca.achar("house") == "house"  # o ícone base, não "map-pin-house"
    assert biblioteca.achar("xyzzy") == biblioteca.achar("") == "sparkles"
    # o desenho é só de traço: nada que rode na página
    assert not any("<script" in d or "href" in d for d in biblioteca.todos().values())


def test_cenas_de_arte_no_plano() -> None:
    bruto = json.loads(json.dumps(ROTEIRO))
    bruto["cenas"][1:-1] = [
        {"tipo": "icone", "fala": "Toda pizza sai no tempo certo.", "icone": "pizza",
         "quando": "pizza"},
        {"tipo": "caos", "fala": "Pedido, entrega, conta e estoque se organizam sozinhos.",
         "icones": ["invoice", "delivery truck", "money", "stock", "nada-disso"],
         "quando": "organizam"},
        {"tipo": "hub", "fala": "Tudo ligado ao agente.", "centro": {"icone": "marca"},
         "ao_redor": [{"icone": "whatsapp"}, {"icone": "pizza"}, {"icone": "truck"}]},
    ]  # fmt: skip
    bruto["cenas"].insert(-1, dict(ROTEIRO["cenas"][1]))  # o mínimo de cenas do ritmo
    r = roteiro.interpretar(json.dumps(bruto), _estilo())
    icone, caos, hub = r.cenas[1:4]
    assert icone["icone"] == "pizza"
    assert caos["icones"] == ["receipt", "truck", "banknote", "package", "sparkles"]
    assert hub["centro"]["icone"] == "marca"
    assert [x["icone"] for x in hub["ao_redor"]] == ["message-circle", "pizza", "truck"]
    assert roteiro.icones_usados(r.cenas) >= {"pizza", "receipt", "message-circle"}
    bruto["cenas"][2]["icones"] = ["pizza"]
    with pytest.raises(roteiro.RoteiroErro):
        roteiro.interpretar(json.dumps(bruto), _estilo())


def test_transicoes_de_carta_e_fundos() -> None:
    bruto = json.loads(json.dumps(ROTEIRO))
    bruto["cenas"][1].update(transicao="carta", fundo="claro")
    bruto["cenas"][2].update(transicao="cubo", fundo="neon")  # fundo que não existe
    r = roteiro.interpretar(json.dumps(bruto), _estilo())
    assert (r.cenas[1]["transicao"], r.cenas[1]["fundo"]) == ("carta", "claro")
    assert (r.cenas[2]["transicao"], r.cenas[2]["fundo"]) == ("cubo", "escuro")
    assert {"carta", "baralho", "cubo", "fatias"} <= set(roteiro.TRANSICOES)


def test_memoria_dos_ultimos_videos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    v, _ = _videos(tmp_path, json.dumps(ROTEIRO), monkeypatch)
    primeiro = v.criar(tema="Atendimento fora do horário", esperar=True)
    assert "Os últimos vídeos desta marca" not in v.pedidos[0]  # ainda não há vídeos
    # o segundo vê o primeiro (tema, gancho e receita); a mesma receita volta para o diretor
    segundo = v.criar(tema="Outro tema", esperar=True)
    memoria = v.pedidos[1]
    assert "Os últimos vídeos desta marca" in memoria and ROTEIRO["titulo"] in memoria
    assert ROTEIRO["cenas"][0]["fala"] in memoria and "gancho (" in memoria
    assert "ficou igual à de um vídeo recente" in v.pedidos[2]
    assert segundo.estado == "rascunho"  # na segunda vez, aceita: o vídeo não falha por isso
    # um ajuste segue a versão anterior, sem a memória
    v.refazer(primeiro.id, "mais curto", esperar=True)
    assert "Os últimos vídeos desta marca" not in v.pedidos[-1]
    assert len(v.recentes()) == 2 and v.recentes(menos=primeiro.id)[0]["titulo"]


def test_tema_do_video_agendado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    v, _ = _videos(tmp_path, json.dumps(ROTEIRO), monkeypatch)
    assert v.proximo_tema(["Agenda cheia", "Recepção"]) == ("Agenda cheia", "")
    v.criar(tema="Agenda cheia", esperar=True)
    assert v.proximo_tema(["agenda  CHEIA", "Recepção"]) == ("Recepção", "")
    v.criar(tema="Recepção", esperar=True)
    assert v.proximo_tema(["Recepção"]) == ("", "existe")  # o artigo publicado novo
    v.criar(artigo="existe", esperar=True)
    assert v.proximo_tema([]) == (videos.TEMA_LIVRE, "")


def test_pedido_da_agenda_de_videos() -> None:
    texto = videos.Videos.pedido_agendado("Agenda cheia\n\n  Recepção  \n", 45)
    assert json.loads(texto) == {"temas": ["Agenda cheia", "Recepção"], "duracao": 45}
    assert len(json.loads(videos.Videos.pedido_agendado(["x"] * 30, 30))["temas"]) == 10
    with pytest.raises(videos.VideoErro):
        videos.Videos.pedido_agendado([], 31)
    with pytest.raises(videos.VideoErro):
        videos.Videos.pedido_agendado(["ã" * 80] * 10, 30)
    from zervis.cerebro.claude import descrever

    fala = descrever("mcp__jarvis__marketing_video_agendar", {"quando": "cron 0 9 * * 1"})
    assert fala.startswith("Vou agendar vídeos (cron 0 9 * * 1) com o tema escolhido pelo site")
    assert fala.endswith("; publicar fica com você.")


def test_video_agendado_cria_na_hora(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    from datetime import datetime
    from queue import Queue
    from types import SimpleNamespace

    from zervis import fuso
    from zervis.automacoes.jobs import Jobs
    from zervis.nucleo.servicos.automacoes import ServicoAutomacoes

    pedidos: list[dict[str, Any]] = []
    feito = threading.Event()

    class VideosFalsos:
        def proximo_tema(self, temas: list[str]) -> tuple[str, str]:
            return temas[0], ""

        def criar(self, **kw: Any) -> Any:
            pedidos.append(kw)
            feito.set()
            return SimpleNamespace(tema=kw["tema"], artigo="")

    monkeypatch.setattr(videos, "PADRAO", VideosFalsos())
    linha: list[str] = []
    n: Any = SimpleNamespace(eventos=Queue(), jobs=Jobs(tmp_path / "jobs.json"), _rodando=set())
    n._na_linha = lambda tipo, texto: linha.append(texto)
    n.eventos_sistema = SimpleNamespace(novos=lambda: [])
    n._vigia_em = n._n8n_em = n._versoes_em = n._agenda_em = 1e18
    agora = datetime(2099, 1, 2, 8, 0, tzinfo=fuso.local())
    texto = videos.Videos.pedido_agendado(["Agenda cheia"], 45)
    n.jobs.criar("Vídeo da marca", "2099-01-02 09:00", "video", texto, agora)
    ServicoAutomacoes(n)._agendador(datetime(2099, 1, 2, 9, 0, 30, tzinfo=fuso.local()).timestamp())
    assert feito.wait(2)
    assert pedidos == [{"tema": "Agenda cheia", "artigo": "", "duracao": 45}]
    for _ in range(50):
        if n.jobs.listar()[0].ultimo_status == "ok":
            break
        threading.Event().wait(0.02)
    assert n.jobs.listar()[0].ultimo_status == "ok"
    assert linha == ["Comecei o vídeo agendado: Agenda cheia."]


def _achado(id_: str, titulo: str) -> Any:
    from zervis.imersivo.imagens import Achado

    return Achado(id_, titulo, "", "foto", "CC BY 4.0", "Ana (talk)", "", "")


def _fotos(tmp_path: Path) -> tuple[Fotos, list[str]]:
    marca = tmp_path / "marca"
    marca.mkdir()
    (marca / "recepcao.jpg").write_bytes(b"jpg")
    buscas: list[str] = []

    def buscar(busca: str) -> list[Any]:
        buscas.append(busca)
        return [_achado("commons:File:Rua.jpg", "Street at night"),
                _achado("commons:File:Oficina.jpg", "Mechanic workshop in Recife")]  # fmt: skip

    def baixar(id_: str, pasta: Path) -> dict[str, Any]:
        assert id_ == "commons:File:Oficina.jpg"  # a que tem as palavras do pedido
        (pasta / "imagens").mkdir(parents=True, exist_ok=True)
        (pasta / "imagens" / "oficina.jpg").write_bytes(b"jpg")
        return {"arquivo": "imagens/oficina.jpg", "autor": "Ana (talk)", "tipo": "foto",
                "licenca": "CC BY 4.0", "fonte": "Wikimedia Commons"}  # fmt: skip

    f = Fotos(da_marca=lambda: ["recepcao.jpg"], pasta_da_marca=lambda: marca, buscar=buscar,
              baixar=baixar)  # fmt: skip
    return f, buscas


def test_fotos_da_marca_e_livres(tmp_path: Path) -> None:
    f, buscas = _fotos(tmp_path)
    pasta = tmp_path / "video"
    cenas: list[dict[str, Any]] = [
        {"tipo": "foto", "foto": "recepcao", "icone": "sparkles"},
        {"tipo": "foto", "foto": "busca: mechanic workshop", "icone": "sparkles"},
        {"tipo": "foto", "foto": "busca: car wash", "icone": "sparkles"},  # passa do limite
        {"tipo": "foto", "foto": "../../etc/passwd", "icone": "sparkles"},  # não é da marca
    ]
    creditos = f.resolver(cenas, pasta)
    assert cenas[0]["imagem"].endswith("/video/fotos/recepcao.jpg") and "credito" not in cenas[0]
    assert cenas[1]["imagem"].endswith("/imagens/oficina.jpg")
    assert creditos == ["Foto: Ana · CC BY 4.0 · Wikimedia Commons"]  # sem o "(talk)"
    assert buscas == ["mechanic workshop", "car wash"]
    # sem foto que sirva, a cena vira um ícone do objeto (o vídeo não falha)
    assert cenas[2]["tipo"] == "icone" and cenas[2]["icone"] == "car" and "foto" not in cenas[2]
    assert cenas[3]["tipo"] == "icone" and cenas[3]["composicao"] == "heroi"


def test_foto_no_plano_e_no_video(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bruto = json.loads(json.dumps(ROTEIRO))
    bruto["cenas"][1] = {"tipo": "foto", "fala": "A oficina não para.", "foto": "busca: mechanic "
                         "workshop", "composicao": "janela", "icone": "car"}  # fmt: skip
    r = roteiro.interpretar(json.dumps(bruto), _estilo())
    assert r.cenas[1]["foto"] == "busca: mechanic workshop" and r.cenas[1]["icone"] == "car"
    del bruto["cenas"][1]["foto"]
    with pytest.raises(roteiro.RoteiroErro):
        roteiro.interpretar(json.dumps(bruto), _estilo())
    prompt = roteiro.montar_prompt("Marca", "Tema: x", "", _estilo(), fotos=["recepcao.jpg"])
    assert "Fotos da marca" in prompt and "recepcao.jpg" in prompt
    assert "ainda não tem fotos" in roteiro.montar_prompt("Marca", "Tema: x", "", _estilo())
    # no vídeo: a foto vira arquivo e o crédito vai para a legenda do Instagram
    bruto["cenas"][1]["foto"] = "busca: mechanic workshop"
    v, _ = _videos(tmp_path, json.dumps(bruto), monkeypatch)
    v.fotos, _b = _fotos(tmp_path)
    feito = v.criar(tema="Oficina", esperar=True)
    assert feito.estado == "rascunho"
    assert feito.legenda.endswith("Fotos: Foto: Ana · CC BY 4.0 · Wikimedia Commons")
    assert feito.roteiro["cenas"][1]["imagem"].startswith("file://")


def test_formato_gancho_e_ritmo_no_plano() -> None:
    bruto = json.loads(json.dumps(ROTEIRO))
    bruto["formato"] = "erro"
    bruto["cenas"][0] = {"tipo": "foto", "fala": "POV: sua recepção às onze da noite.",
                         "foto": "busca: reception desk"}  # fmt: skip
    bruto["cenas"][1] = {"tipo": "frase", "fala": "Ninguém responde ninguém.",
                         "composicao": "cortes"}  # fmt: skip
    r = roteiro.interpretar(json.dumps(bruto), _estilo())
    assert r.formato == "erro" and r.para_json()["formato"] == "erro"
    assert r.cenas[0]["tipo"] == "foto"  # o vídeo pode abrir com foto
    assert r.cenas[1]["composicao"] == "cortes"
    bruto["cenas"][1]["fala"] = "uma fala comprida demais para caber uma palavra por tela inteira"
    assert roteiro.interpretar(json.dumps(bruto), _estilo()).cenas[1]["composicao"] == "carimbo"
    bruto["formato"] = "inventado"
    assert roteiro.interpretar(json.dumps(bruto), _estilo()).formato == ""
    prompt = roteiro.montar_prompt("Marca", "Tema: x", "", _estilo())
    assert "## Formato e gancho" in prompt and "- pov:" in prompt and "um corte a cada" in prompt


def test_formato_repetido_volta_ao_diretor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    com_formato = {**ROTEIRO, "formato": "lista"}
    v, _ = _videos(tmp_path, json.dumps(com_formato), monkeypatch)
    v.criar(tema="Um", esperar=True)
    outro = {**com_formato, "cenas": [*ROTEIRO["cenas"][:1], *ROTEIRO["cenas"][2:]]}
    outro["cenas"].insert(-1, dict(ROTEIRO["cenas"][2]))  # outra receita, o mesmo formato

    def perguntar(prompt: str, modelo: str) -> str:
        v.pedidos.append(prompt)
        return json.dumps(outro)

    v.perguntar = perguntar
    v.criar(tema="Dois", esperar=True)
    assert "formato: lista" in v.pedidos[1]
    assert 'O formato "lista" é o mesmo do último vídeo' in v.pedidos[2]


def test_efeitos_sonoros_das_acoes() -> None:
    cenas: list[dict[str, Any]] = [
        {"inicio": 0.0, "composicao": "cortes", "palavras": [
            {"p": "Você", "i": 0.1}, {"p": "está", "i": 0.5}, {"p": "a", "i": 0.8},
            {"p": "perdendo", "i": 0.9}]},
        {"inicio": 2.0, "transicao": "corte", "composicao": "carimbo", "destaque": "pior",
         "palavras": [{"p": "O", "i": 2.1}, {"p": "pior.", "i": 2.4}]},
        {"inicio": 4.0, "transicao": "carta"},
        {"inicio": 6.0, "transicao": "cubo"},
    ]  # fmt: skip
    assert videos.efeitos_sonoros(cenas) == [
        (0.5, "estalo"), (0.9, "estalo"),
        (2.0, "impacto"), (2.4, "impacto"),
        (4.0, "whoosh"), (4.25, "estalo"),
        (6.0, "whoosh"),
    ]  # fmt: skip
    from zervis.video import trilha

    a = trilha.compor(3.0, [1.0], semente=1, efeitos=[(1.0, "impacto")])
    b = trilha.compor(3.0, [1.0], semente=2, efeitos=[(1.0, "impacto")])
    assert a.shape == b.shape and not (a == b).all()  # a música muda de um vídeo para outro


def test_locutor_do_video(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    v, _ = _videos(tmp_path, json.dumps(ROTEIRO), monkeypatch)
    usados: list[str] = []

    def sintetizador(locutor: str = "") -> Any:
        usados.append(locutor)
        return _fala()

    v.sintetizador = sintetizador
    v._vozes_do_fish = lambda: [
        {"id": "f" * 32, "nome": "Locutora", "detalhe": "sua, female"},
        {"id": "e" * 32, "nome": "Famoso", "detalhe": "male, old"},  # da biblioteca: fica fora
    ]
    assert [x["id"] for x in v.vozes()] == ["", "cadu", "f" * 32]
    primeiro = v.criar(tema="Um", esperar=True, locutor="cadu")
    assert primeiro.locutor == "cadu" and usados == ["cadu"]
    segundo = v.criar(tema="Dois", esperar=True)  # sem escolha (o agendado): o último escolhido
    assert segundo.locutor == "cadu" and v.para_tela(segundo)["locutor"] == "cadu"
    v.criar(tema="Três", esperar=True, locutor="")  # a voz da página Voz
    assert usados[-1] == "" and v.locutor_padrao() == ""


def test_sintetizador_escolhe_o_locutor() -> None:
    from types import SimpleNamespace

    pedidos: list[tuple[str, str]] = []

    class Fish:
        ENDERECO, TAXA = "https://fish.invalido", 44100

        @staticmethod
        def pedido(texto: str, voz: str, modelo: str, chave: str) -> Any:
            pedidos.append((voz, modelo))
            raise RuntimeError("sem rede no teste")

    class Local:
        def abrir_fluxo(self, texto: str) -> Any:
            partes = iter([b"pcm", b""])
            return 22050, SimpleNamespace(read1=lambda n: next(partes))

    motor = SimpleNamespace(
        ativo="fish", local=Local(), provedores={"fish": Fish}, chaves={"fish": "k"},
        escolha=SimpleNamespace(voz=lambda p: {"id": "voz-do-ze", "modelo": "s2.1-pro"}),
    )  # fmt: skip
    assert narracao.sintetizador(motor, "cadu")("oi") == (22050, b"pcm")
    with pytest.raises(RuntimeError):
        narracao.sintetizador(motor, "a" * 32)("oi")
    with pytest.raises(RuntimeError):
        narracao.sintetizador(motor)("oi")
    assert pedidos == [("a" * 32, "s2.1-pro"), ("voz-do-ze", "s2.1-pro")]


def test_lista_e_estilo_editorial() -> None:
    bruto = json.loads(json.dumps(ROTEIRO))
    itens = [{"tipo": "item", "fala": f"Item {n}.", "nome": f"Nome {n}", "detalhe": "Faz algo.",
              "icone": "wrench", "fundo": f, "transicao": "carta"}
             for n, f in ((1, "claro"), (2, "cor"), (3, "escuro"))]  # fmt: skip
    bruto["cenas"][1:4] = itens
    bruto["cenas"][-1].update(composicao="comenta", palavra="oficina")
    r = roteiro.interpretar(json.dumps(bruto), _estilo())
    um, dois, tres = r.cenas[1:4]
    assert um["transicao"] == "carta" and um["icone"] == "wrench"
    # itens seguidos são o mesmo cartão: o fundo do primeiro, sem transição
    assert (dois["fundo"], dois["transicao"]) == ("claro", "corte") == (tres["fundo"], "corte")
    assert r.cenas[-1]["composicao"] == "comenta" and r.cenas[-1]["palavra"] == "oficina"
    e = estilos.achar("editorial")
    assert e.nome == "Editorial" and e.fonte_legenda == "Instrument Serif" and e.css
    assert "family=Instrument+Serif:ital@0;1" in e.fontes_url()
