"""Skills do JARVIS (Fase 6; docs/02-investigacao-hermes.md, seção 2; ADR 0011).

Uma pasta por skill em `~/.local/share/zervis/skills/<nome>/` com `SKILL.md` no padrão aberto
agentskills.io (front matter com `name` e `description`, o mesmo formato do Claude Code, do Codex
e do Hermes) e arquivos de apoio opcionais. Para dar uma skill ao JARVIS basta pôr a pasta ali.

Carregamento progressivo, como no Hermes, mas mais econômico: no prompt vai só uma linha por
skill (nome e descrição, com teto total), dentro da foto congelada; o corpo é lido sob demanda.
Criar ou corrigir uma skill passa pela aprovação falada, com o diff mostrado no Barehands; a
versão anterior vai para `.historico/` (nada se perde). Cada leitura conta como um uso.

Curadoria determinística (como no Hermes, sem modelo): skill sem uso há muito tempo sai do
catálogo para `.arquivo/`, onde nada se perde; voltar é mover a pasta de volta. Assim o catálogo
que vai em toda conversa só carrega o que o usuário de fato usa.
"""

import contextlib
import difflib
import json
import re
import shutil
import time
from pathlib import Path

from jarvis.memoria.curta import varrer

NOME = re.compile(r"[a-z0-9][a-z0-9-]{1,47}")
LIMITE_SKILL = 12_000  # caracteres do SKILL.md: maior que isso, a skill virou manual
LIMITE_LINHA = 200  # descrição no catálogo
LIMITE_CATALOGO = 3_000  # o catálogo inteiro no prompt
FRENTE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class SkillErro(ValueError):
    pass


def frente(conteudo: str) -> dict[str, str]:
    """Os campos simples do front matter (`chave: valor` numa linha)."""
    achado = FRENTE.match(conteudo)
    if not achado:
        return {}
    campos = {}
    for linha in achado.group(1).splitlines():
        chave, separador, valor = linha.partition(":")
        if separador and not linha.startswith((" ", "\t")):
            campos[chave.strip()] = valor.strip().strip("\"'")
    return campos


def e_para_sessoes(campos: dict[str, str]) -> bool:
    return campos.get("sessoes", "").strip().lower() in ("sim", "true", "yes")


