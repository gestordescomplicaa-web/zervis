# Zé · gdautomacao.ia — a interface do Zé movida pelas mãos.
# Copyright (C) 2026 gdautomacao.ia (versão modificada, desde 2026-10-07)
# Copyright (C) 2026 Jared Rhodenizer (obra original)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later
"""O modo imersivo do Zé (Barehands modificado): serve a tela movida pelas mãos em localhost.

Faz parte do Zé desde 09/10/2026 (antes era o Barehands à parte, em outra pasta). O Zé sobe este
servidor junto com ele (`python -m jarvis.imersivo.servidor`); a página fica em `web/`, o estado
na pasta de dados do Zé (`<dados>/imersivo/state`, ou `ZE_IMERSIVO_ESTADO`) e o manifesto dos
orbes em `barehands.json`, ao lado da pasta de estado.

localhost = a secure context, which is what lets the browser open your
camera for the tracker page. Nothing here ever leaves your machine.

Endpoints:
  GET  /stage.html, /media/*   the pages + the media airlock
  POST /state                  tracker's ~45Hz scene heartbeat; the response
                               carries queued commands (the command channel)
  GET  /state                  the render page mirrors the scene from here
  POST /cmd                    board commands (your AI -> the board)
  GET  /config                 the barehands.json config (name + orbs)
  GET  /tree?orb=N             a notes orb's folder tree — read-only, JAILED
  GET  /note?f=N/<rel>         one note's text — read-only, JAILED
  GET  /props                  the media airlock as a browsable tree
  GET  /orb                    your assistant's live state (the ring reads it)

Config lives in barehands.json next to the state folder:
  { "name": "Assistant", "port": 8794,
    "orbs": [ { "title": "Guia", "path": "guia", "kind": "notes" },
              { "title": "Props", "path": "media",        "kind": "media" } ] }

"notes" orbs may point at ANY folder of markdown (an Obsidian vault is
just a folder of markdown). The "media" orb may point anywhere too, so
your props can stay where they already live; a relative path resolves
against the repo. Wherever it points is the airlock: the only place
images and models ever stage from.

Your AI drives the ring by writing tiny files into the state folder:
  state/state      one word: idle | listening | thinking | speaking
  state/mood.json  {"mood": "green"|"amber"|"red", "ts": <unix time>}
  state/expressao.json  {"expressao": "alegria"|"duvida"|"raiva"|"tristeza", "ate": <unix time>}
  state/wave.json  {"samples": [0..1 x 64], "ts": <unix time>}
Missing files are fine — the ring just idles.
"""

import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from jarvis import lugares
from jarvis.imersivo import PASTAS_ACERVO, TIPOS_ACERVO
from jarvis.imersivo.http import gravar_token

HERE = Path(__file__).resolve().parent / "web"  # a página, o avatar e o Guia
ESTADO = Path(os.environ.get("ZE_IMERSIVO_ESTADO") or lugares.DADOS / "imersivo" / "state")
# O Acervo do Zé: imagens/ e 3d/ nos dados de quem usa, nunca no repositório.
ACERVO = Path(os.environ.get("ZE_ACERVO") or lugares.DADOS / "acervo")
TOKEN = os.environ.get("ZE_IMERSIVO_TOKEN") or secrets.token_urlsafe(32)
MAXIMO_CORPO = 262144


def _exigir(condicao: object) -> None:
    """Validação de pedido que vale também com `python -O` (um assert sumiria)."""
    if not condicao:
        raise ValueError("pedido recusado")


