"""O agente de atendimento como projeto: rascunho numa pasta, testes de conversa e Publicar.

A pasta do agente (`<projetos>/agente-de-atendimento`, um repositório Git) é o rascunho: quem usa
edita pela página Atendimento, pede ao Zé ou abre uma sessão de código nela. Os arquivos estão em
`zervis/atendimento/modelo/` (README e AGENTS.md explicam o contrato para as sessões).

Os clientes só veem a versão **publicada**: Publicar valida os arquivos, roda os testes de
`testes/*.toml` com o modelo e, se todos passarem, copia o rascunho para `<dados>/atendente/
publicado/` e registra um commit na pasta. As conversas dos clientes nunca vão para o projeto.
"""

import asyncio
import contextlib
import hashlib
import json
import logging
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zervis.atendimento import agente

log = logging.getLogger(__name__)

MODELO = Path(__file__).with_name("modelo")
NOME = "agente-de-atendimento"
TESTES_MAXIMOS = 30
TESTES_JUNTOS = 3
_LIDOS = ("agente.toml", "persona.md", "passar.md")


@dataclass
class Teste:
    nome: str
    cliente: str
    contem: list[str] = field(default_factory=list)
    nao_contem: list[str] = field(default_factory=list)
    passar: bool | None = None


def existe(raiz: Path) -> bool:
    return (raiz / "agente.toml").is_file()


def _ler_texto(arquivo: Path) -> str:
    try:
        return arquivo.read_text().strip()
    except OSError:
        return ""


def ler(raiz: Path) -> agente.Perfil:
    """A persona escrita na pasta (rascunho ou publicada), conferida pelos limites."""
    try:
        cabeca = tomllib.loads((raiz / "agente.toml").read_text())
    except OSError:
        cabeca = {}
    except tomllib.TOMLDecodeError as erro:
        raise agente.AgenteErro(f"agente.toml inválido: {erro}") from erro
    partes = []
    for arquivo in sorted((raiz / "conhecimento").glob("*.md")):
        if texto := _ler_texto(arquivo):
            partes.append(texto)
    dados = {
        "nome": str(cabeca.get("nome", "")),
        "empresa": str(cabeca.get("empresa", "")),
        "persona": _ler_texto(raiz / "persona.md"),
        "passar": _ler_texto(raiz / "passar.md"),
        "conhecimento": "\n\n".join(partes),
    }
    return agente.validar(dados, agente.Perfil())


def conhecimento_extra(raiz: Path) -> int:
    """Quantos arquivos de conhecimento há além do `geral.md` (o que o formulário edita)."""
    return len([a for a in (raiz / "conhecimento").glob("*.md") if a.name != "geral.md"])


def _toml(texto: str) -> str:
    return json.dumps(texto, ensure_ascii=False)  # uma string JSON é uma string básica do TOML


def gravar(raiz: Path, mudancas: dict[str, Any]) -> agente.Perfil:
    """Grava no rascunho os campos do formulário. O conhecimento do formulário é o `geral.md`;
    os outros arquivos de `conhecimento/` (de uma sessão, por exemplo) continuam como estão."""
    criar(raiz)
    atual = ler(raiz)
    if "conhecimento" in mudancas:
        atual.conhecimento = _ler_texto(raiz / "conhecimento" / "geral.md")
    novo = agente.validar({k: v for k, v in mudancas.items() if k in agente.LIMITES}, atual)
    (raiz / "agente.toml").write_text(
        f"nome = {_toml(novo.nome)}\nempresa = {_toml(novo.empresa)}\n"
    )
    for campo, arquivo in (("persona", "persona.md"), ("passar", "passar.md")):
        if campo in mudancas:
            (raiz / arquivo).write_text(getattr(novo, campo) + "\n" if getattr(novo, campo) else "")
    if "conhecimento" in mudancas:
        (raiz / "conhecimento").mkdir(exist_ok=True)
        geral = novo.conhecimento
        (raiz / "conhecimento" / "geral.md").write_text(geral + "\n" if geral else "")
    return ler(raiz)


