"""O comando `zervis` (ADR 0034, ponto 10): cuidar da instalação sem decorar systemctl e git.

`status` (está de pé?), `doctor` (cada função, disponível ou não, com o motivo e o passo para
resolver), `update` (avança para a versão publicada mais nova, ou para a master com
`--desenvolvimento`, e reinicia; se o painel não voltar, volta para a versão anterior),
`logs`, `abrir` e `uninstall` (tira o serviço, o atalho e o comando; os dados ficam, a não ser
com `--apagar-dados` e a frase de confirmação).

O serviço continua subindo por `python -m jarvis`; este comando só fala com ele de fora.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from jarvis import __version__

REPO = Path(__file__).resolve().parents[1]
SERVICO = "zervis"
PORTA_PADRAO = 8795
ESPERA_PAINEL_S = 90.0
ESPACO_MINIMO = 2 * 1024**3  # modelos, conversas e cópias isoladas das sessões
FRASE_APAGAR = "apagar meus dados"

Rodar = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
Responde = Callable[[int], bool]


def rodar(comando: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 (comandos fixos deste módulo)
        list(comando), capture_output=True, text=True, timeout=600, check=False
    )


def _xdg(variavel: str, padrao: str) -> Path:
    return Path(os.environ.get(variavel) or Path.home() / padrao)


def unidade() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "systemd" / "user" / f"{SERVICO}.service"


def atalho() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / "applications" / f"{SERVICO}.desktop"


def icone() -> Path:
    base = _xdg("XDG_DATA_HOME", ".local/share")
    return base / "icons" / "hicolor" / "scalable" / "apps" / f"{SERVICO}.svg"


def comando() -> Path:
    return Path.home() / ".local" / "bin" / SERVICO


def porta() -> int:
    """A porta do serviço instalado (o `make instalar` grava na unidade), senão a do ambiente."""
    try:
        if achado := re.search(r"JARVIS_PAINEL_PORTA=(\d+)", unidade().read_text()):
            return int(achado.group(1))
    except OSError:
        pass
    return int(os.environ.get("JARVIS_PAINEL_PORTA") or PORTA_PADRAO)


def painel_responde(numero: int) -> bool:
    """Qualquer resposta HTTP do painel local conta: o serviço está de pé."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{numero}/", timeout=3):
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False


def _git(rodar: Rodar, *args: str) -> subprocess.CompletedProcess[str]:
    return rodar(["git", "-C", str(REPO), *args])


def versao(rodar: Rodar = rodar) -> str:
    """A versão do pacote e onde o código está: a etiqueta (`v0.1.0`), ou a etiqueta mais o
    que veio depois (`v0.1.0-3-gabc1234`), ou só o commit, sem versão publicada."""
    onde = _git(rodar, "describe", "--tags", "--always", "--match", "v[0-9]*").stdout.strip()
    sujo = _git(rodar, "status", "--porcelain").stdout.strip()
    detalhe = ", com alterações locais" if sujo else ""
    return f"{__version__} ({onde or 'sem Git'}{detalhe})"


# --- status e doctor ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Verificacao:
    funcao: str
    ok: bool | None  # None: não se aplica nesta máquina
    detalhe: str
    resolver: str = ""


def _ativo(rodar: Rodar) -> bool:
    return rodar(["systemctl", "--user", "is-active", "--quiet", SERVICO]).returncode == 0