def load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "name": "Assistant",
        "port": 8794,
        "orbs": [],
        # Seconds before a non-idle ring state is treated as stale and
        # shown as idle. Only ever rescues a writer that died without
        # saying goodbye; see the note in /orb.
        "state_timeout_s": 600,
    }
    # O manifesto de quem usa (ao lado da pasta de estado); sem ele, o padrão que vem com o Zé.
    proprio = ESTADO.parent / "barehands.json"
    try:
        arquivo = (
            proprio if proprio.is_file() else Path(__file__).with_name("barehands.padrao.json")
        )
        cfg.update(json.loads(arquivo.read_text()))
    except Exception:
        pass
    if not cfg.get("orbs"):
        cfg["orbs"] = [
            {"id": "guia", "title": "Guia", "path": "guia", "kind": "notes"},
            {"id": "acervo", "title": "Acervo", "kind": "media"},
        ]
    for orb in cfg["orbs"]:
        # Sem caminho fica sem caminho: Path("") vira "." e serviria a pasta da página.
        if orb.get("kind", "notes") in ("notes", "media") and orb.get("path"):
            orb["path"] = str(Path(str(orb["path"])).expanduser())
    return cfg


CONFIG = load_config()
try:
    STATE_TIMEOUT = float(CONFIG.get("state_timeout_s", 600))
except (TypeError, ValueError):
    STATE_TIMEOUT = 600.0


def media_root() -> Path:
    """The Acervo's folder, resolved: the manifest's path, or the Zé's own (ZE_ACERVO).

    A notes orb could always point at any folder on disk while the media orb
    was pinned to ./media, and that asymmetry cost real users something: with
    an existing library of props you had to COPY it into the repo to use it.
    Two copies of your own files, and the second one sitting inside a git
    working tree where a single `git add -A` publishes them.

    The Props orb's `path` is honoured the same way a notes orb's is now.
    Point this at the folder you already have; your files stay yours and stay
    out of the repo. A relative path still resolves against the repo, so the
    shipped default is unchanged and an existing config keeps working.
    """
    for orb in CONFIG.get("orbs", []):
        if orb.get("kind") == "media" and orb.get("path"):
            q = Path(str(orb["path"])).expanduser()
            return (q if q.is_absolute() else HERE / q).resolve()
    return ACERVO.resolve()  # sem caminho no manifesto: a pasta do Zé


def orb_root(i: str) -> Path | None:
    """Resolve a notes orb's jail root, or None."""
    try:
        orb = CONFIG["orbs"][int(i)]
        _exigir(orb.get("kind") == "notes")
        p = Path(orb["path"])
        if not p.is_absolute():
            p = HERE / p
        return p.resolve()
    except Exception:
        return None


# barehands-jarvis: GET /stats feeds the activity HUD. Numbers come from the
# Omarchy "Activity Monitor" plugin's native sampler, so the board and the bar
# agree; plain /proc is the fallback when the plugin is absent.
SAMPLER = Path.home() / ".config/omarchy/plugins/stappmus.activity-monitor/activity-sampler"
_CPU_PREV: tuple[int, int] | None = None


def _sample(mode: str) -> str:
    return subprocess.run(  # noqa: S603 (o amostrador do Omarchy, caminho fixo)
        [str(SAMPLER), mode], capture_output=True, text=True, timeout=2
    ).stdout


def system_stats() -> dict[str, int | None]:
    global _CPU_PREV
    out: dict[str, int | None] = {
        "cpu": None,
        "mem": None,
        "gpu": None,
        "vram_used": None,
        "vram_total": None,
    }
    try:
        if SAMPLER.is_file():
            rows = [line.split("\t") for line in _sample("--bar-widget").splitlines()]
            for f in rows:
                if f[0] == "cpu":
                    idle, total = int(f[1]), int(f[2])
                elif f[0] == "memory":
                    out["mem"] = round(float(f[1]))
            for f in (line.split("\t") for line in _sample("--activity-gpus").splitlines()):
                if f[0] == "gpu" and len(f) >= 8:
                    out["gpu"], out["vram_used"], out["vram_total"] = (
                        int(f[5]),
                        int(f[6]) >> 20,
                        int(f[7]) >> 20,
                    )
                    break
        else:
            v = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
            idle, total = v[3] + v[4], sum(v)
            m = dict(ln.split(":", 1) for ln in Path("/proc/meminfo").read_text().splitlines())
            mt, ma = int(m["MemTotal"].split()[0]), int(m["MemAvailable"].split()[0])
            out["mem"] = round(100 * (mt - ma) / mt)
        if _CPU_PREV and total > _CPU_PREV[1]:
            out["cpu"] = round(100 * (1 - (idle - _CPU_PREV[0]) / (total - _CPU_PREV[1])))
        _CPU_PREV = (idle, total)
    except Exception:
        pass
    return out


