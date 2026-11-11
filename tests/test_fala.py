"""Normalizador de fala: casos portados do Zé antigo (VIBE-CODING/jarvis/tests, 06/10/2026)."""

import json
from pathlib import Path

from zervis.voz import fala


def test_numbers_in_words() -> None:
    for n, w in [
        (21, "vinte e um"),
        (100, "cem"),
        (101, "cento e um"),
        (1100, "mil e cem"),
        (1250, "mil duzentos e cinquenta"),
        (2026, "dois mil e vinte e seis"),
        (2500000, "dois milhões e quinhentos mil"),
    ]:
        assert fala.extenso(n) == w
    assert fala.extenso(2, feminino=True) == "duas"


def test_screen_text_becomes_speech() -> None:
    cases = {
        "71% de cobertura": "setenta e um por cento de cobertura",
        "3,5 GB livres": "três vírgula cinco gigabytes livres",
        "às 10:05": "às dez horas e cinco minutos",
        "dia 01/10/2026": "dia primeiro de outubro de dois mil e vinte e seis",
        "em 2026-10-06": "em seis de outubro de dois mil e vinte e seis",
        "1º lugar, 2ª versão": "primeiro lugar, segunda versão",
        "R$ 1.234,50": "mil duzentos e trinta e quatro reais e cinquenta centavos",
        "27°C": "vinte e sete graus Celsius",
        "100 mm x 47 mm": "cem milímetros por quarenta e sete milímetros",
        "2 h de impressão": "duas horas de impressão",
        "de 3-5 arquivos": "de três a cinco arquivos",
        "40% → 51%": "quarenta por cento para cinquenta e um por cento",
    }
    for screen, speech in cases.items():
        assert fala.falavel(screen) == speech, screen
    assert fala.falavel("Tudo certo, Ana.") == "Tudo certo, Ana."


def test_technical_screen_text_becomes_speech() -> None:
    cases = {
        "de 06/10": "de seis de outubro",
        "dia 6/10": "dia seis de outubro",
        "2/3 prontas": "dois de três prontas",
        "Versão 4.0.4": "Versão quatro ponto zero ponto quatro",
        "a v2.1": "a versão dois ponto um",
        "Python 3.12": "Python três ponto doze",
        "1.234 linhas": "mil duzentos e trinta e quatro linhas",
        "2,5x mais rápido": "dois vírgula cinco vezes mais rápido",
        "rodei 3x": "rodei três vezes",
        "1920x1080@180Hz": "mil novecentos e vinte por mil e oitenta a cento e oitenta hertz",
        "Fiz o commit 5814357 na branch": "Fiz o commit na branch",
        "hash a8ae034 salvo": "hash salvo",
        "sessão 01a0f406-1111-2222-3333-444455556666 parada": "sessão parada",
        "em src/app.tsx:42.": "em app ponto tê esse xis, linha quarenta e dois.",
        "o arquivo ~/config.json": "o arquivo config ponto jêison",
        "a pasta ~/3D-NOVO/output": "a pasta output",
        "mudei listener_v2.py": "mudei listener v2 ponto pai",
        "touch /tmp/c-1000/24dc1931-be18-42ad-8b10-b066fa67f04b/aprovacao-claude.txt": "touch aprovacao claude ponto tê xis tê",
        "em 127.0.0.1:8794": "em cento e vinte e sete ponto zero ponto zero ponto um, porta oito mil setecentos e noventa e quatro",
        "o PR #12": "o PR doze",
        "Fase 4b agora": "Fase quatro bê agora",
        "Claude/Codex e/ou": "Claude ou Codex e ou",
        "≥ 80%": "pelo menos oitenta por cento",
    }
    for screen, speech in cases.items():
        assert fala.falavel(screen) == speech, screen


def test_para_fala_tira_markdown_codigo_e_links() -> None:
    texto = fala.para_fala(
        "## Feito\n- **Corrigi** o `login`.\n```py\nx=1\n```\nVeja https://x.y/z"
    )
    assert "#" not in texto
    assert "**" not in texto
    assert "x=1" not in texto
    assert "https" not in texto
    assert "chat" not in texto  # o Zé novo não tem chat
    assert texto.endswith("Veja o link")
    assert fala.para_fala("Frase. " * 600).endswith("Tem mais; se quiser, eu continuo.")


def test_numero_concorda_com_palavra_feminina() -> None:
    assert fala.falavel("Faltam 2 dias, 1 hora e 45 minutos.") == (
        "Faltam dois dias, uma hora e quarenta e cinco minutos."
    )
    assert fala.falavel("Tenho 2 sugestões e 1 pergunta.") == "Tenho duas sugestões e uma pergunta."
    assert fala.falavel("Abri 1 sessão, 2 abas e 200 linhas.") == (
        "Abri uma sessão, duas abas e duzentas linhas."
    )
    assert fala.falavel("São 2 projetos e 1 agente.") == "São dois projetos e um agente."


