"""A abertura do Zé (ADR 0078): o panorama do dia, as fontes de fora sem tokens, os ajustes, o
pedido de fala da Imersão e as ações do painel. Nada aqui sai para a rede."""

import json
import threading
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
CLIMA = clima.Clima("Fortaleza", 30, "garoa fraca", 31, 24, 40, icone="chuva")


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
    assert [b["tipo"] for b in dia["blocos"]] == ["agora", "fim"]
    assert dia["blocos"][0]["fala"] == "Bom dia, Ana. Hoje é quarta-feira, 11 de novembro."
    assert dia["blocos"][0]["clima"] is None
    assert panorama.montar(MANHA)["blocos"][0]["saudacao"] == "Bom dia"  # sem perfil, sem nome


def test_o_dia_completo_em_cenas_pelo_menu_e_falado() -> None:
    hoje = [
        panorama.Item(MANHA.replace(hour=16, minute=30), "Dentista", "compromisso"),
        panorama.Item(MANHA.replace(hour=14, minute=0), "Reunião da equipe", "compromisso"),
        panorama.Item(MANHA.replace(hour=18, minute=0), "Relatório", "automacao"),
    ]
    sessoes = [
        panorama.SessaoParada("Loja", "interrompida"),
        panorama.SessaoParada("Site", "trabalhando"),
    ]
    conversas = [panorama.Conversa("Ana", MANHA.timestamp() - 7200)]
    manchetes = [noticias.Noticia(f"Manchete {i}", "G1") for i in range(6)]
    dia = panorama.montar(MANHA, "Ana", CLIMA, hoje, sessoes, conversas, manchetes)
    blocos = {b["tipo"]: b for b in dia["blocos"]}
    # a hora e o clima; a agenda; as redes sociais; a atividade; as pendências; as manchetes
    assert list(blocos) == ["agora", "hoje", "redes", "atividade", "pendencias", "noticias", "fim"]
    assert blocos["agora"]["fala"] == (
        "Bom dia, Ana. Hoje é quarta-feira, 11 de novembro. "
        "Em Fortaleza, faz 30 graus, com garoa fraca, e 40 por cento de chance de chuva."
    )
    assert blocos["agora"]["clima"]["cidade"] == "Fortaleza"
    assert blocos["hoje"]["fala"] == (
        "Hoje você tem dois compromissos: às 14 horas, Reunião da equipe e às 16 horas e 30, "
        "Dentista. E roda uma automação."
    )
    assert [i["hora"] for i in blocos["hoje"]["itens"]] == ["14:00", "16:30", "18:00"]
    assert blocos["hoje"]["foco"] is None
    assert blocos["redes"]["fala"] == "No WhatsApp, uma conversa espera resposta: Ana."
    assert blocos["redes"]["whatsapp"] == {
        "itens": [{"nome": "Ana", "ha": "há 2 h", "min": 120}],
        "total": 1,
    }
    assert blocos["redes"]["instagram"] is None
    # a sessão que trabalha é atividade; a que parou pede quem usa
    assert blocos["atividade"]["sessoes"] == ["Site"]
    assert blocos["atividade"]["fala"] == "Uma sessão de código está trabalhando: Site."
    assert blocos["pendencias"]["itens"] == [
        {"area": "Sessões", "titulo": "Loja", "detalhe": "Interrompida", "nivel": "alerta"}
    ]
    assert blocos["pendencias"]["fala"] == "Um item pede você: a sessão Loja parou no meio."
    assert len(blocos["noticias"]["itens"]) == panorama.MOSTRADOS
    assert blocos["noticias"]["fala"] == "Nas manchetes de hoje: Manchete 0."
    assert blocos["fim"]["fala"] == panorama.FECHAMENTO
    # toda fala da abertura é reconhecida pelo jeito (nunca volta como aviso)
    assert all(panorama.JEITO_DE_FALA.match(b["fala"]) for b in dia["blocos"])


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
    assert list(blocos) == ["agora", "hoje", "redes", "fim"]
    assert blocos["hoje"]["fala"] == "No foco, o próximo passo é subir as fotos."
    sem_passo = panorama.montar(MANHA, foco=foco._replace(proximo_passo=""))["blocos"][1]
    assert sem_passo["fala"] == "No foco, você estava em Lançar a loja."
    assert (blocos["hoje"]["foco"]["ativas"], blocos["hoje"]["foco"]["feitas_semana"]) == (2, 3)
    assert blocos["hoje"]["itens"] == []
    instagram = blocos["redes"]["instagram"]
    assert blocos["redes"]["fala"] == (
        "No Instagram, você tem 15,3 mil seguidores e duas publicações nesta semana."
    )
    # o gráfico: da mais antiga para a mais nova; o destaque é o melhor da semana
    assert [g["valor"] for g in instagram["grafico"]] == [30000, 4000, 12000]
    assert instagram["destaque"] == {"legenda": "Promoção de novembro", "valor": "12 mil"}
    assert instagram["semana"] == 2
    parado = panorama.Instagram("ana.loja", 980, [])
    assert panorama.montar(MANHA, instagram=parado)["blocos"][1]["fala"] == (
        "No Instagram, você tem 980 seguidores, sem publicação nova nesta semana."
    )
    # sem frente nenhuma e sem agenda, não há a cena de hoje
    vazio = panorama.Foco("", "", 0, 0, 0, 0)
    assert "hoje" not in [b["tipo"] for b in panorama.montar(MANHA, foco=vazio)["blocos"]]