def verificacoes(rodar: Rodar = rodar, responde: Responde = painel_responde) -> list[Verificacao]:
    from jarvis import lugares
    from jarvis.atendimento import preparar_go
    from jarvis.cerebro import acesso
    from jarvis.config import ConfigInvalida, carregar
    from jarvis.preparar import faltando
    from jarvis.sistema.catalogo import tem_omarchy
    from jarvis.voz.deepgram import ler_chave

    lista = []
    ativo = _ativo(rodar)
    lista.append(
        Verificacao("Serviço", True, "Rodando.")
        if ativo
        else Verificacao(
            "Serviço", False, "Parado.", f"systemctl --user start {SERVICO}; zervis logs"
        )
    )
    habilitado = rodar(["systemctl", "--user", "is-enabled", "--quiet", SERVICO]).returncode == 0
    lista.append(
        Verificacao("Início automático", True, "Ligado.")
        if habilitado
        else Verificacao(
            "Início automático", False, "Desligado.", f"systemctl --user enable {SERVICO}"
        )
    )
    numero = porta()
    lista.append(
        Verificacao("Painel", True, f"http://127.0.0.1:{numero}/")
        if responde(numero)
        else Verificacao("Painel", False, f"Sem resposta na porta {numero}.", "zervis logs")
    )
    agentes = [a["nome"] for a in acesso.agentes() if a["logado"]]
    lista.append(
        Verificacao("Agente (Claude ou Codex)", True, ", ".join(agentes))
        if agentes
        else Verificacao(
            "Agente (Claude ou Codex)", False, "Nenhuma conta conectada.", "Painel: Contas."
        )
    )
    try:
        cfg = carregar()
    except ConfigInvalida as erro:
        lista.append(Verificacao("Configuração", False, str(erro), "Corrija o config.toml."))
        return lista
    chave = ler_chave(cfg.caminho("escuta", "chave_deepgram"))
    lista.append(
        Verificacao("Escuta (Deepgram)", True, "Chave guardada.")
        if chave
        else Verificacao(
            "Escuta (Deepgram)",
            False,
            "Sem a chave: a voz fica desligada; o texto funciona.",
            "Painel: Configurar, Voz.",
        )
    )
    modelos = faltando(cfg.caminho("ativacao", "modelos_onnx"))
    lista.append(
        Verificacao("Modelos de voz", True, "Completos.")
        if not modelos
        else Verificacao(
            "Modelos de voz",
            False,
            f"Faltam {len(modelos)}: {', '.join(m.nome for m in modelos[:3])}.",
            f'"{REPO}/.venv/bin/python" -m jarvis.preparar',
        )
    )
    tela = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    audio = [p for p in ("parec", "paplay", "pactl") if shutil.which(p) is None]
    if not tela:
        lista.append(
            Verificacao("Áudio local", None, "Sem tela: servidor, a voz vem do navegador.")
        )
    elif audio:
        lista.append(
            Verificacao(
                "Áudio local",
                False,
                f"Falta {', '.join(audio)}.",
                "No Ubuntu: sudo apt install pulseaudio-utils",
            )
        )
    else:
        lista.append(Verificacao("Áudio local", True, "PipeWire ou PulseAudio."))
    go = [Path.home() / ".local/lib/zervis/bin/go"]
    if do_path := shutil.which("go"):
        go.append(Path(do_path))
    if any(preparar_go._executavel_compativel(str(g)) for g in go if g.exists()):
        lista.append(Verificacao("WhatsApp (Go)", True, "Pronto para compilar o WaCalls."))
    else:
        lista.append(
            Verificacao(
                "WhatsApp (Go)",
                False,
                "Sem o Go verificado.",
                f'"{REPO}/.venv/bin/python" -m jarvis.atendimento.preparar_go',
            )
        )
    lista.append(
        Verificacao("Controle da máquina", True, "Omarchy.")
        if tem_omarchy()
        else Verificacao("Controle da máquina", None, "Reduzido: fora do Omarchy.")
    )
    livre = shutil.disk_usage(lugares.DADOS if lugares.DADOS.exists() else Path.home()).free
    lista.append(
        Verificacao("Espaço em disco", True, f"{livre / 1024**3:.0f} GB livres.")
        if livre >= ESPACO_MINIMO
        else Verificacao(
            "Espaço em disco", False, f"{livre / 1024**3:.1f} GB livres.", "Libere espaço."
        )
    )
    return lista


def status(rodar: Rodar = rodar, responde: Responde = painel_responde) -> int:
    numero = porta()
    ativo, no_ar = _ativo(rodar), responde(numero)
    print(f"Zérvis {versao(rodar)}")
    print(f"Serviço: {'rodando' if ativo else 'parado'}")
    print(f"Painel: http://127.0.0.1:{numero}/ ({'responde' if no_ar else 'sem resposta'})")
    return 0 if ativo and no_ar else 1


