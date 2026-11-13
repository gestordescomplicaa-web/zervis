"""Marketing (ADR 0091): o Zé cuida do site e do blog de quem usa, sempre por Pull Request.

A pessoa aponta a pasta do site (um repositório git com o GitHub) e a branch base. Cada pedido,
um artigo ou uma mudança no site, vira uma sessão de código numa cópia isolada a partir da base.
O Zé envia a branch e abre o PR pelo `gh` desta máquina; a pessoa revisa no preview e mescla.
Nada vai ao ar sem ela.

O site se integra ao Zé, e não o contrário (como os dispositivos, ADR 0089): ele se declara num
`zervis.json` na raiz (`docs/integrar-site.md`), com o manual do blog, a pasta dos artigos, o
modelo, o comando que valida e os campos do cabeçalho. O foco editorial, as categorias e as regras
de escrita ficam no manual do próprio site. Sem o `zervis.json`, só "Mudar o site" funciona.
"""

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.oficina import proposta

ARQUIVO = lugares.CONFIG / "marketing.json"
MANIFESTO = "zervis.json"  # o contrato do site com o Zé, na raiz do repositório
VERSAO = 1
CAMPOS = {"titulo": "title", "categoria": "category", "data": "date", "rascunho": "draft"}
CORPO_PR = ".ze-pr.md"  # o corpo do PR que a sessão escreve na raiz da cópia, sem commit
PREFIXOS = ("blog/", "site/")  # as branches que o Zé abre no repositório do site
ORIGEM = "marketing"
NOMES = {"artigo": "Blog", "site": "Site"}

TAREFA_ARTIGO = """Escreva um artigo para o blog deste site seguindo à risca o manual {manual} \
(o contrato do blog) e o modelo {modelo}. Leia os dois antes de começar.

Tema: {tema}

- Liste {pasta} para não repetir tema nem palavra-chave.
- Instale as dependências se faltarem e {validar}, até não sobrar erro.
- Entregue com `{rascunho}: true` e com os marcadores de experiência real que o manual pede. Não \
invente casos, clientes, números nem resultados.
- Faça um commit só, com a mensagem que o manual indica.
- Não envie a branch nem abra PR: quem publica é o Zé, depois de você terminar.
- Grave o corpo do PR, no modelo do manual, no arquivo {corpo} na raiz do projeto, sem commit. \
Deixe o link do preview como está no modelo: a Vercel cria o preview depois do PR."""

TAREFA_SITE = """Faça esta mudança no site: {pedido}

- Siga as instruções do projeto (README, AGENTS.md ou CLAUDE.md, se houver).
- Instale as dependências se faltarem e rode as verificações do projeto (lint, testes, build) \
até passarem.
- Faça o commit com uma mensagem clara.
- Não envie a branch nem abra PR: quem publica é o Zé, depois de você terminar.
- Grave o corpo do PR (o que mudou, como conferir e o que revisar) no arquivo {corpo} na raiz \
do projeto, sem commit."""


class MarketingErro(ValueError):
    """Mensagem curta para o painel e para a voz."""


@dataclass
class Site:
    pasta: str = ""
    base: str = ""


@dataclass(frozen=True)
class Blog:
    """O que o `zervis.json` do site declara do blog (`docs/integrar-site.md`)."""

    manual: str
    artigos: str
    modelo: str = ""
    validar: str = ""  # o comando que valida um artigo; {slug} vira o nome do arquivo
    marcador: str = ""  # o começo do marcador que o site exige preencher antes de publicar
    campos: tuple[tuple[str, str], ...] = tuple(CAMPOS.items())

    def campo(self, nome: str) -> str:
        return dict(self.campos)[nome]


def _caminho(valor: Any) -> str:
    """Um caminho dentro do repositório: relativo, sem subir de pasta."""
    texto = str(valor or "").strip().strip("/")
    if not texto or ".." in Path(texto).parts or str(valor).startswith("/"):
        raise MarketingErro("O zervis.json do site tem um caminho inválido.")
    return texto


def ler_manifesto(texto: str) -> Blog | None:
    """O blog declarado no `zervis.json` (None se ele não declarar blog)."""
    try:
        dados = json.loads(texto)
    except ValueError as erro:
        raise MarketingErro("O zervis.json do site não é um JSON válido.") from erro
    if not isinstance(dados, dict) or dados.get("zervis") != VERSAO:
        raise MarketingErro(f'O zervis.json do site precisa de "zervis": {VERSAO}.')
    blog = dados.get("blog")
    if blog is None:
        return None
    if not isinstance(blog, dict):
        raise MarketingErro("O blog do zervis.json precisa ser um objeto.")
    campos = {**CAMPOS, **{k: str(v) for k, v in (blog.get("campos") or {}).items() if k in CAMPOS}}
    return Blog(
        manual=_caminho(blog.get("manual")),
        artigos=_caminho(blog.get("artigos")),
        modelo=_caminho(blog["modelo"]) if blog.get("modelo") else "",
        validar=str(blog.get("validar", "")).strip(),
        marcador=str(blog.get("marcador", "")).strip(),
        campos=tuple(campos.items()),
    )