def test_no_whatsapp_o_ze_fala_nomes_nunca_numeros() -> None:
    # Visto em 11/11/2026: "quatro conversas", três citadas, e um telefone lido dígito a dígito.
    agora = MANHA.timestamp()
    conversas = [
        panorama.Conversa("Ana", agora - 60),
        panorama.Conversa("5511999990000", agora - 120),
        panorama.Conversa("Bia", agora - 180),
        panorama.Conversa("Caio", agora - 240),
        panorama.Conversa("Duda", agora - 300),
    ]
    fala = panorama.montar(MANHA, conversas=conversas)["blocos"][1]["fala"]
    assert fala == "No WhatsApp, cinco conversas esperam resposta: Ana, Bia e mais três."
    so_numeros = [panorama.Conversa("+55 11 99999-0000".replace("-", ""), agora - 60)]
    assert panorama.montar(MANHA, conversas=so_numeros)["blocos"][1]["fala"] == (
        "No WhatsApp, uma conversa espera resposta."
    )
    # no painel, o contato aparece como o WhatsApp o mostra
    assert panorama.montar(MANHA, conversas=conversas)["blocos"][1]["whatsapp"]["total"] == 5


def test_a_atividade_e_as_pendencias_levam_a_secao_do_menu() -> None:
    atividade = panorama.Atividade(
        120, 340, 12, [("2026-11-10", 50, 2), ("2026-11-11", 30, 1)], automacoes=2
    )
    pedem = panorama.pendencias(
        [panorama.SessaoParada("Site", "erro"), panorama.SessaoParada("Zérvis", "trabalhando")],
        ["Backup"],
        melhorias=2,
        sugestoes=1,
        atualizacao=True,
    )
    # do mais grave para o menos; a sessão trabalhando não é pendência
    assert [(x.area, x.nivel) for x in pedem] == [
        ("Sessões", "critico"),
        ("Automações", "critico"),
        ("Autodesenvolvimento", "info"),
        ("Memória", "info"),
        ("Atualizações", "info"),
    ]
    dia = panorama.montar(MANHA, atividade=atividade, pedem=pedem)
    blocos = {b["tipo"]: b for b in dia["blocos"]}
    assert blocos["atividade"]["fala"] == (
        "Nos últimos sete dias, atendi 120 pedidos e executei 340 ações, com 12 falhas. "
        "Hoje duas automações rodaram."
    )
    assert blocos["atividade"]["por_dia"][-1] == {"dia": "2026-11-11", "registros": 30, "falhas": 1}
    assert blocos["pendencias"]["total"] == 5
    assert blocos["pendencias"]["areas"][0] == {"area": "Sessões", "n": 1}
    assert blocos["pendencias"]["fala"] == (
        "Cinco itens pedem você: a sessão Site parou com erro, a automação Backup falhou, "
        "há duas melhorias prontas para aprovar e mais dois itens."
    )
    assert all(panorama.JEITO_DE_FALA.match(b["fala"]) for b in dia["blocos"])
    # sem nada feito e sem nada esperando, as duas cenas não entram
    parado = panorama.montar(MANHA, atividade=panorama.Atividade(0, 0, 0))
    assert [b["tipo"] for b in parado["blocos"]] == ["agora", "fim"]


