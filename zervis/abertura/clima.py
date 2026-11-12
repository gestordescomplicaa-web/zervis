"""O clima de hoje pelo Open-Meteo (open-meteo.com): sem chave, sem conta, sem tokens.

Dois pedidos: a cidade vira coordenadas (geocodificação, guardada) e as coordenadas viram o tempo
de agora e o do dia. Qualquer falha devolve None: a abertura só não mostra o clima.
"""

import json
import logging
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any, NamedTuple

log = logging.getLogger(__name__)
AGENTE = "Ze/1 (Zervis)"
GEOCODIFICAR = "https://geocoding-api.open-meteo.com/v1/search"
PREVISAO = "https://api.open-meteo.com/v1/forecast"
PRAZO_S = 6.0

# Os códigos WMO do Open-Meteo, em português.
CEU = {
    0: "céu limpo",
    1: "poucas nuvens",
    2: "parcialmente nublado",
    3: "nublado",
    45: "neblina",
    48: "neblina",
    51: "garoa fraca",
    53: "garoa",
    55: "garoa forte",
    56: "garoa congelante",
    57: "garoa congelante",
    61: "chuva fraca",
    63: "chuva",
    65: "chuva forte",
    66: "chuva congelante",
    67: "chuva congelante",
    71: "neve fraca",
    73: "neve",
    75: "neve forte",
    77: "neve",
    80: "pancadas de chuva",
    81: "pancadas de chuva",
    82: "pancadas fortes de chuva",
    85: "pancadas de neve",
    86: "pancadas de neve",
    95: "trovoadas",
    96: "trovoadas com granizo",
    99: "trovoadas com granizo",
}


def icone(codigo: int, de_dia: bool = True) -> str:
    """O desenho do céu para o painel, pelo código WMO."""
    if codigo in (0, 1):
        return "sol" if de_dia else "lua"
    if codigo == 2:
        return "nuvens"
    if codigo == 3:
        return "nublado"
    if codigo in (45, 48):
        return "neblina"
    if codigo in (71, 73, 75, 77, 85, 86):
        return "neve"
    if codigo >= 95:
        return "trovoada"
    return "chuva" if codigo >= 51 else ""


Obter = Callable[[str], Any]  # a URL -> o JSON (os testes trocam pela resposta pronta)


class Lugar(NamedTuple):
    nome: str
    regiao: str
    latitude: float
    longitude: float


class Clima(NamedTuple):
    cidade: str
    temperatura: int
    ceu: str
    maxima: int
    minima: int
    chuva: int  # a chance de chuva no dia, em %
    horas: tuple[int, ...] = ()  # a temperatura de cada hora do dia (0h a 23h), para o gráfico
    chuva_horas: tuple[int, ...] = ()  # a chance de chuva de cada hora, em %
    icone: str = ""  # "sol", "lua", "nuvens", "nublado", "neblina", "chuva", "neve", "trovoada"


def obter_json(url: str) -> Any:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})  # noqa: S310 (https fixo)
    with urllib.request.urlopen(pedido, timeout=PRAZO_S) as resposta:  # noqa: S310
        return json.loads(resposta.read())


def localizar(cidade: str, obter: Obter = obter_json) -> Lugar | None:
    consulta = urllib.parse.urlencode({"name": cidade, "count": 1, "language": "pt"})
    try:
        achado = (obter(f"{GEOCODIFICAR}?{consulta}").get("results") or [None])[0]
        if not achado:
            return None
        return Lugar(
            str(achado["name"]),
            str(achado.get("admin1") or ""),
            float(achado["latitude"]),
            float(achado["longitude"]),
        )
    except Exception:
        log.info("abertura: a cidade %r não foi localizada", cidade, exc_info=True)
        return None


def _horas(dados: Any, serie: str) -> list[Any]:
    return [t for t in ((dados.get("hourly") or {}).get(serie) or [])[:24] if t is not None]


def buscar(lugar: Lugar, obter: Obter = obter_json) -> Clima | None:
    consulta = urllib.parse.urlencode(
        {
            "latitude": lugar.latitude,
            "longitude": lugar.longitude,
            "current": "temperature_2m,weather_code,is_day",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "hourly": "temperature_2m,precipitation_probability",
            "timezone": "auto",
            "forecast_days": 1,
        }
    )
    try:
        dados = obter(f"{PREVISAO}?{consulta}")
        agora, dia = dados["current"], dados["daily"]
        return Clima(
            lugar.nome,
            round(float(agora["temperature_2m"])),
            CEU.get(int(agora.get("weather_code", -1)), ""),
            round(float(dia["temperature_2m_max"][0])),
            round(float(dia["temperature_2m_min"][0])),
            int(dia.get("precipitation_probability_max", [0])[0] or 0),
            tuple(round(float(t)) for t in _horas(dados, "temperature_2m")),
            tuple(round(float(t)) for t in _horas(dados, "precipitation_probability")),
            icone(int(agora.get("weather_code", -1)), bool(agora.get("is_day", 1))),
        )
    except Exception:
        log.info("abertura: o clima não veio", exc_info=True)
        return None
