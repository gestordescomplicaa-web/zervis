"""Serviço de remoto; pode ser exercitado com dependências próprias, sem subir o núcleo."""

import logging
import secrets
import time
from typing import Any, Protocol
from urllib.parse import urlsplit

import segno

from zervis import usuario
from zervis.avisos import modo as modo_fala
from zervis.filho import porta_ocupada
from zervis.nucleo import estados as e
from zervis.portal import remoto, tunel
from zervis.preparar import PrepararErro
from zervis.transporte import servidor_livekit
from zervis.transporte.navegador import VozNavegador
from zervis.transporte.remoto import SalaRemota
from zervis.transporte.websocket import Conexao

log = logging.getLogger(__name__)


class ContextoRemoto(Protocol):
    _digitado_em: Any
    _fonte: Any
    acesso: Any
    captura: Any
    eventos: Any
    livekit: Any
    maquina: Any
    modo_fala: Any
    portal: Any
    remota: Any
    rostos: Any
    tunel: Any
    voz: Any

    def _fonte_remota(self, fonte: Any, conectada: bool) -> None: ...
    def _na_linha(self, tipo: str, texto: str) -> None: ...
    def _quadro_remoto(self, fonte: Any, quadro: bytes) -> None: ...
    @property
    def microfone_travado(self) -> bool: ...


