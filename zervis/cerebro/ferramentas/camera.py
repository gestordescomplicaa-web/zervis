"""Ferramentas de leitura da câmera local (plano-camera)."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import camera, fuso
from zervis.camera_vigia import Vigia
from zervis.cerebro.ferramentas.comum import _erro, _texto


def ferramentas(
    dispositivo: camera.Camera | None,
    vigia: Vigia | None,
    mostrar: Any = None,
) -> list[SdkMcpTool[Any]]:
    if dispositivo is None or vigia is None:
        return []

    @tool(
        "camera_foto",
        "Tira e guarda uma foto agora da câmera cadastrada (uma por lente, se ela tiver várias), "
        "devolvendo os caminhos e a hora. Use mostrar=true apenas quando a pessoa pedir para ver "
        "ou receber a imagem.",
        {
            "type": "object",
            "properties": {
                "mostrar": {"type": "boolean", "description": "Envie a imagem só se pediram."}
            },
        },
    )
    async def foto(args: dict[str, Any]) -> dict[str, Any]:
        try:
            caminhos = await asyncio.to_thread(vigia.fotos_agora)
        except camera.CameraErro as erro:
            return _erro(erro)
        entrega = ""
        if bool(args.get("mostrar")) and mostrar is not None:
            for caminho in caminhos:
                entrega = await asyncio.to_thread(mostrar, caminho, "Foto da câmera") or entrega
        quando = datetime.fromtimestamp(caminhos[0].stat().st_mtime, fuso.local()).isoformat(
            timespec="seconds"
        )
        return _texto(
            {"fotos": [str(c) for c in caminhos], "quando": quando, "mostrada": bool(entrega)}
        )

    @tool(
        "camera_movimentos",
        "Lista as fotos guardadas por movimento, da mais nova para a mais antiga, com horário. "
        "Use mostrar=true apenas quando a pessoa pedir para ver ou receber a foto mais recente.",
        {
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "minimum": 1, "maximum": 50},
                "mostrar": {
                    "type": "boolean",
                    "description": "Envie a foto mais recente só se pediram.",
                },
            },
        },
    )
    async def movimentos(args: dict[str, Any]) -> dict[str, Any]:
        limite = max(1, min(50, int(args.get("limite", 10) or 10)))
        fotos = await asyncio.to_thread(vigia.fotos)
        recentes = fotos[:limite]
        if bool(args.get("mostrar")) and recentes and mostrar is not None:
            try:
                caminho = await asyncio.to_thread(vigia.ler_foto, Path(recentes[0]["nome"]).name)
                recentes[0]["mostrada"] = bool(
                    await asyncio.to_thread(mostrar, caminho, "Foto da câmera")
                )
            except camera.CameraErro as erro:
                return _erro(erro)
        return _texto(
            {
                "fotos": [
                    {
                        "nome": foto["nome"],
                        "quando": datetime.fromtimestamp(foto["quando"], fuso.local()).isoformat(
                            timespec="seconds"
                        ),
                        **({"mostrada": foto["mostrada"]} if "mostrada" in foto else {}),
                    }
                    for foto in recentes
                ]
            }
        )

    return [foto, movimentos]
