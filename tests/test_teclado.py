"""O Teclado do Núcleo: o pedido escrito é lido uma vez e a resposta vai para a tela."""

import json
import os
import time
from pathlib import Path
from typing import Any

from zervis.rosto.hud import Hud
from zervis.rosto.teclado import Teclado


def escrever(pasta: Path, pedido: str, texto: str, idade: float = 0.0) -> None:
    arquivo = pasta / "teclado.json"
    arquivo.write_text(json.dumps({"id": pedido, "texto": texto, "ts": time.time() - idade}))
    agora = time.time() + len(pedido)  # mtime distinto a cada escrita, mesmo no mesmo instante
    os.utime(arquivo, (agora, agora))


def resposta(pasta: Path) -> dict[str, Any]:
    dados: dict[str, Any] = json.loads((pasta / "teclado-resposta.json").read_text())
    return dados


def test_pedido_novo_sai_uma_vez_e_a_resposta_acompanha_a_fala(tmp_path: Path) -> None:
    t = Teclado(tmp_path, Hud(tmp_path))
    assert t.novo() is None
    escrever(tmp_path, "a1", "  abre o guia  ")
    assert t.novo() == "abre o guia"
    assert t.novo() is None
    assert resposta(tmp_path) | {"ts": 0} == {"pedido": "a1", "texto": "", "fim": False, "ts": 0}
    t.falou("Guia na tela.")
    t.falou("Mais algo?")
    t.terminou()
    t.falou("isto já é de outro pedido")
    r = resposta(tmp_path)
    assert (r["pedido"], r["texto"], r["fim"]) == ("a1", "Guia na tela. Mais algo?", True)


def test_o_que_ja_estava_la_ou_velho_nao_roda(tmp_path: Path) -> None:
    escrever(tmp_path, "antes", "abre o navegador")
    t = Teclado(tmp_path, Hud(tmp_path))  # reinício do Zé: não repete o último pedido
    escrever(tmp_path, "antes", "abre o navegador")
    assert t.novo() is None
    escrever(tmp_path, "velho1", "abre o navegador", idade=60)
    assert t.novo() is None
    escrever(tmp_path, "vazio", "   ")
    assert t.novo() is None


def test_avisar_responde_sem_a_maquina(tmp_path: Path) -> None:
    t = Teclado(tmp_path, Hud(tmp_path))
    escrever(tmp_path, "b2", "oi")
    t.novo()
    t.avisar("Estou inativo agora.")
    r = resposta(tmp_path)
    assert (r["pedido"], r["texto"], r["fim"]) == ("b2", "Estou inativo agora.", True)
