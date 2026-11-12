"""Projetos 3D (ADR 0082): cada projeto é uma pasta com os arquivos da peça, e uma sessão de código
faz o trabalho pesado nela, seguindo o `AGENTS.md` que o Zé escreve ao criar.

Dois tipos: a peça funcional, modelada por código (paramétrica, com medidas), e a arte a partir de
uma imagem, pela pipeline de arte de quem usa (a pasta dela vem dos ajustes, nunca do código). O
Blender entra por linha de comando, quando existe na máquina.

Os arquivos ficam na pasta do projeto (`<raiz dos projetos>/projetos-3d/<id>/`); para a Imersão,
o Zé converte o STL numa prévia sólida (`.glb`, cor de mármore) dentro do Acervo, que é o que ela
serve. As medidas (tamanho, volume, se a malha é fechada) são lidas do próprio STL.

Fatiar e imprimir (ADR 0083) ficam com o Zé, nunca com a sessão: `fatiar` prepara o 3MF com o
filamento que está na impressora e diz o tempo e o peso; `imprimir` manda, só com o sim de quem usa.
"""

import json
import re
import shutil
import struct
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from zervis import fatiador
from zervis.impressora3d import Impressora3D, ImpressoraErro

PASTA = "projetos-3d"  # dentro da raiz dos projetos
PREVIAS = Path("3d") / "projetos"  # dentro do Acervo
TIPOS = {"peca": "Peça funcional", "arte": "Arte a partir de imagem"}
IMAGENS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGEM = 20 * 1024 * 1024
MAX_TRIANGULOS = 2_000_000  # acima disto, a prévia pesa demais para a Imersão
MOSTRADOS = (".stl", ".3mf", ".glb", ".obj", ".step", ".stp", ".blend", ".svg", ".png", ".jpg",
             ".jpeg", ".webp", ".json", ".py", ".md")  # fmt: skip
OCULTOS = {"projeto.json", "AGENTS.md", "CLAUDE.md"}
MARMORE = [0.93, 0.92, 0.89, 1.0]  # a cor da prévia sólida
MESA_PADRAO = [220, 220, 250]


class Projeto3DErro(ValueError):
    """Um pedido que não dá para atender (o texto vai para a tela e para a voz)."""


@dataclass(frozen=True)
class Medidas:
    """O que se lê de um STL: o tamanho em mm, o volume e se a malha é fechada."""

    tamanho_mm: tuple[float, float, float]
    volume_mm3: float
    triangulos: int
    fechada: bool

    def para_json(self) -> dict[str, Any]:
        return {
            "tamanho_mm": [round(v, 2) for v in self.tamanho_mm],
            "volume_cm3": round(self.volume_mm3 / 1000, 2),
            "triangulos": self.triangulos,
            "fechada": self.fechada,
        }


# ---- o STL ----------------------------------------------------------------------------------


def ler_stl(caminho: Path) -> np.ndarray:
    """Os triângulos do STL (binário ou texto), como um array (n, 3, 3) em float64."""
    dados = caminho.read_bytes()
    if len(dados) >= 84:
        n = struct.unpack_from("<I", dados, 80)[0]
        if 84 + 50 * n == len(dados):  # binário: o tamanho confere com a contagem
            if n > MAX_TRIANGULOS:
                raise Projeto3DErro("Modelo grande demais para a prévia.")
            registro = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
            return np.frombuffer(dados, registro, n, 84)["v"].astype(np.float64)
    texto = dados.decode("utf-8", "ignore")
    if "facet" not in texto:
        raise Projeto3DErro("Arquivo STL inválido.")
    numeros = re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", texto)
    if not numeros or len(numeros) % 3:
        raise Projeto3DErro("Arquivo STL inválido.")
    if len(numeros) // 3 > MAX_TRIANGULOS:
        raise Projeto3DErro("Modelo grande demais para a prévia.")
    return np.array(numeros, dtype=np.float64).reshape(-1, 3, 3)