def _slug(texto: str, limite: int = 40) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:limite].strip("-") or "pedido"


def frente(texto: str) -> dict[str, Any]:
    """Os campos simples do cabeçalho de um artigo (`chave: valor` no primeiro nível): título,
    categoria, data e rascunho. Listas e blocos (tags, faq) ficam de fora; o site valida o resto."""
    achado = re.match(r"---\n(.*?)\n---", texto, re.DOTALL)
    if not achado:
        return {}
    dados: dict[str, Any] = {}
    for linha in achado.group(1).splitlines():
        campo = re.match(r"([A-Za-z_]\w*):\s*(.*)$", linha)
        if not campo:
            continue
        valor = campo.group(2)
        if valor and valor[0] in "\"'":
            fecho = valor.find(valor[0], 1)
            valor = valor[1:fecho] if fecho > 0 else valor[1:]
        else:
            valor = valor.split(" #", 1)[0].strip()
        if valor in ("true", "false"):
            dados[campo.group(1)] = valor == "true"
        elif valor and not valor.startswith(("[", "{", "|", ">")):
            dados[campo.group(1)] = valor
    return dados


class Marketing:
    def __init__(self, arquivo: Path = ARQUIVO, gh: str | None = None) -> None:
        self.arquivo = arquivo
        self._gh = gh

    @property
    def gh(self) -> str:
        return self._gh if self._gh is not None else proposta.achar_gh()

    # --- o site ---------------------------------------------------------------------------

    def site(self) -> Site:
        try:
            dados = json.loads(self.arquivo.read_text()).get("site") or {}
        except (OSError, ValueError, AttributeError):
            return Site()
        return Site(str(dados.get("pasta", "")), str(dados.get("base", "")))

    def guardar(self, pasta: str, base: str) -> Site:
        caminho = Path(pasta).expanduser()
        if not (caminho / ".git").exists():
            raise MarketingErro("A pasta não é um repositório git.")
        if proposta._git(caminho, "remote", "get-url", "origin").returncode != 0:
            raise MarketingErro("O repositório não tem o GitHub como origem.")
        base = base.strip() or self._padrao(caminho)
        existe = proposta._git(
            caminho, *self._credenciais(), "ls-remote", "--heads", "origin", base
        )
        if existe.returncode != 0:
            raise MarketingErro("Sem conexão com o GitHub agora.")
        if not existe.stdout.strip():
            raise MarketingErro(f"A branch {base} não existe no GitHub.")
        self._buscar(caminho, base)
        site = Site(str(caminho.resolve()), base)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".next")
        temporario.write_text(json.dumps({"site": asdict(site)}, ensure_ascii=False))
        temporario.replace(self.arquivo)
        return site

    def _padrao(self, pasta: Path) -> str:
        cabeca = proposta._git(pasta, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        return cabeca.stdout.strip().removeprefix("origin/") or "main"

    def _credenciais(self) -> list[str]:
        """O login do GitHub pelo `gh` desta máquina (o repositório pode ser privado)."""
        ajuda = ["-c", "credential.https://github.com.helper="]
        if gh := self.gh:
            ajuda += ["-c", f"credential.https://github.com.helper=!{gh} auth git-credential"]
        return ajuda

    def _buscar(self, pasta: Path, base: str) -> None:
        """Traz a base do GitHub."""
        feito = proposta._git(pasta, *self._credenciais(), "fetch", "--quiet", "origin", base)
        if feito.returncode != 0:
            raise MarketingErro("Sem conexão com o GitHub agora.")

    def _exigir_site(self) -> Site:
        site = self.site()
        if not site.pasta or not site.base:
            raise MarketingErro("Configure o site primeiro.")
        return site

    def _mostrar(self, site: Site, caminho: str) -> str:
        feito = proposta._git(Path(site.pasta), "show", f"origin/{site.base}:{caminho}")
        return feito.stdout if feito.returncode == 0 else ""

    def blog(self, site: Site | None = None) -> Blog | None:
        """O blog que o site declara na base (None sem o `zervis.json` ou sem blog nele)."""
        site = site or self.site()
        if not site.pasta or not site.base:
            return None
        texto = self._mostrar(site, MANIFESTO)
        return ler_manifesto(texto) if texto else None

    def situacao(self) -> dict[str, Any]:
        site = self.site()
        dados = asdict(site)
        if not site.pasta:
            return {"estado": "Não configurado", "configurado": False, "blog": False, **dados}
        if not Path(site.pasta, ".git").exists():
            return {"estado": "Pasta não encontrada", "configurado": False, "blog": False, **dados}
        try:
            blog = self.blog(site)
        except MarketingErro as erro:
            return {"estado": "Integração inválida", "configurado": True, "blog": False,
                    "erro": str(erro), **dados}  # fmt: skip
        if blog is None:
            estado = "Sem integração" if not self._mostrar(site, MANIFESTO) else "Sem blog"
            return {"estado": estado, "configurado": True, "blog": False, **dados}
        return {"estado": "Configurado", "configurado": True, "blog": True, **dados}

    # --- o blog ---------------------------------------------------------------------------

    def artigos(self, hoje: date | None = None) -> list[dict[str, Any]]:
        """Os artigos da base (o que já foi mesclado), do mais novo ao mais velho."""
        site = self.site()
        try:
            blog = self.blog(site)
        except MarketingErro:
            return []
        if blog is None:
            return []
        lista = proposta._git(
            Path(site.pasta), "ls-tree", "--name-only", f"origin/{site.base}", f"{blog.artigos}/"
        )
        hoje = hoje or date.today()
        artigos = []
        for caminho in lista.stdout.split():
            nome = Path(caminho).name
            if not nome.endswith(".md") or nome.startswith("_") or caminho == blog.modelo:
                continue
            texto = self._mostrar(site, caminho)
            dados = frente(texto)
            data = str(dados.get(blog.campo("data"), ""))
            if dados.get(blog.campo("rascunho"), True) is not False:
                estado = "Rascunho"
            elif data > hoje.isoformat():
                estado = "Agendado"
            else:
                estado = "Publicado"
            artigos.append({
                "slug": nome.removesuffix(".md"),
                "titulo": str(dados.get(blog.campo("titulo"), nome)),
                "categoria": str(dados.get(blog.campo("categoria"), "")),
                "data": data,
                "estado": estado,
            })  # fmt: skip
        return sorted(artigos, key=lambda a: a["data"], reverse=True)

    @staticmethod
    def por_categoria(artigos: list[dict[str, Any]]) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for a in artigos:
            if a["categoria"]:
                contagem[a["categoria"]] = contagem.get(a["categoria"], 0) + 1
        return dict(sorted(contagem.items()))

    def prs(self) -> list[dict[str, Any]]:
        """Os PRs abertos que o Zé abriu no site (branches blog/ e site/)."""
        site, gh = self.site(), self.gh
        if not site.pasta or not gh or not Path(site.pasta).is_dir():
            return []
        feito = proposta._rodar(
            [gh, "pr", "list", "--state", "open", "--json", "number,title,url,headRefName"],
            Path(site.pasta),
        )
        try:
            abertos = json.loads(feito.stdout) if feito.returncode == 0 else []
        except ValueError:
            return []
        return [
            {"numero": p["number"], "titulo": p["title"], "endereco": p["url"]}
            for p in abertos
            if str(p.get("headRefName", "")).startswith(PREFIXOS)
        ]

    # --- os pedidos -----------------------------------------------------------------------

    def pedir(self, sessoes: Any, tipo: str, texto: str, motor: str) -> Any:
        """Uma sessão numa cópia isolada a partir da base, já com a tarefa."""
        if tipo not in NOMES:
            raise MarketingErro("Pedido desconhecido.")
        texto = " ".join(texto.split())
        if tipo == "site" and not texto:
            raise MarketingErro("Diga o que mudar no site.")
        site = self._exigir_site()
        self._buscar(Path(site.pasta), site.base)
        blog = self.blog(site)
        if tipo == "artigo" and blog is None:
            raise MarketingErro(f"O site não declara um blog no {MANIFESTO} da branch {site.base}.")
        nome = f"{NOMES[tipo]} · {texto[:40] or 'próximo artigo'}"
        s = sessoes.criar(nome, site.pasta, motor=motor, isolada=True, origem=ORIGEM)
        # A cópia nasce da pasta como ela está; o pedido parte da base do GitHub.
        copia = Path(s.worktree)
        ponta = proposta._git(copia, "rev-parse", f"origin/{site.base}").stdout.strip()
        proposta._git(copia, "reset", "--hard", "--quiet", ponta)
        s = sessoes._mudar(s.id, base=ponta)
        if tipo == "artigo" and blog is not None:
            tema = texto or "escolha você, pelo foco editorial e pela distribuição do manual"
            validar = (
                f"valide com `{blog.validar}` (troque {{slug}} pelo nome do arquivo)"
                if blog.validar
                else "rode a validação que o manual indica"
            )
            tarefa = TAREFA_ARTIGO.format(
                manual=blog.manual, modelo=blog.modelo or "o modelo que o manual indica", tema=tema,
                pasta=blog.artigos, validar=validar, rascunho=blog.campo("rascunho"),
                corpo=CORPO_PR,
            )  # fmt: skip
        else:
            tarefa = TAREFA_SITE.format(pedido=texto, corpo=CORPO_PR)
        return sessoes.enviar(s.id, tarefa)

    def pedidos(self, sessoes: Any) -> list[dict[str, Any]]:
        return [
            {"id": s.id, "nome": s.nome, "estado": s.estado}
            for s in sessoes.listar()
            if s.origem == ORIGEM
        ]

    def abrir_pr(self, sessoes: Any, ref: str) -> proposta.Resultado:
        """Envia a branch da sessão e abre o PR na base. Artigo sai como rascunho, sempre."""
        site = self._exigir_site()
        s = sessoes.achar(ref)
        if s.origem != ORIGEM or not s.worktree:
            return proposta.Resultado(False, "Esta sessão não é um pedido de marketing.")
        if s.estado == "trabalhando":
            return proposta.Resultado(False, "A sessão ainda está trabalhando.")
        copia = Path(s.worktree)
        if proposta._git(copia, "status", "--porcelain", "--untracked-files=no").stdout.strip():
            return proposta.Resultado(False, "A cópia tem alterações sem commit.")
        gh = self.gh
        if not gh:
            return proposta.Resultado(False, "O GitHub não está conectado nesta máquina.")
        try:
            self._buscar(copia, site.base)
        except MarketingErro as erro:
            return proposta.Resultado(False, str(erro))
        base = f"origin/{site.base}"
        commits = proposta._git(copia, "log", "--reverse", "--format=%s", f"{base}..{s.branch}")
        lista = [c for c in commits.stdout.splitlines() if c.strip()]
        if not lista:
            return proposta.Resultado(False, "Não há nada novo para enviar.")
        try:
            blog = self.blog(site)
        except MarketingErro as erro:
            return proposta.Resultado(False, str(erro))
        artigos: list[str] = []
        if blog is not None:
            novos = proposta._git(
                copia, "diff", "--name-only", "--diff-filter=A", f"{base}...{s.branch}", "--",
                f"{blog.artigos}/*.md",
            ).stdout.split()  # fmt: skip
            artigos = [a for a in novos if not Path(a).name.startswith("_") and a != blog.modelo]
        marcadores = False
        if blog is not None and artigos:
            texto = proposta._git(copia, "show", f"{s.branch}:{artigos[0]}").stdout
            dados = frente(texto)
            rascunho = blog.campo("rascunho")
            if dados.get(rascunho) is not True:
                return proposta.Resultado(
                    False,
                    f"O artigo precisa ir como rascunho ({rascunho}: true). Peça para corrigir.",
                )
            marcadores = bool(blog.marcador) and blog.marcador in texto
            slug = Path(artigos[0]).stem
            destino = f"blog/{slug}"
            titulo = f"blog: {dados.get(blog.campo('titulo'), slug)}"
        else:
            destino, titulo = f"site/{_slug(s.nome.split('·')[-1])}-{s.id}", lista[0]
        arquivo = copia / CORPO_PR
        corpo = arquivo.read_text() if arquivo.is_file() else "\n".join(f"- {c}" for c in lista)
        aberto = proposta._rodar(
            [gh, "pr", "list", "--state", "open", "--head", destino, "--json", "url"], copia
        )
        try:
            ja = json.loads(aberto.stdout) if aberto.returncode == 0 else []
        except ValueError:
            ja = []
        if ja:
            envio = proposta.enviar(copia, gh, "--force-with-lease", f"{s.branch}:{destino}")
            if envio.returncode != 0:
                return proposta.Resultado(False, "Não consegui atualizar a branch no GitHub.")
            return proposta.Resultado(True, "Atualizei o PR que já estava aberto.", ja[0]["url"])
        if proposta.enviar(copia, gh, f"{s.branch}:refs/heads/{destino}").returncode != 0:
            return proposta.Resultado(False, "Não consegui enviar a branch ao GitHub.")
        pr = proposta._rodar(
            [gh, "pr", "create", "--base", site.base, "--head", destino,
             "--title", titulo, "--body", corpo],
            copia,
        )  # fmt: skip
        endereco = next(iter(re.findall(r"https://\S+/pull/\d+", pr.stdout)), "")
        if pr.returncode != 0 or not endereco:
            proposta.enviar(copia, gh, "--delete", destino)
            return proposta.Resultado(False, "Enviei a branch, mas o GitHub não abriu o PR.")
        numero = endereco.rsplit("/", 1)[-1]
        aviso = " Tem marcadores para você preencher." if marcadores else ""
        return proposta.Resultado(True, f"Abri o PR {numero}.{aviso}", endereco)


PADRAO = Marketing()