def test_para_fala_mantem_codigo_curto_e_caminhos_da_home() -> None:
    assert (
        fala.para_fala("rode `npm test` em ~/x/a.py e ~~isso~~")
        == "rode npm test em ~/x/a.py e isso"
    )
    assert "trecho técnico" in fala.para_fala("`" + "x" * 50 + "`")


def test_a_marca_de_emocao_vira_rosto_e_sai_da_fala(tmp_path: Path) -> None:
    from zervis.rosto.anel import Anel, separar_emocao

    assert separar_emocao("[alegria] Deu certo!") == ("alegria", "Deu certo!")
    assert separar_emocao(" [Dúvida]  Qual dos dois?") == ("duvida", "Qual dos dois?")
    assert separar_emocao("Veja [raiva] no meio") == ("", "Veja [raiva] no meio")
    assert separar_emocao("[tristeza] Não deu certo.") == ("tristeza", "Não deu certo.")
    assert separar_emocao("[tédio] Oi") == ("", "[tédio] Oi")
    anel = Anel(tmp_path)
    anel.expressao("raiva", 100.0)
    assert json.loads((tmp_path / "expressao.json").read_text()) == {
        "expressao": "raiva",
        "ate": 112.0,
    }
    anel.expressao("neutro", 101.0)
    assert json.loads((tmp_path / "expressao.json").read_text())["ate"] == 0.0


def test_fontes_da_pesquisa_saem_da_fala() -> None:
    from zervis.voz.fala import separar_fontes

    resposta = (
        "O melhor é o QCY MeloBuds Pro.\n\nFontes:\n- [Melhores fones](https://x.com/a)\n"
        "- [Outro](https://y.com/b)"
    )
    falado, fontes = separar_fontes(resposta)
    assert falado.strip() == "O melhor é o QCY MeloBuds Pro."
    assert fontes.startswith("Fontes:") and "https://y.com/b" in fontes
    assert separar_fontes("**Sources:**\n- [a](b)") == ("", "**Sources:**\n- [a](b)")
    assert separar_fontes("As fontes de energia: sol e vento.") == (
        "As fontes de energia: sol e vento.",
        "",
    )


def test_ate_onde_a_voz_chegou_no_pedaco() -> None:
    from zervis.rosto.anel import falado_ate

    texto = "x" * 100  # 6,5 s estimados
    assert falado_ate(texto, 0.0, 6.5, gerando=False) == 0
    assert falado_ate(texto, 3.25, 6.5, gerando=False) == 50
    assert falado_ate(texto, 9.0, 6.5, gerando=False) == 100
    # o áudio ainda chegando (só 2 s gerados): a estimativa pelo texto, não o fim do que já veio
    assert falado_ate(texto, 1.95, 2.0, gerando=True) == 30
    assert falado_ate("", 1.0, 0.0, gerando=True) == 0


def test_o_anel_grava_o_pedaco_que_a_voz_esta_dizendo(tmp_path: Path) -> None:
    import time

    import numpy as np

    from zervis.rosto.anel import Anel

    anel = Anel(tmp_path, intervalo=0.01)
    pcm = np.zeros(16000, dtype=np.float32)  # 1 s a 16 kHz
    anel.comecar(lambda: pcm, 16000, "Primeiro o sol aquece.")
    fim = time.monotonic() + 2
    while not (tmp_path / "fala.json").exists() and time.monotonic() < fim:
        time.sleep(0.01)
    time.sleep(0.2)
    anel.parar()
    fala = json.loads((tmp_path / "fala.json").read_text())
    assert fala["texto"] == "Primeiro o sol aquece." and 0 < fala["ate"] <= 22
    assert fala["inicio"] <= fala["ts"] <= time.time()


def test_a_voz_passa_ao_anel_o_texto_de_cada_pedaco() -> None:
    import io

    from zervis.voz.saida import Voz

    recebidos: list[str] = []

    class Onda:
        def comecar(self, amostras: object, taxa: int, texto: str = "") -> None:
            recebidos.append(texto)

        def parar(self) -> None:
            pass

    class Tocador:
        def __init__(self) -> None:
            self.stdin = io.BytesIO()

        def poll(self) -> int | None:
            return 0

        def wait(self) -> int:
            return 0

        def kill(self) -> None:
            pass

    voz = Voz(onda=Onda(), abrir_fluxo=lambda t: (16000, io.BytesIO(b"\0" * 64000)), folga_s=0)
    voz.destino = lambda taxa: Tocador()
    voz._falar(["Primeiro o sol.", "Depois a chuva."], voz.epoca, 0.0)
    assert recebidos == ["Primeiro o sol.", "Depois a chuva."]