def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (argumentos montados aqui)
        ["git", *args],  # noqa: S607 (o git do sistema, como nas sessões)
        cwd=raiz,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def criar(raiz: Path, inicial: agente.Perfil | None = None) -> bool:
    """Cria a pasta a partir do modelo, se ainda não existir; devolve se criou."""
    if existe(raiz):
        return False
    raiz.mkdir(parents=True, exist_ok=True)
    shutil.copytree(MODELO, raiz, dirs_exist_ok=True)
    if inicial is not None:
        gravar(raiz, {k: getattr(inicial, k) for k in agente.LIMITES})
    if shutil.which("git") and not (raiz / ".git").exists():
        for args in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "Início do agente")):
            _git(raiz, *args)
    return True


def ler_testes(raiz: Path) -> list[Teste]:
    testes: list[Teste] = []
    for arquivo in sorted((raiz / "testes").glob("*.toml")):
        try:
            dados = tomllib.loads(arquivo.read_text())
        except (OSError, tomllib.TOMLDecodeError) as erro:
            raise agente.AgenteErro(f"testes/{arquivo.name} inválido: {erro}") from erro
        for t in dados.get("teste", []):
            if not isinstance(t, dict) or not str(t.get("cliente", "")).strip():
                raise agente.AgenteErro(f"testes/{arquivo.name}: todo teste precisa de 'cliente'.")
            passar = t.get("passar")
            testes.append(
                Teste(
                    str(t.get("nome") or t["cliente"])[:80],
                    str(t["cliente"])[:2000],
                    [str(x) for x in t.get("contem", [])],
                    [str(x) for x in t.get("nao_contem", [])],
                    passar if isinstance(passar, bool) else None,
                )
            )
    if len(testes) > TESTES_MAXIMOS:
        raise agente.AgenteErro(f"No máximo {TESTES_MAXIMOS} testes.")
    return testes


def conferir(t: Teste, resposta: str, motivo: str | None) -> str | None:
    """O que falhou no teste, ou None."""
    baixa = resposta.casefold()
    if faltam := [x for x in t.contem if x.casefold() not in baixa]:
        return "Faltou: " + ", ".join(faltam)
    if proibidos := [x for x in t.nao_contem if x.casefold() in baixa]:
        return "Não podia ter: " + ", ".join(proibidos)
    if t.passar is True and motivo is None:
        return "Devia passar para você."
    if t.passar is False and motivo is not None:
        return "Passou para você sem precisar."
    return None


async def rodar_testes(
    criar_motor: Callable[[], agente.Motor], p: agente.Perfil, testes: list[Teste]
) -> list[dict[str, Any]]:
    vez = asyncio.Semaphore(TESTES_JUNTOS)

    async def um(t: Teste) -> dict[str, Any]:
        async with vez:
            try:
                bruta = await asyncio.wait_for(
                    agente.responder(criar_motor(), p, [], t.cliente), agente.TEMPO_RESPOSTA_S
                )
            except Exception as erro:
                return {
                    "nome": t.nome,
                    "ok": False,
                    "falha": f"Sem resposta ({type(erro).__name__}).",
                }
            resposta, motivo = agente.separar(bruta)
            falha = conferir(t, resposta, motivo)
            return {"nome": t.nome, "ok": falha is None, "falha": falha or "", "resposta": resposta}

    return list(await asyncio.gather(*(um(t) for t in testes)))


def impressao(raiz: Path) -> str:
    """Muda quando algum arquivo que o agente lê muda (para saber se há o que publicar)."""
    h = hashlib.sha256()
    arquivos = [raiz / n for n in _LIDOS]
    arquivos += sorted((raiz / "conhecimento").glob("*.md")) + sorted(
        (raiz / "testes").glob("*.toml")
    )
    for a in arquivos:
        with contextlib.suppress(OSError):
            h.update(a.relative_to(raiz).as_posix().encode() + b"\0" + a.read_bytes() + b"\0")
    return h.hexdigest()


def pendente(raiz: Path, publicado: Path) -> bool:
    return existe(raiz) and (not existe(publicado) or impressao(raiz) != impressao(publicado))