def doctor(rodar: Rodar = rodar, responde: Responde = painel_responde) -> int:
    lista = verificacoes(rodar, responde)
    largura = max(len(v.funcao) for v in lista)
    for v in lista:
        marca = {True: "✓", False: "✗", None: "-"}[v.ok]
        estado = {True: "Disponível", False: "Indisponível", None: "Não se aplica"}[v.ok]
        print(f"{marca} {v.funcao.ljust(largura)}  {estado}. {v.detalhe}")
        if v.resolver:
            print(f"  {' ' * largura}  Resolver: {v.resolver}")
    return 1 if any(v.ok is False for v in lista) else 0


# --- update ------------------------------------------------------------------------------------


def _uv() -> str:
    return shutil.which("uv") or str(Path.home() / ".local/bin/uv")


def _esperar_painel(responde: Responde, espera_s: float, pausa: Callable[[float], None]) -> bool:
    numero, fim = porta(), time.monotonic() + espera_s
    while time.monotonic() < fim:
        if responde(numero):
            return True
        pausa(1.0)
    return False


def ultima_versao(rodar: Rodar = rodar) -> str:
    """A etiqueta de versão mais nova (`v0.1.0`…), ou "" se nenhuma foi publicada."""
    etiquetas = _git(rodar, "tag", "--list", "v[0-9]*", "--sort=-v:refname").stdout.split()
    return etiquetas[0] if etiquetas else ""


