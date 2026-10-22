"""Recorte do pedido depois do "Ei Zé": junta quadros de 80 ms até o silêncio final.

Regras herdadas do Zé antigo (core.py, 06/10/2026): 0,4 s de áudio antes da primeira voz
(o começo da palavra costuma vir antes do VAD reagir), teto de 60 s, e trechos com menos de
dois quadros de voz são descartados (estalo, tosse). O fim fixo subiu de 2 s para 3 s de
silêncio: o usuário pausa para formular o pedido e era cortado no meio.

Com o detector de fim de turno, depois de uma pausa curta o modelo olha o que foi dito, uma
vez por pausa; se ele achar que a frase terminou, o pedido fecha na hora, sem esperar o silêncio
longo. Consultar de novo a cada pedaço da mesma pausa dava ao modelo várias chances de errar
enquanto o usuário pensava. As duas durações vêm da escolha "Espera" (`zervis/voz/espera.py`).

O modelo ouve só a entonação e foi treinado sobretudo em inglês: numa pausa para pensar em
português ("quero uma automação que... toda segunda") ele dava nota 0,95. Por isso, se o texto
reconhecido até ali termina numa palavra que pede continuação ("e", "que", "pra", "tipo") ou numa
vírgula, a frase está pela metade e o pedido só fecha pelo silêncio longo (14/10/2026).
"""

import re
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

DURACAO_QUADRO_S = 0.08

# Palavras que, no fim do que foi dito, pedem continuação: conjunções, preposições, artigos e
# vacilos. "isso", "né" e "aí" ficam de fora: fecham frase com frequência.
_CONTINUACAO = """e ou mas que porque pois então entao tipo quando como onde se também tambem
    de do da dos das pra pro para com sem em no na nos nas num numa por pelo pela pelos pelas
    o a os as um uma uns umas ao à meu minha seu sua teu tua nosso nossa esse essa este esta
    aquele aquela sobre até ate entre mais menos muito assim é eh hum hm ahn ã
    eu você voce ele ela gente quero queria preciso"""
PEDEM_CONTINUACAO = frozenset(_CONTINUACAO.split())


def ficou_no_meio(texto: str) -> bool:
    """O texto reconhecido até a pausa termina pela metade (vírgula ou palavra que pede
    continuação)?"""
    texto = texto.strip().lower()
    if not texto:
        return False
    if texto.endswith((",", "...", "…", "-", ":")):
        return True
    if texto.endswith((".", "?", "!")):
        return False
    ultima = re.findall(r"[\wà-ú]+", texto)
    return bool(ultima) and ultima[-1] in PEDEM_CONTINUACAO


@dataclass
class Segmentador:
    fim_silencio_s: float = 3.0
    maximo_quadros: int = 750
    quadros_antes: int = 5
    fim_de_turno: Callable[[bytes], float] | None = None
    limiar_fim_de_turno: float = 0.7
    # Quadros de silêncio até a consulta ao modelo: 0,64 s. Com 0,32 s, quase todo pedido do
    # o usuário fechava na primeira respiração com nota 0,93 a 0,99 (supressão de ruído deixa o
    # silêncio abrupto; 60 pedidos em 06/10/2026), e ele era atropelado no meio da frase.
    pausa_consulta: int = 8
    # O texto reconhecido até agora (parcial do Deepgram): frase pela metade não fecha no modelo.
    fala_ate_agora: Callable[[], str] | None = None
    coletados: list[bytes] = field(default_factory=list)
    antes: deque[bytes] = field(default_factory=deque)
    silencio: int = 0
    com_voz: int = 0
    fechou_pelo_modelo: bool = False  # o último pedido fechou pelo fim de turno (status)
    notas: list[float] = field(default_factory=list)  # do modelo, nas pausas do pedido atual
    notas_do_ultimo: tuple[float, ...] = ()  # as do último pedido fechado (log)
    # Botão apertado ("segurar para falar"): pausa não fecha o pedido; fecha ao soltar (`fechar`).
    segurando: bool = False

    @property
    def em_fala(self) -> bool:
        return bool(self.coletados)

    def limpar(self) -> None:
        self.coletados.clear()
        self.antes.clear()
        self.silencio = self.com_voz = 0
        self.notas = []

    def quadro(self, dados: bytes, voz: bool) -> bytes | None:
        """Devolve o áudio do pedido quando ele termina; senão None."""
        if not self.coletados:
            if not voz:
                self.antes.append(dados)
                while len(self.antes) > self.quadros_antes:
                    self.antes.popleft()
                return None
            self.coletados.extend(self.antes)
            self.antes.clear()
        self.coletados.append(dados)
        self.com_voz += int(voz)
        self.silencio = 0 if voz else self.silencio + 1
        terminou = not self.segurando and self.silencio * DURACAO_QUADRO_S >= self.fim_silencio_s
        pelo_modelo = False
        if (
            not terminou
            and not self.segurando
            and self.fim_de_turno is not None
            and self.com_voz >= 2
            and self.silencio == self.pausa_consulta
        ):
            self.notas.append(self.fim_de_turno(b"".join(self.coletados)))
            pelo_modelo = self.notas[-1] >= self.limiar_fim_de_turno
            if (
                pelo_modelo
                and self.fala_ate_agora is not None
                and ficou_no_meio(self.fala_ate_agora())
            ):
                pelo_modelo = False
                self.notas[-1] = -self.notas[-1]  # no log, nota negativa: frase pela metade
        if not (terminou or pelo_modelo) and len(self.coletados) < self.maximo_quadros:
            return None
        self.fechou_pelo_modelo = pelo_modelo
        self.notas_do_ultimo = tuple(self.notas)
        trecho = b"".join(self.coletados) if self.com_voz >= 2 else None
        self.limpar()
        return trecho

    def fechar(self) -> bytes | None:
        """Fecha o pedido agora (o botão foi solto); None se não houve fala."""
        self.fechou_pelo_modelo = False
        self.notas_do_ultimo = tuple(self.notas)
        trecho = b"".join(self.coletados) if self.com_voz >= 2 else None
        self.limpar()
        return trecho
