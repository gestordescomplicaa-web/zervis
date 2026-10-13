"""O que o painel lê e muda no núcleo (docs/plano-painel.md).

Só leitura do que já existe (skills, memória, automações, Foco, consumo) e, na fatia 1, as
mudanças da via rápida: motor, modelo, chave e o teste de tempo. A regra continua no núcleo;
aqui só se traduz para a tela.
"""

import asyncio
import base64
import contextlib
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import segno

from jarvis import atividade, fuso, lugares, usuario
from jarvis.automacoes.jobs import JobErro
from jarvis.avisos import modo as modo_fala
from jarvis.cerebro import acesso, conectores, contas, modelos, rapido
from jarvis.cerebro.mcp_externo import McpInvalido
from jarvis.habilidades import revisao
from jarvis.habilidades.skills import SkillErro, frente
from jarvis.memoria.curta import MemoriaErro, Mudanca
from jarvis.oficina import arquivos
from jarvis.oficina.sessoes import Sessao, SessaoErro
from jarvis.portal import remoto
from jarvis.portal.senha import SenhaErro
from jarvis.portal.servidor import Escrita, Leitura, PedidoInvalido
from jarvis.presenca import modo as modo_escuta
from jarvis.voz import chamado, deepgram

log = logging.getLogger(__name__)
DIAGNOSTICO = lugares.ESTADO / "diagnostico.md"  # o último diagnóstico, para rever na página