_STATE = b"{}"  # latest scene state: tracker POSTs, render GETs
# barehands-jarvis: hands calibration profile + camera light (jarvis_maos.py)
from jarvis.imersivo.maos import Camera, Perfil  # noqa: E402

CAMERA = Camera(ESTADO)
PERFIL = Perfil(ESTADO)
_MIRROR_READ = 0.0  # barehands-jarvis: last GET /state (render page, board-state.sh)
_CMDS: list[dict[str, Any]] = []  # queued board commands (your AI -> tracker)
_ALLOWED = (
    "add_img",
    "add_card",
    "clear",
    "reset",
    "hand",
    "give",
    "yank",
    "hover",
    "scroll_note",
    "widget",
    "explode",
    "assemble",
    "present",
)


class Handler(SimpleHTTPRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def _origem_local(self) -> bool:
        porta = cast(ThreadingHTTPServer, self.server).server_port
        hosts = {f"127.0.0.1:{porta}", f"localhost:{porta}"}
        return (
            len(self.headers.get_all("Host", [])) == 1
            and self.headers.get("Host") in hosts
            and self.headers.get("Origin") in (None, *(f"http://{host}" for host in hosts))
        )

    def _autorizado(self) -> bool:
        return self._origem_local() and hmac.compare_digest(
            self.headers.get("X-Ze-Token", "").encode(), TOKEN.encode()
        )

    def do_HEAD(self) -> None:
        if not self._origem_local():
            self._json({"erro": "Pedido não autorizado."}, 403)
            return
        super().do_HEAD()

    def translate_path(self, path: str) -> str:
        """Serve /media/* from the configured Props folder, not blindly from ./media.

        THE THIRD PLACE, and the one that would have made this a half-fix. The
        airlock check and the props tree both honour media_root(), but static
        serving resolved against the repo because the base handler is built with
        directory=HERE. Left alone, the tree would have listed a viewer's real
        props and every one of them would have 404'd.
        """
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/media/"):
            root = media_root()
            rel = urllib.parse.unquote(clean[len("/media/") :]).lstrip("/")
            target = (root / rel).resolve()
            # Same containment rule as the airlock: resolve first, then prove
            # the result is inside. A prefix comparison on strings is not it.
            if root == target or root in target.parents:
                return str(target)
            return str(root)
        return super().translate_path(path)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        # no-store on the page itself so a plain reload always serves
        # current code (Chrome happily caches through reloads otherwise)
        caminho = self.path.split("?")[0]
        if caminho.endswith(
            ("stage.html", "jarvis-cerebro.js", "jarvis-grafo.js", "jarvis-workspace.css")
        ):
            self.send_header("Cache-Control", "no-store")
        elif caminho.startswith(("/jarvis-", "/avatar/")):
            # barehands-jarvis: the Zé's own code and the avatar model change in place; without
            # this Chrome kept a replaced jarvis-chimpanze.glb for hours (08/10/2026). Revalidating
            # costs a 304 on loopback.
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def __init__(self, *a: Any, **k: Any) -> None:
        super().__init__(*a, directory=str(HERE), **k)

    def log_message(self, *a: Any) -> None:
        pass

    def _json(self, obj: Any, code: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        global _STATE
        if not self._autorizado():
            self._json({"erro": "Pedido não autorizado."}, 403)
            return
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            self._json({"erro": "Tamanho inválido."}, 400)
            return
        if not 0 <= n < MAXIMO_CORPO:
            self._json({"erro": "Tamanho inválido."}, 413 if n >= MAXIMO_CORPO else 400)
            return
        body = self.rfile.read(n) if n else b"{}"
        if self.path == "/state":
            # the tracker's heartbeat doubles as the command channel
            _STATE = body
            CAMERA.batimento = time.time()
            out = json.dumps(_CMDS[:8]).encode()
            del _CMDS[:8]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            # barehands-jarvis: tell the tracker whether anyone mirrors the
            # scene, so it streams at full rate only when it is watched.
            self.send_header("X-Mirror", "1" if time.time() - _MIRROR_READ < 5 else "0")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        if self.path == "/cmd":
            try:
                cmd = json.loads(body)
                _exigir(cmd.get("a") in _ALLOWED)
                if cmd["a"] in ("add_img", "hand", "give", "present") and cmd.get("src"):
                    # THE AIRLOCK: only files really inside ./media/ ever
                    # stage — subfolders allowed, escapes 400. If the
                    # exact path misses, a UNIQUE basename match anywhere
                    # inside the airlock self-heals a wrong-folder guess;
                    # zero or many matches still 400.
                    rel = str(cmd.get("src", "")).lstrip("/")
                    if rel.startswith("media/"):
                        rel = rel[6:]
                    media = media_root()
                    target = (media / rel).resolve()
                    if media not in target.parents or not target.is_file():
                        name = Path(rel).name.lower()
                        hits = (
                            [p for p in media.rglob("*") if p.is_file() and p.name.lower() == name]
                            if name
                            else []
                        )
                        if len(hits) != 1:
                            raise ValueError("not in the media airlock")
                        target = hits[0]
                    cmd["src"] = "/media/" + target.relative_to(media).as_posix()
                _CMDS.append(cmd)
                self.send_response(204)
            except Exception:
                self.send_response(400)
            self.end_headers()
            return
        if self.path in (
            "/maos/perfil",
            "/maos/diagnostico",
            "/camera/ajustar",
            "/camera/restaurar",
            "/tela/estado",
            "/teclado",
            "/foco",
        ):
            # barehands-jarvis: JSON only, so a random web page cannot fire
            # these without a CORS preflight (which this server never answers).
            try:
                _exigir(self.headers.get("Content-Type", "").startswith("application/json"))
                d = json.loads(body)
                if self.path == "/maos/perfil":
                    if d.get("padrao"):
                        PERFIL.padrao()
                    else:
                        PERFIL.gravar(d.get("perfil"), d.get("origem"), d.get("resumo"))
                    self._json(PERFIL.ler())
                elif self.path == "/tela/estado":
                    # gdautomacao.ia: the page's answer to the Zé (jarvis-controle.js).
                    destino = ESTADO / "tela-estado.json"
                    tmp = destino.with_suffix(".next")
                    tmp.write_text(
                        json.dumps({**d, "ts": time.time()}, ensure_ascii=False)[:200000]
                    )
                    tmp.replace(destino)
                    self._json({})
                elif self.path == "/foco":
                    # gdautomacao.ia: the "V" marked on the Foco board (jarvis-cerebro.js); the
                    # Zé reads only the new lines of state/foco-acoes.jsonl and answers aloud.
                    acao, frente = str(d.get("acao", "")), str(d.get("id", ""))
                    _exigir(acao in ("passo", "concluir", "pausar", "focar"))
                    _exigir(re.fullmatch(r"[a-z0-9-]{1,64}", frente))
                    linha = json.dumps({"id": frente, "acao": acao, "ts": time.time()}) + "\n"
                    with open(ESTADO / "foco-acoes.jsonl", "a") as f:
                        f.write(linha)
                    self._json({"ok": True})
                elif self.path == "/teclado":
                    # gdautomacao.ia: a typed request (jarvis-teclado.js); the Zé reads it
                    # like speech and answers in teclado-resposta.json.
                    texto = str(d.get("texto", "")).strip()[:2000]
                    _exigir(texto)
                    pedido = f"{time.time_ns():x}"
                    destino = ESTADO / "teclado.json"
                    tmp = destino.with_suffix(".next")
                    tmp.write_text(
                        json.dumps(
                            {"id": pedido, "texto": texto, "ts": time.time()}, ensure_ascii=False
                        )
                    )
                    tmp.replace(destino)
                    self._json({"id": pedido})
                elif self.path == "/maos/diagnostico":
                    destino = ESTADO / "maos-diagnostico.json"
                    tmp = destino.with_suffix(".next")
                    tmp.write_text(
                        json.dumps({**d, "ts": time.time()}, ensure_ascii=False)[:200000]
                    )
                    tmp.replace(destino)
                    self._json({})
                elif self.path == "/camera/ajustar":
                    self._json(CAMERA.ajustar(str(d.get("nome", "")), d.get("valores")))
                else:
                    self._json(CAMERA.restaurar(str(d.get("nome", "")) or None))
            except Exception as e:
                self._json({"erro": str(e)[:200]}, 400)
            return
        if self.path == "/cerebro":
            # barehands-jarvis: a tap on a brain chip in the HUD. Only an id
            # the Zé itself listed in state/cerebros.json is accepted; the
            # Zé picks state/escolha.json up and switches. JSON only, so a
            # random web page cannot fire it without a CORS preflight.
            try:
                _exigir(self.headers.get("Content-Type", "").startswith("application/json"))
                escolha = str(json.loads(body).get("id", ""))
                lista = json.loads((ESTADO / "cerebros.json").read_text())["lista"]
                _exigir(escolha in {c["id"] for c in lista})
                destino = ESTADO / "escolha.json"
                tmp = destino.with_suffix(".next")
                tmp.write_text(json.dumps({"id": escolha, "ts": time.time()}))
                tmp.replace(destino)
                self.send_response(204)
            except Exception:
                self.send_response(400)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:
        if not self._origem_local():
            self._json({"erro": "Pedido não autorizado."}, 403)
            return
        caminho = self.path.split("?", 1)[0]
        if caminho in ("/", "/stage.html"):
            pagina = (HERE / "stage.html").read_bytes().replace(b"__ZE_TOKEN__", TOKEN.encode())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(pagina)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(pagina)
            return
        leitura = caminho.startswith(("/tree", "/note", "/jarvis/", "/camera/")) or caminho in (
            "/config",
            "/props",
            "/stats",
            "/cerebros",
            "/maos/perfil",
            "/orb",
            "/state",
        )
        if leitura and not self._autorizado():
            self._json({"erro": "Pedido não autorizado."}, 403)
            return
        if self.path == "/config":
            # the page builds its ring name + orb bloom from this
            # gdautomacao.ia: the orbs are the Núcleo's manifest (id, title, kind,
            # spoken aliases, what each one holds); folders stay server-side.
            self._json(
                {
                    "name": CONFIG.get("name", "Assistant"),
                    "orbs": [
                        {
                            "id": str(o.get("id") or o.get("title", "?")).lower(),
                            "title": o.get("title", "?"),
                            "kind": o.get("kind", "notes"),
                            "apelidos": [str(a) for a in o.get("apelidos", [])][:20],
                            "descricao": str(o.get("descricao", ""))[:300],
                        }
                        for o in CONFIG["orbs"]
                    ],
                }
            )
            return
        if self.path.startswith("/tree"):
            # a notes orb's folder tree. Jailed to that orb's configured
            # folder, .md only, CLAUDE.md (AI config, not a note) excluded.
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            idx = (q.get("orb") or ["0"])[0]
            raiz = orb_root(idx)
            if raiz is None or not raiz.is_dir():
                self._json({"name": "?", "notes": [], "dirs": []}, 404)
                return
            jaula: Path = raiz

            def walk(d: Path) -> dict[str, Any]:
                out: dict[str, Any] = {"name": d.name, "notes": [], "dirs": []}
                for p in sorted(d.iterdir()):
                    if p.name.startswith("."):
                        continue
                    if p.is_dir():
                        sub = walk(p)
                        if sub["notes"] or sub["dirs"]:
                            out["dirs"].append(sub)
                    elif p.suffix == ".md" and p.name != "CLAUDE.md":
                        # note files travel as "<orb>/<relpath>" so /note
                        # knows which jail to resolve them against
                        out["notes"].append(
                            {
                                "title": p.stem,
                                "file": f"{int(idx)}/{p.relative_to(jaula).as_posix()}",
                            }
                        )
                return out

            try:
                tree = walk(jaula)
                tree["name"] = CONFIG["orbs"][int(idx)].get("title", tree["name"])
                self._json(tree)
            except Exception:
                self._json({"name": "?", "notes": [], "dirs": []}, 500)
            return
        if self.path == "/props":
            # the media airlock as a browsable tree — live filesystem
            # read: drop a file in media/, reopen the orb, it's there
            EXTS = TIPOS_ACERVO
            mroot = media_root()

            def walkm(d: Path) -> dict[str, Any]:
                out: dict[str, Any] = {"name": d.name, "items": [], "dirs": []}
                for p in sorted(d.iterdir()):
                    if p.name.startswith("."):
                        continue
                    if p.is_dir():
                        sub = walkm(p)
                        # A folder carrying a README was made on purpose, so
                        # it stays listed even while empty. holo/ and models/
                        # ship exactly that way -- nothing in them but a
                        # README saying what to drop in -- and hiding every
                        # folder with no stageable file made them invisible
                        # until you had already found them. This board is HOW
                        # you discover a folder, so the one that teaches you
                        # the hologram cannot be the one you must know about
                        # first. Arbitrary empty folders still stay hidden.
                        documented = (p / "README.md").is_file()
                        if sub["items"] or sub["dirs"] or documented:
                            out["dirs"].append(sub)
                    elif p.suffix.lower() in EXTS:
                        # as_posix, because THE FOLDER IS THE RENDER LAW and
                        # the law is read client-side with forward slashes.
                        # str() of a path yields BACKSLASHES on Windows, so
                        # "fx\fireball.png" never matched /\/fx\// in
                        # stage.html: props in fx/ silently kept their card
                        # frame and models in holo/ silently rendered solid
                        # instead of as the blue wire. These strings become
                        # URL fragments in the browser, where a backslash is
                        # not a separator at all, so POSIX is the only
                        # correct wire format here regardless of platform.
                        out["items"].append(p.relative_to(mroot).as_posix())
                return out

            try:
                tree = walkm(mroot)
                tree["name"] = "Props"
                self._json(tree)
            except Exception:
                self._json({"name": "Props", "items": [], "dirs": []}, 500)
            return
        if self.path == "/stats":
            self._json(system_stats())
            return
        if self.path == "/cerebros":
            # barehands-jarvis: brain batteries written by the Zé; a stale
            # file (Zé stopped) hides the row instead of lying.
            try:
                d = json.loads((ESTADO / "cerebros.json").read_text())
                if time.time() - float(d.get("ts", 0)) > 90:
                    d = {"lista": []}
            except Exception:
                d = {"lista": []}
            self._json(d)
            return
        if self.path == "/maos/perfil":
            self._json(PERFIL.ler())
            return
        if self.path.startswith("/camera/info"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self._json(CAMERA.info((q.get("nome") or [""])[0]))
            return
        if self.path.startswith("/jarvis/"):
            # barehands-jarvis: the Zé brain on screen (decision card,
            # efficiency meter, brain map), written by the Zé into
            # state/<name>.json. Fixed names only; a stale file (Zé
            # stopped) answers {} so the page hides it instead of lying.
            nome = self.path[len("/jarvis/") :]
            if nome not in (
                "decisao",
                "eficiencia",
                "mapa",
                "mapa-abrir",
                "trabalho",
                "orbes",
                "presenca",
                "maos-pedido",
                "tela-comando",
                "teclado-resposta",
                "foco",
            ):
                self._json({}, 404)
                return
            try:
                d = json.loads((ESTADO / f"{nome}.json").read_text())
                if (
                    nome not in ("mapa-abrir", "maos-pedido", "tela-comando")
                    and time.time() - float(d.get("ts", 0)) > 90
                ):
                    d = {}
            except Exception:
                d = {}
            self._json(d)
            return
        if self.path == "/orb":
            # the ring's heartbeat: your assistant's live state, read from
            # tiny files in ./state/. Every read fails soft — no files,
            # no assistant, no problem: the ring just breathes.
            s_dir = ESTADO
            out = {"state": "idle", "mood": "green", "wave": None}
            try:
                f = s_dir / "state"
                s = f.read_text().strip().lower()
                if s in ("idle", "listening", "thinking", "speaking"):
                    # A STALE non-idle state DECAYS to idle, because the
                    # only thing that ever writes "idle" is the writer
                    # finishing. A writer that is killed, crashes, or is
                    # force-quit mid-turn never writes it -- so the ring
                    # sat on "thinking" forever, with no timeout, nothing
                    # to reset it, and no way for anyone to guess why.
                    #
                    # This is a safety net for a DEAD writer, not a
                    # liveness signal: a genuinely long turn will decay
                    # too, and showing idle during real work is a far
                    # smaller lie than claiming to think for eternity.
                    # Raise state_timeout_s if your turns run longer.
                    age = time.time() - f.stat().st_mtime
                    if s == "idle" or age < STATE_TIMEOUT:
                        out["state"] = s
            except Exception:
                pass
            try:
                m = json.loads((s_dir / "mood.json").read_text())
                if time.time() - float(m.get("ts", 0)) < 45.0:
                    out["mood"] = m.get("mood", "green")
            except Exception:
                pass
            try:
                # barehands-jarvis: the avatar's emotion, held until "ate" (unix time).
                x = json.loads((s_dir / "expressao.json").read_text())
                if time.time() < float(x.get("ate", 0)) and x.get("expressao") in (
                    "alegria",
                    "duvida",
                    "raiva",
                    "tristeza",
                ):
                    out["expressao"] = x["expressao"]
            except Exception:
                pass
            if out["state"] == "speaking":
                try:
                    w = json.loads((s_dir / "wave.json").read_text())
                    if time.time() - float(w.get("ts", 0)) < 0.6:
                        out["wave"] = w.get("samples", [])[:64]
                except Exception:
                    pass
            self._json(out)
            return
        if self.path == "/state":
            global _MIRROR_READ
            _MIRROR_READ = time.time()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(_STATE)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(_STATE)
            return
        if not self.path.startswith("/note?"):
            return super().do_GET()
        # one note's text: f=<orb>/<relpath>, resolved against that orb's
        # jail. Inside the root, .md only, must exist — anything else 404s.
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        rel = (q.get("f") or [""])[0]
        idx, _, rel = rel.partition("/")
        root = orb_root(idx)
        if root is None:
            self.send_response(404)
            self.end_headers()
            return
        target = (root / rel).resolve()
        if (root not in target.parents) or target.suffix != ".md" or not target.is_file():
            self.send_response(404)
            self.end_headers()
            return
        body = target.read_text(encoding="utf-8", errors="replace").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ESTADO.mkdir(parents=True, exist_ok=True, mode=0o700)  # the ring's runtime files land here
    gravar_token(ESTADO, TOKEN)
    for pasta in PASTAS_ACERVO:  # onde quem usa põe o que o Zé mostra
        (ACERVO / pasta).mkdir(parents=True, exist_ok=True, mode=0o700)
    CAMERA.vigiar()
    import atexit
    import signal

    atexit.register(CAMERA.restaurar)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    port = int(os.environ.get("ZE_IMERSIVO_PORTA") or CONFIG.get("port", 8794))
    print(f"Zé, modo imersivo: http://127.0.0.1:{port}/stage.html", flush=True)
    print("  tracker (camera): open that URL in Chrome", flush=True)
    print("  render (overlay): same URL + ?role=render", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
