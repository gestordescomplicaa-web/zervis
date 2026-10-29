"""A tela do Zé (Barehands) e o Núcleo nela. Ver, agir, abrir e fechar.

O Núcleo é o anel do Zé com os orbes que nascem dele (Mapa, Hoje, Trabalho, Acervo, Guia).
A janela do Zé é onde ele vive: com ela fechada, a câmera fica apagada e não há Núcleo.

Contrato pela pasta de estado do Barehands, como o resto do rosto:
- `tela-comando.json`: o Zé escreve `{id, acoes, ts}`; a página executa as ações em ordem.
- `tela-estado.json`: a página publica o estado a cada poucos segundos (o batimento que diz se a
  janela está aberta), avisa `recebido: id` ao começar e `resposta: id` com os resultados ao
  terminar.

A janela costuma ficar em outro workspace; escondida, o Chromium pausa as animações. Antes de
mostrar algo, `trazer()` põe a janela na frente pelo Hyprland. `em_foco()` diz se a janela do
Zé é a ativa: é assim que "aumenta o brilho" vira o brilho da câmera dele e não o do monitor.
"""

import contextlib
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

ACOES = {
    "nucleo": "valor: abrir (mostra os orbes ao redor do anel) ou fechar (recolhe)",
    "abrir": "alvo: um orbe (pelo nome ou apelido) ou qualquer item do Núcleo pelo nome falado: "
    "nota, arquivo do Acervo ou pasta; orbe (opcional) restringe a "
    "busca a um orbe. Abre exatamente aquilo, abrindo o Núcleo antes se precisar",
    "buscar": "alvo: um nome; orbe (opcional). Lista o que existe com esse nome: nome, orbe, "
    "tipo e endereço (orbe/pasta/item). Use antes de abrir quando não souber o nome exato",
    "fechar": "alvo: um orbe, um item aberto (nota ou arquivo), ou tudo",
    "abrir_mapa": "abre o Mapa (o mesmo que abrir Mapa)",
    "fechar_mapa": "fecha o Mapa",
    "modo": "valor: a vista do Mapa: geral, trabalho ou foco",
    "focar": "alvo: área do Mapa (memoria, projetos, agentes, tarefas, conexoes, pessoas) ou item "
    "pelo nome ou id; abre o item no Foco ou expande a área",
    "localizar": "alvo: item pelo nome ou id; mostra onde ele está nas conexões",
    "zoom": "valor: fator (1.5 aproxima, 0.7 afasta)",
    "enquadrar": "mostra o mapa inteiro",
    "mover": "valor: 'x,y' em pixels para arrastar o mapa",
    "rolar": "valor: pixels para rolar Trabalho ou Foco (negativo sobe)",
    "voltar": "volta para a vista anterior",
    "aguardar": "valor: milissegundos (até 10000), para dar tempo de ver cada passo",
    "menu": "valor: abrir ou fechar o menu de configurações",
    "teclado": "valor: abrir ou fechar o Teclado (a barra para o usuário escrever pedidos)",
    "foco": "mostra o quadro do Foco (as frentes, a atual em destaque, com o V para marcar)",
    "visual": "valor: avatar (o busto holográfico que fala, no lugar do anel) ou anel",
    "girar": "valor: voltas (1 a 3, padrão 1). O Zé dá uma volta completa na tela",
    "apresentar": "valor: quem (o Zé vai para o canto e mostra, em painéis holográficos, os "
    "próprios dados: identidade, atividade, conexões, o que mais executa e o registro recente) "
    "ou encerrar (recolhe os painéis). Só para 'se apresenta' sem assunto; um aspecto seu (um "
    "gráfico do que fez, conexões, falhas) é ze_sobre e tela_explicar",
    "expressao": "valor: alegria, duvida, raiva, tristeza ou neutro; segundos (opcional, "
    "padrão 6). O rosto do avatar; numa resposta, prefira a marca no começo do texto",
    "tema": "alvo: original, roxo, marinho, esmeralda ou grafite",
    "brilho": "valor: 0 desligado, 1 suave, 2 médio, 3 forte (é o brilho da câmera do Núcleo)",
    "calibrar_maos": "começa a calibração guiada das mãos",
    "maos_padrao": "volta à calibração e à câmera originais",
}
CENA = "explicar"  # a cena animada (tela_explicar), com a cena em JSON no lugar de alvo e valor
JANELA = r"class:^(chrome-127\.0\.0\.1__(stage\.html.*|-Default))$"  # o imersivo ou o painel
CLASSE_PAINEL = "chrome-127.0.0.1__-Default"
CLASSE = "chrome-127.0.0.1__stage.html"
SERVICOS = ["barehands.service", "barehands-window.service"]
VIVO_S = 15.0  # a página publica o estado a cada 5 s; sem isso por 15 s, a janela está fechada
MODOS = {"brain": "geral", "work": "trabalho", "focus": "foco"}


EVENTO_VALIDO_S = 15.0  # evento mais velho que isso (o Zé estava parado) não é falado


def evento_novo(dados: dict[str, Any], visto: str, agora: float) -> dict[str, Any] | None:
    """O evento da página (`jarvisControle.evento`) ainda não tratado e recente; senão None."""
    evento = dados.get("evento")
    if not isinstance(evento, dict) or not evento.get("id") or str(evento["id"]) == visto:
        return None
    try:
        recente = agora - float(evento.get("ts", 0)) < EVENTO_VALIDO_S
    except (TypeError, ValueError):
        return None
    return evento if recente else None


class TelaErro(Exception):
    pass


def _hyprctl(*args: str) -> str:
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        return subprocess.run(  # noqa: S603 (binário e argumentos fixos)
            ["/usr/bin/hyprctl", *args], capture_output=True, text=True, timeout=3, check=False
        ).stdout
    return ""


