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
import subprocess
import threading
import time
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from zervis import lugares
from zervis.marca import Marca, cores_validas, ler_marca
from zervis.oficina import proposta
from zervis.oficina.agentes import LIVRES_DA_SESSAO

ARQUIVO = lugares.CONFIG / "marketing.json"
MANIFESTO = "zervis.json"  # o contrato do site com o Zé, na raiz do repositório
VERSAO = 1
CAMPOS = {"titulo": "title", "categoria": "category", "data": "date", "rascunho": "draft"}
CORPO_PR = ".ze-pr.md"  # o corpo do PR que a sessão escreve na raiz da cópia, sem commit
PREFIXOS = ("blog/", "site/")  # as branches que o Zé abre no repositório do site
ORIGEM = "marketing"
NOMES = {"artigo": "Blog", "site": "Site"}
PENDENTES = lugares.ESTADO / "marketing.json"  # as sessões que esperam publicar e os PRs delas
COMANDO = re.compile(r"[\w@./=:{}, -]+")  # um comando do zervis.json: sem caractere de shell
# Numa cópia isolada e protegida, sem como enviar nada: a sessão segue sem esperar ninguém.
GIT_LIVRES = [f"Bash(git {c}:*)" for c in ("status", "diff", "log", "add", "commit", "show")]
PRAZO_DEPLOY_S = 600.0
LIMITE_MANUAL = 6000

TAREFA_ARTIGO = """Escreva um artigo para o blog deste site seguindo à risca o manual {manual} \
(o contrato do blog) e o modelo {modelo}. Leia os dois antes de começar.

Tema: {tema}

- Liste {pasta} para não repetir tema nem palavra-chave.
- {instalar} e {validar}, até não sobrar erro. Rode um comando por vez, sem juntar com `;`, \
`&&` ou `|`: assim eles rodam sem esperar aprovação.
- Entregue com `{rascunho}: true` e com os marcadores de experiência real que o manual pede. Não \
invente casos, clientes, números nem resultados.
- Faça um commit só, com a mensagem que o manual indica.
- Não envie a branch nem abra PR: quem publica é o Zé, depois de você terminar.
- Grave o corpo do PR, no modelo do manual, no arquivo {corpo} na raiz do projeto, sem commit. \
Deixe o link do preview como está no modelo: a Vercel cria o preview depois do PR."""

TAREFA_PUBLICAR = """O usuário aprovou o artigo {arquivo}. Prepare a publicação, sem enviar nada:

- {respostas}
- Mude `{rascunho}` para false e ponha a data de hoje ({hoje}) em `{data}`.
- Confira que não sobrou nenhum marcador de experiência real{marcador}.
- {validar}, e faça um commit: "blog: publica <título>".
- Não envie a branch: quem publica é o Zé, depois de você terminar."""

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
    instalar: str = ""  # o comando que instala as dependências (npm ci, por exemplo)
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
        validar=_comando(blog.get("validar")),
        instalar=_comando(blog.get("instalar") or dados.get("instalar")),
        marcador=str(blog.get("marcador", "")).strip(),
        campos=tuple(campos.items()),
    )


def _comando(valor: Any) -> str:
    texto = " ".join(str(valor or "").split())
    if texto and not COMANDO.fullmatch(texto):
        raise MarketingErro("O zervis.json do site tem um comando inválido.")
    return texto