def test_o_clima_cruza_com_a_agenda() -> None:
    # chove a partir das 14h: o Zé diz a hora e avisa do compromisso que cai nela
    chuva = tuple([10] * 14 + [70] * 10)
    molhado = CLIMA._replace(chuva=80, chuva_horas=chuva)
    hoje = [
        panorama.Item(MANHA.replace(hour=10, minute=0), "Café", "compromisso"),
        panorama.Item(MANHA.replace(hour=15, minute=0), "Reunião", "compromisso"),
    ]
    blocos = panorama.montar(MANHA, clima=molhado, hoje=hoje)["blocos"]
    assert blocos[0]["fala"].endswith("e 80 por cento de chance de chuva, a partir das 14 horas.")
    assert blocos[1]["fala"] == (
        "Hoje você tem dois compromissos: às 10 horas, Café e às 15 horas, Reunião. "
        "Há chuva prevista para a hora de Reunião."
    )
    assert [i["chuva"] for i in blocos[1]["itens"]] == [False, True]
    # já chovendo agora, a hora não precisa ser dita
    agora = panorama.montar(MANHA.replace(hour=15), clima=molhado)["blocos"][0]["fala"]
    assert agora.endswith("e 80 por cento de chance de chuva.")


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
    assert panorama.montar(MANHA, clima=seco)["blocos"][0]["fala"] == (
        "Bom dia. Hoje é quarta-feira, 11 de novembro. Em Fortaleza, faz 30 graus."
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
            "current": {"temperature_2m": 30.4, "weather_code": 51, "is_day": 1},
            "daily": {"temperature_2m_max": [31.1], "temperature_2m_min": [24.2],
                      "precipitation_probability_max": [40]},
            "hourly": {"temperature_2m": [24.4, 25.1, None], "precipitation_probability": [5, 60]},
        }  # fmt: skip

    lugar = clima.localizar("Fortaleza", obter)
    assert lugar == clima.Lugar("Fortaleza", "Ceará", -3.7, -38.5)
    # a temperatura e a chance de chuva de cada hora, e o desenho do céu
    assert clima.buscar(lugar, obter) == CLIMA._replace(horas=(24, 25), chuva_horas=(5, 60))
    assert "precipitation_probability" in pedidos[1] and "is_day" in pedidos[1]
    assert [clima.icone(c, d) for c, d in ((0, True), (1, False), (2, True), (3, True), (45, True),
                                           (63, True), (73, True), (95, True))] == [
        "sol", "lua", "nuvens", "nublado", "neblina", "chuva", "neve", "trovoada"]  # fmt: skip
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

    def job(nome: str, quando: datetime | None, ativo: bool = True, **campos: Any) -> Any:
        base = {"ultima": "", "ultimo_status": "nunca"}
        return SimpleNamespace(
            nome=nome,
            ativo=ativo,
            proxima=quando.isoformat() if quando else "",
            **{**base, **campos},
        )

    jobs = SimpleNamespace(
        listar=lambda: [
            job("Relatório", agora + timedelta(hours=3)),
            job("Amanhã", agora + timedelta(days=1)),
            job("Pausada", agora + timedelta(hours=1), ativo=False),
            job("Já foi", agora - timedelta(hours=1), ultima=agora.isoformat(), ultimo_status="ok"),
            job(
                "Backup", None, ultima=(agora - timedelta(days=1)).isoformat(), ultimo_status="erro"
            ),
            job("Erro antigo", None, ativo=False, ultimo_status="erro"),
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
        pendencias=SimpleNamespace(listar=lambda: ["uma sugestão", "outra"]),
        versoes=SimpleNamespace(foto=lambda: {"disponivel": True, "rodando": False}),
        historico=lambda dias: SimpleNamespace(
            dias=dias,
            contagem={"pedido": 12, "execucao": 40, "falha": 3, "negada": 1},
            por_dia=[SimpleNamespace(dia=agora.date().isoformat(), registros=20, falhas=1)],
        ),
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


def test_a_coleta_traz_a_atividade_e_o_que_espera_no_menu(tmp_path: Path) -> None:
    agora = datetime.now(FUSO).replace(hour=9, minute=0, second=0, microsecond=0)
    fontes = _fontes(tmp_path, agora)
    partes = servico.coletar(fontes, agora, melhorias=2)
    # o que o Zé fez em sete dias, e só a automação que rodou hoje
    assert partes["atividade"] == panorama.Atividade(
        12, 40, 3, [(agora.date().isoformat(), 20, 1)], automacoes=1, dias=7
    )
    # a automação ativa que falhou, as melhorias, as sugestões de memória e a atualização
    assert [(x.area, x.titulo, x.detalhe) for x in partes["pedem"]] == [
        ("Automações", "Backup", "Falhou"),
        ("Autodesenvolvimento", "Melhorias prontas", "2 para aprovar"),
        ("Memória", "Sugestões", "2 para decidir"),
        ("Atualizações", "Nova versão", "Disponível"),
    ]
    # uma fonte que falha só tira o item dela
    fontes.versoes.foto = lambda: (_ for _ in ()).throw(OSError("git"))
    del fontes.historico
    partes = servico.coletar(fontes, agora)
    assert partes["atividade"] is None
    assert [x.area for x in partes["pedem"]] == ["Automações", "Memória"]


def test_as_melhorias_prontas_sao_contadas_fora_do_laco() -> None:
    contadas = [3]
    externas = Externas(
        localizar=lambda c: None, buscar_noticias=lambda: [], melhorias=lambda: contadas[0]
    )
    externas.renovar("", 0.0)
    externas.esperar()
    assert externas.melhorias == 3
    externas._contar_melhorias = lambda: (_ for _ in ()).throw(OSError("git"))
    externas.renovar("", 1e9)
    externas.esperar()
    assert externas.melhorias == 3  # sem conseguir contar, fica a última


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
    assert tipos[0] == "agora" and tipos[-1] == "fim"
    assert {"redes", "atividade", "pendencias", "noticias"} <= set(tipos)
    assert dia["blocos"][0]["clima"]["cidade"] == "Recife"
    assert dia["ligada"] is True and dia["musica"] is False
    assert rotas.panorama(tmp_path) == dia


def test_o_primeiro_panorama_diz_que_falta_o_de_fora(abertura: Abertura, tmp_path: Path) -> None:
    # Visto em 11/11/2026: abrir o programa sobe o Zé, e a página leu o panorama gravado antes
    # da primeira busca de fora (sem clima, Instagram nem manchetes): só três cards.
    solta = threading.Event()
    buscar = abertura.externas._noticias
    abertura.externas._noticias = lambda: (solta.wait(5), buscar())[1]
    abertura.retratar(time.time())
    primeiro = rotas.panorama(tmp_path)
    assert primeiro["completo"] is False
    assert "noticias" not in [b["tipo"] for b in primeiro["blocos"]]
    solta.set()
    abertura.externas.esperar()
    abertura.retratar(time.time())
    dia = rotas.panorama(tmp_path)
    assert dia["completo"] is True
    assert dia["blocos"][0]["clima"] is not None
    assert "noticias" in [b["tipo"] for b in dia["blocos"]]


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


def test_a_fala_de_uma_cena_sai_inteira_nunca_como_manchete(
    abertura: Abertura, tmp_path: Path
) -> None:
    from zervis.avisos import modo
    from zervis.nucleo import voz_tipos
    from zervis.nucleo.servicos.avisos import ServicoAvisos

    # Visto em 11/11/2026: com as cenas, as falas passaram de 30 palavras, e a regra dos avisos
    # longos cortava cada uma e dizia "O resto está na tela".
    longa = "Bom dia, Ana. Hoje é quarta-feira, 11 de novembro. " + "E mais uma coisa do dia. " * 8
    assert modo.manchete(longa).endswith("O resto está na tela.")
    abertura._faladas.add(longa.strip())
    na_tela: list[str] = []
    n: Any = SimpleNamespace(
        abertura=abertura, avisos_lidos={}, _avisos_dados={}, _comecados={}, _cortados=set(),
        _na_tela=set(), _meta={}, _na_linha=lambda tipo, texto: na_tela.append(texto),
    )  # fmt: skip
    pedido = voz_tipos.Aviso(longa.strip(), pedido=True)
    assert ServicoAvisos(n)._regras_de_fala(pedido) is pedido  # inteira, e segue "pedida"
    assert na_tela == []  # o painel da cena já está na tela: o texto não vira linha de aviso
    # um aviso comum do mesmo tamanho continua virando manchete
    comum = ServicoAvisos(n)._regras_de_fala(voz_tipos.Aviso("O relatório ficou pronto. " * 12))
    assert comum is not None and comum.texto.endswith("O resto está na tela.")


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