def copiar_publicado(raiz: Path, publicado: Path) -> None:
    """Troca a versão publicada pelo rascunho, de uma vez."""
    novo = publicado.with_name(publicado.name + ".novo")
    shutil.rmtree(novo, ignore_errors=True)
    novo.mkdir(parents=True, mode=0o700)
    for nome in _LIDOS:
        if (raiz / nome).is_file():
            shutil.copy2(raiz / nome, novo / nome)
    for pasta in ("conhecimento", "testes"):
        (novo / pasta).mkdir()
        for a in (raiz / pasta).glob("*.md" if pasta == "conhecimento" else "*.toml"):
            shutil.copy2(a, novo / pasta / a.name)
    velho = publicado.with_name(publicado.name + ".velho")
    shutil.rmtree(velho, ignore_errors=True)
    if publicado.exists():
        publicado.replace(velho)
    novo.replace(publicado)
    shutil.rmtree(velho, ignore_errors=True)


def registrar_publicacao(raiz: Path) -> None:
    """Um commit com o que foi publicado, se a pasta for um repositório Git."""
    if not shutil.which("git") or not (raiz / ".git").exists():
        return
    if _git(raiz, "status", "--porcelain").stdout.strip():
        _git(raiz, "add", "-A")
        _git(raiz, "commit", "-qm", "Publicação do agente")


def _com_ajustes(base: agente.Perfil, pasta: Path) -> agente.Perfil:
    ajustes = agente.ler(pasta)
    base.ligado, base.modo, base.numeros_teste = ajustes.ligado, ajustes.modo, ajustes.numeros_teste
    base.ligacoes = ajustes.ligacoes
    base.cerebro = ajustes.cerebro
    return base


def perfil(pasta: Path = agente.PASTA) -> agente.Perfil:
    """O que atende os clientes: a versão publicada, com os ajustes (ligado, modo, números)."""
    publicado = pasta / "publicado"
    try:
        base = ler(publicado) if existe(publicado) else agente.ler(pasta)
    except agente.AgenteErro:
        base = agente.Perfil()
    return _com_ajustes(base, pasta)


def rascunho(raiz: Path, pasta: Path = agente.PASTA) -> agente.Perfil:
    """O que está na pasta, ainda não publicado (o Testar da página usa este)."""
    return _com_ajustes(ler(raiz), pasta) if existe(raiz) else perfil(pasta)


def migrar(raiz: Path, pasta: Path = agente.PASTA) -> None:
    """O perfil da primeira versão (tudo em `agente.json`) vira a pasta e a versão publicada."""
    antigo = agente.ler(pasta)
    if existe(raiz) or existe(pasta / "publicado"):
        return
    if all(getattr(antigo, k) == getattr(agente.Perfil(), k) for k in agente.LIMITES):
        return
    criar(raiz, antigo)
    copiar_publicado(raiz, pasta / "publicado")
    log.info("atendimento: o perfil do agente virou a pasta %s", raiz)


def publicar(
    raiz: Path,
    pasta: Path,
    criar_motor: Callable[[], agente.Motor],
    executar: Callable[[Any], list[dict[str, Any]]],
) -> dict[str, Any]:
    """Testa o rascunho e, se tudo passar, publica. `executar` roda a corrotina dos testes."""
    if not existe(raiz):
        raise agente.AgenteErro("Salve o agente antes de publicar.")
    p = rascunho(raiz, pasta)
    testes = ler_testes(raiz)
    resultados = executar(rodar_testes(criar_motor, p, testes)) if testes else []
    passaram = sum(1 for r in resultados if r["ok"])
    if passaram < len(resultados):
        aviso = f"{passaram} de {len(resultados)} testes passaram. Nada foi publicado."
        return {"publicado": False, "resultados": resultados, "aviso": aviso}
    copiar_publicado(raiz, pasta / "publicado")
    registrar_publicacao(raiz)
    return {"publicado": True, "resultados": resultados, "aviso": "Agente publicado."}
