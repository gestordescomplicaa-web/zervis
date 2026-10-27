"""Voz pelo ElevenLabs (ADR 0041), um provedor da `zervis/voz/nuvem.py`.

Síntese em streaming (`/v1/text-to-speech/{voz}/stream`, PCM 16 bits a 24 kHz) com o
`eleven_v4_turbo` em português. A chave é conferida listando as vozes da conta (as prontas do
ElevenLabs e as da pessoa). Conta e chave: https://elevenlabs.io/app/settings/api-keys
"""

from typing import Any
from urllib.parse import quote

from zervis.voz import nuvem

NOME = "elevenlabs"
TITULO = "ElevenLabs"
DESCRICAO = "Voz natural, na nuvem. Paga por caractere."
ENDERECO = "https://api.elevenlabs.io"
CADASTRO = "https://elevenlabs.io/app/settings/api-keys"
# v4 Turbo: o recomendado para conversa em tempo real (~100 ms), com o mesmo preço por
# caractere do Flash v2.5 (US$ 0,04 por mil na tabela de 27/10/2026).
MODELO = "eleven_v4_turbo"
TAXA = 24000
IDIOMA = "pt"
CONHECIDOS = {
    "invalid_api_key": "Chave inválida.",
    "quota_exceeded": "Sem créditos no ElevenLabs.",
    "missing_permissions": "A chave não tem permissão para isso.",
    "voice_not_found": "Essa voz não existe mais na conta.",
    "paid_plan_required": "Essa voz exige um plano pago no ElevenLabs.",
}


def motivo(codigo: int, corpo: bytes) -> str:
    """O que o ElevenLabs explica na recusa (`detail.status` e `detail.message`), em uma linha."""
    situacao, mensagem = nuvem.detalhe_do_erro(corpo)
    return CONHECIDOS.get(situacao) or nuvem.recusa_generica(TITULO, codigo, mensagem)


def _cabecalhos(chave: str) -> dict[str, str]:
    return {"xi-api-key": chave}


def _detalhe_da_voz(v: dict[str, Any]) -> str:
    rotulos = v.get("labels") or {}
    traducao = {"male": "masculina", "female": "feminina", "neutral": "neutra"}
    partes = [traducao.get(str(rotulos.get("gender", "")), "")]
    partes += [str(rotulos.get(k, "")) for k in ("accent", "age", "descriptive", "use_case")]
    return ", ".join(p.replace("_", " ") for p in partes if p)


def _fala_portugues(v: dict[str, Any]) -> bool:
    return any(
        str(idioma.get("language", "")).lower().startswith("pt")
        for idioma in v.get("verified_languages") or []
        if isinstance(idioma, dict)
    )


def vozes(chave: str, endereco: str = ENDERECO) -> list[dict[str, str]]:
    """As vozes da conta, as de português primeiro e, nelas, as masculinas ("Zé")."""
    dados = nuvem.obter(endereco, "/v2/voices?page_size=100", _cabecalhos(chave), motivo, TITULO)
    lista = [v for v in dados.get("voices") or [] if isinstance(v, dict) and v.get("voice_id")]
    lista.sort(
        key=lambda v: (
            not _fala_portugues(v),
            (v.get("labels") or {}).get("gender") != "male",
            str(v.get("name", "")).lower(),
        )
    )
    return [
        {"id": str(v["voice_id"]), "nome": str(v.get("name", "")), "detalhe": _detalhe_da_voz(v)}
        for v in lista
    ]


def conta(chave: str, endereco: str = ENDERECO) -> tuple[str, str]:
    """Confere a chave (listar as vozes pede só a permissão de vozes); devolve (modelo, nota)."""
    vozes(chave, endereco)
    return MODELO, ""


def voz_colada(texto: str, chave: str, endereco: str = ENDERECO) -> dict[str, str] | None:
    """As vozes do ElevenLabs vêm da conta; colar link fica para o Fish Audio."""
    return None


def pedido(
    texto: str, voz: str, modelo: str, chave: str
) -> tuple[str, dict[str, Any], dict[str, str]]:
    caminho = f"/v1/text-to-speech/{quote(voz, safe='')}/stream?output_format=pcm_{TAXA}"
    corpo = {"text": texto, "model_id": modelo or MODELO, "language_code": IDIOMA}
    return caminho, corpo, _cabecalhos(chave)