class ServicoRemoto:
    def __init__(self, contexto: ContextoRemoto) -> None:
        self.n = contexto

    def _no_proprio_pc(self) -> bool:
        """O pedido em curso veio do microfone do próprio PC (não do celular nem digitado)."""
        return (
            getattr(self.n, "_digitado_em", None) is None
            and getattr(self.n, "_fonte", None) is None
        )

    def _origem(self) -> str:
        """De onde veio o pedido em curso, para a atividade."""
        if self.n._digitado_em is not None:
            return "texto"
        return "voz remota" if isinstance(getattr(self.n, "_fonte", None), VozNavegador) else "voz"

    def _ligar_voz_remota(self) -> None:
        """Sobe a sala da voz remota e põe o Zé nela (plano da voz remota, etapa 1)."""
        rede = remoto.rede(self.n.portal.porta) if self.n.portal is not None else remoto.Rede()
        if rede.ativo and self.n.portal is not None:
            self.n.portal.permitir(rede.nome)  # o celular já alcançava o painel antes do reinício
        if not self.n.livekit.iniciar(*((rede.ip, rede.casa) if rede.ativo else ("", ""))):
            return
        chave, segredo = servidor_livekit.credenciais()
        self.n.remota = SalaRemota(
            self.n.livekit.url,
            lambda: servidor_livekit.token(chave, segredo, "ze", "Zé", validade_s=3600),
            lambda quadro: self.n._quadro_remoto(self.n.remota, quadro),
            lambda conectada: self.n._fonte_remota(self.n.remota, conectada),
            pronto=lambda: porta_ocupada(self.n.livekit.porta),
        )
        self.n.remota.iniciar()

    def _fonte_remota(self, fonte: Any, conectada: bool) -> None:
        """Uma voz remota (o navegador pelo HTTPS do painel ou a sala LiveKit) conectou ou saiu:
        a entrada e a saída de áudio trocam de lado, e o aparelho conectado vale como rosto
        (ADR 0021). Uma fonte por vez: a nova assume e a anterior é desligada, para duas não
        escreverem juntas na mesma fila."""
        anterior = self.n._fonte
        if conectada:
            self.n._fonte = fonte
            if isinstance(anterior, VozNavegador) and anterior is not fonte:
                anterior.conexao.fechar()
        elif anterior is fonte:
            self.n._fonte = None
        else:
            return  # saiu uma fonte que já não era a atual
        ligada = self.n._fonte is not None
        self.n.captura.remota(ligada)
        self.n.voz.destino = self.n._fonte.tocador if self.n._fonte is not None else None
        if (anterior is None) != (self.n._fonte is None):
            self.n.rostos.marcar("remoto", ligada)
        # Conectada, a voz é ao vivo (ADR 0023), menos a do app no modo chamado; trocar uma pela
        # outra (o navegador e o app) também troca o modo.
        desejado = ligada and bool(getattr(self.n._fonte, "ao_vivo", True))
        if desejado != self.n.maquina.ao_vivo or (anterior is None) != (self.n._fonte is None):
            self.n.eventos.put(e.AoVivo(desejado))

    def _quadro_remoto(self, fonte: Any, quadro: bytes) -> None:
        if fonte is self.n._fonte and not self.n.microfone_travado:
            self.n.captura.receber(quadro)

    def voz_pelo_navegador(self, conexao: Conexao, taxa: int) -> None:
        """O botão Ao vivo do navegador abriu o canal de voz pelo HTTPS do painel (roteiro,
        passo 4.2); fica aqui, na thread da conexão, até ela fechar."""
        if self.n.microfone_travado:
            log.info("voz pelo navegador: recusada no modo Silencioso")
            conexao.fechar()
            return
        voz = VozNavegador(conexao, taxa)
        log.info("voz pelo navegador: conectada (%d Hz)", voz.taxa)
        self.n._fonte_remota(voz, True)
        try:
            voz.ouvir(lambda quadro: self.n._quadro_remoto(voz, quadro))
        finally:
            self.n._fonte_remota(voz, False)
            log.info("voz pelo navegador: desconectada")

    def voz_pelo_app(
        self, conexao: Conexao, taxa: int, modo: str, aparelho: dict[str, Any]
    ) -> None:
        """O app de voz do Android (`zervis/portal/voz_app.py`): o celular bloqueado, no bolso.
        No modo chamado, o Zé trata o áudio como o do microfone do PC ("Ei Zé" e o botão do
        fone); ao vivo, como o navegador."""
        if self.n.microfone_travado:
            log.info("app de voz: recusado no modo Silencioso")
            conexao.fechar()
            return
        voz = VozNavegador(conexao, taxa, ao_vivo=modo == "ao_vivo")
        log.info("app de voz: %s conectado (%s, %d Hz)", aparelho.get("nome"), modo, voz.taxa)
        self.n._fonte_remota(voz, True)

        def controle(mensagem: dict[str, object]) -> None:
            if voz is not self.n._fonte:
                return
            if mensagem.get("tipo") == "apertar" and not self.n.microfone_travado:
                self.n.eventos.put(e.Apertou())
            elif mensagem.get("tipo") == "soltar":
                self.n.eventos.put(e.Soltou())

        try:
            voz.ouvir(lambda quadro: self.n._quadro_remoto(voz, quadro), controle)
        finally:
            self.n._fonte_remota(voz, False)
            log.info("app de voz: desconectado")

    def estado_remoto(self) -> dict[str, Any]:
        rede = remoto.rede(self.n.portal.porta if self.n.portal else 0).para_tela()
        endereco = self.n.tunel.endereco
        qr = (
            segno.make(endereco, error="m").svg_inline(
                scale=5, dark="#070c11", light="#ffffff", border=2
            )
            if endereco
            else ""
        )
        return {
            **rede,
            "senha": self.n.acesso.tem_senha,
            "codigo": self.n.acesso.tem_codigo,
            "aparelhos": self.n.acesso.aparelhos(),
            "lista": self.n.acesso.lista(),
            "tunel": {"ativo": self.n.tunel.ativo, "endereco": endereco, "qr": qr},
        }

    def _aparelho_entrou(self, nome: str) -> None:
        """Quem entra de outro aparelho não passa em silêncio: aviso na tela e, se o modo de
        fala deixar, falado."""
        texto = f"Um aparelho entrou no painel: {nome}."
        log.warning("painel: %s", texto)
        self.n._na_linha("aviso", texto)
        if modo_fala.falar(self.n.modo_fala, "urgente"):
            self.n.eventos.put(e.Aviso(texto))

    def _tunel_pronto(self, endereco: str) -> None:
        if self.n.portal is not None:
            self.n.portal.permitir(urlsplit(endereco).netloc)

    def _tunel_caiu(self, endereco: str) -> None:
        if self.n.portal is not None:
            self.n.portal.proibir(urlsplit(endereco).netloc)

    def _subir_tunel(self) -> None:
        if self.n.portal is None:
            return
        try:
            self.n.tunel.iniciar(self.n.portal.porta, tunel.garantir())
        except (PrepararErro, OSError) as erro:
            log.warning("túnel não subiu: %s", erro)

    def ativar_tunel(self) -> str:
        """Acesso de qualquer lugar, sem nada no celular além do navegador (Cloudflare)."""
        if self.n.portal is None:
            raise remoto.RemotoErro("Painel indisponível.")
        if not (self.n.acesso.tem_senha and self.n.acesso.tem_codigo):
            raise remoto.RemotoErro("Defina a senha e ligue o código do autenticador antes.")
        try:
            self.n.tunel.iniciar(self.n.portal.porta, tunel.garantir())
        except (PrepararErro, OSError) as erro:
            raise remoto.RemotoErro("Não consegui baixar o túnel do Cloudflare.") from erro
        tunel.escolher(True)
        for _ in range(150):  # o endereço sai em alguns segundos
            if self.n.tunel.endereco or not self.n.tunel.ativo:
                break
            time.sleep(0.1)
        if not self.n.tunel.endereco:
            raise remoto.RemotoErro("O túnel não respondeu. Tente de novo em instantes.")
        return "Acesso de qualquer lugar ativo."

    def desativar_tunel(self) -> str:
        tunel.escolher(False)
        endereco = self.n.tunel.endereco
        self.n.tunel.parar()
        if self.n.portal is not None and endereco:
            self.n.portal.proibir(urlsplit(endereco).netloc)
        return "Acesso de qualquer lugar desativado."

    def ativar_remoto(self) -> str:
        """Publica o painel e a sala de voz na rede privada (Voz > Acesso pelo celular)."""
        if self.n.portal is None:
            raise remoto.RemotoErro("Painel indisponível.")
        if not self.n.acesso.tem_senha:
            raise remoto.RemotoErro("Defina a senha de acesso antes de ativar.")
        rede = remoto.rede(self.n.portal.porta)
        if not rede.conectado:
            raise remoto.RemotoErro("Tailscale desconectado neste computador.")
        remoto.ativar(self.n.portal.porta, self.n.livekit.porta)
        self.n.portal.permitir(rede.nome)
        self.n.livekit.reiniciar(rede.ip, rede.casa)
        log.info("acesso pelo celular: %s", rede.endereco)
        return "Acesso pelo celular ativo."

    def desativar_remoto(self) -> str:
        rede = remoto.rede(self.n.portal.porta if self.n.portal else 0)
        remoto.desativar()
        if self.n.portal is not None and rede.nome:
            self.n.portal.proibir(rede.nome)
        self.n.livekit.reiniciar("")
        return "Acesso pelo celular desativado."

    def token_voz_remota(self) -> dict[str, str]:
        """Um token curto para o navegador entrar na sala e falar com o Zé."""
        if self.n.remota is None:
            raise ValueError("Voz remota indisponível.")
        chave, segredo = servidor_livekit.credenciais()
        identidade = f"pessoa-{secrets.token_hex(4)}"
        return {
            "url": self.n.livekit.url,
            "token": servidor_livekit.token(chave, segredo, identidade, usuario.PERFIL.rotulo),
        }