class Skills:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta

    def _dir(self, nome: str) -> Path:
        if not NOME.fullmatch(nome):
            raise SkillErro("nome de skill inválido: use minúsculas, números e hífen")
        return self.pasta / nome

    def listar(self) -> list[tuple[str, str]]:
        if not self.pasta.is_dir():
            return []
        skills = []
        for arquivo in sorted(self.pasta.glob("*/SKILL.md")):
            if arquivo.parent.name.startswith("."):
                continue
            try:
                campos = frente(arquivo.read_text())
            except OSError:
                continue
            descricao = " ".join(campos.get("description", "").split())
            skills.append((arquivo.parent.name, descricao[:LIMITE_LINHA]))
        return skills

    def sugeridas(self) -> list[tuple[str, str]]:
        """Skills iniciais do Zé que ainda não foram instaladas por quem usa."""
        instaladas = {
            pasta.name for pasta in self.pasta.glob("*") if pasta.is_dir() or pasta.is_symlink()
        } | set(self.arquivadas())
        base = Path(__file__).with_name("iniciais")
        saida = []
        for arquivo in sorted(base.glob("*/SKILL.md")):
            nome = arquivo.parent.name
            if nome in instaladas:
                continue
            try:
                campos = frente(arquivo.read_text())
            except OSError:
                continue
            descricao = " ".join(campos.get("description", "").split())
            if campos.get("name") == nome and descricao:
                saida.append((nome, descricao[:LIMITE_LINHA]))
        return saida

    def instalar_sugerida(self, nome: str) -> None:
        """Copia uma skill inicial para a pasta do usuário, sem sobrescrever nada."""
        self._dir(nome)
        origem = Path(__file__).with_name("iniciais") / nome / "SKILL.md"
        if not origem.is_file():
            raise SkillErro("skill sugerida não existe")
        alvos = (self.pasta / nome, self.pasta / ".arquivo" / nome)
        if any(alvo.exists() or alvo.is_symlink() for alvo in alvos):
            raise SkillErro(f"a skill {nome} já está instalada")
        conteudo = self.novo_conteudo(nome, conteudo=origem.read_text())
        self.gravar(nome, conteudo)

    def para_sessoes(self) -> list[tuple[str, str]]:
        """As skills marcadas "Também nas sessões de código" (`sessoes: sim` no cabeçalho): só
        elas vão para os agentes de código; uma skill pessoal ("resumo do dia") não tem nada a
        fazer numa sessão de programação (13/10/2026)."""
        marcadas = []
        for nome, descricao in self.listar():
            with contextlib.suppress(OSError):
                if e_para_sessoes(frente((self.pasta / nome / "SKILL.md").read_text())):
                    marcadas.append((nome, descricao))
        return marcadas

    def catalogo(self, lista: list[tuple[str, str]] | None = None) -> str:
        linhas = ["## Skills (leia a skill antes de uma tarefa que ela cobre)"]
        tamanho = 0
        for nome, descricao in self.listar() if lista is None else lista:
            linha = f"- {nome}: {descricao}"
            if tamanho + len(linha) > LIMITE_CATALOGO:
                linhas.append("- (há mais skills; liste com a ferramenta de skills)")
                break
            linhas.append(linha)
            tamanho += len(linha)
        if len(linhas) == 1:
            linhas.append("(nenhuma ainda)")
        return "\n".join(linhas)

    def ver(self, nome: str, arquivo: str = "") -> str:
        base = self._dir(nome)
        alvo = (base / (arquivo or "SKILL.md")).resolve()
        if base.resolve() not in alvo.parents or not alvo.is_file():
            raise SkillErro(f"não achei {arquivo or 'a skill'} em {nome}")
        texto = alvo.read_text()
        if not arquivo:
            self._contar_uso(nome)
        return texto

    def uso(self) -> dict[str, dict[str, int]]:
        """Por skill: `usos` e `ultimo` (época) da última leitura."""
        try:
            uso = json.loads((self.pasta / ".uso.json").read_text())
        except (OSError, ValueError):
            return {}
        return uso if isinstance(uso, dict) else {}

    def arquivadas(self) -> list[str]:
        base = self.pasta / ".arquivo"
        return sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []

    def arquivar_paradas(self, dias: float, agora: float) -> list[str]:
        """Move para `.arquivo/` as skills sem uso há `dias` (nunca usada: conta da gravação)."""
        uso = self.uso()
        limite = agora - dias * 86_400
        arquivadas = []
        for nome, _ in self.listar():
            base = self.pasta / nome
            ultimo = uso.get(nome, {}).get("ultimo") or (base / "SKILL.md").stat().st_mtime
            if ultimo >= limite:
                continue
            destino = self.pasta / ".arquivo" / nome
            if destino.exists():
                destino = destino.with_name(f"{nome}-{time.strftime('%Y%m%d-%H%M%S')}")
            destino.parent.mkdir(exist_ok=True, mode=0o700)
            shutil.move(base, destino)
            arquivadas.append(nome)
        return arquivadas

    def ligar(self, nome: str, ligada: bool) -> None:
        """Desligada = em `.arquivo/` (fora do catálogo, nada se perde); ligar traz de volta."""
        self._dir(nome)
        ativa, arquivada = self.pasta / nome, self.pasta / ".arquivo" / nome
        origem, destino = (arquivada, ativa) if ligada else (ativa, arquivada)
        if not origem.is_dir():
            if destino.is_dir():
                return
            raise SkillErro(f"a skill {nome} não existe")
        if destino.exists():
            raise SkillErro(f"já existe outra {nome} {'ligada' if ligada else 'desligada'}")
        destino.parent.mkdir(exist_ok=True, mode=0o700)
        shutil.move(origem, destino)

    def excluir(self, nome: str) -> None:
        """Vai para `.lixeira/` com a data: some do painel, mas dá para recuperar à mão."""
        self._dir(nome)
        for origem in (self.pasta / nome, self.pasta / ".arquivo" / nome):
            if origem.is_dir():
                lixeira = self.pasta / ".lixeira"
                lixeira.mkdir(exist_ok=True, mode=0o700)
                shutil.move(origem, lixeira / f"{nome}-{time.strftime('%Y%m%d-%H%M%S')}")
                return
        raise SkillErro(f"a skill {nome} não existe")

    def _contar_uso(self, nome: str) -> None:
        arquivo = self.pasta / ".uso.json"
        uso = self.uso()
        registro = uso.setdefault(nome, {"usos": 0})
        registro["usos"] += 1
        registro["ultimo"] = round(time.time())
        temporario = arquivo.with_suffix(".next")
        temporario.write_text(json.dumps(uso))
        temporario.replace(arquivo)

    # --- escrita (sempre aprovada pelo usuário) -----------------------------------------------

    def atual(self, nome: str) -> str:
        arquivo = self._dir(nome) / "SKILL.md"
        return arquivo.read_text() if arquivo.is_file() else ""

    def novo_conteudo(self, nome: str, conteudo: str = "", antigo: str = "", novo: str = "") -> str:
        """O SKILL.md como ficaria (criar: `conteudo`; corrigir: troca `antigo` por `novo`)."""
        if antigo:
            atual = self.atual(nome)
            if not atual:
                raise SkillErro(f"a skill {nome} não existe")
            if atual.count(antigo) != 1:
                raise SkillErro("o trecho a corrigir precisa aparecer exatamente uma vez")
            conteudo = atual.replace(antigo, novo)
        elif self.atual(nome):
            raise SkillErro(f"a skill {nome} já existe; corrija um trecho dela")
        campos = frente(conteudo)
        if campos.get("name") != nome or not campos.get("description"):
            raise SkillErro(
                "o SKILL.md precisa de front matter com name igual ao nome e description"
            )
        if len(conteudo) > LIMITE_SKILL:
            raise SkillErro(f"skill grande demais ({len(conteudo)} de {LIMITE_SKILL} caracteres)")
        if motivo := varrer(conteudo.replace("§", "")):
            raise SkillErro(f"bloqueado pela varredura de segurança ({motivo})")
        return conteudo

    def diff(self, nome: str, conteudo: str) -> str:
        linhas = difflib.unified_diff(
            self.atual(nome).splitlines(),
            conteudo.splitlines(),
            "antes",
            "depois",
            lineterm="",
            n=1,
        )
        return "\n".join(linhas)

    def gravar(self, nome: str, conteudo: str) -> None:
        base = self._dir(nome)
        anterior = self.atual(nome)
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        if anterior:
            historico = self.pasta / ".historico"
            historico.mkdir(exist_ok=True, mode=0o700)
            (historico / f"{nome}-{time.strftime('%Y%m%d-%H%M%S')}.md").write_text(anterior)
        temporario = base / "SKILL.md.next"
        temporario.write_text(conteudo)
        temporario.replace(base / "SKILL.md")


