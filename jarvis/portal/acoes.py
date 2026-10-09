"""O que o painel lê e muda no núcleo (docs/plano-painel.md).

Só leitura do que já existe (skills, memória, automações, Foco, consumo) e, na fatia 1, as
mudanças da via rápida: motor, modelo, chave e o teste de tempo. A regra continua no núcleo;
aqui só se traduz para a tela.
"""

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Any

from jarvis.automacoes.jobs import JobErro
from jarvis.cerebro import conectores, rapido
from jarvis.cerebro.mcp_externo import McpInvalido
from jarvis.habilidades.skills import SkillErro, frente
from jarvis.memoria.curta import MemoriaErro, Mudanca
from jarvis.oficina import arquivos
from jarvis.oficina.sessoes import Sessao, SessaoErro
from jarvis.portal.servidor import Escrita, Leitura, PedidoInvalido

MOTORES = [
    {
        "id": "plano",
        "nome": "Claude pelo plano",
        "detalhe": "A sua assinatura do Claude. Sem chave; ~1 s até a primeira palavra.",
        "modelo": "claude-sonnet-5-5",
    },
    {
        "id": "openai",
        "nome": "OpenAI",
        "detalhe": "Chave de API. O mais rápido, como no Ligatia.",
        "modelo": "gpt-5.4-mini",
    },
    {
        "id": "anthropic",
        "nome": "Anthropic",
        "detalhe": "Chave de API do Claude, direto, sem o programa intermediário.",
        "modelo": "claude-haiku-4-5",
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
        "detalhe": "Qualquer proxy no formato OpenAI (OmniRoute, LiteLLM...).",
        "modelo": "",
    },
]


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
            "inicio": self.inicio,
            "cerebro": self.cerebro,
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
            "chave": self.guardar_chave,
            "chave/apagar": self.apagar_chave,
            "testar": self.testar,
            "sessao/criar": self.criar_sessao,
            "sessao/ler": self.ler_sessao,
            "sessao/enviar": self.enviar_a_sessao,
            "sessao/parar": self.parar_sessao,
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
            "skill/ligar": self.ligar_skill,
            "skill/excluir": self.excluir_skill,
            "sessao/excluir": self.excluir_sessao,
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
        }

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
            "chaves": {
                m["id"]: rapido.situacao_da_chave(
                    m["id"], via["arquivo_chave"] if m["id"] == via["motor"] else ""
                )
                for m in MOTORES
            },
            "completo": {
                "provedor": self.n.provedor,
                "modelo": getattr(self.n.cerebro, "modelo", ""),
            },
        }

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
        }

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

    # --- sessões da oficina (docs/plano-oficina.md) -------------------------------------------

    def _sessao(self, s: Sessao) -> dict[str, Any]:
        return {
            "id": s.id,
            "nome": s.nome,
            "pasta": s.pasta.replace(str(Path.home()), "~", 1),
            "motor": s.motor,
            "modelo": s.modelo,
            "isolada": s.isolada,
            "branch": s.branch,
            "estado": "trabalhando" if s.id in self.n.sessoes.trabalhando() else s.estado,
            "resumo": s.resumo,
            "atualizada": s.atualizada,
        }

    def sessoes(self) -> list[dict[str, Any]]:
        return [self._sessao(s) for s in self.n.sessoes.listar()]

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

    def enviar_a_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        anexos = dados.get("anexos") or []
        if not isinstance(anexos, list) or len(anexos) > 10:
            raise PedidoInvalido("no máximo dez anexos por mensagem")
        s = self._chamar(
            lambda: self.n.sessoes.enviar(
                str(dados.get("id", "")),
                str(dados.get("texto", "")),
                anexos=[str(a) for a in anexos],
            )
        )
        return self._sessao(s)

    def anexar(self, corpo: bytes, consulta: dict[str, str]) -> dict[str, Any]:
        nome = self._chamar(
            lambda: self.n.sessoes.anexar(consulta.get("id", ""), consulta.get("nome", ""), corpo)
        )
        return {"anexo": nome}

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

    def parar_sessao(self, dados: dict[str, Any]) -> dict[str, Any]:
        return self._sessao(self._chamar(lambda: self.n.sessoes.parar(str(dados.get("id", "")))))

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
