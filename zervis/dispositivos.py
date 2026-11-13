"""Os dispositivos da casa (ADR 0089, fase 1): um registro só, lido dos cadastros de cada um.

Por enquanto, cada aparelho guarda o próprio cadastro (`camera.json`, `impressora3d.json`,
`tv.json`). Daqui sai a lista que o painel Dispositivos e a voz mostram, sem mover nem migrar
nada: no PC de quem já usa, tudo continua onde estava. O registro em SQLite vem com as
integrações por pacote (fase 3).
"""

from typing import Any

TIPOS = [
    {
        "id": "camera",
        "nome": "Câmera",
        "descricao": "Câmera Wi-Fi iCSee (Xiongmai): fotos por movimento e conversa pela câmera.",
    },
    {
        "id": "impressora",
        "nome": "Impressora 3D",
        "descricao": "Bambu Lab na rede local: estado, câmera, avisos e impressão.",
    },
    {
        "id": "tv",
        "nome": "TV",
        "descricao": "O navegador da TV mostra o que o Zé apresenta, como as peças 3D.",
    },
]


def listar(camera: Any, vigia_camera: Any, impressora: Any, tela_tv: Any) -> list[dict[str, Any]]:
    """Os aparelhos cadastrados, com o estado em uma ou duas palavras."""
    lista: list[dict[str, Any]] = []
    if camera is not None and (c := camera.para_tela())["configurada"]:
        estado = vigia_camera.estado() if vigia_camera is not None else "Configurada"
        lentes = getattr(vigia_camera, "lentes", 1)
        detalhe = c["ip"] + (f" · {lentes} lentes" if lentes > 1 else "")
        lista.append(_item("camera", "Câmera", estado, estado == "Conectada", detalhe))
    if impressora is not None and (i := impressora.para_tela())["configurada"]:
        vivo = impressora.retrato_vivo() if impressora.retrato_vivo is not None else None
        estado = "Conectada" if vivo else "Sem conexão"
        detalhe = " · ".join(
            x for x in (f"Bambu Lab {i['modelo']}" if i["modelo"] else "", i["ip"]) if x
        )
        lista.append(_item("impressora", "Impressora 3D", estado, bool(vivo), detalhe))
    if tela_tv is not None and (t := tela_tv.para_tela())["ligado"]:
        estado = "Aberto na TV" if t["aberta"] else "Ligado"
        lista.append(_item("tv", "TV", estado, bool(t["aberta"]), t["ip_tv"]))
    return lista


def _item(ident: str, nome: str, estado: str, bom: bool, detalhe: str) -> dict[str, Any]:
    return {"id": ident, "nome": nome, "estado": estado, "bom": bom, "detalhe": detalhe}
