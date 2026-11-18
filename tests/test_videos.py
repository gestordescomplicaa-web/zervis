"""Os vídeos de Marketing (ADR 0106): estilos, roteiro, voz, trilha, a página no Chromium e o
caminho inteiro com o modelo, a voz, a captura e o FFmpeg trocados por falsos."""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from zervis.marca import Marca
from zervis.video import captura, estilos, narracao, roteiro, trilha, videos

EMBUTIDOS = estilos.EMBUTIDOS

ROTEIRO: dict[str, Any] = {
    "titulo": "Sua recepção perde pacientes no WhatsApp",
    "legenda": "Legenda do Instagram.",
    "cenas": [
        {"tipo": "gancho", "fala": "Sua recepção perde pacientes no WhatsApp.",
         "texto": "Sua recepção perde pacientes", "destaque": "perde pacientes"},
        {"tipo": "passos", "fala": "O paciente chama, o agente agenda.", "titulo": "Como funciona",
         "passos": ["Paciente chama", "Agente agenda", "Recepção confirma"]},
        {"tipo": "antes_depois", "fala": "Antes no dia seguinte, agora em segundos.",
         "antes": "Resposta no dia seguinte", "depois": "Resposta em segundos"},
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
    [zervis] = estilos.listar(EMBUTIDOS, tmp_path)
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
    [proprio] = estilos.listar(EMBUTIDOS, tmp_path)  # o de quem usa vale no lugar do embutido
    assert proprio.nome == "Meu" and proprio.proprio and proprio.js is not None
    assert proprio.bpm == 160 and proprio.energia == "alta" and not proprio.onda
    assert list(proprio.cenas_extras) == ["citacao"]
    assert estilos.achar("nao-existe", EMBUTIDOS, tmp_path).id == "zervis"


# --- roteiro ----------------------------------------------------------------------------------


def test_roteiro_conferido_e_cortado() -> None:
    bruto = json.loads(json.dumps(ROTEIRO))
    bruto["cenas"][0]["texto"] = "x" * 200
    bruto["cenas"][1]["passos"].append("<b>quarto</b>")
    resposta = "Aqui está:\n```json\n" + json.dumps(bruto) + "\n```"
    r = roteiro.interpretar(resposta, _estilo())
    assert [c["tipo"] for c in r.cenas] == [c["tipo"] for c in ROTEIRO["cenas"]]
    assert len(r.cenas[0]["texto"]) == 70 and r.cenas[0]["texto"].endswith("…")
    assert r.cenas[1]["passos"][-1] == "<b>quarto</b>"  # texto puro: a página mostra como texto
    assert r.falas[0] == "Sua recepção perde pacientes no WhatsApp."
    assert r.titulo == ROTEIRO["titulo"]


@pytest.mark.parametrize(
    ("mudar", "erro"),
    [
        (lambda r: r["cenas"].pop(0), "gancho"),
        (lambda r: r["cenas"][1].update(tipo="slide"), "desconhecido"),
        (lambda r: r["cenas"][1].update(passos=["só um"]), "pelo menos 2"),
        (lambda r: r["cenas"].insert(1, {"tipo": "numero", "fala": "x", "valor": "muito",
                                         "rotulo": "a", "fonte": "b"}), "não tem número"),
        (lambda r: r["cenas"].insert(1, {"tipo": "numero", "fala": "x", "valor": "9%",
                                         "rotulo": "a"}), "sem fonte"),
        (lambda r: r["cenas"][2].update(fala="ab " * 50), "longa"),
        (lambda r: r["cenas"][2].update(fala=""), "sem fala"),
        (lambda r: r.update(cenas=r["cenas"][:2]), "4 a 7"),
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
    assert r.cenas[1] == {"tipo": "citacao", "fala": "Uma frase.", "texto": "y" * 199 + "…"}
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
    n = narracao.narrar(["um", "dois", "três"], _fala(), minimos=[0, 3.0, 0])
    inicios = [f["inicio"] for f in n.falas]
    assert inicios[0] == narracao.INICIO_S
    assert all(math.isclose(i / 0.5, round(i / 0.5)) for i in inicios)  # 120 BPM
    assert all(1.0 <= f["dur"] <= 1.1 for f in n.falas)  # o silêncio das pontas saiu
    assert inicios[2] - inicios[1] >= 3.0  # o mínimo da cena 2 segura a fala 3
    assert n.cenas[0][0] == 0 and n.cenas[-1][1] == n.duracao
    assert len(n.volume) == round(n.duracao * narracao.FPS) and max(n.volume) == 1.0

    sem_voz = narracao.narrar(["uma fala com cinco palavras", "fim"], None)
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
    for c in ROTEIRO["cenas"]:
        cenas.append({**c, "inicio": t, "fim": t + 2.0})
        t += 2.0
    falas = [{"texto": c["fala"], "inicio": c["inicio"] + 0.3, "dur": 1.2} for c in cenas]
    estilo = _estilo()
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


def _videos(tmp_path: Path, resposta: str, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    monkeypatch.setattr(videos.Videos, "disponivel", staticmethod(lambda: ""))
    site = SiteFalso()
    pedidos: list[str] = []

    def perguntar(prompt: str) -> str:
        pedidos.append(prompt)
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

    v = videos.Videos(tmp_path, site, perguntar, lambda: _fala(), capturar, montar)  # type: ignore[arg-type]
    v.pedidos = pedidos  # type: ignore[attr-defined]
    return v, site


def test_do_pedido_ao_mp4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    v, site = _videos(tmp_path, json.dumps(ROTEIRO), monkeypatch)
    feito = v.criar(tema="Atendimento fora do horário", esperar=True)
    assert feito.estado == "rascunho" and feito.erro == "" and feito.etapa == ""
    assert feito.titulo == ROTEIRO["titulo"] and feito.duracao > 6
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
    with pytest.raises(videos.VideoErro, match="Vídeo"):
        v.ler("../x")
    preso = videos.Video("abcdef12", tema="x")  # criando, de antes de um reinício
    v._gravar(preso)
    assert v.ler("abcdef12").estado == "erro"
    monkeypatch.setattr(videos.Videos, "disponivel", staticmethod(lambda: "Falta o FFmpeg."))
    with pytest.raises(videos.VideoErro, match="indisponíveis"):
        v.criar(tema="x")
