"""`zervis avaliar` (ou `python -m zervis.avaliacao`): roda a bateria com o cérebro de verdade.

Usa o cérebro e a conta de quem usa (Claude ou Codex, como o Zé), com ou sem as respostas
rápidas na frente; cada cenário é uma conversa nova, numa pasta temporária. Cada rodada anota
também os tokens que gastou. O relatório vai para `<estado>/avaliacao/`, e a rodada é comparada
com a anterior do mesmo cérebro.
"""

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from claude_agent_sdk import SdkMcpTool

from zervis import avaliacao, lugares, usuario
from zervis.avaliacao import Cenario, Cerebro, Conferencia

HISTORICO = lugares.ESTADO / "avaliacao"


def persona() -> str:
    """A persona do Zé, com quem usa e a máquina fixos: a nota não pode mudar de um PC para
    outro nem carregar dados de ninguém."""
    from zervis.nucleo.apoio import PERSONA
    from zervis.rosto import manifesto
    from zervis.sistema.maquina import Maquina

    quem = usuario.Perfil("Ana", "Gestora de automação e IA; atende empresas.")
    maquina = Maquina(sistema="Arch Linux", omarchy=True, tela=True, audio=True)
    return "\n\n".join(
        [
            PERSONA.read_text(),
            quem.para_persona(),
            maquina.para_persona(),
            manifesto.para_persona(manifesto.PADRAO),
        ]
    )


def criar_claude(modelo: str, assinatura: bool = False) -> avaliacao.CriarCerebro:
    from zervis.cerebro import acesso, contas
    from zervis.cerebro.claude import ClaudeBrain
    from zervis.cerebro.ferramentas import LIVRES, servidor

    conta = contas.Contas().em_uso("claude")
    if not assinatura:
        acesso.aplicar()  # a chave colada no painel, se houver, como no Zé

    def criar(ferramentas: list[SdkMcpTool[Any]]) -> Cerebro:
        return ClaudeBrain(
            modelo,
            [],
            Path(tempfile.mkdtemp(prefix="ze-avaliacao-")),
            env={"CLAUDE_CONFIG_DIR": str(conta.onde)},
            tempo_limite_s=120,
            mcp={"jarvis": servidor(ferramentas)},
            livres=list(LIVRES),
        )

    return criar


def criar_codex(modelo: str) -> avaliacao.CriarCerebro:
    from zervis.cerebro.codex import CodexBrain
    from zervis.cerebro.ferramentas import LIVRES, servidor

    def criar(ferramentas: list[SdkMcpTool[Any]]) -> Cerebro:
        return CodexBrain(
            modelo,
            [],
            Path(tempfile.mkdtemp(prefix="ze-avaliacao-")),
            tempo_limite_s=120,
            mcp={"jarvis": servidor(ferramentas)},
            livres=list(LIVRES),
        )

    return criar


def persona_rapida() -> str:
    """A da via rápida, com a mesma pessoa e a mesma máquina fixas da persona completa."""
    from zervis.nucleo.apoio import PERSONA_RAPIDA
    from zervis.sistema.maquina import Maquina

    quem = usuario.Perfil("Ana", "Gestora de automação e IA; atende empresas.")
    maquina = Maquina(sistema="Arch Linux", omarchy=True, tela=True, audio=True)
    return "\n\n".join([PERSONA_RAPIDA.read_text(), quem.para_persona(), maquina.para_persona()])


def com_rapidas(criar: avaliacao.CriarCerebro, via: dict[str, Any]) -> avaliacao.CriarCerebro:
    """As respostas rápidas na frente do cérebro, como o Zé faz com elas ligadas."""
    from zervis.cerebro import rapido

    def criar_com(ferramentas: list[SdkMcpTool[Any]]) -> Cerebro:
        pasta = Path(tempfile.mkdtemp(prefix="ze-avaliacao-rapida-"))
        completo: Any = criar(ferramentas)  # os cérebros de verdade são `Brain`
        cerebro = rapido.envolver(
            completo, {**via, "ligada": True, "quando": "sempre"}, pasta, persona_rapida()
        )
        if not isinstance(cerebro, rapido.Roteado):
            raise avaliacao.AvaliacaoErro("as respostas rápidas não montaram (motor ou chave)")
        return cerebro

    return criar_com