def _systemctl(*args: str) -> None:
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.run(  # noqa: S603 (binário e argumentos fixos)
            ["/usr/bin/systemctl", "--user", *args], capture_output=True, timeout=10, check=False
        )


class Tela:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta

    def _ler(self) -> dict[str, Any]:
        try:
            dados = json.loads((self.pasta / "tela-estado.json").read_text())
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def estado_bruto(self) -> dict[str, Any]:
        """O último `tela-estado.json` como a página escreveu (com o evento, se houver)."""
        return self._ler()

    def aberto(self) -> bool:
        """A janela do Zé está rodando (a página publicou o estado há pouco)."""
        return time.time() - float(self._ler().get("ts", 0)) < VIVO_S

    def em_foco(self) -> bool:
        """A janela do Zé é a janela ativa do Hyprland agora."""
        try:
            ativa = json.loads(_hyprctl("activewindow", "-j") or "{}")
        except ValueError:
            return False
        classe = str(ativa.get("class", "")) if isinstance(ativa, dict) else ""
        return classe.startswith(CLASSE) or classe == CLASSE_PAINEL

    def ver(self) -> dict[str, Any]:
        dados = self._ler()
        if not self.aberto():
            raise TelaErro("a janela do Zé está fechada (sem ela não há Núcleo)")
        return {**dict(dados.get("estado") or {}), "em_foco": self.em_foco()}

    def resumo(self) -> str:
        """Uma linha para o cérebro saber, onde está a janela e o que o Núcleo mostra."""
        if not self.aberto():
            return "Janela do Zé: fechada (não há Núcleo na tela)."
        estado = self._ler().get("estado") or {}
        partes = [
            "Janela do Zé: aberta, "
            + ("é a janela ativa" if self.em_foco() else "em segundo plano")
        ]
        n = estado.get("nucleo") or {}
        if n:
            orbes = ", ".join(n.get("orbes") or [])
            partes.append(
                f"Núcleo aberto (orbes {orbes})"
                if n.get("aberto")
                else f"Núcleo recolhido ({orbes})"
            )
            abertos = list(n.get("orbes_abertos") or [])
            abertos += [f"nota {t}" for t in n.get("notas_abertas") or []]
            abertos += [f"arquivo {t}" for t in n.get("arquivos_abertos") or []]
            if abertos:
                partes.append("abertos: " + ", ".join(abertos))
        c = estado.get("cerebro") or {}
        if c.get("aberto"):
            foco = c.get("foco") or {}
            partes.append(
                f"Mapa na vista {MODOS.get(str(c.get('modo')), c.get('modo'))}"
                + (f", mostrando {foco['nome']}" if foco.get("nome") else "")
            )
        if (estado.get("menu_configuracoes") or {}).get("aberto"):
            partes.append("menu de configurações aberto")
        if estado.get("maos_em_uso"):
            partes.append("o usuário está usando as mãos agora")
        return "; ".join(partes) + "."

    def agir(
        self,
        acoes: list[dict[str, Any]],
        trazer: bool = True,
        espera_s: float | None = None,
        esperar_fim: bool | None = None,
    ) -> dict[str, Any]:
        """Executa as ações em ordem. Passeios (com 'aguardar' ou longos) voltam assim que a
        página confirma o início, para o Zé falar enquanto a tela anda."""
        for a in acoes:
            if a.get("acao") not in ACOES and a.get("acao") != CENA:
                raise TelaErro(f"ação desconhecida: {a.get('acao')}")
        if acoes and not self.aberto():
            raise TelaErro("a janela do Zé está fechada; ofereça abrir (janela_abrir)")
        if trazer and acoes:
            self.trazer()
        if esperar_fim is None:
            esperar_fim = len(acoes) <= 4 and not any(a.get("acao") == "aguardar" for a in acoes)
        pedido = uuid.uuid4().hex[:12]
        self._escrever(pedido, acoes)
        if espera_s is None:
            espera_s = min(12.0, 3.0 + 0.6 * len(acoes)) if esperar_fim else 4.0
        limite = time.monotonic() + espera_s
        while time.monotonic() < limite:
            dados = self._ler()
            if dados.get("resposta") == pedido:
                return dados
            if not esperar_fim and dados.get("recebido") == pedido:
                return {**dados, "resultados": "em andamento na tela"}
            time.sleep(0.1)
        raise TelaErro("a tela do Zé não respondeu a tempo")

    def enviar(self, acoes: list[dict[str, Any]]) -> None:
        """Sem esperar resposta (comandos locais por voz: a fala não espera a tela)."""
        self._escrever(uuid.uuid4().hex[:12], acoes)

    def _escrever(self, pedido: str, acoes: list[dict[str, Any]]) -> None:
        arquivo = self.pasta / "tela-comando.json"
        temporario = arquivo.with_name(".tela-comando.next")
        temporario.write_text(
            json.dumps({"id": pedido, "acoes": acoes, "ts": time.time()}, ensure_ascii=False)
        )
        temporario.replace(arquivo)

    def trazer(self) -> None:
        """Põe a janela do Zé na frente; escondida, as animações não rodam."""
        _hyprctl("dispatch", "focuswindow", JANELA)

    def abrir(self) -> None:
        """Liga a janela do Zé (servidor e janela; a câmera acende) e a traz para a frente."""
        _systemctl("start", *SERVICOS)
        for _ in range(20):
            if self.aberto():
                break
            time.sleep(0.5)
        self.trazer()

    def fechar(self) -> None:
        """Fecha a janela do Zé (a câmera apaga); o servidor fica para o HUD."""
        _systemctl("stop", SERVICOS[1])