def update(
    rodar: Rodar = rodar,
    responde: Responde = painel_responde,
    espera_s: float = ESPERA_PAINEL_S,
    pausa: Callable[[float], None] = time.sleep,
    desenvolvimento: bool = False,
) -> int:
    """Avança para a versão publicada mais nova (ou, com `desenvolvimento`, para o código mais
    novo da branch da origem), só se for um avanço limpo (sem alterações nem commits locais por
    cima), e só fica nela se o painel voltar."""
    if _git(rodar, "status", "--porcelain").stdout.strip():
        print(
            "Há alterações locais no código: o update não mexe nelas. Registre-as ou descarte-as."
        )
        return 1
    seguida = _git(rodar, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if seguida.returncode != 0:
        print(
            "Esta instalação não segue uma branch da origem (veio como pacote?): "
            "reinstale pelo git clone."
        )
        return 1
    if _git(rodar, "fetch", "--quiet", "--tags").returncode != 0:
        print("Sem conexão com a origem do código.")
        return 1
    antes = _git(rodar, "rev-parse", "HEAD").stdout.strip()
    if desenvolvimento:
        destino, rotulo = "@{u}", seguida.stdout.strip()
    else:
        if not (rotulo := ultima_versao(rodar)):
            print(
                "Ainda não há versão publicada. "
                "Para seguir a master: zervis update --desenvolvimento"
            )
            return 0
        destino = f"{rotulo}^{{commit}}"
    alvo = _git(rodar, "rev-parse", destino).stdout.strip()
    if antes == alvo:
        print(f"Já está na versão mais nova ({rotulo}).")
        return 0
    if (
        not desenvolvimento
        and _git(rodar, "merge-base", "--is-ancestor", alvo, "HEAD").returncode == 0
    ):
        print(
            f"Já está à frente da versão mais nova ({rotulo}), no código em desenvolvimento. "
            "Para seguir a master: zervis update --desenvolvimento"
        )
        return 0
    if _git(rodar, "merge-base", "--is-ancestor", "HEAD", alvo).returncode != 0:
        print(
            "Há commits locais que não estão na origem (melhorias do próprio Zé, por exemplo): "
            "junte-os numa sessão de autodesenvolvimento antes de atualizar."
        )
        return 1
    novidades = _git(
        rodar, "log", "--oneline", "--no-decorate", f"HEAD..{alvo}"
    ).stdout.splitlines()
    print(f"Atualizando {antes[:7]} → {rotulo} ({len(novidades)} mudanças):")
    for linha in novidades[:8]:
        print(f"  {linha}")
    if _git(rodar, "merge", "--ff-only", "--quiet", alvo).returncode != 0:
        print("O avanço falhou; nada mudou.")
        return 1
    if rodar([_uv(), "sync", "--frozen", "--project", str(REPO)]).returncode == 0:
        rodar(["systemctl", "--user", "restart", SERVICO])
        if _esperar_painel(responde, espera_s, pausa):
            print(f"Atualizado para {rotulo}. O painel respondeu.")
            return 0
        print("O painel não voltou na versão nova: voltando para a anterior.")
    else:
        print("As dependências da versão nova não instalaram: voltando para a anterior.")
    _git(rodar, "reset", "--hard", "--quiet", antes)  # a árvore estava limpa: só desfaz o avanço
    rodar([_uv(), "sync", "--frozen", "--project", str(REPO)])
    rodar(["systemctl", "--user", "restart", SERVICO])
    voltou = _esperar_painel(responde, espera_s, pausa)
    estado = "de volta" if voltou else "restaurada, mas o painel não respondeu: zervis logs"
    print(f"Versão anterior ({antes[:7]}) {estado}.")
    return 1


# --- uninstall ---------------------------------------------------------------------------------


def uninstall(
    apagar_dados: bool = False,
    rodar: Rodar = rodar,
    perguntar: Callable[[str], str] = input,
) -> int:
    from jarvis import lugares

    raizes = [lugares.CONFIG, lugares.DADOS, lugares.ESTADO]
    if apagar_dados:
        print("Isto apaga, sem volta, a configuração, as chaves, a memória e as conversas:")
        for raiz in raizes:
            print(f"  {raiz}")
        if perguntar(f'Digite "{FRASE_APAGAR}" para confirmar: ').strip() != FRASE_APAGAR:
            print("Nada foi apagado.")
            return 1
    rodar(["systemctl", "--user", "disable", "--now", SERVICO])
    for arquivo in (unidade(), atalho(), icone()):
        arquivo.unlink(missing_ok=True)
    nosso = comando()
    if nosso.is_symlink() and REPO in nosso.resolve().parents:
        nosso.unlink()
    rodar(["systemctl", "--user", "daemon-reload"])
    print("Serviço, atalho e comando removidos.")
    if apagar_dados:
        for raiz in raizes:
            if raiz.name.startswith(SERVICO) and raiz.is_dir():  # nunca uma pasta de outro
                shutil.rmtree(raiz)
        print("Dados apagados.")
    else:
        print("Os seus dados ficaram em:")
        for raiz in raizes:
            print(f"  {raiz}")
    print(f"O código continua em {REPO}; apague a pasta se não for reinstalar.")
    return 0


# --- entrada -----------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    partes = argparse.ArgumentParser(prog="zervis", description="Cuida da instalação do Zérvis.")
    sub = partes.add_subparsers(dest="acao", metavar="comando")
    sub.add_parser("status", help="se o serviço está de pé, a versão e o painel")
    sub.add_parser("doctor", help="cada função, disponível ou não, e como resolver")
    atualizar = sub.add_parser("update", help="atualiza e reinicia; volta se o painel não subir")
    atualizar.add_argument(
        "--desenvolvimento", action="store_true", help="segue a master, não as versões publicadas"
    )
    sub.add_parser("logs", help="o registro do serviço, ao vivo")
    sub.add_parser("abrir", help="abre o painel")
    remover = sub.add_parser("uninstall", help="remove o serviço, o atalho e o comando")
    remover.add_argument("--apagar-dados", action="store_true", help="apaga também os dados")
    sub.add_parser("version", help="a versão instalada")
    sub.add_parser(
        "avaliar",
        help="a bateria de avaliação do cérebro (gasta a conta do Claude)",
        add_help=False,
    )
    args, resto = partes.parse_known_args(argv)
    if args.acao == "avaliar":
        from jarvis.avaliacao.__main__ import main as avaliar

        return avaliar(resto)
    if resto:
        partes.error(f"argumentos desconhecidos: {' '.join(resto)}")
    if args.acao == "status":
        return status()
    if args.acao == "doctor":
        return doctor()
    if args.acao == "update":
        return update(desenvolvimento=args.desenvolvimento)
    if args.acao == "uninstall":
        return uninstall(args.apagar_dados)
    if args.acao == "version":
        print(f"Zérvis {versao()}")
        return 0
    if args.acao == "logs":
        os.execvp("journalctl", ["journalctl", "--user", "-u", SERVICO, "-n", "100", "-f"])  # noqa: S606, S607
    if args.acao == "abrir":
        os.environ["JARVIS_PAINEL_PORTA"] = str(porta())
        abrir = str(REPO / "deploy" / "abrir-painel.sh")
        os.execv(abrir, [abrir])  # noqa: S606
    partes.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
