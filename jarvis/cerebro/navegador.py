"""O navegador do JARVIS (08/10/2026): o Playwright MCP num Chromium próprio, em segundo plano.

Como o `browser` do Hermes Agent (Chromium headless lido pela árvore de acessibilidade, janela só
quando pedem), mas pelo servidor MCP oficial da Microsoft (Apache-2.0), ligado em
`~/.config/zervis/mcp.toml` como `[servidores.navegador]`; nenhum código copiado.

Regras desta camada, por cima da aprovação falada de todo MCP externo:
- livre (está em `livres` do mcp.toml): abrir endereço, voltar, ler a página, procurar texto,
  esperar, abas, passar o mouse, fechar; e rolar (só as teclas de rolagem, `autoaprovar`);
- pergunta falada: clicar, digitar, preencher, escolher opção, outras teclas, responder avisos;
- recusado antes de perguntar: rodar código na página, enviar ou soltar arquivos.
O perfil é separado do Chromium do usuário (sem as senhas e sessões dele).

O que volta do navegador passa por `ajustar` antes do modelo (gancho PostToolUse do ClaudeBrain),
como o `browser_tool_snapshot` do Hermes, com três melhorias:
- enxuga a árvore de acessibilidade (sem `[cursor=pointer]`, sem embrulhos `generic` vazios,
  `[ref=…]` só no que se clica ou preenche, endereços curtos): a mesma página, bem menos texto;
- mascara segredos (campos de senha, chaves de API, tokens, cartões que passam no Luhn);
- corta em LIMITE caracteres numa quebra de linha, grava a leitura inteira e avisa como seguir
  com `navegador_continuar`, junto com o índice das seções que ficaram de fora (o Hermes só dá
  o número da linha). Abrir uma página já devolve o esboço dela (títulos e o que dá para clicar
  ou preencher), sem precisar de outro passo para saber o que tem lá.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from jarvis import lugares

log = logging.getLogger(__name__)
SERVIDOR = "navegador"
PREFIXO = f"mcp__{SERVIDOR}__"
PROIBIDAS = {
    "browser_run_code_unsafe": "rodar código na página",
    "browser_evaluate": "rodar código na página",
    "browser_file_upload": "enviar arquivos do computador",
    "browser_drop": "soltar arquivos na página",
}
ROLAGEM = {"PageDown", "PageUp", "Home", "End", "ArrowDown", "ArrowUp"}
LIMITE = 15_000  # o mesmo teto do Hermes (browser.snapshot_threshold): uns 4 mil tokens
ESBOCO = 4_000  # o esboço que acompanha a página aberta
SAIDA = lugares.ESTADO / "navegador"  # --output-dir do mcp.toml
LEITURAS = SAIDA / "leituras"
CONTINUAR = "navegador_continuar"

# Papéis da árvore em que se clica ou escreve: só estes guardam o [ref=…] (é o que as
# ferramentas usam como alvo); nos demais ele só ocupa espaço.
INTERATIVOS = {
    "link", "button", "textbox", "searchbox", "combobox", "checkbox", "radio", "option",
    "menuitem", "menuitemcheckbox", "menuitemradio", "tab", "switch", "slider", "spinbutton",
    "listbox", "treeitem", "iframe",
}  # fmt: skip
EMBRULHOS = {"generic", "group", "none", "presentation"}
_LINHA = re.compile(r"^(\s*)- ([a-zA-Z]+)\b(.*)$")
_REF = re.compile(r" \[ref=[^\]]+\]")
_NOTA = re.compile(r'\s*"\[?\d{1,3}\]?"')
_SNAPSHOT_ARQUIVO = re.compile(r"\[Snapshot\]\(([^)]+\.yml)\)")

_SEGREDOS = [
    re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
]
_CAMPO_SECRETO = re.compile(
    r'^(\s*- (?:textbox|searchbox) "[^"]*(?:senha|password|passe|pin|cvv|cvc|token|secret)[^"]*"'
    r"[^:]*:\s*)(.+)$",
    re.IGNORECASE,
)
_CARTAO = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _elemento(entrada: dict[str, Any]) -> str:
    return str(entrada.get("element") or "o elemento marcado").strip()


def prechecar(nome: str, entrada: dict[str, Any]) -> str | None:
    """Recusa o que nunca vai por voz; o cérebro recebe o motivo e conta ao usuário."""
    if not nome.startswith(PREFIXO):
        return None
    motivo = PROIBIDAS.get(nome.removeprefix(PREFIXO))
    if motivo:
        return f"Recusado: o navegador do JARVIS não pode {motivo}. Faça de outro jeito ou diga."
    return None


def autoaprovar(nome: str, entrada: dict[str, Any]) -> bool:
    """Rolar a página não muda nada nela: sem pergunta."""
    return nome == PREFIXO + "browser_press_key" and str(entrada.get("key")) in ROLAGEM


def descrever(nome: str, entrada: dict[str, Any]) -> str | None:
    """A frase falada da aprovação, dizendo exatamente o que vai para a página."""
    if not nome.startswith(PREFIXO):
        return None
    ferramenta = nome.removeprefix(PREFIXO)
    if ferramenta == "browser_click":
        return f"Vou clicar em {_elemento(entrada)}."
    if ferramenta == "browser_type":
        enviar = " e enviar" if entrada.get("submit") else ""
        return f'Vou digitar "{entrada.get("text", "")}" em {_elemento(entrada)}{enviar}.'
    if ferramenta == "browser_fill_form":
        campos = []
        for campo in entrada.get("fields") or []:
            if not isinstance(campo, dict):
                continue
            secreto = "senha" in str(campo.get("name", "")).casefold() or campo.get("type") in (
                "password",
            )
            valor = "uma senha" if secreto else f'"{campo.get("value", "")}"'
            campos.append(f"{campo.get('name', 'campo')} com {valor}")
        return "Vou preencher " + ("; ".join(campos) or "o formulário") + "."
    if ferramenta == "browser_select_option":
        valores = ", ".join(str(v) for v in entrada.get("values") or [])
        return f"Vou escolher {valores} em {_elemento(entrada)}."
    if ferramenta == "browser_press_key":
        return f"Vou apertar a tecla {entrada.get('key', '')} na página."
    if ferramenta == "browser_handle_dialog":
        return (
            "Vou aceitar o aviso da página."
            if entrada.get("accept")
            else "Vou recusar o aviso da página."
        )
    if ferramenta == "browser_drag":
        return (
            f"Vou arrastar {entrada.get('startElement', 'um elemento')} "
            f"até {entrada.get('endElement', 'outro')}."
        )
    return None


def _luhn(digitos: str) -> bool:
    soma = 0
    for i, d in enumerate(reversed(digitos)):
        n = int(d) * (2 if i % 2 else 1)
        soma += n - 9 if n > 9 else n
    return soma % 10 == 0


def mascarar(texto: str) -> str:
    """Senhas, chaves, tokens e cartões viram [oculto] antes do modelo e do disco."""
    for padrao in _SEGREDOS:
        texto = padrao.sub("[oculto]", texto)

    def cartao(m: re.Match[str]) -> str:
        digitos = re.sub(r"\D", "", m[0])
        return "[cartão oculto]" if 13 <= len(digitos) <= 19 and _luhn(digitos) else m[0]

    texto = _CARTAO.sub(cartao, texto)
    return "\n".join(
        _CAMPO_SECRETO.sub(lambda m: m[1] + "[oculto]", linha) for linha in texto.split("\n")
    )


def enxugar(texto: str) -> str:
    """A árvore de acessibilidade sem o que não informa nada ao modelo."""
    saida: list[str] = []
    pular = -1  # recuo da subárvore descartada (nota de rodapé), -1 = nenhuma
    for linha in texto.split("\n"):
        linha = linha.replace(" [cursor=pointer]", "")
        recuo_atual = len(linha) - len(linha.lstrip())
        if pular >= 0:
            if recuo_atual > pular and linha.strip():
                continue
            pular = -1
        m = _LINHA.match(linha)
        if m:
            recuo, papel, resto = m.groups()
            if papel == "link" and _NOTA.match(resto):
                pular = len(recuo)  # "[3]" e o endereço dela: só ruído para quem lê em voz
                continue
            if papel not in INTERATIVOS:
                resto = _REF.sub("", resto)
            if papel in EMBRULHOS | {"superscript"} and resto.strip() in ("", ":"):
                continue  # embrulho vazio: os filhos continuam, um nível mais fundo
            linha = f"{recuo}- {papel}{resto}"
        elif linha.lstrip().startswith("- /url:"):
            endereco = linha.split(":", 1)[1].strip().strip('"')
            if endereco.startswith("#"):
                continue  # âncora da própria página
            if len(endereco) > 90:
                endereco = endereco[:87] + "…"
            linha = " " * recuo_atual + "- /url: " + endereco
        saida.append(linha)
    return "\n".join(saida)


def _titulos(linhas: list[str], inicio: int) -> list[str]:
    achados = []
    for n, linha in enumerate(linhas[inicio:], start=inicio + 1):
        m = re.match(r'\s*- heading "([^"]+)"', linha)
        if m:
            achados.append(f"linha {n}: {m[1][:60]}")
    return achados


def cortar(texto: str, pasta: Path = LEITURAS) -> str:
    """Até LIMITE caracteres, numa quebra de linha; o resto fica gravado para continuar."""
    if len(texto) <= LIMITE:
        return texto
    linhas = texto.split("\n")
    guardado = guardar(texto, pasta)
    mantidas, total = [], 0
    for linha in linhas:
        if total + len(linha) + 1 > LIMITE - 1500:  # reserva para o aviso e o índice
            break
        mantidas.append(linha)
        total += len(linha) + 1
    seguinte = len(mantidas) + 1
    indice = _titulos(linhas, len(mantidas))
    aviso = (
        f"\n[… cortei aqui: faltam {len(linhas) - len(mantidas)} de {len(linhas)} linhas. "
        f'Para continuar: {CONTINUAR} com leitura "{guardado}" e linha {seguinte}'
    )
    if indice:
        mostrar = indice[:15] + ([f"e mais {len(indice) - 15}"] if len(indice) > 15 else [])
        aviso += ". Seções que ficaram de fora: " + "; ".join(mostrar)
    return "\n".join(mantidas) + aviso + ". Ou use browser_find para um trecho.]"


def guardar(texto: str, pasta: Path = LEITURAS) -> str:
    """Grava a leitura inteira (já mascarada) e devolve o nome curto dela."""
    nome = hashlib.sha256(texto.encode()).hexdigest()[:10]
    try:
        pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        (pasta / f"{nome}.txt").write_text(texto)
    except OSError:
        pass
    return nome


def continuar(leitura: str, linha: int, pasta: Path = LEITURAS) -> str:
    """O trecho seguinte de uma leitura cortada, com o mesmo teto."""
    if not re.fullmatch(r"[0-9a-f]{10}", leitura):
        raise ValueError("leitura inválida: use o nome que veio no aviso de corte")
    try:
        linhas = (pasta / f"{leitura}.txt").read_text().split("\n")
    except OSError:
        raise ValueError("essa leitura não existe mais; leia a página de novo") from None
    inicio = max(1, linha) - 1
    if inicio >= len(linhas):
        return f"A leitura tem {len(linhas)} linhas; não há nada a partir da {linha}."
    trecho, total = [], 0
    for linha_ in linhas[inicio:]:
        if total + len(linha_) + 1 > LIMITE - 300:
            break
        trecho.append(linha_)
        total += len(linha_) + 1
    fim = inicio + len(trecho)
    resto = (
        f"\n[… faltam {len(linhas) - fim} linhas: {CONTINUAR} com linha {fim + 1}.]"
        if fim < len(linhas)
        else "\n[fim da leitura]"
    )
    return f"[linhas {inicio + 1} a {fim} de {len(linhas)}]\n" + "\n".join(trecho) + resto


def esboco(arvore: str, links: int = 30) -> str:
    """Títulos, campos e botões, e os primeiros links (sem as notas "[1]"), até ESBOCO."""
    linhas, total, vistos = [], 0, 0
    for linha in enxugar(arvore).split("\n"):
        m = _LINHA.match(linha)
        if not m or m[2] not in INTERATIVOS | {"heading"}:
            continue
        if m[2] == "link":
            if vistos >= links:
                continue
            vistos += 1
        curta = linha.strip().removesuffix(":")[:140]
        if total + len(curta) > ESBOCO:
            linhas.append("… (mais itens: browser_find ou browser_snapshot)")
            break
        linhas.append(curta)
        total += len(curta) + 1
    return "\n".join(linhas)


def _snapshot_gravado(texto: str, saida: Path) -> str | None:
    m = _SNAPSHOT_ARQUIVO.search(texto)
    if not m:
        return None
    arquivo = saida / Path(m[1]).name  # o MCP grava em --output-dir; o link é relativo ao cwd
    try:
        arvore = arquivo.read_text()
        arquivo.unlink()  # cru, sem máscara: não fica no disco depois de virar esboço
    except OSError:
        return None
    return arvore


def ajustar_texto(nome: str, texto: str, saida: Path = SAIDA) -> str:
    cru = len(texto)
    texto = mascarar(enxugar(texto))
    if nome == PREFIXO + "browser_navigate":
        arvore = _snapshot_gravado(texto, saida)
        if arvore:
            texto = _SNAPSHOT_ARQUIVO.sub("(esboço abaixo)", texto)
            texto += "\n### Esboço da página (títulos e o que dá para clicar ou preencher)\n"
            texto += mascarar(esboco(arvore))
            texto += "\n(Para o texto: browser_find com o assunto, ou browser_snapshot.)"
    final = cortar(texto, saida / "leituras")
    log.info(
        "navegador: %s devolveu %d caracteres, o modelo vê %d",
        nome.removeprefix(PREFIXO),
        cru,
        len(final),
    )
    return final


def ajustar(nome: str, resposta: Any, saida: Path = SAIDA) -> Any | None:
    """Gancho PostToolUse: a resposta do navegador como o modelo deve ver; None = sem mudança."""
    if not nome.startswith(PREFIXO):
        return None
    if isinstance(resposta, str):
        return ajustar_texto(nome, resposta, saida)
    blocos = resposta.get("content") if isinstance(resposta, dict) else resposta
    if not isinstance(blocos, list):
        return None
    novos = [
        {**b, "text": ajustar_texto(nome, str(b.get("text", "")), saida)}
        if isinstance(b, dict) and b.get("type") == "text"
        else b
        for b in blocos
    ]
    return {**resposta, "content": novos} if isinstance(resposta, dict) else novos
