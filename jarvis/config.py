"""Configuração do `jarvisd`: padrões + `~/.config/zervis/config.toml`, validados na carga.

Erro de config = mensagem clara e o serviço não sobe meio configurado (docs/06-qualidade.md):
seção ou chave desconhecida, tipo errado ou versão diferente param a carga. Segredos nunca
ficam aqui; vêm do ambiente do serviço.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jarvis import lugares

VERSAO = 1
CAMINHO = lugares.CONFIG / "config.toml"

PADRAO: dict[str, dict[str, Any]] = {
    "presenca": {"classe_janela": "chrome-127.0.0.1__stage.html-Default"},
    "audio": {"microfone": "omarchy_mic_fx"},
    "ativacao": {
        # "Ei Zé" / "Hey Zé", treinado com a voz de quem usa (voz/treino_ativacao.py); sem o
        # modelo treinado, o Zé atende pelo teclado e pelo painel.
        "modelo": str(lugares.DADOS / "ativacao/ei_ze.npz"),
        "modelos_onnx": str(lugares.DADOS / "modelos"),
        "paciencia": 3,
    },
    # conversa_s: quanto tempo a conversa espera a próxima pergunta antes de encerrar sozinha.
    # registrar_texto: diagnóstico; põe o que foi transcrito no log. Desligado por padrão.
    "escuta": {
        "fim_silencio_s": 3.0,
        "limiar_vad": 0.35,
        "conversa_s": 8.0,
        "registrar_texto": False,
        # Smart Turn: fecha o pedido pela entonação antes dos fim_silencio_s (0 desliga).
        "limiar_fim_de_turno": 0.7,
        # Pausa que o Smart Turn espera antes de opinar (mais curta = responde antes e corta mais).
        "pausa_fim_de_turno_s": 0.64,
        # Escuta só pelo Deepgram (streaming, ADR 0012; decisão de 09/10/2026): sem a chave, a
        # voz fica desligada. A chave fica num arquivo fora do repositório (600).
        "chave_deepgram": str(lugares.CONFIG / "deepgram.key"),
    },
    # pasta_jarvis: as notas que o JARVIS escreve sobre si (memória, skills, automações,
    # aprendizado, consumo) para a bolha "JARVIS" do Barehands; só leitura para o usuário.
    # desenvolvedor: o modo imersivo mostra medidores de CPU, GPU, baterias dos modelos e tokens.
    "barehands": {
        "pasta_estado": str(lugares.DADOS / "imersivo/state"),
        "pasta_jarvis": str(lugares.DADOS / "pasta"),
        "desenvolvedor": False,
        # O que o Zé mostra no modo imersivo (orbe Acervo): imagens/ e 3d/.
        "pasta_acervo": str(lugares.DADOS / "acervo"),
    },
    # motor: "piper" (Cadu pelo Piper, dentro do processo; ADR 0013). Outros motores entram aqui.
    "voz": {"motor": "piper"},
    # Ações do Omarchy forçadas a um nível (docs/07): "update" pede senha num terminal e, por voz,
    # travaria; vai para proibido (faz-se pelo menu do Omarchy).
    "sistema": {"proibidos": ["update"], "confirmar": [], "livres": []},
    # raiz_projetos: onde nasce um projeto novo criado por voz (só criar, nunca apagar).
    "oficina": {"raiz_projetos": "~/projetos"},
    # Limites rígidos da memória curta (caracteres): cheia, o cérebro consolida antes de gravar.
    # Skills: uma pasta por skill com SKILL.md (padrão agentskills.io); pôr a pasta ali já basta.
    # arquivar_apos_dias: curadoria; skill sem uso há tanto tempo sai do catálogo para
    # `.arquivo/` (nada se perde). 0 desliga.
    "skills": {"pasta": str(lugares.DADOS / "skills"), "arquivar_apos_dias": 30.0},
    # Revisão em segundo plano (ADR 0011): só no fim de conversa com correção ou longa.
    "revisao": {
        "ligada": True,
        "modelo": "claude-haiku-4-5-20251001",
        "max_por_dia": 8,
        "pensamento_tokens": 1500,  # 0 desliga (mais barato, aprende pior; ADR 0011)
        "pendencias": str(lugares.DADOS / "pendencias.json"),
    },
    "memoria": {
        "pasta": str(lugares.DADOS / "memoria"),
        "limite_usuario": 2000,
        "limite_jarvis": 2500,
    },
    # ferramentas: embutidas do Claude Code; cada uso pede aprovação falada.
    # tempo_limite_s: espera máxima pelo começo da resposta; depois disso, aviso de falha.
    # omniroute_*: o mesmo cérebro pelo gateway local (ADR 0008). A chave vem de
    # OMNIROUTER_API_KEY ou do arquivo indicado, lida só no uso; nunca fica aqui.
    # reserva: provedor usado se o OmniRoute estiver parado ou sem chave (com aviso no log).
    # provedor é só o ponto de partida: a troca por voz ou no Barehands fica gravada no estado.
    "cerebro": {
        "provedor": "claude",
        "modelo": "claude-sonnet-5-5",
        "ferramentas": ["WebSearch", "WebFetch"],
        "tempo_limite_s": 30.0,
        # Conversa parada há tanto tempo recomeça do zero (a memória fica): o histórico longo é
        # relido a cada turno e gasta a cota. 0 desliga.
        "nova_conversa_apos_min": 30.0,
        "omniroute_endereco": "http://127.0.0.1:20128",
        "omniroute_rota": "auto/subscription",
        "omniroute_arquivo_chave": str(lugares.CONFIG / "omniroute.key"),
        # Só leitura: as cotas que o OmniRoute guarda de cada conta (baterias, ADR 0010).
        "omniroute_banco": "~/.config/omniroute/storage.sqlite",
        "reserva": "claude",
    },
    # Via rápida (docs/plano-voz-rapida.md, 09/10/2026): a conversa simples vai a um motor
    # rápido com a persona enxuta; o que precisa de ferramenta segue para o cérebro acima.
    # motor: plano (Claude pela assinatura), anthropic, openai, openrouter ou ponte (qualquer
    # proxy no formato OpenAI; endereco obrigatório). A chave vem de arquivo_chave (chmod 600)
    # ou da variável do motor (ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY,
    # JARVIS_PONTE_API_KEY); nunca desta config. raciocinio: só para GPT-5 e série "o".
    # espera_s: sem a primeira palavra nesse tempo, o pedido vai ao cérebro completo.
    "via_rapida": {
        "ligada": True,
        "motor": "plano",
        "modelo": "claude-sonnet-5-5",
        "endereco": "",
        "arquivo_chave": "",
        "raciocinio": "low",
        "max_tokens": 300,
        "espera_s": 3.0,
        "historico": 12,
    },
}
PROVEDORES = {"eco", "claude", "omniroute"}  # Codex na Fase 8
RESERVAS = {"eco", "claude"}
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class ConfigInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    secoes: dict[str, dict[str, Any]]

    def __getitem__(self, secao: str) -> dict[str, Any]:
        return self.secoes[secao]

    def caminho(self, secao: str, chave: str) -> Path:
        return Path(str(self.secoes[secao][chave])).expanduser()


def validar(dados: dict[str, Any], origem: str) -> Config:
    versao = dados.pop("versao", VERSAO)
    if versao != VERSAO:
        raise ConfigInvalida(f"{origem}: versao {versao!r}, esperado {VERSAO}")
    secoes = {nome: dict(valores) for nome, valores in PADRAO.items()}
    for nome, valores in dados.items():
        if nome not in PADRAO:
            raise ConfigInvalida(f"{origem}: seção desconhecida [{nome}]")
        if not isinstance(valores, dict):
            raise ConfigInvalida(f"{origem}: [{nome}] precisa ser uma seção")
        for chave, valor in valores.items():
            if chave not in PADRAO[nome]:
                raise ConfigInvalida(f"{origem}: chave desconhecida {nome}.{chave}")
            esperado = type(PADRAO[nome][chave])
            if esperado is float and isinstance(valor, int) and not isinstance(valor, bool):
                valor = float(valor)
            if esperado is list and not (
                isinstance(valor, list) and all(isinstance(v, str) for v in valor)
            ):
                raise ConfigInvalida(f"{origem}: {nome}.{chave} precisa ser lista de textos")
            if type(valor) is not esperado:
                raise ConfigInvalida(
                    f"{origem}: {nome}.{chave} precisa ser {esperado.__name__}, "
                    f"veio {type(valor).__name__}"
                )
            secoes[nome][chave] = valor
    cerebro = secoes["cerebro"]
    if cerebro["provedor"] not in PROVEDORES:
        raise ConfigInvalida(
            f"{origem}: cerebro.provedor deve ser um de {sorted(PROVEDORES)} nesta fase"
        )
    if secoes["via_rapida"]["motor"] not in ("plano", "anthropic", "openai", "openrouter", "ponte"):
        raise ConfigInvalida(
            f"{origem}: via_rapida.motor deve ser plano, anthropic, openai, openrouter ou ponte"
        )
    if secoes["via_rapida"]["motor"] == "ponte" and not secoes["via_rapida"]["endereco"]:
        raise ConfigInvalida(f"{origem}: via_rapida.endereco é obrigatório na ponte")
    if secoes["voz"]["motor"] != "piper":
        raise ConfigInvalida(f"{origem}: voz.motor deve ser piper")
    if cerebro["reserva"] not in RESERVAS:
        raise ConfigInvalida(f"{origem}: cerebro.reserva deve ser um de {sorted(RESERVAS)}")
    if cerebro["tempo_limite_s"] <= 0:
        raise ConfigInvalida(f"{origem}: cerebro.tempo_limite_s precisa ser positivo")
    endereco = urlsplit(cerebro["omniroute_endereco"])
    if endereco.scheme != "http" or endereco.hostname not in LOOPBACK:
        raise ConfigInvalida(
            f"{origem}: cerebro.omniroute_endereco precisa ser http em loopback (ADR 0008)"
        )
    return Config(secoes)


def carregar(caminho: Path = CAMINHO) -> Config:
    if not caminho.exists():
        return validar({}, "padrão")
    try:
        dados = tomllib.loads(caminho.read_text())
    except tomllib.TOMLDecodeError as erro:
        raise ConfigInvalida(f"{caminho}: TOML inválido: {erro}") from None
    return validar(dados, str(caminho))
