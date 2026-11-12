"""Projetos 3D (ADR 0082): criar um projeto (uma pasta e a sessão de código que modela a peça),
listar os projetos e mostrar um modelo como sólido na Imersão. Criar pede o sim falado, como
criar uma sessão; listar e mostrar só leem e mexem na própria tela."""

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import projetos3d
from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.cerebro.ferramentas.sessoes import motor_conectado
from zervis.oficina.sessoes import SessaoErro, Sessoes
from zervis.rosto.tela import Tela, TelaErro


def _imagem(caminho: str, acervo: Path | None) -> tuple[bytes, str] | None:
    """A imagem de referência: um caminho no Acervo ("imagens/galo.png") ou na pasta pessoal."""
    if not caminho.strip():
        return None
    bruto = Path(caminho.strip()).expanduser()
    candidatos = [bruto] if bruto.is_absolute() else [(acervo or Path.home()) / bruto]
    for c in candidatos:
        c = c.resolve()
        if not (c.is_relative_to(Path.home().resolve()) and c.is_file()):
            continue
        if c.suffix.lower() not in projetos3d.IMAGENS or c.stat().st_size > projetos3d.MAX_IMAGEM:
            raise projetos3d.Projeto3DErro("Imagem inválida: PNG, JPG ou WebP, até 20 MB.")
        return c.read_bytes(), c.name
    raise projetos3d.Projeto3DErro("Imagem não encontrada.")


def ferramentas(
    projetos: projetos3d.Projetos3D | None,
    sessoes: Sessoes | None,
    tela: Tela | None,
    acervo: Path | None = None,
) -> list[SdkMcpTool[Any]]:
    if projetos is None:
        return []

    @tool(
        "projetos3d_listar",
        "Os projetos 3D (aba Projetos 3D): nome, tipo, a sessão que trabalha nele e os arquivos, "
        "com as medidas de cada STL (tamanho em mm, volume, se a malha é fechada).",
        {"type": "object", "properties": {}},
    )
    async def listar(args: dict[str, Any]) -> dict[str, Any]:
        lista = await asyncio.to_thread(projetos.listar)
        return _texto(
            {
                "projetos": [
                    {k: p[k] for k in ("id", "nome", "tipo_nome", "sessao", "arquivos")}
                    for p in lista
                ]
            }
        )

    @tool(
        "projeto3d_criar",
        "Cria um projeto 3D: uma pasta na aba Projetos 3D e uma sessão de código que modela a "
        "peça e entrega os STLs. tipo peca: peça funcional, modelada por código com medidas "
        "(suporte, caixa, encaixe); o pedido precisa das medidas e do uso. tipo arte: relevo a "
        "partir de uma imagem, pela pipeline de arte de quem usa; imagem é o caminho dela no "
        "Acervo (imagens/...) ou na pasta pessoal. Não imprime nada. O Zé avisa quando a sessão "
        "terminar; depois, projeto3d_mostrar põe a peça na Imersão.",
        {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome curto: Suporte de celular"},
                "tipo": {"type": "string", "enum": list(projetos3d.TIPOS)},
                "pedido": {"type": "string", "description": "O que modelar, com medidas e uso"},
                "imagem": {"type": "string", "description": "Só no tipo arte"},
            },
            "required": ["nome", "tipo", "pedido"],
        },
    )
    async def criar(args: dict[str, Any]) -> dict[str, Any]:
        if sessoes is None:
            return _erro(SessaoErro("as sessões de código não estão disponíveis"))

        def fazer() -> dict[str, Any]:
            imagem = _imagem(str(args.get("imagem") or ""), acervo)
            p = projetos.criar(
                str(args.get("nome", "")),
                str(args.get("tipo", "")),
                str(args.get("pedido", "")),
                *(imagem or (None, "")),
            )
            sessao = projetos3d.comecar(projetos, sessoes, p["id"], motor_conectado(), "voz")
            return {"criado": True, "projeto": p["id"], "sessao": sessao, "pasta": p["pasta"]}

        try:
            return _texto(await asyncio.to_thread(fazer))
        except (projetos3d.Projeto3DErro, SessaoErro) as erro:
            return _erro(erro)

    @tool(
        "projeto3d_mostrar",
        "Mostra um modelo de um projeto 3D na Imersão, como sólido (cor de mármore), num cartão "
        "que a pinça gira. Sem arquivo, o principal (modelo.stl, senão o STL maior).",
        {
            "type": "object",
            "properties": {
                "projeto": {"type": "string", "description": "O id, de projetos3d_listar"},
                "arquivo": {"type": "string", "description": "Um STL ou GLB do projeto"},
            },
            "required": ["projeto"],
        },
    )
    async def mostrar(args: dict[str, Any]) -> dict[str, Any]:
        id_ = str(args.get("projeto", ""))
        try:
            previa = await asyncio.to_thread(projetos.previa, id_, str(args.get("arquivo") or ""))
            nome = (await asyncio.to_thread(projetos.ler, id_))["nome"]
        except projetos3d.Projeto3DErro as erro:
            return _erro(erro)
        if tela is None:
            return _texto({"previa": previa, "mostrado": "tela indisponível"})
        acao = {"acao": "mostrar_modelo", "alvo": previa, "valor": nome, "estilo": "solido"}
        try:
            r = await asyncio.to_thread(tela.agir, [acao])
        except (TelaErro, OSError) as erro:
            return _texto({"previa": previa, "mostrado": f"não: {erro}"})
        feito = (r.get("resultados") or [{}])[0]
        return _texto({"previa": previa, "mostrado": bool(feito.get("ok"))})

    return [listar, criar, mostrar]
