"""A abertura do Zé (ADR 0078): o panorama do dia, as fontes de fora sem tokens, os ajustes, o
pedido de fala da Imersão e as ações do painel. Nada aqui sai para a rede."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from zervis import usuario
from zervis.abertura import ajustes, clima, noticias, panorama, servico
from zervis.abertura.servico import Abertura, Externas
from zervis.imersivo import abertura as rotas

FUSO = ZoneInfo("America/Fortaleza")
MANHA = datetime(2026, 11, 11, 9, 5, tzinfo=FUSO)
CLIMA = clima.Clima("Fortaleza", 30, "garoa fraca", 31, 24, 40)


# ---- o panorama ----


@pytest.mark.parametrize(
    ("hora", "esperado"),
    [(5, "Bom dia"), (11, "Bom dia"), (12, "Boa tarde"), (17, "Boa tarde"), (18, "Boa noite"),
     (0, "Boa noite"), (4, "Boa noite")],
)  # fmt: skip
def test_a_saudacao_segue_a_hora(hora: int, esperado: str) -> None:
    assert panorama.saudacao(MANHA.replace(hour=hora)) == esperado


def test_a_data_e_os_numeros_saem_como_se_fala() -> None:
    assert panorama.data_por_extenso(MANHA) == "quarta-feira, 11 de novembro"
    assert panorama.quantos(2, "conversa", "conversas", feminino=True) == "duas conversas"
    assert panorama.quantos(1, "compromisso", "compromissos") == "um compromisso"
    assert panorama.quantos(14, "sessão", "sessões", feminino=True) == "14 sessões"
    assert panorama.hora_falada(MANHA.replace(hour=14, minute=0)) == "14 horas"
    assert panorama.hora_falada(MANHA.replace(hour=16, minute=30)) == "16 horas e 30"
    assert panorama.enumerar(["a", "b", "c"]) == "a, b e c"


def test_sem_nada_no_dia_so_a_saudacao_e_o_fechamento() -> None:
    dia = panorama.montar(MANHA, "Ana")
    assert [b["tipo"] for b in dia["blocos"]] == ["relogio", "fim"]
    assert dia["blocos"][0]["fala"] == "Bom dia, Ana. Hoje é quarta-feira, 11 de novembro."
    assert panorama.montar(MANHA)["blocos"][0]["saudacao"] == "Bom dia"  # sem perfil, sem nome


def test_o_dia_completo_em_ordem_e_falado() -> None:
    hoje = [
        panorama.Item(MANHA.replace(hour=16, minute=30), "Dentista", "compromisso"),
        panorama.Item(MANHA.replace(hour=14, minute=0), "Reunião da equipe", "compromisso"),
        panorama.Item(MANHA.replace(hour=18, minute=0), "Relatório", "automacao"),
    ]
    sessoes = [panorama.SessaoParada("Loja", "interrompida")]
    conversas = [panorama.Conversa("Ana", MANHA.timestamp() - 7200)]
    manchetes = [noticias.Noticia(f"Manchete {i}", "G1") for i in range(6)]
    dia = panorama.montar(MANHA, "Ana", CLIMA, hoje, sessoes, conversas, manchetes)
    blocos = {b["tipo"]: b for b in dia["blocos"]}
    assert list(blocos) == ["relogio", "clima", "hoje", "sessoes", "whatsapp", "noticias", "fim"]
    assert blocos["clima"]["fala"] == (
        "Em Fortaleza, faz 30 graus, com garoa fraca. Máxima de 31 e mínima de 24, "
        "com 40 por cento de chance de chuva."
    )
    assert blocos["hoje"]["fala"] == (
        "Hoje você tem dois compromissos: às 14 horas, Reunião da equipe e às 16 horas e 30, "
        "Dentista. E roda uma automação: Relatório, às 18 horas."
    )
    assert [i["hora"] for i in blocos["hoje"]["itens"]] == ["14:00", "16:30", "18:00"]
    assert blocos["sessoes"]["fala"] == (
        "Uma sessão de código pede continuidade: Loja, que parou no meio."
    )
    assert blocos["sessoes"]["itens"] == [
        {"nome": "Loja", "situacao": "Interrompida", "chave": "interrompida"}
    ]
    assert blocos["whatsapp"]["fala"] == "No WhatsApp, uma conversa espera resposta: Ana."
    assert blocos["whatsapp"]["itens"] == [{"nome": "Ana", "ha": "há 2 h"}]
    assert len(blocos["noticias"]["itens"]) == panorama.MOSTRADOS
    assert blocos["noticias"]["fala"] == (
        "Nas manchetes de hoje: Manchete 0. Manchete 1. Manchete 2."
    )
    assert blocos["fim"]["fala"] == panorama.FECHAMENTO


def test_o_foco_e_o_instagram_entram_com_os_numeros_para_os_graficos() -> None:
    foco = panorama.Foco("Lançar a loja", "subir as fotos", 2, 1, 1, 3)
    agora = MANHA.timestamp()
    ig = panorama.Instagram(
        "ana.loja",
        15300,
        [
            panorama.Publicacao(agora - 86400, 12000, "Promoção de novembro"),
            panorama.Publicacao(agora - 3 * 86400, 4000, "Bastidores"),
            panorama.Publicacao(agora - 10 * 86400, 30000, "Antiga"),
        ],
    )
    dia = panorama.montar(MANHA, "Ana", CLIMA, instagram=ig, foco=foco)
    blocos = {b["tipo"]: b for b in dia["blocos"]}
    assert list(blocos) == ["relogio", "clima", "foco", "instagram", "fim"]
    assert blocos["foco"]["fala"] == (
        "No foco, você estava em Lançar a loja; o próximo passo é subir as fotos. "
        "Uma frente está travada. Nesta semana você concluiu três frentes."
    )
    assert (blocos["foco"]["ativas"], blocos["foco"]["travadas"]) == (2, 1)
    assert blocos["instagram"]["fala"] == (
        "No Instagram, você tem 15,3 mil seguidores. Nesta semana saíram duas publicações; "
        "a que mais rendeu teve 12 mil visualizações."
    )
    # o gráfico: da mais antiga para a mais nova; o destaque é o melhor da semana
    assert [g["valor"] for g in blocos["instagram"]["grafico"]] == [30000, 4000, 12000]
    assert blocos["instagram"]["destaque"] == {"legenda": "Promoção de novembro", "valor": "12 mil"}
    assert blocos["instagram"]["semana"] == 2
    parado = panorama.Instagram("ana.loja", 980, [])
    assert panorama.montar(MANHA, instagram=parado)["blocos"][1]["fala"] == (
        "No Instagram, você tem 980 seguidores. Nesta semana não saiu publicação nova."
    )
    # sem frente nenhuma, não há card de foco
    vazio = panorama.Foco("", "", 0, 0, 0, 0)
    assert "foco" not in [b["tipo"] for b in panorama.montar(MANHA, foco=vazio)["blocos"]]


def test_o_instagram_da_abertura_le_so_as_publicacoes_novas() -> None:
    pedidos: list[str] = []

    class Leitor:
        conectado = True

        def perfil(self) -> dict[str, Any]:
            pedidos.append("perfil")
            return {"username": "ana.loja", "followers_count": 15300}

        def recentes(self, n: int) -> list[dict[str, Any]]:
            pedidos.append(f"recentes {n}")
            return [{"timestamp": "2026-11-10T12:00:00+0000", "caption": "Oi\n de novo",
                     "metricas": {"views": 900}}]  # fmt: skip

    ig = servico.ler_instagram(Leitor())
    assert ig == panorama.Instagram(
        "ana.loja",
        15300,
        [
            panorama.Publicacao(
                datetime.fromisoformat("2026-11-10T12:00:00+00:00").timestamp(), 900.0, "Oi de novo"
            )
        ],
    )
    assert pedidos == ["perfil", f"recentes {panorama.NO_GRAFICO}"]  # nunca todas as publicações
    assert servico.ler_instagram(SimpleNamespace(conectado=False)) is None
    assert servico.ler_instagram(None) is None


def test_sem_rede_o_instagram_fica_o_ultimo_lido() -> None:
    respostas: list[Any] = [
        SimpleNamespace(conectado=True, perfil=lambda: {"username": "a", "followers_count": 5},
                        recentes=lambda n: []),
        SimpleNamespace(conectado=True, perfil=lambda: (_ for _ in ()).throw(OSError("rede"))),
    ]  # fmt: skip
    externas = Externas(
        localizar=lambda c: None, buscar_noticias=lambda: [], instagram=lambda: respostas.pop(0)
    )
    externas.renovar("", 0.0)
    externas.esperar()
    assert externas.instagram == panorama.Instagram("a", 5, [])
    externas.renovar("", 1e9)
    externas.esperar()
    assert externas.instagram == panorama.Instagram("a", 5, [])


def test_pouca_chance_de_chuva_nao_entra_na_fala() -> None:
    seco = CLIMA._replace(chuva=10, ceu="")
    assert panorama.montar(MANHA, clima=seco)["blocos"][1]["fala"] == (
        "Em Fortaleza, faz 30 graus. Máxima de 31 e mínima de 24."
    )


# ---- as fontes de fora ----


def test_o_clima_pelo_open_meteo() -> None:
    pedidos: list[str] = []

    def obter(url: str) -> Any:
        pedidos.append(url)
        if "geocoding" in url:
            return {"results": [{"name": "Fortaleza", "admin1": "Ceará", "latitude": -3.7,
                                 "longitude": -38.5}]}  # fmt: skip
        return {
            "current": {"temperature_2m": 30.4, "weather_code": 51},
            "daily": {"temperature_2m_max": [31.1], "temperature_2m_min": [24.2],
                      "precipitation_probability_max": [40]},
        }  # fmt: skip

    lugar = clima.localizar("Fortaleza", obter)
    assert lugar == clima.Lugar("Fortaleza", "Ceará", -3.7, -38.5)
    assert clima.buscar(lugar, obter) == CLIMA
    assert "name=Fortaleza" in pedidos[0] and "latitude=-3.7" in pedidos[1]
    assert all(u.startswith("https://") for u in pedidos)


def test_sem_rede_ou_cidade_desconhecida_nao_ha_clima() -> None:
    def falha(_url: str) -> Any:
        raise OSError("sem rede")

    assert clima.localizar("Fortaleza", falha) is None
    assert clima.localizar("Xyzzy", lambda _u: {"generationtime_ms": 0.1}) is None
    assert clima.buscar(clima.Lugar("x", "", 0, 0), falha) is None


GOOGLE = b"""<?xml version="1.0"?><rss><channel><title>Google Not\xc3\xadcias</title>
<item><title>Lula cobra pa\xc3\xadses ricos na COP31 - G1</title><source>G1</source></item>
<item><title>Lula cobra pa\xc3\xadses ricos na COP31 - G1</title></item>
<item><title>Ind\xc3\xbastria cresce 0,8% - UOL Not\xc3\xadcias</title></item>
</channel></rss>"""


def test_as_manchetes_com_o_veiculo_separado_e_sem_repetir() -> None:
    assert noticias.ler_rss(GOOGLE) == [
        noticias.Noticia("Lula cobra países ricos na COP31", "G1"),
        noticias.Noticia("Indústria cresce 0,8%", "UOL Notícias"),
    ]
    com_nome = noticias.ler_rss(GOOGLE, "Agência Brasil", quantas=1)
    assert com_nome == [noticias.Noticia("Lula cobra países ricos na COP31 - G1", "Agência Brasil")]


def test_a_primeira_fonte_caiu_vale_a_reserva() -> None:
    def obter(url: str) -> bytes:
        if "google" in url:
            raise OSError("fora do ar")
        return GOOGLE

    assert noticias.buscar(obter=obter)[0].fonte == "Agência Brasil"
    assert noticias.buscar(obter=lambda _u: b"<html>nada</html>") == []


def test_xml_com_entidades_em_cascata_nao_passa() -> None:
    bomba = b"""<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">
    <!ENTITY c "&b;&b;&b;&b;">]><rss><channel><item><title>&c;</title></item></channel></rss>"""
    assert noticias.buscar([("https://x", "")], obter=lambda _u: bomba) in ([], [
        noticias.Noticia("a" * 64, "")])  # fmt: skip


# ---- os ajustes e a música ----


def test_os_ajustes_e_a_cidade_do_fuso(tmp_path: Path) -> None:
    arquivo = tmp_path / "abertura.json"
    assert ajustes.ler(arquivo) == ajustes.Ajustes(True, "")
    ajustes.gravar(ajustes.Ajustes(False, "Recife"), arquivo)
    assert ajustes.ler(arquivo) == ajustes.Ajustes(False, "Recife")
    assert ajustes.cidade_do_fuso("America/Sao_Paulo") == "Sao Paulo"
    assert ajustes.cidade_do_fuso("UTC") == ajustes.cidade_do_fuso("Etc/GMT+3") == ""


def test_a_musica_so_entra_se_for_audio(tmp_path: Path) -> None:
    assert ajustes.musica(tmp_path) is None
    with pytest.raises(ajustes.AjusteErro, match="Formato"):
        ajustes.guardar_musica(b"<html>nada</html>", tmp_path)
    mp3 = ajustes.guardar_musica(b"ID3" + b"\0" * 64, tmp_path)
    assert mp3.name == "musica.mp3" and ajustes.musica(tmp_path) == mp3
    ogg = ajustes.guardar_musica(b"OggS" + b"\0" * 64, tmp_path)  # trocar tira a anterior
    assert ajustes.musica(tmp_path) == ogg and not mp3.exists()
    assert ajustes.tipo_do_audio(b"RIFF\0\0\0\0WAVEfmt ") == ".wav"
    assert ajustes.tipo_do_audio(b"\0\0\0\x20ftypM4A ") == ".m4a"
    ajustes.remover_musica(tmp_path)
    assert ajustes.musica(tmp_path) is None


# ---- o serviço: o que o Zé junta, grava e fala ----


def _fontes(tmp_path: Path, agora: datetime) -> Any:
    def sessao(id_: str, nome: str, **campos: Any) -> Any:
        base = {"id": id_, "nome": nome, "origem": "painel", "interrompida": "", "limite": False,
                "estado": "parada"}  # fmt: skip
        return SimpleNamespace(**{**base, **campos})

    sessoes = SimpleNamespace(
        listar=lambda: [
            sessao("a", "Parada"),
            sessao("b", "Loja", interrompida="o pedido"),
            sessao("c", "Zérvis"),
            sessao("d", "Manutenção", origem="manutencao", interrompida="x"),
            sessao("e", "Site", estado="erro"),
        ],
        trabalhando=lambda: ["c"],
    )

    def job(nome: str, quando: datetime | None, ativo: bool = True) -> Any:
        return SimpleNamespace(nome=nome, ativo=ativo, proxima=quando.isoformat() if quando else "")

    jobs = SimpleNamespace(
        listar=lambda: [
            job("Relatório", agora + timedelta(hours=3)),
            job("Amanhã", agora + timedelta(days=1)),
            job("Pausada", agora + timedelta(hours=1), ativo=False),
            job("Já foi", agora - timedelta(hours=1)),
            job("Sem próxima", None),
        ]
    )
    cache = tmp_path / "calendar-events.json"
    cache.write_text(
        json.dumps(
            {
                "version": 1,
                "syncedAt": agora.isoformat(),
                "events": [
                    {
                        "id": "1",
                        "title": "Reunião",
                        "start": (agora + timedelta(hours=2)).isoformat(),
                    },
                    {"id": "2", "title": "Ontem", "start": (agora - timedelta(days=1)).isoformat()},
                    {"id": "3", "title": "Feriado", "start": agora.isoformat(), "allDay": True},
                ],
            }
        )
    )

    def conversa(nome: str, horas: float, de_mim: bool = False, chat: str = "") -> Any:
        quando = agora.timestamp() - horas * 3600
        return SimpleNamespace(
            nome=nome, chat=chat or nome, telefone="", quando=quando, sem_resposta=not de_mim
        )

    caixa = SimpleNamespace(
        conversas=lambda grupos: [
            conversa("Ana", 1),
            conversa("Bia", 2, de_mim=True),
            conversa("Velho", 30),
            conversa("Calado", 1, chat="calado"),
        ]
    )
    prioridade = SimpleNamespace(calado=lambda chat, telefone: chat == "calado")
    return SimpleNamespace(
        sessoes=sessoes, jobs=jobs, calendario=SimpleNamespace(cache=cache), caixa=caixa,
        prioridade=prioridade,
    )  # fmt: skip


def test_a_coleta_pega_so_o_que_pede_voce(tmp_path: Path) -> None:
    agora = datetime.now(FUSO).replace(hour=9, minute=0, second=0, microsecond=0)
    partes = servico.coletar(_fontes(tmp_path, agora), agora)
    assert sorted((i.titulo, i.tipo) for i in partes["hoje"]) == [
        ("Relatório", "automacao"),
        ("Reunião", "compromisso"),
    ]
    assert partes["sessoes"] == [
        panorama.SessaoParada("Loja", "interrompida"),
        panorama.SessaoParada("Site", "erro"),
        panorama.SessaoParada("Zérvis", "trabalhando"),
    ]
    assert [c.nome for c in partes["conversas"]] == ["Ana"]


def test_uma_parte_que_falha_nao_derruba_a_abertura(tmp_path: Path) -> None:
    agora = datetime.now(FUSO)
    fontes = _fontes(tmp_path, agora)

    def quebrou() -> list[Any]:
        raise RuntimeError("banco travado")

    fontes.sessoes.listar = quebrou
    partes = servico.coletar(fontes, agora)
    assert partes["sessoes"] == [] and partes["conversas"]


def _externas() -> Externas:
    return Externas(
        localizar=lambda cidade: clima.Lugar(cidade, "", 0, 0),
        buscar_clima=lambda lugar: CLIMA._replace(cidade=lugar.nome),
        buscar_noticias=lambda: [noticias.Noticia("Manchete", "G1")],
    )


@pytest.fixture
def abertura(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Abertura:
    monkeypatch.setattr(usuario, "ler", lambda *_a: usuario.Perfil("Ana"))
    monkeypatch.setattr(ajustes, "PASTA_MUSICA", tmp_path / "musica")
    a = Abertura(
        tmp_path,
        _fontes(tmp_path, datetime.now(FUSO)),
        _externas(),
        lambda: ajustes.Ajustes(True, "Recife"),
    )
    return a


def test_o_ze_grava_o_dia_para_a_imersao(abertura: Abertura, tmp_path: Path) -> None:
    abertura.retratar(time.time())
    abertura.externas.esperar()
    abertura.retratar(time.time())  # a busca terminou: regrava na hora, sem esperar o minuto
    dia = json.loads((tmp_path / "abertura.json").read_text())
    tipos = [b["tipo"] for b in dia["blocos"]]
    assert tipos[0] == "relogio" and tipos[-1] == "fim"
    assert "clima" in tipos and "noticias" in tipos
    assert dia["blocos"][tipos.index("clima")]["cidade"] == "Recife"
    assert dia["ligada"] is True and dia["musica"] is False
    assert rotas.panorama(tmp_path) == dia


def test_a_pagina_escolhe_o_passo_e_o_ze_fala_o_texto_dele(
    abertura: Abertura, tmp_path: Path
) -> None:
    abertura.retratar(time.time())
    dia = rotas.panorama(tmp_path)
    assert abertura.fala() is None  # nada pedido
    rotas.pedir_fala(tmp_path, {"montado": dia["montado"], "passo": 0})
    assert abertura.fala() == dia["blocos"][0]["fala"]
    assert abertura.fala() is None  # uma vez só
    time.sleep(0.01)
    rotas.pedir_fala(tmp_path, {"montado": "2020-01-01T00:00:00", "passo": 0})
    assert abertura.fala() is None  # um panorama que o Zé não montou
    time.sleep(0.01)
    rotas.pedir_fala(tmp_path, {"montado": dia["montado"], "passo": 31})
    assert abertura.fala() is None  # passo que não existe
    time.sleep(0.01)
    rotas.pedir_fala(tmp_path, {"montado": dia["montado"], "passo": 0})
    assert abertura.fala(agora=time.time() + 60) is None  # velho demais (o Zé estava parado)


def test_enquanto_a_abertura_roda_os_avisos_esperam(abertura: Abertura, tmp_path: Path) -> None:
    # Ligada, a abertura já conta como vindo assim que o Zé sobe (abrir o programa a abre).
    assert abertura.rodando()
    abertura._rodando_ate = 0.0
    abertura.retratar(time.time())
    dia = rotas.panorama(tmp_path)
    ultimo = len(dia["blocos"]) - 1
    passos = [-1, 0, ultimo]
    estados = []
    for passo in passos:
        time.sleep(0.01)
        rotas.pedir_fala(tmp_path, {"montado": dia["montado"], "passo": passo})
        fala = abertura.fala()
        estados.append((fala is not None, abertura.rodando()))
    # começou (sem fala), um passo (fala, segue rodando), o fechamento (fala, acabou)
    assert estados == [(False, True), (True, True), (True, False)]
    time.sleep(0.01)
    rotas.pedir_fala(tmp_path, {"montado": dia["montado"], "passo": -1})
    abertura.fala()
    time.sleep(0.01)
    rotas.pedir_fala(tmp_path, {"montado": dia["montado"], "passo": -2})  # pulada com o Esc
    assert abertura.fala() is None and not abertura.rodando()
    assert not abertura.rodando(time.time() + servico.INICIO_S + 1)
    desligada = Abertura(tmp_path, _fontes(tmp_path, MANHA), _externas(),
                         lambda: ajustes.Ajustes(False, "Recife"))  # fmt: skip
    assert not desligada.rodando()


def test_os_avisos_nao_atropelam_a_abertura(tmp_path: Path) -> None:
    import queue

    from zervis.avisos.fila import Fila
    from zervis.nucleo.servicos.avisos import ServicoAvisos

    # Visto em 11/11/2026: ao abrir o programa, a oferta dos avisos da subida entrou no meio da
    # abertura. Com ela rodando, nada sai da fila; depois do fechamento, a oferta vem.

    rodando = [True]
    fila = Fila(tmp_path / "avisos.json")
    for texto in ("O n8n voltou.", "A memória passou de 80%."):
        fila.guardar(texto)
    n: Any = SimpleNamespace(
        abertura=SimpleNamespace(rodando=lambda: rodando[0], e_fala=lambda t: False), fila=fila,
        eventos=queue.Queue(),
        _meta={}, _oferta_ate=0.0,
    )  # fmt: skip
    ServicoAvisos(n)._sair_da_fila()
    assert n.eventos.empty() and len(fila.validos()) == 2
    rodando[0] = False
    ServicoAvisos(n)._sair_da_fila()
    assert n.eventos.get_nowait().texto == "Duas novidades esperando. Começo pela primeira?"


def test_aviso_que_chega_no_meio_da_abertura_espera_na_fila() -> None:
    from zervis.nucleo import estados as e
    from zervis.nucleo import ouvir

    guardados: list[str] = []
    n: Any = SimpleNamespace(
        modo_fala="normal", _fonte=None, abertura=SimpleNamespace(rodando=lambda: True),
        _guardar=guardados.append,
    )  # fmt: skip
    ouvir.tratar(n, e.Aviso("A sessão Loja terminou."))
    assert guardados == ["A sessão Loja terminou."]  # não foi falado: esperou na fila


def test_a_musica_da_abertura_nao_vale_como_chamado() -> None:
    # Visto em 11/11/2026: a música no microfone soou como "Ei Zé" 4 s depois de subir; o Zé
    # abriu uma conversa no meio da abertura.
    from zervis.nucleo import estados as e
    from zervis.nucleo import ouvir

    rodando = [True]
    tratados: list[Any] = []
    n: Any = SimpleNamespace(
        modo_fala="normal", _fonte=None, abertura=SimpleNamespace(rodando=lambda: rodando[0]),
        _guardar=tratados.append, _pessoa_falando=lambda: True,
    )  # fmt: skip
    ouvir.tratar(n, e.Ativacao())  # ignorado: nada mais é chamado no núcleo
    rodando[0] = False
    with pytest.raises(AttributeError):  # fora da abertura, o chamado segue para a máquina
        ouvir.tratar(n, e.Ativacao())


def test_fala_da_abertura_nao_dita_na_hora_nao_vira_aviso(
    abertura: Abertura, tmp_path: Path
) -> None:
    from zervis.avisos.fila import Fila
    from zervis.nucleo import efeitos
    from zervis.nucleo import estados as e

    abertura.retratar(time.time())
    dia = rotas.panorama(tmp_path)
    rotas.pedir_fala(tmp_path, {"montado": dia["montado"], "passo": 0})
    fala = abertura.fala()
    assert fala is not None and abertura.e_fala(fala)
    guardados: list[str] = []
    n: Any = SimpleNamespace(abertura=abertura, _guardar=guardados.append, _comecados={})
    efeitos._executar(n, e.ReterAviso(fala))  # o Zé não estava livre quando ela chegou
    assert guardados == []  # descartada, não guardada para "depois"
    efeitos._executar(n, e.ReterAviso("A sessão Loja terminou."))
    assert guardados == ["A sessão Loja terminou."]  # um aviso de verdade espera, como antes
    # As que ficaram na fila antes desta correção (o caso real) saem antes de qualquer oferta.
    import queue

    from zervis.nucleo.servicos.avisos import ServicoAvisos

    fila = Fila(tmp_path / "avisos.json")
    for texto in ("Boa tarde, Ana. Hoje é quarta-feira, 11 de novembro.",
                  "No WhatsApp, três conversas esperam resposta: Bia, Caio e Davi.",
                  "Boa noite, Ana. Hoje é quarta-feira, 11 de novembro.",
                  "A sessão Loja terminou."):  # fmt: skip
        fila.guardar(texto)
    abertura._rodando_ate = 0.0
    m: Any = SimpleNamespace(abertura=abertura, fila=fila, eventos=queue.Queue(), _meta={})
    ServicoAvisos(m)._sair_da_fila()
    assert m.eventos.get_nowait().texto == "A sessão Loja terminou."
    assert not fila.validos()


@pytest.mark.parametrize(
    "pedido",
    [
        {"montado": "x", "passo": 0},
        {"montado": "2026-11-11T09:00:00-03:00", "passo": "0"},
        {"montado": "2026-11-11T09:00:00-03:00", "passo": -3},
        {"montado": "2026-11-11T09:00:00-03:00", "passo": True},
        {"texto": "fale qualquer coisa"},
    ],
)
def test_a_rota_de_fala_so_aceita_um_passo(tmp_path: Path, pedido: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="recusado"):
        rotas.pedir_fala(tmp_path, pedido)
    assert not (tmp_path / "abertura-falar.json").exists()


def test_a_rota_da_musica(tmp_path: Path) -> None:
    assert rotas.musica(tmp_path) is None
    ajustes.guardar_musica(b"ID3" + b"\1" * 32, tmp_path)
    assert rotas.musica(tmp_path) == (b"ID3" + b"\1" * 32, "audio/mpeg")


# ---- o painel ----


def test_o_cartao_abertura_salva_e_regrava_o_dia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zervis.portal.acoes.abertura import AcoesAbertura
    from zervis.portal.acoes.pagina import Servicos
    from zervis.portal.servidor import PedidoInvalido

    monkeypatch.setattr(ajustes, "ARQUIVO", tmp_path / "abertura.json")
    monkeypatch.setattr(ajustes, "PASTA_MUSICA", tmp_path / "musica")
    retratos: list[bool] = []
    nucleo = SimpleNamespace(abertura=SimpleNamespace(retratar=lambda _a, ja: retratos.append(ja)))
    pagina = AcoesAbertura(None, Servicos({"abertura": lambda: nucleo.abertura}))  # type: ignore[arg-type]
    assert pagina.abertura()["ligada"] is True and pagina.abertura()["musica"] is False
    r = pagina.salvar_abertura({"ligada": False, "cidade": " Recife "})
    assert (r["ligada"], r["cidade"], r["aviso"]) == (False, "Recife", "Abertura salva.")
    assert pagina.enviar_musica(b"ID3" + b"\0" * 16, {})["musica"] is True
    with pytest.raises(PedidoInvalido, match="Formato"):
        pagina.enviar_musica(b"nada", {})
    assert pagina.remover_musica({})["musica"] is False
    with pytest.raises(PedidoInvalido, match="80"):
        pagina.salvar_abertura({"cidade": "x" * 81})
    assert retratos == [True, True, True]