def _anterior(rotulo: str = "") -> dict[str, Any]:
    """A última vez que cada cenário rodou com o mesmo cérebro, juntando o histórico: rodar só
    alguns cenários não apaga a referência dos outros."""
    ultimas: dict[str, Any] = {}
    for arquivo in sorted(HISTORICO.glob("*.json")):
        try:
            relatorio = json.loads(arquivo.read_text())
        except (OSError, ValueError):
            continue
        if relatorio.get("rotulo", relatorio.get("modelo", "")) != rotulo and rotulo:
            continue
        for c in relatorio.get("cenarios", []):
            if any(r.get("passou") is not None for r in c.get("rodadas", [])):
                ultimas[c["arquivo"]] = c
    return {"cenarios": list(ultimas.values())}


async def avaliar(
    cenarios: list[Cenario], criar: avaliacao.CriarCerebro, repetir: int
) -> dict[str, Any]:
    """Cada cenário `repetir` vezes. Uma rodada em que o cérebro não respondeu (limite da
    conta, acesso, rede) fica sem nota: não é julgamento. No limite da conta, a bateria para."""
    texto_persona, saida, parou = persona(), [], ""
    for c in cenarios:
        rodadas: list[dict[str, Any]] = []
        for _ in range(repetir if not parou else 0):
            rodada = await avaliacao.rodar(c, criar, texto_persona)
            if rodada.erro:
                rodadas.append({"passou": None, "erro": rodada.erro})
                print(f"- {c.nome}: sem nota ({rodada.erro})")
                if rodada.erro == "limite_de_uso":
                    parou = rodada.erro
                    break
                continue
            regras = avaliacao.julgar(c, rodada)
            rodadas.append(
                {
                    "passou": avaliacao.nota(regras),
                    "falhas": [
                        f"{r.regra} ({r.detalhe})" if r.detalhe else r.regra
                        for r in regras
                        if not r.ok
                    ],
                    "resposta": rodada.resposta,
                    "ferramentas": [ch.ferramenta for ch in rodada.chamadas],
                    "chamadas": [
                        {"ferramenta": ch.ferramenta, "entrada": ch.entrada}
                        for ch in rodada.chamadas
                    ],
                    "aprovacoes": rodada.aprovacoes,
                    "segundos": round(rodada.segundos, 1),
                    "tokens": rodada.tokens,
                    "via": rodada.via,
                    "gastos": rodada.gastos,
                }
            )
            _mostrar(c, rodada, regras)
        saida.append({"arquivo": c.arquivo, "nome": c.nome, "rodadas": rodadas})
    return {"quando": time.strftime("%Y-%m-%dT%H:%M:%S"), "cenarios": saida, "parou": parou}


def _taxas(relatorio: dict[str, Any]) -> dict[str, float]:
    """A taxa de acerto de cada cenário, só com as rodadas que tiveram nota."""
    taxas = {}
    for c in relatorio.get("cenarios", []):
        notas = [r["passou"] for r in c["rodadas"] if r.get("passou") is not None]
        if notas:
            taxas[c["arquivo"]] = sum(notas) / len(notas)
    return taxas


def _tokens(relatorio: dict[str, Any]) -> dict[str, float]:
    """A média de tokens de cada cenário, nas rodadas com nota."""
    medias = {}
    for c in relatorio.get("cenarios", []):
        valores = [
            r["tokens"] for r in c["rodadas"] if r.get("passou") is not None and "tokens" in r
        ]
        if valores:
            medias[c["arquivo"]] = sum(valores) / len(valores)
    return medias


def _mil(n: float) -> str:
    return f"{n / 1000:.1f} mil".replace(".", ",")


def _mostrar(c: Cenario, rodada: avaliacao.Rodada, regras: list[Conferencia]) -> None:
    resposta = rodada.resposta
    marca = "✓" if avaliacao.nota(regras) else "✗"
    print(f"{marca} {c.nome} · {_mil(rodada.tokens)} tokens · {rodada.via or '?'}")
    for r in regras:
        if not r.ok:
            print(f"    ✗ {r.regra}" + (f": {r.detalhe}" if r.detalhe else ""))
    if not avaliacao.nota(regras):
        print(f"    resposta: {resposta[:240]}")


