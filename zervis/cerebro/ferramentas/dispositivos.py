"""Os dispositivos da casa para a voz (ADR 0089): quais há e como estão."""

from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import dispositivos
from zervis.cerebro.ferramentas.comum import _texto


def ferramentas(
    camera: Any, vigia_camera: Any, impressora: Any, tela_tv: Any
) -> list[SdkMcpTool[Any]]:
    if camera is None and impressora is None and tela_tv is None:
        return []

    @tool(
        "dispositivos_listar",
        "Os aparelhos da casa que o Zé usa pela rede local (câmera, impressora 3D, TV), com o "
        "estado de cada um. Use para 'quais dispositivos você tem', 'a câmera está conectada?'. "
        "Para agir num deles, use as ferramentas próprias (camera_*, impressora_*, tela_tv_*).",
        {"type": "object", "properties": {}},
    )
    async def listar(_args: dict[str, Any]) -> dict[str, Any]:
        lista = dispositivos.listar(camera, vigia_camera, impressora, tela_tv)
        if not lista:
            return _texto("Nenhum dispositivo adicionado. Adicione em Dispositivos, no painel.")
        return _texto(
            {"dispositivos": [{k: d[k] for k in ("nome", "estado", "detalhe")} for d in lista]}
        )

    return [listar]