def medir(triangulos: np.ndarray) -> Medidas:
    """Tamanho, volume (pela divergência) e se cada aresta é de exatamente dois triângulos."""
    if not len(triangulos):
        return Medidas((0.0, 0.0, 0.0), 0.0, 0, False)
    pontos = triangulos.reshape(-1, 3)
    tamanho = pontos.max(axis=0) - pontos.min(axis=0)
    v0, v1, v2 = triangulos[:, 0], triangulos[:, 1], triangulos[:, 2]
    volume = float(abs(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum()) / 6)
    # vértices iguais (até 1 µm) viram o mesmo índice; cada aresta, um par ordenado
    _, indices = np.unique(np.round(pontos, 3), axis=0, return_inverse=True)
    faces = indices.reshape(-1, 3)
    arestas = np.sort(
        np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1
    )
    _, contagem = np.unique(arestas, axis=0, return_counts=True)
    return Medidas(
        (float(tamanho[0]), float(tamanho[1]), float(tamanho[2])),
        volume,
        len(triangulos),
        bool(len(contagem)) and bool((contagem == 2).all()),
    )


def para_glb(triangulos: np.ndarray, cor: list[float] = MARMORE) -> bytes:
    """Um GLB sólido (faces planas, material fosco) do STL. Uma peça alta aparece de pé, como
    sai da mesa (o Z da impressão vira o Y do glTF); uma achatada (um relevo, uma placa, que se
    imprime deitada) aparece de frente, olhando para quem vê."""
    t = triangulos.astype(np.float32)
    tamanho = t.reshape(-1, 3).max(axis=0) - t.reshape(-1, 3).min(axis=0) if len(t) else None
    achatada = tamanho is not None and tamanho[2] < 0.25 * min(tamanho[0], tamanho[1])
    if not achatada:
        t = np.stack([t[..., 0], t[..., 2], -t[..., 1]], axis=-1)  # Z para cima → Y para cima
    normais = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    comprimento = np.linalg.norm(normais, axis=1, keepdims=True)
    normais = np.where(comprimento > 0, normais / np.maximum(comprimento, 1e-12), 0).astype(
        np.float32
    )
    posicoes = t.reshape(-1, 3)
    normais = np.repeat(normais, 3, axis=0)
    binario = posicoes.tobytes() + normais.tobytes()
    n = len(posicoes)
    gltf = {
        "asset": {"version": "2.0", "generator": "Zervis"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "material": 0}]}],
        "materials": [
            {
                "name": "Mármore",
                "pbrMetallicRoughness": {
                    "baseColorFactor": cor,
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.55,
                },
            }
        ],
        "buffers": [{"byteLength": len(binario)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": n * 12, "target": 34962},
            {"buffer": 0, "byteOffset": n * 12, "byteLength": n * 12, "target": 34962},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": n,
                "type": "VEC3",
                "min": posicoes.min(axis=0).tolist() if n else [0, 0, 0],
                "max": posicoes.max(axis=0).tolist() if n else [0, 0, 0],
            },
            {"bufferView": 1, "componentType": 5126, "count": n, "type": "VEC3"},
        ],
    }
    texto = json.dumps(gltf, separators=(",", ":")).encode()
    texto += b" " * (-len(texto) % 4)
    binario += b"\0" * (-len(binario) % 4)
    total = 12 + 8 + len(texto) + 8 + len(binario)
    return (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<I4s", len(texto), b"JSON")
        + texto
        + struct.pack("<I4s", len(binario), b"BIN\0")
        + binario
    )


# ---- os projetos ----------------------------------------------------------------------------


