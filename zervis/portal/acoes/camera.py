"""Ações da seção Câmera no painel."""

import base64
from typing import Any

from zervis import camera
from zervis.portal.acoes.pagina import Pagina
from zervis.portal.servidor import PedidoInvalido

GALERIA = 100  # as mais novas na tela; as outras seguem guardadas


class AcoesCamera(Pagina):
    dependencias = ("camera", "vigia_camera")

    def camera(self) -> dict[str, Any]:
        return {
            **self.n.camera.para_tela(),
            "estado": self.n.vigia_camera.estado(),
            "lentes": self.n.vigia_camera.lentes,
            "fotos": [
                {"nome": foto["nome"], "quando": foto["quando"], "lente": foto["lente"]}
                for foto in self.n.vigia_camera.fotos()[:GALERIA]
            ],
        }

    def procurar_camera(self, dados: dict[str, Any]) -> dict[str, Any]:
        achadas = self.n.camera.procurar()
        return {"achadas": achadas, "aviso": "" if achadas else "Nenhuma câmera encontrada."}

    def salvar_camera(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.camera.guardar(
                str(dados.get("ip", "")),
                str(dados.get("usuario", "admin")),
                str(dados.get("senha", "")),
                int(dados.get("intervalo_s", 30)),
                bool(dados.get("ligado", False)),
                _girar(dados.get("girar")),
            )
        except (camera.CameraErro, ValueError) as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.camera(), "aviso": "Salvo."}

    def testar_camera(self, dados: dict[str, Any]) -> dict[str, Any]:
        if self.n.vigia_camera.estado() == "Conectada":
            return {"aviso": "Conectada."}
        try:
            self.n.camera.testar()
        except camera.CameraErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return {"aviso": "Conectada."}

    def foto_camera(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            nome = str(dados.get("nome", ""))
            if nome:
                caminho = self.n.vigia_camera.ler_foto(nome)
            else:
                caminho = self.n.vigia_camera.fotos_agora()[0]
            imagem = caminho.read_bytes()
        except (camera.CameraErro, OSError) as erro:
            raise PedidoInvalido(
                str(erro) if isinstance(erro, camera.CameraErro) else "A foto não está disponível."
            ) from None
        return {
            "nome": caminho.name,
            "foto": "data:image/jpeg;base64," + base64.b64encode(imagem).decode("ascii"),
        }


def _girar(valor: Any) -> list[int] | None:
    if valor is None:
        return None
    if not isinstance(valor, list):
        raise PedidoInvalido("Lentes inválidas.")
    return [int(v) for v in valor if isinstance(v, int) and not isinstance(v, bool)]