def _descricao(conteudo: str) -> tuple[str, str]:
    """Nome e descrição do front matter de uma skill de agente, inclusive a descrição em várias
    linhas (`description: >`), que o padrão permite."""
    achado = FRENTE.match(conteudo)
    if not achado:
        return "", ""
    nome, descricao, juntando = "", "", False
    for linha in achado.group(1).splitlines():
        if juntando and linha.startswith((" ", "\t")):
            descricao = f"{descricao} {linha.strip()}".strip()
            continue
        juntando = False
        chave, _, valor = linha.partition(":")
        valor = valor.strip().strip("\"'")
        if chave.strip() == "name":
            nome = valor
        elif chave.strip() == "description":
            juntando = valor in (">", "|", ">-", "|-")
            descricao = "" if juntando else valor
    return nome, descricao


def dos_agentes() -> list[dict[str, str]]:
    """As skills que a pessoa já tem nos agentes (as pastas `skills` do Claude Code e do Codex da
    conta em uso): as sessões de código daquele agente já as usam sozinhas. Só leitura."""
    from jarvis.cerebro import contas

    saida = []
    for agente in ("claude", "codex"):
        try:
            pasta = contas.Contas().em_uso(agente).onde / "skills"
        except contas.ContaErro:
            continue
        for arquivo in sorted(pasta.glob("*/SKILL.md")) if pasta.is_dir() else []:
            try:
                nome, descricao = _descricao(arquivo.read_text(errors="replace")[:LIMITE_SKILL])
            except OSError:
                continue
            saida.append(
                {
                    "agente": agente,
                    "nome": nome or arquivo.parent.name,
                    "descricao": descricao[:LIMITE_LINHA],
                }
            )
    return saida