def identificador(nome: str) -> str:
    """ "Suporte de celular" -> "suporte-de-celular"."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:50]


def instrucoes(nome: str, tipo: str, pedido: str, ajustes: dict[str, Any], imagem: str) -> str:
    """O `AGENTS.md` do projeto: o que a sessão de código entrega e como."""
    mesa = " x ".join(str(int(v)) for v in ajustes.get("mesa_mm") or MESA_PADRAO)
    impressora = str(ajustes.get("impressora") or "").strip()
    onde = f"{impressora}: mesa de {mesa} mm" if impressora else f"mesa de {mesa} mm"
    partes = [
        f"# Projeto 3D: {nome}",
        "",
        f"Tipo: {TIPOS[tipo]}.",
        f"Pedido: {pedido}",
        "",
        "## Entregas (o Zé lê esta pasta)",
        "",
        "- Um STL por peça, em milímetros, já orientado para imprimir (apoiado em Z=0), com nome "
        "claro (`modelo.stl`; com mais de uma peça, `arte.stl`, `base.stl`...).",
        "- O script que gera tudo (`gerar.py`), com as medidas como variáveis no topo: pedir "
        '"aumenta a base em 5 mm" deve ser mudar um número e rodar de novo.',
        "- Um `LEIA_ME.md` curto: as peças, as medidas finais e o que ainda não foi testado.",
        "- Não imprima nem mande nada para a impressora: isso é do Zé, com o sim de quem usa.",
        "",
        f"## Para imprimir ({onde}, bico de 0,4 mm)",
        "",
        "- Sólido fechado, sem faces soltas nem buracos; confira antes de entregar.",
        "- Paredes de no mínimo 1,2 mm. Encaixes e furos com folga de 0,2 mm por lado.",
        "- Evite balanços acima de 45° sem apoio: prefira chanfro, ou divida em peças.",
        "",
    ]
    if tipo == "peca":
        partes += [
            "## Peça funcional: modelagem por código",
            "",
            "- Modele de forma paramétrica em Python, com build123d (ou CadQuery). Se não estiver "
            "instalado, crie um ambiente nesta pasta (`uv venv` e `uv pip install build123d`).",
            "- Exporte o STL pelo próprio script e confira medidas e volume.",
        ]
    else:
        pipeline = str(ajustes.get("pipeline_arte") or "").strip()
        partes += ["## Arte a partir de imagem", ""]
        partes.append(
            f"- A imagem de referência está em `{imagem}`." if imagem else
            "- Ainda não há imagem: peça uma a quem usa antes de começar."
        )  # fmt: skip
        if pipeline:
            partes.append(
                f"- Use a pipeline aprovada em `{pipeline}`: leia o `AGENTS.md` e o `README.md` de "
                "lá antes de começar e siga as regras dela (espessuras, base, encaixe). Grave os "
                "resultados nesta pasta, não na da pipeline."
            )
        else:
            partes.append(
                "- Extraia a máscara e os contornos da imagem (OpenCV), suavize os contornos "
                "(shapely) e faça o relevo como sólido (manifold3d ou trimesh)."
            )
    if shutil.which("blender"):
        partes += [
            "",
            "## Blender",
            "",
            "- O Blender está instalado: use em linha de comando (`blender -b --python "
            "script.py`) para conferir, consertar e exportar as malhas.",
        ]
    return "\n".join(partes) + "\n"


def _trabalho(pasta: Path, arquivo: str) -> Path:
    return (
        pasta / ".ze" / "impressao" / re.sub(r"[^\w.-]+", "-", str(Path(arquivo).with_suffix("")))
    )


class Projetos3D:
    def __init__(self, raiz: Path, acervo: Path, ajustes: Path) -> None:
        self.raiz = raiz.expanduser()
        self.acervo = acervo.expanduser()
        self.arquivo_ajustes = ajustes

    # ---- ajustes: a impressora e a pipeline de arte de quem usa ----

    def ajustes(self) -> dict[str, Any]:
        try:
            dados = json.loads(self.arquivo_ajustes.read_text())
        except (OSError, ValueError):
            dados = {}
        mesa = dados.get("mesa_mm")
        if not (isinstance(mesa, list) and len(mesa) == 3):
            mesa = MESA_PADRAO
        return {
            "impressora": str(dados.get("impressora") or ""),
            "mesa_mm": [float(v) for v in mesa],
            "pipeline_arte": str(dados.get("pipeline_arte") or ""),
        }

    def guardar_ajustes(self, impressora: str, mesa_mm: list[Any], pipeline_arte: str) -> None:
        try:
            mesa = [float(v) for v in mesa_mm]
        except (TypeError, ValueError):
            raise Projeto3DErro("Medidas da mesa inválidas.") from None
        if len(mesa) != 3 or not all(50 <= v <= 2000 for v in mesa):
            raise Projeto3DErro("Medidas da mesa inválidas.")
        pipeline = pipeline_arte.strip()
        if pipeline and not Path(pipeline).expanduser().is_dir():
            raise Projeto3DErro("Pasta da pipeline não encontrada.")
        self.arquivo_ajustes.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo_ajustes.write_text(
            json.dumps(
                {
                    "impressora": " ".join(impressora.split())[:60],
                    "mesa_mm": mesa,
                    "pipeline_arte": pipeline,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    # ---- os projetos ----

    def pasta(self, id_: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,49}", id_ or ""):
            raise Projeto3DErro("Projeto não encontrado.")
        pasta = self.raiz / id_
        if not (pasta / "projeto.json").is_file():
            raise Projeto3DErro("Projeto não encontrado.")
        return pasta

    def criar(
        self, nome: str, tipo: str, pedido: str, imagem: bytes | None = None, nome_imagem: str = ""
    ) -> dict[str, Any]:
        """A pasta nova do projeto, com o `AGENTS.md` (e o `CLAUDE.md` que o importa) e a imagem
        de referência em `entrada/`. A sessão que trabalha nela é criada por quem chama."""
        nome = " ".join(nome.split())[:60]
        pedido = " ".join(pedido.split())[:2000]
        if tipo not in TIPOS:
            raise Projeto3DErro("Tipo de projeto inválido.")
        if not (id_ := identificador(nome)):
            raise Projeto3DErro("Dê um nome ao projeto.")
        if not pedido:
            raise Projeto3DErro("Descreva a peça.")
        pasta = self.raiz / id_
        if pasta.exists():
            raise Projeto3DErro(f"Já existe um projeto {nome}.")
        caminho_imagem = ""
        if imagem is not None:
            sufixo = Path(nome_imagem).suffix.lower()
            if sufixo not in IMAGENS or not imagem or len(imagem) > MAX_IMAGEM:
                raise Projeto3DErro("Imagem inválida: PNG, JPG ou WebP, até 20 MB.")
            caminho_imagem = f"entrada/referencia{sufixo}"
        pasta.mkdir(parents=True)
        if imagem is not None:
            (pasta / "entrada").mkdir()
            (pasta / caminho_imagem).write_bytes(imagem)
        (pasta / "AGENTS.md").write_text(
            instrucoes(nome, tipo, pedido, self.ajustes(), caminho_imagem)
        )
        (pasta / "CLAUDE.md").write_text("@AGENTS.md\n")
        dados = {"nome": nome, "tipo": tipo, "pedido": pedido, "criado": time.time(), "sessao": ""}
        (pasta / "projeto.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2))
        return {"id": id_, **dados, "pasta": str(pasta)}

    def vincular(self, id_: str, sessao: str) -> None:
        arquivo = self.pasta(id_) / "projeto.json"
        dados = json.loads(arquivo.read_text())
        dados["sessao"] = sessao
        arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2))

    def ler(self, id_: str) -> dict[str, Any]:
        pasta = self.pasta(id_)
        try:
            dados = json.loads((pasta / "projeto.json").read_text())
        except ValueError:
            dados = {}
        arquivos = []
        for f in sorted(pasta.rglob("*")):
            relativo = f.relative_to(pasta)
            if (
                not f.is_file()
                or f.name in OCULTOS
                or f.suffix.lower() not in MOSTRADOS
                or any(p.startswith(".") or p in ("__pycache__", ".venv") for p in relativo.parts)
            ):
                continue
            item: dict[str, Any] = {
                "nome": str(relativo),
                "tamanho": f.stat().st_size,
                "modificado": f.stat().st_mtime,
            }
            if f.suffix.lower() == ".stl":
                item["medidas"] = self._medidas(f)
                if fatia := self.fatia(id_, str(relativo)):
                    item["fatiado"] = {k: fatia[k] for k in ("minutos", "gramas", "filamento")}
            arquivos.append(item)
        tipo = str(dados.get("tipo") or "peca")
        return {
            "id": id_,
            "nome": str(dados.get("nome") or id_),
            "tipo": tipo,
            "tipo_nome": TIPOS.get(tipo, tipo),
            "pedido": str(dados.get("pedido") or ""),
            "criado": float(dados.get("criado") or pasta.stat().st_mtime),
            "sessao": str(dados.get("sessao") or ""),
            "pasta": str(pasta),
            "arquivos": arquivos,
        }

    def listar(self) -> list[dict[str, Any]]:
        if not self.raiz.is_dir():
            return []
        projetos = []
        for pasta in self.raiz.iterdir():
            if (pasta / "projeto.json").is_file():
                try:
                    projetos.append(self.ler(pasta.name))
                except Projeto3DErro:
                    continue
        return sorted(projetos, key=lambda p: -p["criado"])

    def _medidas(self, stl: Path) -> dict[str, Any] | None:
        """As medidas de um STL, guardadas ao lado (`.ze/`) enquanto o arquivo não muda."""
        guardado = stl.parent / ".ze" / f"{stl.name}.medidas.json"
        marca = [stl.stat().st_size, stl.stat().st_mtime]
        try:
            antigo = json.loads(guardado.read_text())
            if antigo.get("marca") == marca:
                return dict(antigo["medidas"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
        try:
            medidas = medir(ler_stl(stl)).para_json()
        except (Projeto3DErro, OSError, ValueError):
            return None
        guardado.parent.mkdir(exist_ok=True)
        guardado.write_text(json.dumps({"marca": marca, "medidas": medidas}))
        return medidas

    def fatia(self, id_: str, arquivo: str) -> dict[str, Any] | None:
        """O último fatiamento desse STL, se ainda vale (o STL não mudou depois)."""
        pasta = self.pasta(id_)
        guardado = _trabalho(pasta, arquivo) / "fatia.json"
        try:
            dados: dict[str, Any] = json.loads(guardado.read_text())
            if (pasta / arquivo).stat().st_mtime > guardado.stat().st_mtime:
                return None
            if not Path(dados["arquivo"]).is_file():
                return None
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return dados

    def principal(self, id_: str) -> str:
        """O modelo que se mostra quando ninguém diz qual: `modelo.stl`, senão o STL maior,
        senão um GLB."""
        p = self.ler(id_)
        modelos = [a for a in p["arquivos"] if a["nome"].lower().endswith((".stl", ".glb"))]
        if not modelos:
            raise Projeto3DErro("O projeto ainda não tem modelo.")
        for a in modelos:
            if Path(a["nome"]).name.lower() == "modelo.stl":
                return str(a["nome"])
        stls = [a for a in modelos if a["nome"].lower().endswith(".stl")]
        return str(max(stls or modelos, key=lambda a: a["tamanho"])["nome"])

    def previa(self, id_: str, arquivo: str = "") -> str:
        """O caminho, no Acervo, da prévia sólida para a Imersão (feita de novo só quando o
        arquivo muda)."""
        pasta = self.pasta(id_)
        arquivo = arquivo or self.principal(id_)
        origem = (pasta / arquivo).resolve()
        if not origem.is_relative_to(pasta.resolve()) or not origem.is_file():
            raise Projeto3DErro("Arquivo não encontrado.")
        if origem.suffix.lower() not in (".stl", ".glb"):
            raise Projeto3DErro("A Imersão mostra arquivos STL ou GLB.")
        nome = re.sub(r"[^\w.-]+", "-", str(Path(arquivo).with_suffix(""))).strip("-")
        relativo = PREVIAS / id_ / f"{nome}.glb"
        destino = self.acervo / relativo
        if not destino.is_file() or destino.stat().st_mtime < origem.stat().st_mtime:
            destino.parent.mkdir(parents=True, exist_ok=True)
            if origem.suffix.lower() == ".glb":
                shutil.copyfile(origem, destino)
            else:
                destino.write_bytes(para_glb(ler_stl(origem)))
        return str(relativo)


def tarefa(projeto: dict[str, Any]) -> str:
    """A primeira tarefa da sessão do projeto."""
    return (
        f'Projeto 3D "{projeto["nome"]}" ({TIPOS[projeto["tipo"]].lower()}): '
        f"{projeto['pedido']} Siga o AGENTS.md desta pasta. No fim, diga em poucas palavras as "
        "peças entregues e as medidas finais."
    )


def comecar(projetos: Projetos3D, sessoes: Any, id_: str, motor: str, origem: str) -> str:
    """A sessão de código do projeto, com a primeira tarefa: devolve o id dela."""
    p = projetos.ler(id_)
    s = sessoes.criar(f"3D · {p['nome']}", p["pasta"], motor=motor, origem=origem)
    projetos.vincular(id_, s.id)
    sessoes.enviar(s.id, tarefa(p))
    return str(s.id)


# ---- fatiar e imprimir (ADR 0083) ------------------------------------------------------------


def _bandeja(status: dict[str, Any] | None) -> tuple[int | None, str, str]:
    """A bandeja do AMS a usar (a primeira com filamento; PLA antes), ou o carretel de fora."""
    if status:
        bandejas = sorted(status["bandejas"], key=lambda b: (b["tipo"] != "PLA", b["indice"]))
        if bandejas:
            b = bandejas[0]
            return int(b["indice"]), str(b["tipo"]), str(b["marca"])
        if status.get("externo"):
            return None, str(status["externo"]), ""
    return None, "PLA", ""


def fatiar(
    projetos: Projetos3D, impressora: Impressora3D, id_: str, arquivo: str = ""
) -> dict[str, Any]:
    """Fatia o STL com o perfil da impressora e o filamento que está nela agora."""
    pasta = projetos.pasta(id_)
    arquivo = arquivo or projetos.principal(id_)
    stl = (pasta / arquivo).resolve()
    if not stl.is_relative_to(pasta.resolve()) or not stl.is_file() or stl.suffix.lower() != ".stl":
        raise Projeto3DErro("Escolha um STL do projeto.")
    conexao = impressora.conexao()
    if conexao is None or not conexao.modelo:
        raise Projeto3DErro("Configure a impressora na aba Projetos 3D.")
    try:
        status: dict[str, Any] | None = impressora.status()
    except ImpressoraErro:
        status = None  # desligada: fatia com PLA e escolhe a bandeja na hora de imprimir
    bandeja, tipo, marca = _bandeja(status)
    try:
        f = fatiador.fatiar(stl, _trabalho(pasta, arquivo), conexao.modelo, tipo, marca)
    except fatiador.FatiadorErro as erro:
        raise Projeto3DErro(str(erro)) from None
    dados = {**f.para_json(), "stl": arquivo, "bandeja": bandeja, "tipo": tipo}
    (_trabalho(pasta, arquivo) / "fatia.json").write_text(json.dumps(dados, ensure_ascii=False))
    return {**dados, "fala": fala_da_fatia(dados)}


def fala_da_fatia(dados: dict[str, Any]) -> str:
    horas, minutos = divmod(int(dados["minutos"]), 60)
    tempo = f"{horas} h {minutos:02d}" if horas else f"{minutos} min"
    filamento = (
        str(dados["filamento"]).split(" @")[0].removeprefix("Bambu ").removeprefix("Generic ")
    )
    onde = (
        f"da bandeja {dados['bandeja'] + 1}" if dados.get("bandeja") is not None else "do carretel"
    )
    return f"Leva {tempo} e {round(float(dados['gramas']))} g de {filamento} {onde}."


def imprimir(
    projetos: Projetos3D, impressora: Impressora3D, id_: str, arquivo: str = ""
) -> dict[str, Any]:
    """Manda o fatiado para a impressora (fatia antes, se preciso). Quem chama já pediu o sim."""
    arquivo = arquivo or projetos.principal(id_)
    fatia = projetos.fatia(id_, arquivo) or fatiar(projetos, impressora, id_, arquivo)
    nome = projetos.ler(id_)["nome"]
    try:
        impressora.imprimir(Path(fatia["arquivo"]), nome, fatia.get("bandeja"))
    except ImpressoraErro as erro:
        raise Projeto3DErro(str(erro)) from None
    return {"imprimindo": nome, "fala": f"Mandei {nome} para a impressora. {fala_da_fatia(fatia)}"}