def livres(blog: Blog | None) -> list[str]:
    """O que a sessão de marketing roda sem pedir: o git da cópia e os comandos do site."""
    regras = list(GIT_LIVRES)
    if blog is not None and blog.instalar:
        regras.append(f"Bash({blog.instalar})")
    if blog is not None and blog.validar:
        prefixo = re.sub(r"\s*--\s*$", "", blog.validar.split("{slug}")[0].strip())
        if prefixo:
            regras += [f"Bash({prefixo})", f"Bash({prefixo}:*)"]
    return regras


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
    def __init__(
        self, arquivo: Path = ARQUIVO, gh: str | None = None, pendentes: Path = PENDENTES
    ) -> None:
        self.arquivo = arquivo
        self._gh = gh
        self.pendentes = pendentes
        self._trava = threading.Lock()
        # Como o Zé avisa o que acontece depois (o PR, o deploy): o núcleo liga ao subir.
        self.avisar: Callable[[str], None] | None = None

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
        self._gravar_config(site=asdict(site))
        return site

    def _config(self) -> dict[str, Any]:
        try:
            dados = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def _gravar_config(self, **partes: Any) -> None:
        dados = {**self._config(), **partes}
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_suffix(".next")
        temporario.write_text(json.dumps(dados, ensure_ascii=False))
        temporario.replace(self.arquivo)

    # --- a marca --------------------------------------------------------------------------

    def marca_do_site(self) -> Marca | None:
        site = self.site()
        if not site.pasta or not site.base:
            return None
        texto = self._mostrar(site, MANIFESTO)
        return ler_marca(texto) if texto else None

    def paleta(self) -> dict[str, Any]:
        """A escolha de Marketing: "site" (a do `zervis.json`) ou "propria", com as cores."""
        escolha = self._config().get("marca") or {}
        escolha = escolha if isinstance(escolha, dict) else {}
        modo = "propria" if escolha.get("paleta") == "propria" else "site"
        return {"paleta": modo, "cores": cores_validas(escolha.get("cores"))}

    def marca(self) -> Marca:
        """A marca dos posts: a do site, com a paleta própria por cima, se foi escolhida."""
        base = self.marca_do_site() or Marca()
        escolha = self.paleta()
        if escolha["paleta"] == "propria" and escolha["cores"]:
            return replace(base, cores=tuple({**dict(base.cores), **escolha["cores"]}.items()))
        return base

    def guardar_paleta(self, paleta: str, cores: dict[str, Any]) -> Marca:
        if paleta not in ("site", "propria"):
            raise MarketingErro("Paleta desconhecida.")
        validas = cores_validas(cores)
        if paleta == "propria" and not validas:
            raise MarketingErro("Escolha as cores da paleta.")
        self._gravar_config(marca={"paleta": paleta, "cores": validas})
        return self.marca()

    def logo(self) -> bytes:
        """O logo declarado pelo site, como está na base (vazio se não houver)."""
        site, marca = self.site(), self.marca_do_site()
        if not site.pasta or marca is None or not marca.logo:
            return b""
        feito = subprocess.run(  # noqa: S603 (git com argumentos montados aqui)
            ["/usr/bin/git", "-C", site.pasta, "show", f"origin/{site.base}:{marca.logo}"],
            capture_output=True, timeout=30, check=False,
        )  # fmt: skip
        return feito.stdout if feito.returncode == 0 else b""

    def manual(self) -> str:
        """O manual do blog do site, para os posts seguirem a mesma linha (cortado)."""
        try:
            blog = self.blog()
        except MarketingErro:
            return ""
        return self._mostrar(self.site(), blog.manual)[:LIMITE_MANUAL] if blog else ""

    def artigo(self, slug: str) -> str:
        """O texto de um artigo da base, pelo slug."""
        site = self.site()
        try:
            blog = self.blog(site)
        except MarketingErro:
            return ""
        if blog is None or not re.fullmatch(r"[a-z0-9-]{1,120}", slug):
            return ""
        return self._mostrar(site, f"{blog.artigos}/{slug}.md")

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
        (sessoes.pasta / s.id / LIVRES_DA_SESSAO).write_text(json.dumps(livres(blog)))
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
                instalar=(
                    f"Se faltarem as dependências, instale com `{blog.instalar}`"
                    if blog.instalar
                    else "Instale as dependências se faltarem"
                ),
                corpo=CORPO_PR,
            )  # fmt: skip
        else:
            tarefa = TAREFA_SITE.format(pedido=texto, corpo=CORPO_PR)
        return sessoes.enviar(s.id, tarefa)

    def pedidos(self, sessoes: Any) -> list[dict[str, Any]]:
        estado = self._estado()
        return [
            {
                "id": s.id,
                "nome": s.nome,
                "estado": s.estado,
                "pr": estado["prs"].get(s.id, ""),
                "publicando": s.id in estado["publicar"],
            }
            for s in sessoes.listar()
            if s.origem == ORIGEM
        ]

    # --- o estado: as sessões que esperam publicar e o PR de cada uma ---------------------

    def _estado(self) -> dict[str, Any]:
        try:
            dados = json.loads(self.pendentes.read_text())
        except (OSError, ValueError):
            dados = {}
        dados = dados if isinstance(dados, dict) else {}
        return {"publicar": list(dados.get("publicar") or []), "prs": dict(dados.get("prs") or {})}

    def _mudar_estado(self, mudar: Callable[[dict[str, Any]], None]) -> None:
        with self._trava:
            dados = self._estado()
            mudar(dados)
            self.pendentes.parent.mkdir(parents=True, exist_ok=True)
            temporario = self.pendentes.with_suffix(".next")
            temporario.write_text(json.dumps(dados, ensure_ascii=False))
            temporario.replace(self.pendentes)

    # --- o PR -------------------------------------------------------------------------------

    def _sessao(self, sessoes: Any, ref: str) -> Any:
        s = sessoes.achar(ref)
        if s.origem != ORIGEM or not s.worktree:
            raise MarketingErro("Esta sessão não é um pedido de marketing.")
        if s.estado == "trabalhando":
            raise MarketingErro("A sessão ainda está trabalhando.")
        if proposta._git(
            Path(s.worktree), "status", "--porcelain", "--untracked-files=no"
        ).stdout.strip():
            raise MarketingErro("A cópia tem alterações sem commit.")
        return s

    def _artigo(self, copia: Path, base: str, branch: str, blog: Blog | None) -> str:
        """O artigo novo da sessão (o caminho no repositório), ou vazio numa mudança no site."""
        if blog is None:
            return ""
        novos = proposta._git(
            copia, "diff", "--name-only", "--diff-filter=A", f"{base}...{branch}", "--",
            f"{blog.artigos}/*.md",
        ).stdout.split()  # fmt: skip
        return next((a for a in novos if not Path(a).name.startswith("_") and a != blog.modelo), "")

    @staticmethod
    def _destino(s: Any, artigo: str) -> str:
        if artigo:
            return f"blog/{Path(artigo).stem}"
        return f"site/{_slug(s.nome.split('·')[-1])}-{s.id}"

    def abrir_pr(self, sessoes: Any, ref: str) -> proposta.Resultado:
        """Envia a branch da sessão e abre o PR na base. Artigo sai como rascunho, sempre."""
        try:
            site = self._exigir_site()
            s = self._sessao(sessoes, ref)
            copia = Path(s.worktree)
            self._buscar(copia, site.base)
            blog = self.blog(site)
        except MarketingErro as erro:
            return proposta.Resultado(False, str(erro))
        gh = self.gh
        if not gh:
            return proposta.Resultado(False, "O GitHub não está conectado nesta máquina.")
        base = f"origin/{site.base}"
        commits = proposta._git(copia, "log", "--reverse", "--format=%s", f"{base}..{s.branch}")
        lista = [c for c in commits.stdout.splitlines() if c.strip()]
        if not lista:
            return proposta.Resultado(False, "Não há nada novo para enviar.")
        artigo = self._artigo(copia, base, s.branch, blog)
        marcadores = False
        titulo = lista[0]
        if blog is not None and artigo:
            texto = proposta._git(copia, "show", f"{s.branch}:{artigo}").stdout
            dados = frente(texto)
            rascunho = blog.campo("rascunho")
            if dados.get(rascunho) is not True:
                return proposta.Resultado(
                    False,
                    f"O artigo precisa ir como rascunho ({rascunho}: true). Peça para corrigir.",
                )
            marcadores = bool(blog.marcador) and blog.marcador in texto
            titulo = f"blog: {dados.get(blog.campo('titulo'), Path(artigo).stem)}"
        destino = self._destino(s, artigo)
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
            envio = proposta.enviar(copia, gh, f"+{s.branch}:refs/heads/{destino}")
            if envio.returncode != 0:
                return proposta.Resultado(False, "Não consegui atualizar a branch no GitHub.")
            self._mudar_estado(lambda d: d["prs"].__setitem__(s.id, ja[0]["url"]))
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
        self._mudar_estado(lambda d: d["prs"].__setitem__(s.id, endereco))
        numero = endereco.rsplit("/", 1)[-1]
        aviso = " Tem marcadores para você responder." if marcadores else ""
        return proposta.Resultado(True, f"Abri o PR {numero}.{aviso}", endereco)

    # --- publicar ---------------------------------------------------------------------------

    def publicar(self, sessoes: Any, ref: str, respostas: str = "") -> proposta.Resultado:
        """O "aprovado" de quem usa. Num artigo, a sessão tira o rascunho (e encaixa as
        respostas aos marcadores, se vierem) e, quando ela terminar, o Zé envia à base. Numa
        mudança no site, envia à base agora."""
        try:
            site = self._exigir_site()
            s = self._sessao(sessoes, ref)
            copia = Path(s.worktree)
            self._buscar(copia, site.base)
            blog = self.blog(site)
        except MarketingErro as erro:
            return proposta.Resultado(False, str(erro))
        artigo = self._artigo(copia, f"origin/{site.base}", s.branch, blog)
        if blog is None or not artigo:
            return self.finalizar(sessoes, s.id)
        respostas = " ".join(respostas.split())
        tarefa = TAREFA_PUBLICAR.format(
            arquivo=artigo,
            respostas=(
                f"Encaixe estas respostas do usuário nos marcadores, cada uma no lugar do seu, "
                f"com as palavras dele e sem acrescentar fatos: {respostas}"
                if respostas
                else "Tire os marcadores de experiência real sem resposta (o parágrafo inteiro "
                "de cada um); o texto em volta continua."
            ),
            rascunho=blog.campo("rascunho"),
            data=blog.campo("data"),
            hoje=date.today().isoformat(),
            marcador=f" (`{blog.marcador}`)" if blog.marcador else "",
            validar=(
                f"Valide com `{blog.validar}`" if blog.validar else "Rode a validação do manual"
            ),
        )
        self._mudar_estado(lambda d: d["publicar"].append(s.id))
        sessoes.enviar(s.id, tarefa)
        return proposta.Resultado(True, "Preparando a publicação. Aviso quando estiver no ar.")

    def finalizar(self, sessoes: Any, ref: str) -> proposta.Resultado:
        """Envia a branch da sessão direto à base (sem commit de merge: o autor dos commits é o
        de quem usa, que o deploy aceita) e acompanha o deploy."""
        try:
            site = self._exigir_site()
            s = self._sessao(sessoes, ref)
            copia = Path(s.worktree)
            self._buscar(copia, site.base)
            blog = self.blog(site)
        except MarketingErro as erro:
            return proposta.Resultado(False, str(erro))
        gh = self.gh
        if not gh:
            return proposta.Resultado(False, "O GitHub não está conectado nesta máquina.")
        base = f"origin/{site.base}"
        artigo = self._artigo(copia, base, s.branch, blog)
        if blog is not None and artigo:
            texto = proposta._git(copia, "show", f"{s.branch}:{artigo}").stdout
            if frente(texto).get(blog.campo("rascunho")) is not False:
                return proposta.Resultado(False, "O artigo ainda está como rascunho.")
            if blog.marcador and blog.marcador in texto:
                return proposta.Resultado(False, "O artigo ainda tem marcador para responder.")
        if not proposta._git(copia, "log", "--format=%h", f"{base}..{s.branch}").stdout.strip():
            return proposta.Resultado(False, "Não há nada novo para publicar.")
        atras = proposta._git(copia, "merge-base", "--is-ancestor", base, s.branch).returncode
        sem_hooks = ("-c", "core.hooksPath=/dev/null")  # fora do isolamento, nada do site roda
        if atras != 0 and proposta._git(copia, *sem_hooks, "rebase", "--quiet", base).returncode:
            proposta._git(copia, "rebase", "--abort")
            return proposta.Resultado(
                False, "O site mudou e não consegui juntar. Peça à sessão para atualizar."
            )
        destino = self._destino(s, artigo)
        proposta.enviar(copia, gh, f"+{s.branch}:refs/heads/{destino}")  # o PR fica igual
        if proposta.enviar(copia, gh, f"{s.branch}:refs/heads/{site.base}").returncode != 0:
            return proposta.Resultado(
                False,
                f"A branch {site.base} não aceitou o envio direto. Publique pelo GitHub, com "
                "Rebase and merge.",
            )
        sha = proposta._git(copia, "rev-parse", s.branch).stdout.strip()
        self._mudar_estado(lambda d: d["prs"].pop(s.id, None))
        if self.avisar is not None:
            threading.Thread(
                target=self._vigiar_deploy, args=(sha, s.nome), name="deploy", daemon=True
            ).start()
        return proposta.Resultado(True, f"Enviei à {site.base}. Aviso quando o deploy terminar.")

    def ao_terminar(self, sessoes: Any, ref: str) -> str:
        """A sessão de marketing terminou: publica, se a pessoa já aprovou, ou abre o PR. Devolve
        o que avisar."""
        estado = self._estado()
        if ref in estado["publicar"]:
            self._mudar_estado(lambda d: d["publicar"].remove(ref))
            r = self.finalizar(sessoes, ref)
            return r.texto if r.ok else f"Não publiquei: {r.texto}"
        if ref in estado["prs"]:
            return ""  # já tem PR: a sessão respondeu a outra coisa
        r = self.abrir_pr(sessoes, ref)
        if not r.ok:
            return f"O pedido de marketing terminou, mas não abri o PR: {r.texto}"
        return f"{r.texto} Para publicar, aprove em Marketing ou diga aprovado."

    # --- o deploy ---------------------------------------------------------------------------

    def implantacao(self, sha: str) -> tuple[str, str]:
        """O deploy de produção deste commit, pelo GitHub: ("ok", endereço), ("falhou", motivo)
        ou ("esperando", "")."""
        site, gh = self.site(), self.gh
        if not site.pasta or not gh:
            return "esperando", ""
        pasta = Path(site.pasta)
        repo = proposta._rodar([gh, "repo", "view", "--json", "nameWithOwner", "-q",
                                ".nameWithOwner"], pasta).stdout.strip()  # fmt: skip
        if not repo:
            return "esperando", ""
        consulta = proposta._rodar(
            [gh, "api", f"repos/{repo}/deployments?sha={sha}", "--jq",
             '[.[] | select(.environment | ascii_downcase == "production") | .id]'],
            pasta,
        )  # fmt: skip
        try:
            ids = json.loads(consulta.stdout or "[]")
        except ValueError:
            return "esperando", ""
        for id_ in ids:
            estado = proposta._rodar(
                [gh, "api", f"repos/{repo}/deployments/{id_}/statuses", "--jq",
                 ".[0] | [.state, (.description // \"\"), (.environment_url // \"\")]"],
                pasta,
            )  # fmt: skip
            try:
                st, descricao, endereco = json.loads(estado.stdout or '["", "", ""]')
            except ValueError:
                continue
            if st == "success":
                return "ok", str(endereco)
            if st in ("failure", "error"):
                return "falhou", str(descricao)
        return "esperando", ""

    def _vigiar_deploy(self, sha: str, nome: str, intervalo: float = 15.0) -> None:
        fim = time.monotonic() + PRAZO_DEPLOY_S
        while time.monotonic() < fim:
            estado, detalhe = self.implantacao(sha)
            if estado == "ok":
                self._avisar(f"{nome}: está no ar.")
                return
            if estado == "falhou":
                self._avisar(f"{nome}: o deploy falhou ({detalhe}).")
                return
            time.sleep(intervalo)
        self._avisar(f"{nome}: o deploy não respondeu em 10 minutos. Confira no provedor.")

    def _avisar(self, texto: str) -> None:
        if self.avisar is not None:
            self.avisar(texto)


PADRAO = Marketing()
