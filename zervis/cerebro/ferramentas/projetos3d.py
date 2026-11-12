"""Projetos 3D (ADR 0082 e 0083): criar um projeto (uma pasta e a sessão de código que modela a
peça), listar, mostrar como sólido na Imersão, fatiar e imprimir. Criar, imprimir e mandar um
comando à impressora pedem o sim falado; listar, mostrar, fatiar e ver a impressora não mexem em
nada fora do Zé."""

import asyncio
import base64
from pathlib import Path
from typing import Any

from claude_agent_sdk import SdkMcpTool, tool

from zervis import projetos3d
from zervis.cerebro.ferramentas.comum import _erro, _texto
from zervis.cerebro.ferramentas.sessoes import motor_conectado
from zervis.impressora3d import COMANDOS, Impressora3D, ImpressoraErro
from zervis.oficina.sessoes import SessaoErro, Sessoes
from zervis.rosto.tela import Tela, TelaErro

# Onde a foto da câmera apareceu para quem pediu (ADR 0086), dito ao cérebro no resultado.
ENTREGA_DA_FOTO = {
    "celular": "A foto foi enviada ao celular de quem pediu, numa notificação.",
    "navegador": "A foto abriu na tela de quem pediu, no painel.",
    "": "Ninguém fala de outro aparelho agora: a foto não foi enviada; no painel, Projetos 3D, "
    "Ver câmera mostra a imagem.",
}


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
    impressora: Impressora3D | None = None,
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
        "terminar; depois, projeto3d_mostrar põe a peça na Imersão. Para mudar uma peça que já "
        "existe, não crie outro projeto: mande o pedido à sessão dele (sessao_enviar, com o id de "
        "sessão de projetos3d_listar).",
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

    ferramentas_impressao = _impressao(projetos, impressora)
    return [listar, criar, mostrar, *ferramentas_impressao]


def _impressao(
    projetos: projetos3d.Projetos3D, impressora: Impressora3D | None
) -> list[SdkMcpTool[Any]]:
    if impressora is None:
        return []

    @tool(
        "projeto3d_fatiar",
        "Fatia o STL de um projeto para a impressora, com o filamento que está nela: devolve o "
        "tempo, os gramas, o filamento e a bandeja, e a frase pronta (fala). Faça antes de "
        "imprimir e diga a fala a quem usa. Sem arquivo, o principal.",
        {
            "type": "object",
            "properties": {"projeto": {"type": "string"}, "arquivo": {"type": "string"}},
            "required": ["projeto"],
        },
    )
    async def fatiar(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _texto(
                await asyncio.to_thread(
                    projetos3d.fatiar,
                    projetos,
                    impressora,
                    str(args.get("projeto", "")),
                    str(args.get("arquivo") or ""),
                )
            )
        except projetos3d.Projeto3DErro as erro:
            return _erro(erro)

    @tool(
        "projeto3d_imprimir",
        "Manda a peça fatiada para a impressora e começa a imprimir. Antes: projeto3d_fatiar e a "
        "fala dele para quem usa, que aprova pela voz. Só com a impressora parada; o Zé avisa "
        "quando a impressão termina.",
        {
            "type": "object",
            "properties": {"projeto": {"type": "string"}, "arquivo": {"type": "string"}},
            "required": ["projeto"],
        },
    )
    async def imprimir(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _texto(
                await asyncio.to_thread(
                    projetos3d.imprimir,
                    projetos,
                    impressora,
                    str(args.get("projeto", "")),
                    str(args.get("arquivo") or ""),
                )
            )
        except projetos3d.Projeto3DErro as erro:
            return _erro(erro)

    @tool(
        "impressora_status",
        "Como está a impressora 3D: parada, imprimindo (com a porcentagem e o tempo que falta), "
        "pausada, concluída, cancelada ou com falha (com o código do erro); as temperaturas, o "
        "filamento de cada bandeja e os últimos avisos do vigia (o Zé já avisa sozinho dos erros, "
        "da primeira camada e do fim).",
        {"type": "object", "properties": {}},
    )
    async def status(args: dict[str, Any]) -> dict[str, Any]:
        try:
            agora = await asyncio.to_thread(impressora.status)
        except ImpressoraErro as erro:
            return _erro(erro)
        recentes = [{k: a[k] for k in ("quando", "fala", "texto")} for a in impressora.avisos()[:3]]
        return _texto({**agora, "avisos_recentes": recentes})

    @tool(
        "impressora_foto",
        "Uma foto agora da câmera da impressora 3D: para ver a peça na mesa, conferir a primeira "
        "camada ou entender um erro, e para mandar a foto a quem pede ('me manda uma foto da "
        "impressão'): quem fala pelo celular ou pelo navegador recebe a foto na tela na hora. O "
        "resultado diz onde ela apareceu. A foto fica guardada no Zé.",
        {"type": "object", "properties": {}},
    )
    async def foto(args: dict[str, Any]) -> dict[str, Any]:
        if impressora.fotografar is None:
            return _erro(ImpressoraErro("Câmera indisponível."))
        try:
            caminho = await asyncio.to_thread(impressora.fotografar)
        except (ImpressoraErro, OSError) as erro:
            return _erro(ImpressoraErro(f"Sem foto da câmera ({erro})."))
        imagem = base64.b64encode(caminho.read_bytes()).decode()
        onde = ""
        if impressora.mostrar is not None:
            onde = await asyncio.to_thread(impressora.mostrar, caminho, "Câmera da impressora")
        entrega = ENTREGA_DA_FOTO.get(onde, ENTREGA_DA_FOTO[""])
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Foto da câmera da impressora ({caminho.name}). {entrega}",
                },
                {"type": "image", "data": imagem, "mimeType": "image/jpeg"},
            ]
        }

    @tool(
        "impressora_comando",
        "Pausa, retoma ou para a impressão em andamento. Parar cancela a impressão.",
        {
            "type": "object",
            "properties": {"comando": {"type": "string", "enum": list(COMANDOS)}},
            "required": ["comando"],
        },
    )
    async def comando(args: dict[str, Any]) -> dict[str, Any]:
        try:
            await asyncio.to_thread(impressora.comando, str(args.get("comando", "")))
        except ImpressoraErro as erro:
            return _erro(erro)
        return _texto({"feito": args.get("comando")})

    return [fatiar, imprimir, status, foto, comando]