def resumo(relatorio: dict[str, Any], anterior: dict[str, Any]) -> str:
    taxa, antes = _taxas(relatorio), _taxas(anterior)
    sem_nota = [c["arquivo"] for c in relatorio["cenarios"] if c["arquivo"] not in taxa]
    if not taxa:
        return "Sem nota: o cérebro não respondeu em nenhum cenário."
    total = sum(taxa.values()) / len(taxa)
    certos = sum(v == 1 for v in taxa.values())
    linhas = [f"Nota: {total * 100:.0f}% ({certos} de {len(taxa)} cenários sempre certos)"]
    if tokens := _tokens(relatorio):
        media = sum(tokens.values()) / len(tokens)
        linha = f"Tokens: {_mil(media)} por cenário, em média"
        if antes_t := {k: v for k, v in _tokens(anterior).items() if k in tokens}:
            antes_media = sum(antes_t.values()) / len(antes_t)
            agora_media = sum(tokens[k] for k in antes_t) / len(antes_t)
            linha += f" (antes {_mil(antes_media)} → agora {_mil(agora_media)} nos mesmos)"
        linhas.append(linha)
    if sem_nota:
        linhas.append(f"  sem nota: {', '.join(sem_nota)}")
    for arquivo, valor in taxa.items():
        if arquivo in antes and antes[arquivo] != valor:
            sentido = "melhorou" if valor > antes[arquivo] else "piorou"
            de, para = antes[arquivo] * 100, valor * 100
            linhas.append(f"  {sentido}: {arquivo} ({de:.0f}% → {para:.0f}%)")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    partes = argparse.ArgumentParser(prog="zervis avaliar", description=__doc__)
    partes.add_argument("cenarios", nargs="*", help="só estes (nome do arquivo, sem .toml)")
    partes.add_argument("--repetir", type=int, default=1, help="rodadas por cenário")
    partes.add_argument("--modelo", default="", help="o modelo do cérebro (padrão: o do Zé)")
    partes.add_argument(
        "--cerebro",
        choices=("claude", "codex"),
        default="",
        help="o cérebro (padrão: o escolhido no Zé)",
    )
    partes.add_argument(
        "--rapidas",
        action="store_true",
        help="com as respostas rápidas na frente, como escolhidas em Modelos",
    )
    partes.add_argument(
        "--assinatura",
        action="store_true",
        help="usa o login da assinatura do Claude, não a chave colada no painel",
    )
    args = partes.parse_args(argv)
    cenarios = avaliacao.carregar()
    if args.cenarios:
        cenarios = [c for c in cenarios if c.arquivo in args.cenarios]
        if not cenarios:
            print("Nenhum cenário com esses nomes.", file=sys.stderr)
            return 2
    from zervis.cerebro import catalogo, rapido
    from zervis.config import carregar

    cfg = carregar()
    catalogo.aplicar_modelos(cfg, catalogo.ler_modelos(lugares.ESTADO / "cerebro-modelos.json"))
    agente = args.cerebro or catalogo.ler_escolha(lugares.ESTADO / "cerebro") or "claude"
    if agente not in ("claude", "codex"):
        agente = "claude"  # o OmniRoute não tem conta própria para a bateria
    modelo = args.modelo or cfg["cerebro"][catalogo.CHAVE_DO_MODELO[agente]]
    criar = criar_codex(modelo) if agente == "codex" else criar_claude(modelo, args.assinatura)
    rotulo = f"{agente}:{modelo or 'padrão da conta'}"
    if args.rapidas:
        via = rapido.efetiva(cfg["via_rapida"])
        criar = com_rapidas(criar, via)
        rotulo += f" + rápidas:{via['motor']}:{via['modelo']}"
    print(f"Avaliando {len(cenarios)} cenários com {rotulo} ({args.repetir}x cada)…\n")
    relatorio = asyncio.run(avaliar(cenarios, criar, max(1, args.repetir)))
    relatorio["modelo"], relatorio["rotulo"] = modelo, rotulo
    anterior = _anterior(rotulo)
    print()
    print(resumo(relatorio, anterior))
    if relatorio["parou"] == "limite_de_uso":
        print(
            "O acesso do Claude bateu no limite de uso. Rode de novo quando ele renovar, ou com "
            "--assinatura, se o limite for da chave colada no painel."
        )
    if not _taxas(relatorio):
        return 2  # sem nota nenhuma, nada vai para o histórico (seria uma base falsa)
    HISTORICO.mkdir(parents=True, exist_ok=True)
    destino = HISTORICO / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1))
    print(f"Relatório: {destino}")
    return 0 if all(v == 1 for v in _taxas(relatorio).values()) and not relatorio["parou"] else 1


if __name__ == "__main__":
    sys.exit(main())