def linhas_do_registro() -> list[str] | None:
    """As últimas linhas do serviço no journal, sem segredos; None sem acesso ao journal."""
    try:
        r = subprocess.run(
            ["/usr/bin/journalctl", "--user", "-u", "zervis", "-n", "3000", "-o", "short-iso",
             "--no-pager"],
            capture_output=True, text=True, timeout=10, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    return [
        atividade.VALOR_SECRETO.sub("•••", x)
        for x in r.stdout.splitlines()
        if not x.startswith("-- ")
    ]


MOTORES = [
    {"id": "contas", "nome": "Automático", "detalhe": "Usa as contas dos agentes.", "modelo": ""},
    {"id": "codex", "nome": "Codex", "detalhe": "Conta do Codex.", "modelo": ""},
    {
        "id": "plano",
        "nome": "Claude pelo plano",
        "detalhe": "Assinatura do Claude, sem chave.",
        "modelo": "claude-sonnet-5-5",
    },
    {
        "id": "openai",
        "nome": "OpenAI",
        "detalhe": "Chave de API da OpenAI.",
        "modelo": "gpt-5.4-mini",
    },
    {
        "id": "anthropic",
        "nome": "Anthropic",
        "detalhe": "Chave de API da Anthropic.",
        "modelo": "claude-haiku-4-5-20251001",
    },
    {
        "id": "openrouter",
        "nome": "OpenRouter",
        "detalhe": "Uma chave para muitos modelos.",
        "modelo": "openai/gpt-5.4-mini",
    },
    {
        "id": "ponte",
        "nome": "Ponte",
        "detalhe": "Qualquer serviço no formato OpenAI.",
        "modelo": "",
    },
    {
        "id": "omniroute",
        "nome": "OmniRoute",
        "detalhe": "A conexão do OmniRoute configurada no Cérebro.",
        "modelo": "",
    },
]


# Os agentes de cada camada (ADR 0015). Marca: "Claude", nunca "Claude Code".
AGENTES = [
    {"id": "claude", "nome": "Claude", "disponivel": True},
    {"id": "codex", "nome": "Codex", "disponivel": True},
    {"id": "omniroute", "nome": "OmniRoute", "disponivel": True},
]
AGENTES_SESSOES = [
    {"id": "claude", "nome": "Claude", "disponivel": True},
    {"id": "codex", "nome": "Codex", "disponivel": True},
]


def catalogo_provedor(agente: str) -> str:
    """O agente da tela no catálogo de cérebros: o OmniRoute é a opção "auto"."""
    return {"omniroute": "auto"}.get(agente, agente)


def _latencia_de_hoje(pasta: Path, dia: str) -> list[dict[str, Any]]:
    try:
        resumo = json.loads((pasta / f"{dia}-resumo.json").read_text())
    except (OSError, ValueError):
        return []
    grupos = []
    for g in resumo.get("grupos", []):
        etapas = g.get("etapas", {})
        if "total" not in etapas and "cerebro" not in etapas:
            continue
        grupos.append(
            {
                "origem": g.get("origem"),
                "provedor": g.get("provedor") or g.get("rota"),
                "turnos": g.get("turnos"),
                "cerebro_ms": (etapas.get("cerebro") or {}).get("mediana_ms"),
                "total_ms": (etapas.get("total") or {}).get("mediana_ms"),
            }
        )
    return grupos


class Acoes:
    """Lê e muda o núcleo; `nucleo` é o `jarvis.nucleo.laco.Nucleo` (tipado solto de propósito)."""

    def __init__(self, nucleo: Any, pasta_latencias: Path, pasta_teste: Path) -> None:
        self.n = nucleo
        self.pasta_latencias = pasta_latencias
        self.pasta_teste = pasta_teste
        self.conectores_pendentes = False  # mudou algo nos conectores e ainda não aplicou

    def leituras(self) -> dict[str, Leitura]:
        return {
            "estado": self.estado,
            "conversa": self.conversa,
            "remoto": self.remoto,
            "atividade": self.atividade,
            "configuracao": self.configuracao,
            "contas": self.contas,
            "inicio": self.inicio,
            "cerebro": self.cerebro,
            "escuta": self.escuta,
            "skills": self.skills,
            "memoria": self.memoria,
            "automacoes": self.automacoes,
            "foco": self.foco,
            "sessoes": self.sessoes,
            "pastas": self.pastas,
            "conectores": self.conectores,
        }

    def escritas(self) -> dict[str, Escrita]:
        return {
            "cerebro": self.mudar_cerebro,
            "fala/modo": self.mudar_modo_fala,
            "escuta/modo": self.mudar_escuta,
            "voz/token": self.token_voz,
            "voz/apertar": self.apertar,
            "voz/soltar": self.soltar,
            "voz/chamado": self.mudar_chamado,
            "remoto/ativar": self.ativar_remoto,
            "voz/evento": self.evento_voz,
            "atividade/registro": self.registro_tecnico,
            "ze/melhorias": self.melhorias,
            "ze/diagnosticar": self.diagnosticar,
            "ze/manutencao": self.manutencao,
            "conversa/escrever": self.escrever,
            "ze/diagnostico": self.diagnostico,
            "ze/sessao": self.sessao_de_melhorias,
            "ze/aplicar": self.aplicar_melhorias,
            "ze/descartar": self.descartar_melhorias,
            "acesso/senha": self.definir_senha,
            "acesso/encerrar": self.encerrar_acessos,
            "acesso/desconectar": self.desconectar_aparelho,
            "acesso/codigo/preparar": self.preparar_codigo,
            "acesso/codigo/confirmar": self.confirmar_codigo,
            "acesso/codigo/desligar": self.desligar_codigo,
            "remoto/desativar": self.desativar_remoto,
            "tunel/ativar": self.ativar_tunel,
            "tunel/desativar": self.desativar_tunel,
            "painel/vendo": self.painel_vendo,
            "chave": self.guardar_chave,
            "chave/apagar": self.apagar_chave,
            "testar": self.testar,
            "escuta/chave": self.guardar_chave_escuta,
            "escuta/apagar": self.apagar_chave_escuta,
            "escuta/testar": self.testar_chave_escuta,
            "perfil": self.salvar_perfil,
            "acesso/chave": self.guardar_chave_claude,
            "acesso/remover": self.remover_acesso,
            "acesso/testar": self.testar_acesso,
            "conta/adicionar": self.adicionar_conta,
            "conta/remover": self.remover_conta,
            "conta/usar": self.usar_conta,
            "conta/entrar": self.entrar_conta,
            "sessao/criar": self.criar_sessao,
            "sessao/ler": self.ler_sessao,
            "sessao/trocar": self.trocar_sessao,
            "terminal/abrir": self.abrir_terminal,
            "terminal/ler": self.ler_terminal,
            "terminal/escrever": self.escrever_terminal,
            "terminal/tamanho": self.tamanho_terminal,
            "terminal/fechar": self.fechar_terminal,
            "sessao/arquivo": self.criar_arquivo,
            "sessao/arquivos": self.arquivos,
            "sessao/ver": self.ver_arquivo,
            "sessao/buscar": self.buscar_arquivos,
            "skill/ver": self.ver_skill,
            "skill/salvar": self.salvar_skill,
            "conector/salvar": self.salvar_conector,
            "conector/remover": self.remover_conector,
            "conector/ligar": self.ligar_conector,
            "conector/segredo": self.segredo_conector,
            "conector/testar": self.testar_conector,
            "conectores/aplicar": self.aplicar_conectores,
            "foco/acao": self.acao_no_foco,
            "automacao/ativar": self.ativar_automacao,
            "automacao/remover": self.remover_automacao,
            "memoria/mudar": self.mudar_memoria,
            "sugestao/decidir": self.decidir_sugestao,
            "skill/ligar": self.ligar_skill,
            "skill/excluir": self.excluir_skill,
            "sessao/excluir": self.excluir_sessao,
            "cerebro/escolher": self.escolher_cerebro,
            "cerebro/modelo": self.modelo_do_cerebro,
            "omniroute/salvar": self.salvar_omniroute,
        }

    def envios(self) -> dict[str, Any]:
        return {"sessao/anexo": self.anexar}

    # --- leituras ------------------------------------------------------------------------

    def _via(self) -> dict[str, Any]:
        return rapido.efetiva(self.n.cfg["via_rapida"])

    def estado(self) -> dict[str, Any]:
        from jarvis.memoria.linha import agora

        via = self._via()
        cerebro = self.n.cerebro
        return {
            "ze": self.n.maquina.estado.value,
            "cerebro": {"provedor": self.n.provedor, "modelo": getattr(cerebro, "modelo", "")},
            "via_rapida": {
                "ativa": isinstance(cerebro, rapido.Roteado),
                "motor": via["motor"],
                "modelo": via["modelo"],
            },
            "consumo": self.n.consumo.resumo_falado(),
            "latencia": _latencia_de_hoje(self.pasta_latencias, agora().date().isoformat()),
            "foco": self.n.foco.onde_estava(),
            "tela_ts": self._tela_ts(),
            "modo_fala": self.n.modo_fala,
            "escuta": {"modo": self.n.modo_escuta, "janela": self.n.tem_janela},
            "chamado": self.n.chamado,
            "voz_remota": {"conectada": self.n._fonte is not None},
            "manutencao": {
                "ligada": self.n.manutencao.ligado,
                "aguardando": self.n._aplicar_depois is not None,
            },
            "tela": self.n.ultimo_na_tela,  # [quando, texto]: o painel mostra no Silencioso
            "inicio": os.getpid(),  # muda a cada reinício: o painel recarrega sozinho
        }

    def mudar_modo_fala(self, dados: dict[str, Any]) -> dict[str, Any]:
        modo = str(dados.get("modo", ""))
        if modo not in modo_fala.MODOS:
            raise PedidoInvalido("modo de fala desconhecido")
        return {"modo": modo, "aviso": self.n.mudar_modo_fala(modo)}

    def mudar_escuta(self, dados: dict[str, Any]) -> dict[str, Any]:
        modo = str(dados.get("modo", ""))
        if modo not in modo_escuta.MODOS:
            raise PedidoInvalido("modo de escuta desconhecido")
        try:
            aviso = self.n.mudar_escuta(modo)
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {"modo": modo, "aviso": aviso}

    def remoto(self) -> dict[str, Any]:
        return dict(self.n.estado_remoto())

    def ativar_remoto(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            aviso = self.n.ativar_remoto()
        except remoto.RemotoErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.remoto(), "aviso": aviso}

    def ativar_tunel(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            aviso = self.n.ativar_tunel()
        except remoto.RemotoErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.remoto(), "aviso": aviso}

    def desativar_tunel(self, dados: dict[str, Any]) -> dict[str, Any]:
        return {**self.remoto(), "aviso": self.n.desativar_tunel()}

    def desativar_remoto(self, dados: dict[str, Any]) -> dict[str, Any]:
        return {**self.remoto(), "aviso": self.n.desativar_remoto()}

    def definir_senha(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A senha de quem entra de outro aparelho; trocá-la encerra os acessos."""
        try:
            self.n.acesso.definir(str(dados.get("senha", "")))
        except SenhaErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.remoto(), "aviso": "Senha salva."}

    def desconectar_aparelho(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.acesso.desconectar_por_id(str(dados.get("id", "")))
        except SenhaErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.remoto(), "aviso": "Aparelho desconectado."}

    def preparar_codigo(self, dados: dict[str, Any]) -> dict[str, Any]:
        """A semente nova do autenticador: QR para ler e a chave para digitar."""
        endereco = self.n.acesso.preparar_codigo(usuario.PERFIL.nome)
        qr = segno.make(endereco, error="m").svg_inline(
            scale=4, dark="#070c11", light="#ffffff", border=2
        )
        chave = self.n.acesso.semente_pendente
        return {"qr": qr, "chave": " ".join(chave[i : i + 4] for i in range(0, len(chave), 4))}

    def confirmar_codigo(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            self.n.acesso.confirmar_codigo(str(dados.get("codigo", "")))
        except SenhaErro as erro:
            raise PedidoInvalido(str(erro)) from erro
        return {**self.remoto(), "aviso": "Verificação em duas etapas ligada."}

    def desligar_codigo(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.acesso.desligar_codigo()
        if self.n.tunel.ativo:
            self.n.desativar_tunel()  # na internet aberta, só com o código
        return {**self.remoto(), "aviso": "Verificação em duas etapas desligada."}

    def encerrar_acessos(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.acesso.sair_todos()
        return {**self.remoto(), "aviso": "Acessos encerrados."}

    def melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O que a sessão de melhorias do Zé tem pronto para aprovar (ADR 0026)."""
        return dict(self.n.manutencao.mudancas())

    def sessao_de_melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        return {"id": self._chamar(lambda: self.n.manutencao.abrir_sessao())}

    def aplicar_melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        atividade.PADRAO.origem = "painel"
        return {"aviso": self.n.aplicar_melhorias(revisado=bool(dados.get("revisei")))}

    def conversa(self) -> dict[str, Any]:
        """O fio de hoje com o Zé: o que a pessoa disse ou escreveu, as respostas e os avisos."""
        from jarvis.memoria.linha import agora

        hoje = agora()
        itens: list[dict[str, str]] = []
        for t in self.n.conversas.do_dia(hoje.date()):
            quando = t.em.isoformat(timespec="seconds")
            itens.append({"quando": quando, "tipo": "voce", "texto": t.gabriel})
            if t.ze:
                itens.append({"quando": quando, "tipo": "ze", "texto": t.ze})
        inicio = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
        for ev in self.n.linha.entre(inicio, hoje, {"aviso", "lembrete", "manutencao"}):
            # Um lembrete é gravado ao ser criado, com a hora em que vai tocar.
            momento = max(ev.quando, ev.registrado)
            if momento <= hoje:
                itens.append(
                    {
                        "quando": momento.isoformat(timespec="seconds"),
                        "tipo": "aviso",
                        "texto": ev.texto,
                    }
                )
        itens.sort(key=lambda i: i["quando"])  # estável: o pedido antes da resposta
        fila = getattr(self.n, "fila", None)
        esperando = [a.titulo or a.texto for a in fila.validos()] if fila is not None else []
        return {"itens": itens[-200:], "esperando": esperando}

    def escrever(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Um pedido escrito no painel: o mesmo caminho da fala."""
        return {"aviso": self.n.escrever(str(dados.get("texto", "")))}

    def manutencao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Entra ou sai do estado de manutenção (ADR 0028)."""
        atividade.PADRAO.origem = "painel"
        return {"aviso": self.n.mudar_manutencao(bool(dados.get("ligar")))}

    def descartar_melhorias(self, dados: dict[str, Any]) -> dict[str, Any]:
        atividade.PADRAO.origem = "painel"
        aviso = self.n.manutencao.descartar()
        return {**self.n.manutencao.mudancas(), "aviso": aviso}

    def atividade(self) -> dict[str, Any]:
        """O que o Zé fez e onde tropeçou (ADR 0025), do mais recente ao mais antigo."""
        return {"itens": atividade.PADRAO.listar(300), "resumo": atividade.PADRAO.resumo()}

    def registro_tecnico(self, dados: dict[str, Any]) -> dict[str, Any]:
        """As últimas linhas do registro do serviço, sem segredos; `nivel`: erros, avisos, tudo.
        O nível sai do texto da linha: o journal guarda tudo o que o Zé escreve num nível só."""
        marcas = {
            "erros": ("ERROR", "CRITICAL", "Traceback"),
            "avisos": ("WARNING", "ERROR", "CRITICAL", "Traceback"),
        }
        linhas = linhas_do_registro()
        if linhas is None:
            return {"linhas": [], "aviso": "Registro do sistema indisponível."}
        if filtro := marcas.get(str(dados.get("nivel", ""))):
            linhas = [x for x in linhas if any(m in x for m in filtro)]
        return {"linhas": linhas[-400:]}

    def diagnosticar(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O relatório do que deu errado vai para a sessão de melhorias (ADR 0025 e 0026)."""
        relatorio, aviso = self.n.diagnosticar(linhas_do_registro() or [])
        return {"relatorio": relatorio, "aviso": aviso}

    def diagnostico(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"relatorio": DIAGNOSTICO.read_text()}
        except OSError:
            return {"relatorio": ""}

    def evento_voz(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O que aconteceu na voz do navegador (conectou, caiu, erro de microfone): só para o
        registro, para diagnosticar o celular; nunca áudio nem credenciais."""
        evento = str(dados.get("evento", ""))[:40]
        detalhe = " ".join(str(dados.get("detalhe", "")).split())[:300]
        aparelho = str(dados.get("aparelho", ""))[:120]
        nivel = logging.INFO if evento in ("conectou", "desligou", "encerrada") else logging.WARNING
        log.log(nivel, "voz do navegador: %s %s (%s)", evento, detalhe, aparelho)
        if evento in ("falhou", "microfone"):
            atividade.PADRAO.registrar(
                "falha", "A voz do navegador falhou", erro=detalhe, aparelho=aparelho
            )
        return {}

    def apertar(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Botão de falar apertado: abre o pedido, como o "Ei Zé"."""
        try:
            self.n.apertar()
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        return {}

    def soltar(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.soltar()
        return {}

    def mudar_chamado(self, dados: dict[str, Any]) -> dict[str, Any]:
        modo = str(dados.get("modo", ""))
        if modo not in chamado.MODOS:
            raise PedidoInvalido("ativação desconhecida")
        return {"modo": modo, "aviso": self.n.mudar_chamado(modo)}

    def token_voz(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Entrar na sala da voz remota pelo navegador (token curto, só microfone)."""
        try:
            return dict(self.n.token_voz_remota())
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from erro

    def painel_vendo(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O painel está com esta sessão aberta e à vista: o Zé não fala o que ela já mostra."""
        self.n.ver_sessao(str(dados.get("sessao", ""))[:40])
        return {}

    def _tela_ts(self) -> float:
        """Quando o Zé mandou algo para o modo imersivo pela última vez (o painel abre a aba)."""
        try:
            pasta: Path = self.n.cfg.caminho("barehands", "pasta_estado")
            return float((pasta / "tela-comando.json").stat().st_mtime)
        except (OSError, KeyError):
            return 0.0

    def cerebro(self) -> dict[str, Any]:
        via = self._via()
        return {
            "via": {k: via[k] for k in rapido.AJUSTAVEIS},
            "ativa": isinstance(self.n.cerebro, rapido.Roteado),
            "motores": MOTORES,
            # Os motores com lista de modelos (com a versão), como no cérebro; os outros têm
            # modelos demais para listar e ficam com o campo livre.
            "listas": {
                motor: [{"id": m["id"], "nome": m["nome"]} for m in lista]
                for motor, lista in (
                    ("plano", modelos.do_cerebro("claude")),
                    ("codex", modelos.do_cerebro("codex")),
                    ("anthropic", modelos.CLAUDE),
                    ("omniroute", [{"id": r, "nome": r} for r in self.n.modelos_do_omniroute()]),
                )
            },
            "chaves": {
                m["id"]: rapido.situacao_da_chave(
                    m["id"], via["arquivo_chave"] if m["id"] == via["motor"] else ""
                )
                for m in MOTORES
            },
            "completo": self._completo(),
            # Cérebro e sessões de código usam as contas cadastradas (ADR 0020).
            "agentes": AGENTES,
            "sessoes": {"agentes": AGENTES_SESSOES, "total": len(self.n.sessoes.listar())},
        }

    def _completo(self) -> dict[str, Any]:
        """O cérebro em uso para a tela: o agente, o modelo e a lista de modelos dele."""
        c, provedor = self.n.cfg["cerebro"], self.n.provedor
        omni = {
            "endereco": c["omniroute_endereco"],
            "tem_chave": bool(self.n._chave_do_omniroute()),
        }
        if provedor == "auto":
            rotas = self.n.modelos_do_omniroute()
            return {
                "provedor": "omniroute",
                "modelo": c["omniroute_rota"],
                "modelos": [{"id": r, "nome": r} for r in rotas],
                "omniroute": omni,
            }
        lista = modelos.do_cerebro(provedor) if provedor in ("claude", "codex") else []
        return {
            "provedor": provedor,
            "modelo": c["modelo_codex" if provedor == "codex" else "modelo"],
            "modelos": [{"id": m["id"], "nome": m["nome"]} for m in lista],
            "omniroute": omni,
        }

    def salvar_omniroute(self, dados: dict[str, Any]) -> dict[str, Any]:
        chave = str(dados.get("chave", "")).strip() or None  # vazio: mantém a chave salva
        try:
            aviso = self.n.configurar_omniroute(str(dados.get("endereco", "")), chave)
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.cerebro(), "aviso": aviso}

    def modelo_do_cerebro(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            aviso = self.n.mudar_modelo_do_cerebro(
                str(dados.get("agente", "")), str(dados.get("modelo", ""))
            )
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.cerebro(), "aviso": aviso}

    def escolher_cerebro(self, dados: dict[str, Any]) -> dict[str, Any]:
        agente = str(dados.get("agente", ""))
        if agente not in ("claude", "codex", "omniroute"):
            raise PedidoInvalido("Agente desconhecido.")
        aviso = self.n.trocar_cerebro(catalogo_provedor(agente))
        return {**self.cerebro(), "aviso": aviso}

    def skills(self) -> list[dict[str, Any]]:
        sk = self.n.skills
        uso = sk.uso()
        ligadas = [
            {
                "nome": nome,
                "descricao": descricao,
                "ligada": True,
                "usos": (uso.get(nome) or {}).get("usos", 0),
            }
            for nome, descricao in sk.listar()
        ]
        desligadas = []
        for nome in sk.arquivadas():
            arquivo = sk.pasta / ".arquivo" / nome / "SKILL.md"
            with contextlib.suppress(OSError):
                descricao = frente(arquivo.read_text()).get("description", "")
                desligadas.append(
                    {"nome": nome, "descricao": descricao, "ligada": False, "usos": 0}
                )
        return sorted(ligadas + desligadas, key=lambda k: k["nome"])

    def memoria(self) -> dict[str, Any]:
        m = self.n.memoria
        return {
            "usuario": m.entradas("usuario"),
            "jarvis": m.entradas("jarvis"),
            "limites": dict(m.limites),
            # O que o Zé aprendeu sozinho numa conversa e espera a pessoa (memória e skill).
            "sugestoes": [revisao.resumo_dict(p) for p in self.n.pendencias.listar()],
        }

    def decidir_sugestao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Aprovar ou descartar uma sugestão pelo painel: o mesmo caminho da voz."""
        id_, aprovar = str(dados.get("id", "")), bool(dados.get("aprovar"))
        try:
            proposta = self.n.pendencias.tirar(id_)
        except KeyError:
            raise PedidoInvalido("Sugestão não encontrada.") from None
        if aprovar:
            self._chamar(lambda: revisao.aplicar(proposta, self.n.memoria, self.n.skills))
            self.n.diario.registrar(
                "aprovada",
                proposta.resumo,
                origem=proposta.origem,
                sugerida=round(proposta.criada),
                **revisao.alvo_da_proposta(proposta),
            )
        else:
            self.n.diario.registrar("descartada", proposta.resumo, origem=proposta.origem)
        return {**self.memoria(), "aviso": "Aprovada." if aprovar else "Descartada."}

    def automacoes(self) -> list[dict[str, Any]]:
        return [
            {
                "id": j.id,
                "nome": j.nome,
                "tipo": j.tipo,
                "agenda": j.agenda,
                "proxima": j.proxima,
                "ativo": j.ativo,
                "ultimo_status": j.ultimo_status,
            }
            for j in self.n.jobs.listar()
        ]

    def foco(self) -> dict[str, Any]:
        return dict(self.n.foco.quadro())

    # --- mudanças ------------------------------------------------------------------------

    def mudar_cerebro(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            rapido.gravar_escolha(dados)
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        aviso = self.n.aplicar_via_rapida()
        return {**self.cerebro(), "aviso": aviso}

    def guardar_chave(self, dados: dict[str, Any]) -> dict[str, Any]:
        motor, chave = str(dados.get("motor", "")), str(dados.get("chave", ""))
        try:
            rapido.gravar_chave(motor, chave)
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        aviso = self.n.aplicar_via_rapida() if motor == self._via()["motor"] else ""
        return {**self.cerebro(), "aviso": aviso}

    def apagar_chave(self, dados: dict[str, Any]) -> dict[str, Any]:
        motor = str(dados.get("motor", ""))
        try:
            rapido.apagar_chave(motor)
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        aviso = self.n.aplicar_via_rapida() if motor == self._via()["motor"] else ""
        return {**self.cerebro(), "aviso": aviso}

    def testar(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Mede um motor com os dados da tela, ainda sem salvar."""
        try:
            escolha = rapido.validar_escolha({k: v for k, v in dados.items() if k != "ligada"})
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        via = {**self._via(), **escolha}
        if via["motor"] != self._via()["motor"]:
            via["arquivo_chave"] = ""
        try:
            motor = rapido.criar_motor(via, self.pasta_teste)
        except rapido.MotorErro as erro:
            raise PedidoInvalido(str(erro)) from None
        if motor is None:
            return {"ok": False, "erro": "falta a chave deste motor"}
        persona = self.n.persona_rapida()
        return asyncio.run(rapido.medir(motor, persona))

    # --- escuta (Deepgram) ---------------------------------------------------------------------

    def escuta(self) -> dict[str, Any]:
        dg = self.n.deepgram
        ativacao = getattr(self.n.modelo_ativacao, "treinada", True)
        return {"deepgram": dg.situacao(), "cadastro": deepgram.CADASTRO, "ativacao": ativacao}

    def guardar_chave_escuta(self, dados: dict[str, Any]) -> dict[str, Any]:
        chave = str(dados.get("chave", "")).strip()
        try:
            deepgram.gravar_chave(self.n.deepgram.arquivo_chave, chave)
        except ValueError as erro:
            raise PedidoInvalido(str(erro)) from None
        self.n.aplicar_escuta()
        ok, mensagem = deepgram.conferir(chave)
        aviso = "Chave salva." if ok else f"Chave salva. {mensagem}"
        return {**self.escuta(), "aviso": aviso, "valida": ok}

    def apagar_chave_escuta(self, dados: dict[str, Any]) -> dict[str, Any]:
        self.n.deepgram.arquivo_chave.unlink(missing_ok=True)
        self.n.aplicar_escuta()
        return {**self.escuta(), "aviso": "Chave removida."}

    def testar_chave_escuta(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Confere a chave colada (ou, sem ela, a guardada) direto no Deepgram."""
        chave = str(dados.get("chave", "")).strip() or (self.n.deepgram.chave or "")
        if not chave:
            return {"ok": False, "mensagem": "Informe a chave."}
        ok, mensagem = deepgram.conferir(chave)
        return {"ok": ok, "mensagem": mensagem}

    # --- configuração da primeira vez: perfil e acesso ao Claude ----------------------------------

    def configuracao(self) -> dict[str, Any]:
        p = usuario.ler()
        return {
            "feita": usuario.existe(),
            "perfil": {"nome": p.nome, "sobre": p.sobre, "fuso": p.fuso},
            "fuso_sistema": fuso.do_sistema().key,
            "fusos": fuso.nomes(),
            "acesso": acesso.situacao(),
            "agentes": acesso.agentes(),
            "chave_anthropic": "https://console.anthropic.com/settings/keys",
        }

    def salvar_perfil(self, dados: dict[str, Any]) -> dict[str, Any]:
        nome = str(dados.get("nome", "")).strip()
        sobre = str(dados.get("sobre", "")).strip()
        zona = str(dados.get("fuso", "")).strip()
        if len(nome) > 60:
            raise PedidoInvalido("Nome com mais de 60 caracteres.")
        if len(sobre) > 2000:
            raise PedidoInvalido("Texto com mais de 2.000 caracteres.")
        if zona and not fuso.valido(zona):
            raise PedidoInvalido("Fuso horário inválido.")
        antes = fuso.local().key
        perfil = usuario.Perfil(nome, sobre, zona)
        usuario.gravar(perfil)
        aviso = self.n.aplicar_perfil(perfil) or "Perfil salvo."
        if fuso.local().key != antes:
            aviso += " O fuso horário vale a partir do próximo início."
        return {**self.configuracao(), "aviso": aviso}

    def _acesso(self, aviso: str) -> dict[str, Any]:
        return {
            "acesso": acesso.situacao(),
            "agentes": acesso.agentes(),
            "aviso": self.n.aplicar_acesso() or aviso,
        }

    def guardar_chave_claude(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            rapido.gravar_chave("anthropic", str(dados.get("chave", "")))
        except rapido.MotorErro:
            raise PedidoInvalido("Informe a chave.") from None
        return self._acesso("Chave salva.")

    def remover_acesso(self, dados: dict[str, Any]) -> dict[str, Any]:
        rapido.apagar_chave("anthropic")
        return self._acesso("Chave removida.")

    def testar_acesso(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Uma pergunta mínima ao provedor escolhido com o acesso salvo."""
        if self.n.provedor == "auto":
            ok, mensagem = self.n.testar_omniroute()
            return {"ok": ok, "mensagem": mensagem}
        if self.n.provedor == "codex":
            from jarvis.cerebro.codex import testar

            ok, mensagem = asyncio.run(
                testar(self.n.cfg["cerebro"]["modelo_codex"], self.pasta_teste / "codex")
            )
            return {"ok": ok, "mensagem": mensagem}
        if not acesso.situacao()["metodo"]:
            return {"ok": False, "mensagem": "Acesso não configurado."}
        modelo = self.n.cfg["cerebro"]["modelo"]
        self.pasta_teste.mkdir(parents=True, exist_ok=True, mode=0o700)
        ok, mensagem = asyncio.run(acesso.testar(modelo, self.pasta_teste))
        return {"ok": ok, "mensagem": mensagem}

    # --- contas dos agentes (ADR 0016) ---------------------------------------------------------

    def contas(self) -> dict[str, Any]:
        cs = contas.Contas()
        instalados = {a["id"]: a["instalado"] for a in acesso.agentes()}
        return {
            "agentes": [
                {
                    "id": agente,
                    "nome": nome,
                    "instalado": instalados.get(agente, False),
                    "em_uso": cs.em_uso(agente).id,
                    "contas": [
                        {
                            "id": c.id,
                            "nome": c.nome,
                            "padrao": not c.pasta,
                            "comando": " ".join(c.comando_login()[1:]),
                            **contas.quem(c),
                        }
                        for c in cs.listar(agente)
                    ],
                }
                for agente, nome in contas.NOMES.items()
            ]
        }

    def adicionar_conta(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            c = contas.Contas().adicionar(str(dados.get("agente", "")), str(dados.get("nome", "")))
        except (contas.ContaErro, OSError) as erro:
            raise PedidoInvalido(str(erro)) from None
        return {**self.contas(), "aviso": f"Conta {c.nome} criada. Entre nela para usar."}

    def remover_conta(self, dados: dict[str, Any]) -> dict[str, Any]:
        cs = contas.Contas()
        try:
            conta = cs.achar(str(dados.get("id", "")))
            em_uso = cs.em_uso(conta.agente).id == conta.id
            cs.remover(conta.id)
        except contas.ContaErro as erro:
            raise PedidoInvalido(str(erro)) from None
        if em_uso:
            self.n.aplicar_acesso()
        return {**self.contas(), "aviso": "Conta removida."}

    def usar_conta(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            conta = contas.Contas().usar(str(dados.get("id", "")))
        except contas.ContaErro as erro:
            raise PedidoInvalido(str(erro)) from None
        aviso = self.n.aplicar_acesso()
        return {**self.contas(), "aviso": aviso or f"Usando a conta {conta.nome}."}

    def entrar_conta(self, dados: dict[str, Any]) -> dict[str, Any]:
        try:
            conta = contas.Contas().achar(str(dados.get("id", "")))
        except contas.ContaErro as erro:
            raise PedidoInvalido(str(erro)) from None
        if contas.abrir_login(conta):
            return {"aberto": True, "aviso": "Terminal aberto. Faça o login e volte aqui."}
        return {"aberto": False, "aviso": "Sem terminal: rode o comando mostrado."}

    # --- sessões da oficina (docs/plano-oficina.md) -------------------------------------------

    @staticmethod
    def _nome_da_conta(id_: str) -> str:
        try:
            return contas.Contas().achar(id_).nome if id_ else ""
        except contas.ContaErro:
            return ""

    def _sessao(self, s: Sessao) -> dict[str, Any]:
        return {
            "id": s.id,
            "nome": s.nome,
            "pasta": s.pasta.replace(str(Path.home()), "~", 1),
            "motor": s.motor,
            "agente": contas.NOMES.get(s.motor, s.motor),
            "conta": self._nome_da_conta(s.conta),
            "modelo": s.modelo,
            "esforco": s.esforco,
            "isolada": s.isolada,
            "branch": s.branch,
            "melhorias": s.origem == "manutencao" and bool(s.worktree),  # a sessão do Zé
            "estado": "trabalhando" if s.id in self.n.sessoes.trabalhando() else s.estado,
            "conta_id": s.conta,
            "limite": s.limite,
            "resumo": s.resumo,
            "atualizada": s.atualizada,
        }

    def sessoes(self) -> list[dict[str, Any]]:
        # A sessão do Zé (melhorias) mora na página Melhorias, não junto dos projetos.
        return [self._sessao(s) for s in self.n.sessoes.listar() if s.origem != "manutencao"]

    def pastas(self) -> list[str]:
        """Sugestões para uma sessão nova: as pastas de projetos que existem nesta máquina."""
        raizes = [self.n.cfg.caminho("oficina", "raiz_projetos"), Path.home() / "Work"]
        raizes += [Path.home() / n for n in ("DESENVOLVIMENTO", "Projetos", "projetos", "code")]
        achadas: list[str] = []
        for raiz in raizes:
            if raiz.is_dir():
                achadas += sorted(
                    str(p).replace(str(Path.home()), "~", 1)
                    for p in raiz.iterdir()
                    if p.is_dir() and not p.name.startswith(".")
                )
        return achadas[:200]

    def _chamar(self, fazer: Any) -> Any:
        try:
            return fazer()
        except (
            SessaoErro,
            arquivos.ArquivoErro,
            SkillErro,
            McpInvalido,
            JobErro,
            MemoriaErro,
        ) as erro:
            raise PedidoInvalido(str(erro)) from None

    def _onde(self, dados: dict[str, Any]) -> Path:
        return Path(self._chamar(lambda: self.n.sessoes.ler(str(dados.get("id", "")))).onde)

    def arquivos(self, dados: dict[str, Any]) -> dict[str, Any]:
        onde = self._onde(dados)
        pasta = str(dados.get("pasta", ""))
        return {"pasta": pasta, "itens": self._chamar(lambda: arquivos.listar(onde, pasta))}

    def ver_arquivo(self, dados: dict[str, Any]) -> dict[str, Any]:
        onde = self._onde(dados)
        return dict(self._chamar(lambda: arquivos.ler(onde, str(dados.get("caminho", "")))))

    def buscar_arquivos(self, dados: dict[str, Any]) -> dict[str, Any]:
        onde = self._onde(dados)
        modo = "conteudo" if dados.get("modo") == "conteudo" else "nomes"
        achados = arquivos.buscar(onde, str(dados.get("termo", "")), modo)
        return {"modo": modo, "achados": achados}

    def criar_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        pasta = str(dados.get("pasta", ""))
        if dados.get("novo"):
            projeto = str(dados.get("projeto") or dados.get("nome") or "")
            pasta = str(self._chamar(lambda: self.n.sessoes.criar_projeto(projeto)))
        s = self._chamar(
            lambda: self.n.sessoes.criar(
                str(dados.get("nome", "")),
                pasta,
                str(dados.get("motor", "claude")),
                str(dados.get("modelo", "")),
                bool(dados.get("isolada", False)),
            )
        )
        return self._sessao(s)

    def ler_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        id_ = str(dados.get("id", ""))
        desde = max(0, int(dados.get("desde", 0) or 0))
        s = self._chamar(lambda: self.n.sessoes.ler(id_))
        return {"sessao": self._sessao(s), "mensagens": self.n.sessoes.mensagens(id_, desde)}

    def anexar(self, corpo: bytes, consulta: dict[str, str]) -> dict[str, Any]:
        nome = self._chamar(
            lambda: self.n.sessoes.anexar(consulta.get("id", ""), consulta.get("nome", ""), corpo)
        )
        return {
            "anexo": nome,
            "caminho": str(self.n.sessoes.pasta_de_anexos(consulta.get("id", "")) / nome),
        }

    def criar_arquivo(self, dados: dict[str, Any]) -> dict[str, Any]:
        relativo = self._chamar(
            lambda: self.n.sessoes.criar_arquivo(
                str(dados.get("id", "")),
                str(dados.get("nome", "")),
                str(dados.get("conteudo", "")),
                bool(dados.get("sobrescrever", False)),
            )
        )
        return {"arquivo": relativo}

    def trocar_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Troca agente ou conta; com `continuar`, manda de novo o pedido que bateu no limite."""
        id_ = str(dados.get("id", ""))
        s, aviso = self._chamar(
            lambda: self.n.sessoes.trocar(
                id_, str(dados.get("motor", "")), str(dados.get("conta", ""))
            )
        )
        if dados.get("continuar") and s.ultimo_pedido:
            s = self._chamar(lambda: self.n.sessoes.continuar(id_))
            aviso += " Continuando o pedido."
        return {**self._sessao(s), "aviso": aviso}

    # --- o terminal real de cada sessão (ADR 0017) -------------------------------------------

    def abrir_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        id_ = str(dados.get("id", ""))
        t = self._chamar(
            lambda: self.n.sessoes.abrir_terminal(
                id_, colunas=int(dados.get("colunas", 120)), linhas=int(dados.get("linhas", 32))
            )
        )
        t.redimensionar(int(dados.get("colunas", 120)), int(dados.get("linhas", 32)))
        return {"posicao": t.inicio, "vivo": t.vivo}

    def ler_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Long-poll: espera até 20 s por saída nova a partir de `desde`."""
        t = self.n.sessoes.terminais.get(str(dados.get("id", "")))
        desde = int(dados.get("desde", 0))
        if t is None:
            return {"posicao": desde, "dados": "", "vivo": False}
        posicao, saida, vivo = t.ler(desde, float(dados.get("espera", 20)))
        return {"posicao": posicao, "dados": base64.b64encode(saida).decode(), "vivo": vivo}

    def escrever_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        t = self.n.sessoes.terminais.get(str(dados.get("id", "")))
        if t is None or not t.vivo:
            raise PedidoInvalido("o terminal desta sessão está fechado")
        t.escrever(str(dados.get("dados", "")).encode())
        return {}

    def tamanho_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        t = self.n.sessoes.terminais.get(str(dados.get("id", "")))
        if t is not None:
            t.redimensionar(int(dados.get("colunas", 120)), int(dados.get("linhas", 32)))
        return {}

    def fechar_terminal(self, dados: dict[str, Any]) -> dict[str, Any]:
        t = self.n.sessoes.terminais.pop(str(dados.get("id", "")), None)
        if t is not None:
            t.encerrar()
        return {"aviso": "Terminal fechado. A conversa continua ao reabrir."}

    # --- skills do jeito do usuário ----------------------------------------------------------

    def ver_skill(self, dados: dict[str, Any]) -> dict[str, Any]:
        nome = str(dados.get("nome", ""))
        conteudo = self._chamar(lambda: self.n.skills.atual(nome))
        if not conteudo:
            raise PedidoInvalido("skill desconhecida")
        return {"nome": nome, "conteudo": conteudo}

    def salvar_skill(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O próprio usuário escreve: grava direto (a versão anterior vai para o histórico)."""
        nome, conteudo = str(dados.get("nome", "")).strip(), str(dados.get("conteudo", ""))
        skills = self.n.skills

        def validar() -> str:
            atual = skills.atual(nome)
            if atual:
                return str(skills.novo_conteudo(nome, antigo=atual, novo=conteudo))
            return str(skills.novo_conteudo(nome, conteudo))

        final = self._chamar(validar)
        skills.gravar(nome, final)
        return {"nome": nome, "skills": self.skills()}

    # --- conectores MCP -----------------------------------------------------------------------

    def conectores(self) -> dict[str, Any]:
        return {
            "conectores": self._chamar(conectores.listar),
            "pendente": self.conectores_pendentes,
        }

    def aplicar_conectores(self, _dados: dict[str, Any]) -> dict[str, Any]:
        aviso = self.n.recarregar_conectores()
        self.conectores_pendentes = False
        return {**self.conectores(), "aviso": aviso}

    def salvar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        nome = str(dados.get("nome", "")).strip()
        self._chamar(lambda: conectores.salvar(nome, dados))
        self.conectores_pendentes = True
        return self.conectores()

    def remover_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        self._chamar(lambda: conectores.remover(str(dados.get("nome", ""))))
        self.conectores_pendentes = True
        return self.conectores()

    def ligar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        self._chamar(
            lambda: conectores.ligar(str(dados.get("nome", "")), bool(dados.get("ligado")))
        )
        self.conectores_pendentes = True
        return self.conectores()

    def segredo_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        self._chamar(
            lambda: conectores.gravar_segredo(
                str(dados.get("nome", "")),
                str(dados.get("variavel", "")),
                str(dados.get("valor", "")),
            )
        )
        self.conectores_pendentes = True
        return self.conectores()

    def testar_conector(self, dados: dict[str, Any]) -> dict[str, Any]:
        return dict(self._chamar(lambda: conectores.testar(str(dados.get("nome", "")))))

    # --- a tela de início e as ações que faltavam (o redesenho de 09/10/2026) ------------------

    def inicio(self) -> dict[str, Any]:
        from jarvis.memoria.linha import agora

        hoje = self.n.consumo.retrato()
        lido = sum(int(hoje.get(k) or 0) for k in ("entrada", "cache_lido", "cache_criado"))
        totais = [
            g["total_ms"]
            for g in _latencia_de_hoje(self.pasta_latencias, agora().date().isoformat())
            if g.get("origem") == "voz" and g.get("total_ms")
        ]
        trabalhando = set(self.n.sessoes.trabalhando())
        sessoes = self.n.sessoes.listar()
        proximas = sorted(
            (j for j in self.n.jobs.listar() if j.ativo and j.proxima), key=lambda j: j.proxima
        )[:3]
        atual = self.n.foco.atual()
        return {
            "ze": self.n.maquina.estado.value,
            "foco": {"titulo": atual.titulo, "passo": atual.proximo_passo} if atual else None,
            "sessoes": {
                "total": len(sessoes),
                "trabalhando": [s.nome for s in sessoes if s.id in trabalhando],
            },
            "proximas": [{"nome": j.nome, "quando": j.proxima} for j in proximas],
            "hoje": {
                "respostas": int(hoje.get("respostas") or 0) + int(hoje.get("locais") or 0),
                "tokens_mil": round(lido / 1000),
                "voz_s": round(min(totais) / 1000, 1) if totais else None,
            },
        }

    def acao_no_foco(self, dados: dict[str, Any]) -> dict[str, Any]:
        from jarvis.foco.frentes import FocoErro

        foco, id_, acao = self.n.foco, str(dados.get("id", "")), str(dados.get("acao", ""))
        try:
            f = foco.por_id(id_)
            if acao == "passo":
                foco.passo_feito(f.id)
            elif acao == "concluir":
                foco.concluir(f.id)
            elif acao == "pausar":
                foco.atualizar(f.id, estado="pausada")
            elif acao == "focar":
                foco.focar(f.id)
            elif acao == "descartar":
                foco.atualizar(f.id, estado="descartada")
            elif acao == "passo_novo":
                foco.atualizar(f.id, proximo_passo=str(dados.get("texto", "")))
            else:
                raise PedidoInvalido("ação desconhecida")
        except FocoErro as erro:
            raise PedidoInvalido(str(erro)) from None
        return self.foco()

    def ativar_automacao(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        from jarvis.memoria.linha import agora

        id_ = str(dados.get("id", ""))
        if dados.get("ativo"):
            self._chamar(lambda: self.n.jobs.retomar(id_, agora()))
        else:
            self._chamar(lambda: self.n.jobs.pausar(id_))
        return self.automacoes()

    def remover_automacao(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        self._chamar(lambda: self.n.jobs.remover(str(dados.get("id", ""))))
        return self.automacoes()

    def mudar_memoria(self, dados: dict[str, Any]) -> dict[str, Any]:
        """O próprio usuário adiciona ou tira uma entrada: vale na próxima conversa."""
        acao, alvo, texto = (str(dados.get(k, "")) for k in ("acao", "alvo", "texto"))
        if acao not in ("adicionar", "remover") or alvo not in ("usuario", "jarvis"):
            raise PedidoInvalido("pedido inválido")
        mudanca = (
            Mudanca(acao, alvo, texto=texto)
            if acao == "adicionar"
            else Mudanca(acao, alvo, antigo=texto)
        )
        self._chamar(lambda: self.n.memoria.aplicar(mudanca))
        return self.memoria()

    def ligar_skill(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        self._chamar(
            lambda: self.n.skills.ligar(str(dados.get("nome", "")), bool(dados.get("ligada")))
        )
        return self.skills()

    def excluir_skill(self, dados: dict[str, Any]) -> list[dict[str, Any]]:
        self._chamar(lambda: self.n.skills.excluir(str(dados.get("nome", ""))))
        return self.skills()

    def excluir_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        aviso = self._chamar(lambda: self.n.sessoes.excluir(str(dados.get("id", ""))))
        return {"aviso": aviso, "sessoes": self.sessoes()}
