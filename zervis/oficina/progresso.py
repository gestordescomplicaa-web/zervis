"""Andamento da atualização: etapas reais e tempos estimados, preservados no reinício.

Observar a atualização nunca pode impedi-la. Arquivo ilegível ou falha ao publicar o andamento
vira aviso no log; só o resultado do reinício confirma que a versão nova iniciou.
"""

import json
import logging
import math
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
ETAPAS = (
    ("testes_copia", "Verificando melhorias", 75.0),
    ("juntando", "Aplicando melhorias", 5.0),
    ("testes_ze", "Verificando atualização", 75.0),
    ("reiniciando", "Reiniciando", 20.0),
)
FINAIS = {
    "pronto": "Atualização aplicada.",
    "voltou": "Versão anterior restaurada.",
}
MOSTRAR_FIM_S = 600.0
REINICIO_MAXIMO_S = 300.0


def _numero(valor: Any, padrao: float = 0.0) -> float:
    try:
        n = float(valor)
        return n if math.isfinite(n) and n >= 0 else padrao
    except (ValueError, TypeError, OverflowError):
        return padrao


class Progresso:
    def __init__(self, pasta: Path) -> None:
        self.arquivo = pasta / "progresso.json"
        self.tempos_arquivo = pasta / "tempos.json"
        self._trava = threading.Lock()
        tempos = self._ler(self.tempos_arquivo)
        self.tempos = {n: max(1.0, _numero(tempos.get(n), p)) for n, _, p in ETAPAS}
        self._limpar()
        self._retomar(self._ler(self.arquivo))

    @staticmethod
    def _ler(arquivo: Path) -> dict[str, Any]:
        try:
            dados = json.loads(arquivo.read_text())
        except (OSError, ValueError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def _limpar(self) -> None:
        self.estado = ""
        self.inicio = 0.0
        self.feitas: dict[str, float] = {}
        self.atual = ""
        self.atual_desde = 0.0
        self.texto = ""
        self.fim = 0.0

    def _retomar(self, salvo: dict[str, Any]) -> None:
        estado = salvo.get("estado")
        inicio = _numero(salvo.get("inicio"))
        if estado not in ("aplicando", "aguardando", "falhou", *FINAIS) or not inicio:
            return
        self.estado, self.inicio = str(estado), inicio
        feitas = salvo.get("feitas")
        if isinstance(feitas, dict):
            self.feitas = {n: _numero(feitas[n]) for n in self.tempos if n in feitas}
        atual = salvo.get("atual")
        self.atual = atual if isinstance(atual, str) and atual in self.tempos else ""
        self.atual_desde = _numero(salvo.get("atual_desde"), inicio)
        self.texto = str(salvo.get("texto", ""))[:1000]
        self.fim = _numero(salvo.get("fim"))
        if self.estado == "aplicando" and self.atual != "reiniciando":
            self.falhou(
                "Atualização interrompida. Confira as alterações antes de tentar novamente."
            )
        elif self.estado == "aguardando":
            # A aprovação em espera pertence ao processo anterior; não reaplicar ao subir.
            self.cancelar_espera()

    def _gravar(self, arquivo: Path, dados: dict[str, Any]) -> None:
        temporario: Path | None = None
        try:
            arquivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=arquivo.parent, suffix=".tmp", delete=False
            ) as f:
                temporario = Path(f.name)  # nasce 0600
                json.dump(dados, f, ensure_ascii=False)
                f.flush()
            temporario.replace(arquivo)
        except OSError:
            log.warning("atualização: não foi possível gravar o andamento")
        finally:
            if temporario is not None:
                try:
                    temporario.unlink(missing_ok=True)
                except OSError:
                    log.warning("atualização: não foi possível remover o temporário")

    def _salvar(self) -> None:
        self._gravar(
            self.arquivo,
            {
                "estado": self.estado,
                "inicio": self.inicio,
                "feitas": self.feitas,
                "atual": self.atual,
                "atual_desde": self.atual_desde,
                "texto": self.texto,
                "fim": self.fim,
            },
        )

    def aguardar(self) -> bool:
        with self._trava:
            if self.estado == "aplicando":
                return False
            if self.estado != "aguardando":
                self._limpar()
                self.estado, self.inicio = "aguardando", time.time()
                self._salvar()
            return True

    def cancelar_espera(self) -> None:
        with self._trava:
            if self.estado == "aguardando":
                self._limpar()
                self._salvar()

    def comecar(self) -> bool:
        """Só uma aplicação por vez, inclusive com dois painéis enviando juntos."""
        with self._trava:
            if self.estado == "aplicando":
                return False
            self._limpar()
            self.estado, self.inicio = "aplicando", time.time()
            self._salvar()
            return True

    def etapa(self, nome: str) -> None:
        if nome not in self.tempos and nome not in FINAIS:
            return
        agora = time.time()
        with self._trava:
            if self.estado != "aplicando":
                self._limpar()
                self.estado, self.inicio = "aplicando", agora
            if self.atual:
                self.feitas[self.atual] = max(0.0, agora - self.atual_desde)
                self.tempos[self.atual] = max(1.0, self.feitas[self.atual])
            if nome in FINAIS:
                self.estado, self.texto, self.fim, self.atual = nome, FINAIS[nome], agora, ""
                self._gravar(self.tempos_arquivo, self.tempos)
            else:
                self.atual, self.atual_desde = nome, agora
            self._salvar()

    def _falhou(self, texto: str) -> None:
        self.estado, self.texto, self.fim = "falhou", texto, time.time()
        # Mantém a etapa que falhou, em vez de marcá-la como concluída.
        self._salvar()

    def falhou(self, texto: str) -> None:
        with self._trava:
            if self.estado in ("aplicando", "aguardando"):
                self._falhou(texto)

    def reserva(self) -> str | None:
        foto = self.foto()
        if foto and foto["estado"] in ("aguardando", "aplicando"):
            return "Atualização em andamento. Aguarde a conclusão."
        return None

    def foto(self) -> dict[str, Any] | None:
        agora = time.time()
        with self._trava:
            if not self.estado or (self.fim and agora - self.fim > MOSTRAR_FIM_S):
                return None
            if (
                self.estado == "aplicando"
                and self.atual == "reiniciando"
                and agora - self.atual_desde > REINICIO_MAXIMO_S
            ):
                self._falhou("O reinício não confirmou.")
            fim = self.fim or agora
            etapas = []
            for nome, titulo, _ in ETAPAS:
                if nome in self.feitas:
                    estado, segundos = "feita", self.feitas[nome]
                elif nome == self.atual:
                    estado = "falhou" if self.estado in ("falhou", "voltou") else "atual"
                    segundos = max(0.0, fim - self.atual_desde)
                else:
                    estado, segundos = "pendente", 0.0
                etapas.append(
                    {
                        "id": nome,
                        "titulo": titulo,
                        "estado": estado,
                        "segundos": round(segundos),
                        "estimado": round(self.tempos[nome]),
                    }
                )
            return {
                "estado": self.estado,
                "etapas": etapas,
                "decorrido": round(max(0.0, fim - self.inicio)),
                "texto": self.texto,
                "fim": self.fim,
            }
