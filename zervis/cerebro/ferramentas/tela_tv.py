"""O Modo TV (ADR 0084): mostrar na TV da casa uma peça de um projeto 3D ou um modelo do Acervo,
e fechar. Só mexem na TV de quem usa, no navegador dela, e voltam atrás fechando: passam sem
perguntar, como a própria tela do Zé."""

import asyncio
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import projetos3d
from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.tv import TelaTV, TVErro


def _medidas(projeto: dict[str, Any], arquivo: str) -> str:
    for a in projeto["arquivos"]:
        if a["nome"] == arquivo and a.get("medidas"):
            x, y, z = (round(v) for v in a["medidas"]["tamanho_mm"])
            return f"{x} × {y} × {z} mm"  # noqa: RUF001 (o sinal de vezes, na tela da TV)
    return ""


def mostrar_projeto(
    tela: TelaTV, projetos: projetos3d.Projetos3D, id_: str, arquivo: str = ""
) -> dict[str, Any]:
    """A peça do projeto como sólido na TV, com o nome e as medidas; abre o navegador se preciso."""
    arquivo = arquivo or projetos.principal(id_)
    previa = projetos.previa(id_, arquivo)
    p = projetos.ler(id_)
    tela.mostrar_modelo(previa, p["nome"], _medidas(p, arquivo))
    tela.abrir()
    return {"mostrado": p["nome"], "na_tv": True}


def ferramentas(
    tela: TelaTV | None, projetos: projetos3d.Projetos3D | None
) -> list[SdkMcpTool[Any]]:
    if tela is None:
        return []

    @tool(
        "tela_tv_mostrar",
        "Mostra na TV da casa (Modo TV), em 3D sólido girando com o nome e as medidas: a peça de "
        "um projeto 3D (projeto, o id de projetos3d_listar; arquivo opcional) ou um modelo do "
        "Acervo (modelo: o arquivo 3d/...glb que modelo3d_baixar devolveu, com titulo). Abre o "
        "navegador da TV se ele estiver fechado. Para quem pede 'mostra na TV'.",
        {
            "type": "object",
            "properties": {
                "projeto": {"type": "string"},
                "arquivo": {"type": "string"},
                "modelo": {"type": "string"},
                "titulo": {"type": "string"},
            },
        },
    )
    async def mostrar(args: dict[str, Any]) -> dict[str, Any]:
        def fazer() -> dict[str, Any]:
            if projeto := str(args.get("projeto") or ""):
                if projetos is None:
                    raise TVErro("Projetos 3D indisponíveis.")
                return mostrar_projeto(tela, projetos, projeto, str(args.get("arquivo") or ""))
            modelo = str(args.get("modelo") or "")
            if not modelo:
                raise TVErro("Diga o projeto ou o modelo.")
            tela.mostrar_modelo(modelo, str(args.get("titulo") or ""))
            tela.abrir()
            return {"mostrado": modelo, "na_tv": True}

        try:
            return _texto(await asyncio.to_thread(fazer))
        except (TVErro, projetos3d.Projeto3DErro) as erro:
            return _erro(erro)

    @tool(
        "tela_tv_fechar",
        "Fecha o Modo TV: o navegador da TV fecha e a TV volta ao que estava.",
        {"type": "object", "properties": {}},
    )
    async def fechar(args: dict[str, Any]) -> dict[str, Any]:
        await asyncio.to_thread(tela.fechar)
        return _texto({"fechado": True})

    return [mostrar, fechar]
