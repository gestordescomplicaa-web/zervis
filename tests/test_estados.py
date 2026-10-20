"""Máquina de estados: as cinco invariantes do docs/04-arquitetura.md e o ciclo do pedido."""

import pytest

from jarvis.nucleo import estados
from jarvis.nucleo.estados import (
    NAO_ENTENDI,
    PRAZO_CONFIRMACAO_S,
    AbrirMicrofone,
    Ativacao,
    Aviso,
    Bip,
    Comando,
    CortarFala,
    Digitado,
    EnviarAoCerebro,
    Estado,
    Evento,
    FalaOcioso,
    Falar,
    FecharMicrofone,
    FimDeFala,
    Frase,
    InterromperCerebro,
    Maquina,
    PedidoAprovacao,
    Presenca,
    ResponderAprovacao,
    RespostaFim,
    ReterAviso,
    Silencio,
    Tempo,
    comando,
)

TODOS_OS_EVENTOS: list[Evento] = [
    Ativacao(),
    FimDeFala("abre o navegador"),
    Digitado("abre o navegador"),
    Silencio(),
    Frase("Olá."),
    RespostaFim(),
    FalaOcioso(),
    PedidoAprovacao("Abaixar o volume."),
    Tempo(),
]


def estado(m: Maquina) -> Estado:
    """Lido por função: asserts seguidos sobre `m.estado` confundem o estreitamento do mypy."""
    return m.estado


def ativa() -> Maquina:
    m = Maquina()
    m.tratar(Presenca(True), 0)
    return m


def pensando(pedido: str = "teste") -> Maquina:
    m = ativa()
    m.tratar(Ativacao(), 1)
    m.tratar(FimDeFala(pedido), 2)
    return m


def test_ciclo_hey_orca_teste() -> None:
    m = ativa()
    assert m.tratar(Ativacao(), 1) == [Bip()]
    assert estado(m) is Estado.OUVINDO
    assert m.tratar(FimDeFala("teste"), 2) == [EnviarAoCerebro("teste")]
    assert estado(m) is Estado.PENSANDO
    assert m.tratar(Frase("Você disse: teste."), 3) == [Falar("Você disse: teste.")]
    assert estado(m) is Estado.FALANDO
    m.tratar(RespostaFim(), 3)
    assert estado(m) is Estado.FALANDO  # ainda falando a última frase
    m.tratar(FalaOcioso(), 4)
    assert estado(m) is Estado.OUVINDO  # conversa: segue ouvindo sem "Ei Zé"
    assert m.tratar(FimDeFala("Ok."), 6) == [Bip()]
    assert estado(m) is Estado.ATIVO
    assert m.historico == [
        Estado.ATIVO,
        Estado.OUVINDO,
        Estado.PENSANDO,
        Estado.FALANDO,
        Estado.OUVINDO,
        Estado.ATIVO,
    ]


# --- invariante 1 ---------------------------------------------------------------------


@pytest.mark.parametrize("evento", TODOS_OS_EVENTOS)
def test_inativo_nao_abre_microfone_nem_fala(evento: Evento) -> None:
    m = Maquina()
    assert m.tratar(evento, 0) == []
    assert estado(m) is Estado.INATIVO
    assert not m.microfone_aberto
    assert not m.detector_ligado
    assert not m.transcrevendo


def test_aviso_em_inativo_fica_retido() -> None:
    assert Maquina().tratar(Aviso("Bateria fraca."), 0) == [ReterAviso("Bateria fraca.")]


@pytest.mark.parametrize(
    "preparar",
    [ativa, lambda: pensando(), lambda: _falando(), lambda: _confirmando()],
    ids=["ativo", "pensando", "falando", "confirmando"],
)
def test_fechar_a_janela_corta_tudo_de_qualquer_estado(preparar: object) -> None:
    m = preparar()  # type: ignore[operator]
    efeitos = m.tratar(Presenca(False), 10)
    assert CortarFala() in efeitos
    assert FecharMicrofone() in efeitos
    assert estado(m) is Estado.INATIVO
    assert not m.microfone_aberto
    if Estado.CONFIRMANDO in m.historico:
        assert ResponderAprovacao(aprovado=False) in efeitos


def test_abrir_a_janela_abre_o_microfone_uma_vez() -> None:
    m = Maquina()
    assert m.tratar(Presenca(True), 0) == [AbrirMicrofone()]
    assert m.tratar(Presenca(True), 1) == []
    assert m.microfone_aberto


# --- invariante 2 ---------------------------------------------------------------------


@pytest.mark.parametrize("preparar", [ativa, lambda: pensando(), lambda: _falando()])
def test_fala_sem_ativacao_nao_vira_pedido(preparar: object) -> None:
    m = preparar()  # type: ignore[operator]
    antes = m.estado
    assert m.tratar(FimDeFala("apaga tudo"), 5) == []
    assert estado(m) is antes


def test_um_pedido_consome_a_autorizacao_ate_a_resposta() -> None:
    m = pensando()
    assert not m.autorizado
    assert m.tratar(FimDeFala("outro pedido"), 3) == []  # enquanto pensa, nada novo entra
    m.tratar(Frase("Ok."), 3)
    assert m.tratar(FimDeFala("outro pedido"), 3) == []  # nem enquanto fala
    m.tratar(RespostaFim(), 3)
    m.tratar(FalaOcioso(), 4)
    assert m.autorizado  # só a resposta concede a próxima pergunta


# --- conversa contínua (ADR 0009) -----------------------------------------------------


def _respondido() -> Maquina:
    m = pensando("que horas são?")
    m.tratar(Frase("São três horas."), 3)
    m.tratar(RespostaFim(), 3)
    m.tratar(FalaOcioso(), 4)
    return m


def test_pergunta_seguinte_dispensa_hey_orca() -> None:
    m = _respondido()
    assert m.transcrevendo
    assert m.tratar(FimDeFala("E amanhã chove?"), 5) == [EnviarAoCerebro("E amanhã chove?")]


@pytest.mark.parametrize("fala", ["Ok.", "OK", "Okay!", "ok, obrigado", "Okey, valeu."])
def test_ok_encerra_a_conversa(fala: str) -> None:
    m = _respondido()
    assert m.tratar(FimDeFala(fala), 5) == [Bip()]
    assert estado(m) is Estado.ATIVO
    assert m.tratar(FimDeFala("mais um pedido"), 6) == []


def test_ok_no_meio_da_frase_e_pedido() -> None:
    m = _respondido()
    assert m.tratar(FimDeFala("ok, abre o navegador"), 5) == [
        EnviarAoCerebro("ok, abre o navegador")
    ]


def test_silencio_na_conversa_encerra() -> None:
    m = _respondido()
    assert m.prazo == 4 + m.prazo_conversa_s
    m.tratar(Silencio(), 13)
    assert estado(m) is Estado.ATIVO
    assert m.tratar(FimDeFala("atrasado"), 14) == []


def test_aviso_nao_abre_conversa() -> None:
    m = ativa()
    m.tratar(Aviso("Reunião em dez minutos."), 1)
    m.tratar(FalaOcioso(), 2)
    assert estado(m) is Estado.ATIVO
    assert m.tratar(FimDeFala("abre o navegador"), 3) == []


def test_aviso_de_maos_livres_abre_a_escuta_sem_o_chamado() -> None:
    m = ativa()
    m.tratar(Aviso("A sessão Loja terminou.", escutar=True), 1)
    assert m.tratar(FalaOcioso(), 2) == [Bip()]
    assert estado(m) is Estado.OUVINDO and m.em_conversa and m.autorizado


def test_aviso_de_maos_livres_retido_volta_como_aviso_comum() -> None:
    m = pensando()
    assert m.tratar(Aviso("A sessão Loja terminou.", escutar=True), 1) == [
        ReterAviso("A sessão Loja terminou.")
    ]


def test_fechar_a_janela_encerra_a_conversa() -> None:
    m = _respondido()
    m.tratar(Presenca(False), 5)
    m.tratar(Presenca(True), 6)
    assert estado(m) is Estado.ATIVO
    assert not m.em_conversa
    assert m.tratar(FimDeFala("pedido"), 7) == []


def test_pedido_vazio_consome_a_autorizacao_e_avisa() -> None:
    m = ativa()
    m.tratar(Ativacao(), 1)
    assert m.tratar(FimDeFala("ã"), 2) == [Falar(NAO_ENTENDI)]
    assert not m.autorizado


def test_silencio_depois_da_ativacao_volta_sem_pedido() -> None:
    m = ativa()
    m.tratar(Ativacao(), 1)
    m.tratar(Silencio(), 21)
    assert estado(m) is Estado.ATIVO
    assert m.tratar(FimDeFala("atrasado"), 22) == []


# --- invariante 3 ---------------------------------------------------------------------


def _falando() -> Maquina:
    m = pensando()
    m.tratar(Frase("Resposta longa."), 3)
    return m


def test_falando_nao_transcreve_mas_detector_escuta() -> None:
    m = _falando()
    assert not m.transcrevendo
    assert m.detector_ligado


def test_hey_orca_falando_interrompe_e_abre_pedido_novo() -> None:
    m = _falando()
    assert m.tratar(Ativacao(), 4) == [CortarFala(), InterromperCerebro(), Bip()]
    assert estado(m) is Estado.OUVINDO
    assert m.tratar(Frase("resto da resposta antiga"), 5) == []
    assert m.tratar(FimDeFala("novo pedido"), 6) == [EnviarAoCerebro("novo pedido")]


@pytest.mark.parametrize(
    "fala", ["Para.", "Pare!", "Interromper.", "Cancela.", "Para de falar.", "Silêncio, Jarvis."]
)
def test_hey_orca_e_ordem_de_parar_interrompem_sem_ir_ao_cerebro(fala: str) -> None:
    m = _falando()
    assert InterromperCerebro() in m.tratar(Ativacao(), 4)
    assert m.tratar(FimDeFala(fala), 5) == [Bip()]
    assert estado(m) is Estado.ATIVO
    assert not m.em_conversa


@pytest.mark.parametrize("fala", ["para que serve isso", "cancela a reunião de amanhã"])
def test_parar_dentro_de_um_pedido_vai_ao_cerebro(fala: str) -> None:
    m = _falando()
    m.tratar(Ativacao(), 4)
    assert m.tratar(FimDeFala(fala), 5) == [EnviarAoCerebro(fala)]


def test_ouvindo_transcreve_e_desliga_o_detector() -> None:
    m = ativa()
    m.tratar(Ativacao(), 1)
    assert m.transcrevendo
    assert not m.detector_ligado


# --- invariante 4 ---------------------------------------------------------------------


def _confirmando() -> Maquina:
    m = pensando("abaixa o volume")
    m.tratar(PedidoAprovacao("Vou abaixar o volume."), 3)
    return m


def test_pergunta_de_confirmacao_nao_e_transcrita_ate_terminar() -> None:
    m = _confirmando()
    assert estado(m) is Estado.CONFIRMANDO
    assert not m.transcrevendo
    assert m.tratar(FimDeFala("sim"), 4) == []  # o eco da própria pergunta não aprova
    assert m.tratar(FalaOcioso(), 5) == [Bip()]
    assert m.transcrevendo


@pytest.mark.parametrize(
    ("resposta", "aprovado"),
    [
        ("Sim.", True),
        ("sim, pode", True),
        ("Pode mandar ver.", True),
        ("Pode mandar para o Codex.", True),
        ("Claro, beleza.", True),
        ("Bora!", True),
        ("Isso aí.", True),
        ("Não.", False),
        ("Melhor não.", False),
        ("Pode não.", False),
        ("Sim, mas troca o projeto para o Loja.", False),
        ("Espera um pouco.", False),
        ("Cancela.", False),
    ],
)
def test_confirmacao_entende_a_fala_natural(resposta: str, aprovado: bool) -> None:
    m = _confirmando()
    m.tratar(FalaOcioso(), 5)
    assert m.tratar(FimDeFala(resposta), 6) == [ResponderAprovacao(aprovado, resposta)]
    assert estado(m) is Estado.PENSANDO


def test_resposta_confusa_pergunta_de_novo_uma_vez_e_depois_nega() -> None:
    from jarvis.nucleo.estados import REPERGUNTA

    m = _confirmando()
    m.tratar(FalaOcioso(), 5)
    assert m.tratar(FimDeFala("simulação"), 6) == [Falar(REPERGUNTA)]
    assert m.tratar(FimDeFala("sim"), 7) == []  # eco da nova pergunta não aprova
    m.tratar(FalaOcioso(), 8)
    assert m.tratar(FimDeFala("talvez"), 9) == [ResponderAprovacao(False, "talvez")]


def test_confirmacao_sem_resposta_nega() -> None:
    m = _confirmando()
    m.tratar(FalaOcioso(), 5)
    assert m.tratar(Tempo(), 5 + PRAZO_CONFIRMACAO_S - 1) == []
    assert m.tratar(Tempo(), 5 + PRAZO_CONFIRMACAO_S) == [ResponderAprovacao(False)]


def test_confirmacao_com_silencio_nega() -> None:
    m = _confirmando()
    m.tratar(FalaOcioso(), 5)
    assert m.tratar(Silencio(), 10) == [ResponderAprovacao(False)]


def test_pedido_de_aprovacao_fora_de_um_pedido_e_negado() -> None:
    m = ativa()
    assert m.tratar(PedidoAprovacao("Apagar arquivos."), 1) == [ResponderAprovacao(False)]
    assert estado(m) is Estado.ATIVO


# --- invariante 5 ---------------------------------------------------------------------


def test_aviso_so_sai_em_ativo_sem_pedido() -> None:
    m = ativa()
    assert m.tratar(Aviso("Reunião em dez minutos."), 1) == [Falar("Reunião em dez minutos.")]
    m.tratar(FalaOcioso(), 2)
    m.tratar(Ativacao(), 3)
    assert m.tratar(Aviso("Outro aviso."), 4) == [ReterAviso("Outro aviso.")]
    m.tratar(FimDeFala("teste"), 5)
    assert m.tratar(Aviso("Mais um."), 6) == [ReterAviso("Mais um.")]


def test_pausa_entre_frases_volta_a_pensando_e_nao_a_ativo() -> None:
    m = _falando()
    m.tratar(FalaOcioso(), 4)  # a voz acabou a frase, mas o cérebro ainda gera
    assert estado(m) is Estado.PENSANDO
    assert m.tratar(Aviso("Aviso."), 5) == [ReterAviso("Aviso.")]


@pytest.mark.parametrize(
    "fala",
    ["Ok, ok.", "Okay, tá.", "Tá bom, obrigado.", "Valeu!", "Tchau.", "Chega.", "Pode parar."],
)
def test_variacoes_de_ok_encerram(fala: str) -> None:
    m = _respondido()
    assert m.tratar(FimDeFala(fala), 5) == [Bip()]
    assert estado(m) is Estado.ATIVO


@pytest.mark.parametrize("fala", ["tá bom", "isso", "obrigado pela ajuda com o código"])
def test_frases_que_nao_encerram(fala: str) -> None:
    m = _respondido()
    assert m.tratar(FimDeFala(fala), 5) == [EnviarAoCerebro(fala)]


def test_transcricao_vazia_na_continuacao_encerra_sem_laco() -> None:
    m = _respondido()
    assert m.tratar(FimDeFala(""), 5) == []
    assert estado(m) is Estado.ATIVO
    assert not m.em_conversa


def test_transcricao_vazia_logo_apos_hey_orca_fecha_com_bip() -> None:
    m = ativa()
    m.tratar(Ativacao(), 1)
    assert m.tratar(FimDeFala(""), 2) == [Bip()]
    assert estado(m) is Estado.ATIVO
    assert not m.autorizado


@pytest.mark.parametrize(
    ("fala", "nome"),
    [
        ("Nova conversa.", "nova_conversa"),
        ("Relatório de uso.", "relatorio_de_uso"),
        ("Como estão as baterias?", "relatorio_de_uso"),
        ("Muda para o GPT.", "trocar:gpt"),
        ("Troca pro G P T.", "trocar:gpt"),
        ("Usa o Gemini.", "trocar:gemini"),
        ("Volta para o Claude.", "trocar:claude"),
        ("Muda o cérebro para o automático.", "trocar:auto"),
        ("Passa pro Chat GPT agora.", "trocar:gpt"),
        ("Mostra o seu cérebro.", "mostrar_mapa"),
        ("Me mostra o cérebro!", "mostrar_mapa"),
        ("Abre o mapa do cérebro.", "mostrar_mapa"),
        ("Calibrar as mãos.", "calibrar_maos"),
        ("Calibra a minha mão!", "calibrar_maos"),
        ("Volta as mãos ao padrão.", "maos_padrao"),
        ("Restaura a calibração original.", "maos_padrao"),
        ("Aumenta o brilho da câmera.", "brilho_mais"),
        ("Liga o filtro da câmera.", "brilho_liga"),
        ("Desliga o brilho da câmera!", "brilho_desliga"),
        ("Diminui o brilho da câmera.", "brilho_menos"),
        ("Muda o tema para roxo.", "tema_roxo"),
        ("Volta o tema original.", "tema_original"),
        ("Tema azul marinho.", "tema_marinho"),
        ("Muda o tema para verde.", "tema_esmeralda"),
        ("Coloca o tema grafite.", "tema_grafite"),
        ("Usa o tema violeta.", "tema_roxo"),
        ("Abre as configurações.", "configuracoes"),
    ],
)
def test_comandos_de_console_nao_vao_ao_cerebro(fala: str, nome: str) -> None:
    m = ativa()
    m.tratar(Ativacao(), 1)
    assert m.tratar(FimDeFala(fala), 2) == [Comando(nome)]
    assert estado(m) is Estado.PENSANDO
    m.tratar(Frase("Certo."), 3)
    m.tratar(RespostaFim(), 3)
    m.tratar(FalaOcioso(), 4)
    assert estado(m) is Estado.OUVINDO  # a conversa continua depois do comando


@pytest.mark.parametrize(
    "fala",
    [
        "Muda para o modo escuro.",
        "Usa o Claude para revisar o código do projeto X.",
        "Mostra o mapa de Recife.",
        "Qual é o seu cérebro agora?",
    ],
)
def test_frases_parecidas_com_troca_vao_ao_cerebro(fala: str) -> None:
    from jarvis.nucleo.estados import comando

    assert comando(fala) is None


def test_aviso_cortado_por_hey_orca_volta_para_a_fila_sem_mexer_no_cerebro() -> None:
    from jarvis.nucleo.estados import ReterAviso

    m = ativa()
    assert m.tratar(Aviso("O Codex terminou: deu certo."), 1) == [
        Falar("O Codex terminou: deu certo.")
    ]
    efeitos = m.tratar(Ativacao(), 2)
    assert ReterAviso("O Codex terminou: deu certo.") in efeitos
    assert InterromperCerebro() not in efeitos  # o cérebro não estava respondendo
    assert estado(m) is Estado.OUVINDO


def test_aviso_falado_inteiro_nao_volta() -> None:
    m = ativa()
    m.tratar(Aviso("Pronto."), 1)
    m.tratar(FalaOcioso(), 2)
    assert estado(m) is Estado.ATIVO
    assert m.aviso_falando is None


@pytest.mark.parametrize("fala", ["Aumenta o brilho.", "Aumenta o brilho da tela."])
def test_brilho_sem_camera_nao_e_comando_local(fala: str) -> None:
    # O brilho da tela não é o filtro da câmera: segue para o cérebro.
    assert comando(fala) is None


@pytest.mark.parametrize(
    ("fala", "nome"),
    [
        ("Abre o núcleo.", "nucleo_abrir"),
        ("Abra o Núcleo.", "nucleo_abrir"),
        ("Fecha o núcleo.", "nucleo_fechar"),
        ("Fecha a janela do Zé.", "janela_fechar"),
        ("Desliga a câmera.", "janela_fechar"),
        ("Abra o GUIA do núcleo.", "abrir_orbe:Guia"),
        ("Abre o guia.", "abrir_orbe:Guia"),
        ("Abre a aba do Guia.", "abrir_orbe:Guia"),
        ("Me mostra o acervo do Núcleo.", "abrir_orbe:Acervo"),
        ("Abre o mapa do núcleo.", "abrir_orbe:Mapa"),
        ("Abre a memória do núcleo.", "abrir_item::memoria"),
        ("Abre o cérebro do núcleo.", "abrir_orbe:Mapa"),
        ("Fecha o guia.", "fechar_alvo:Guia"),
        ("Abre o Comece aqui do núcleo.", "abrir_item::comece aqui"),
        ("Abre o burrinho no Acervo.", "abrir_item:Acervo:burrinho"),
        ("Abra o arquivo burrinho do acervo.", "abrir_item:Acervo:burrinho"),
        ("Abre o porto do pé no acervo.", "abrir_item:Acervo:porto do pe"),
        ("Abre o burrinho do núcleo.", "abrir_item::burrinho"),
        ("Fecha o burrinho.", None),
        ("Abre o teclado.", "teclado_abrir"),
        ("Mostra o seu avatar.", "visual_avatar"),
        ("Volta o anel.", "visual_anel"),
        ("Volta para o anel.", "visual_anel"),
        ("Fecha o teclado.", "teclado_fechar"),
        ("Fecha seu cérebro.", "mapa_fechar"),
        ("Me mostra as sessões.", "mostrar_sessoes"),
        ("Mostra os lembretes.", "mostrar_automacoes"),
        ("Mostra suas memórias.", "mostrar_memoria"),
        ("Abre as conexões.", None),
    ],
)
def test_comandos_do_nucleo_nao_vao_ao_cerebro(fala: str, nome: str | None) -> None:
    assert comando(fala) == nome


@pytest.mark.parametrize(
    "fala", ["Abre o guia de viagem que te mandei.", "Abre o burrinho.", "Guia."]
)
def test_o_que_nao_e_um_orbe_conhecido_vai_ao_cerebro(fala: str) -> None:
    # Notas e outros nomes o cérebro resolve com tela_agir (e diz se não achar).
    assert comando(fala) is None


@pytest.mark.parametrize(
    ("fala", "nome"),
    [
        ("Aumenta o brilho.", "brilho_mais"),
        ("Diminui o brilho.", "brilho_menos"),
        ("Liga o brilho.", "brilho_liga"),
        ("Mais brilho.", "brilho_mais"),
    ],
)
def test_brilho_sem_alvo_e_do_nucleo_so_com_ele_em_foco(fala: str, nome: str) -> None:
    assert comando(fala, nucleo_em_foco=True) == nome
    assert comando(fala, nucleo_em_foco=False) is None  # o monitor: segue para o cérebro


def test_maquina_pergunta_ao_laco_se_o_nucleo_esta_em_foco() -> None:
    m = ativa()
    m.nucleo_em_foco = lambda: True
    m.tratar(Ativacao(), 1)
    assert m.tratar(FimDeFala("Aumenta o brilho."), 2) == [Comando("brilho_mais")]
    m2 = ativa()
    m2.tratar(Ativacao(), 1)
    assert m2.tratar(FimDeFala("Aumenta o brilho."), 2) == [EnviarAoCerebro("Aumenta o brilho.")]


# --- o Teclado do Núcleo ----------------------------------------------------------------


def test_escrito_e_pedido_sem_hey_orca_e_sem_abrir_conversa_por_voz() -> None:
    m = ativa()
    assert m.tratar(Digitado("qual a previsão do tempo"), 1) == [
        EnviarAoCerebro("qual a previsão do tempo")
    ]
    assert estado(m) is Estado.PENSANDO
    m.tratar(Frase("Sol."), 2)
    m.tratar(RespostaFim(), 2)
    m.tratar(FalaOcioso(), 3)
    assert estado(m) is Estado.ATIVO  # não fica ouvindo: quem escreveu não pediu conversa


def test_escrito_passa_pelos_comandos_locais() -> None:
    assert ativa().tratar(Digitado("Abra o Guia do núcleo"), 1) == [Comando("abrir_orbe:Guia")]


def test_escrito_no_meio_da_resposta_corta_e_vale_o_novo() -> None:
    m = pensando("conta uma história")
    m.tratar(Frase("Era uma vez."), 3)
    assert m.tratar(Digitado("para e me diz as horas"), 4) == [
        CortarFala(),
        InterromperCerebro(),
        EnviarAoCerebro("para e me diz as horas"),
    ]
    assert estado(m) is Estado.PENSANDO


@pytest.mark.parametrize(("texto", "aprovado"), [("sim", True), ("não", False), ("pode", True)])
def test_escrito_responde_a_confirmacao_mesmo_durante_a_pergunta(
    texto: str, aprovado: bool
) -> None:
    m = _confirmando()  # a pergunta ainda está sendo falada
    assert m.tratar(Digitado(texto), 4) == [CortarFala(), ResponderAprovacao(aprovado, texto)]
    assert estado(m) is Estado.PENSANDO


def test_escrito_vazio_ou_inativo_nao_faz_nada() -> None:
    assert ativa().tratar(Digitado("?"), 1) == []
    assert Maquina().tratar(Digitado("abre o navegador"), 1) == []


def test_os_orbes_falados_vem_do_manifesto() -> None:
    from jarvis.rosto import manifesto

    orbes = manifesto.falados(
        (
            manifesto.Orbe("orca", "Orca", "orca", ("oficina", "agentes de código")),
            manifesto.Orbe("identidade", "Identidade", "notes", ("quem você é",)),
        )
    )
    assert comando("Abre o Orca.", orbes=orbes) == "abrir_orbe:Orca"
    assert comando("Abre a oficina.", orbes=orbes) == "abrir_orbe:Orca"
    assert comando("Abre os agentes de código.", orbes=orbes) == "abrir_orbe:Orca"
    assert comando("Abre as skills na identidade.", orbes=orbes) == "abrir_item:Identidade:skills"
    assert comando("Abre o guia.", orbes=orbes) is None  # fora do manifesto, fica com o cérebro


def test_o_nome_ze_vale_nos_comandos_locais() -> None:
    assert estados.comando("Zé, abre o guia.") == estados.comando("Abre o guia.")
    assert estados.comando("Ei Zé, abre o guia.") == estados.comando("Abre o guia.")
    assert estados.comando("Reinicia o Zé.") == "reiniciar"
    assert estados.comando("Zé, entre no modo manutenção.") == "manutencao_entrar"
    assert estados.comando("Jarvis, entre no modo manutenção.") == "manutencao_entrar"
    assert estados.comando("Zé.") is None


@pytest.mark.parametrize(
    "fala",
    [
        "Dê uma voltinha.",
        "Zé, dá uma voltinha pra mim.",
        "Faz um giro.",
        "Gira aí.",
        "Ei Zé, roda.",
    ],
)
def test_a_voltinha_do_ze_e_comando_local(fala: str) -> None:
    assert estados.comando(fala) == "avatar_voltinha"


def test_evento_da_tela_e_tratado_uma_vez_e_so_recente() -> None:
    from jarvis.rosto.tela import evento_novo

    dados = {"evento": {"id": "a1", "tipo": "tonto", "ts": 100.0}}
    assert evento_novo(dados, "", 105.0) == dados["evento"]
    assert evento_novo(dados, "a1", 105.0) is None  # já falado
    assert evento_novo(dados, "", 200.0) is None  # velho: o Zé estava parado
    assert evento_novo({}, "", 105.0) is None


def test_chamado_no_comeco_sai_do_pedido() -> None:
    from jarvis.nucleo.estados import sem_chamado

    assert sem_chamado("Ei Zé, que horas são?") == "que horas são?"
    assert sem_chamado("Eis é. Tá me ouvindo?") == "Tá me ouvindo?"
    assert sem_chamado("Zé, abre a sessão Loja") == "abre a sessão Loja"
    assert sem_chamado("Ei, Zé!") is None and sem_chamado("Zé.") is None
    assert sem_chamado("Que horas são?") == "Que horas são?"
    assert sem_chamado("Zezinho chegou?") == "Zezinho chegou?"


def test_chamado_repetido_continua_ouvindo_sem_nao_entendi() -> None:
    from jarvis.nucleo import estados as e

    m = e.Maquina()
    m.tratar(e.Presenca(True), 0.0)
    m.tratar(e.Ativacao(), 1.0)
    assert m.tratar(e.FimDeFala("Eis é."), 2.0) == [e.Bip()]
    assert m.estado is e.Estado.OUVINDO and m.autorizado
    assert m.tratar(e.FimDeFala("Ei Zé, como vai a Loja?"), 3.0) == [
        e.EnviarAoCerebro("como vai a Loja?")
    ]


def test_segurar_para_falar_abre_e_soltar_fecha() -> None:
    from jarvis.nucleo import estados as e

    m = e.Maquina()
    assert m.tratar(e.Apertou(), 0.0) == []  # inativo: o botão não abre nada
    m.tratar(e.Presenca(True), 0.0)
    assert m.tratar(e.Apertou(), 1.0) == [e.Bip()]
    assert m.estado is e.Estado.OUVINDO and m.segurando and m.prazo >= 120.0
    assert m.tratar(e.Soltou(), 5.0) == [e.FecharPedido()]
    assert not m.segurando and m.tratar(e.Soltou(), 5.1) == []
    assert m.tratar(e.FimDeFala("como vai a Loja?"), 6.0) == [e.EnviarAoCerebro("como vai a Loja?")]


def test_apertar_durante_a_fala_interrompe_e_ouve() -> None:
    from jarvis.nucleo import estados as e

    m = e.Maquina()
    m.tratar(e.Presenca(True), 0.0)
    m.tratar(e.Aviso("A sessão Loja terminou."), 1.0)
    assert m.estado is e.Estado.FALANDO
    efeitos = m.tratar(e.Apertou(), 2.0)
    assert e.CortarFala() in efeitos and e.Bip() in efeitos and m.segurando
    m.tratar(e.Presenca(False), 3.0)
    assert not m.segurando  # perdeu o rosto: nada fica apertado


def test_pedido_pelo_botao_nao_abre_conversa() -> None:
    from jarvis.nucleo import estados as e

    m = e.Maquina()
    m.tratar(e.Presenca(True), 0.0)
    m.tratar(e.Apertou(), 1.0)
    m.tratar(e.Soltou(), 2.0)
    m.tratar(e.FimDeFala("como vai a Loja?"), 3.0)
    m.tratar(e.Frase("Vai bem."), 4.0)
    m.tratar(e.RespostaFim(), 4.1)
    m.tratar(e.FalaOcioso(), 5.0)
    assert m.estado is e.Estado.ATIVO  # espera o botão de novo, não fica ouvindo


def test_ao_vivo_ouve_sem_parar_e_sem_chamado() -> None:
    from jarvis.nucleo import estados as e

    m = e.Maquina()
    m.tratar(e.AoVivo(True), 0.0)  # chega antes do rosto: só guarda
    assert m.tratar(e.Presenca(True), 0.0) == [e.AbrirMicrofone(), e.Bip()]
    assert m.estado is e.Estado.OUVINDO and m.autorizado
    assert m.tratar(e.Silencio(), 100.0) == [] and m.estado is e.Estado.OUVINDO
    assert m.tratar(e.FimDeFala("hum"), 101.0) == []  # ruído: sem "não entendi"
    assert m.tratar(e.FimDeFala("ok"), 102.0) == [] and m.estado is e.Estado.OUVINDO
    assert m.tratar(e.FimDeFala("como vai a Loja?"), 103.0) == [
        e.EnviarAoCerebro("como vai a Loja?")
    ]
    m.tratar(e.Frase("Vai bem."), 104.0)
    m.tratar(e.RespostaFim(), 104.1)
    m.tratar(e.FalaOcioso(), 105.0)
    assert m.estado is e.Estado.OUVINDO and m.autorizado  # o próximo pedido sem chamado
    assert m.tratar(e.Aviso("A sessão Loja terminou."), 106.0) == [
        e.Falar("A sessão Loja terminou.")
    ]
    m.tratar(e.FalaOcioso(), 107.0)
    assert m.estado is e.Estado.OUVINDO
    m.tratar(e.AoVivo(False), 108.0)
    assert m.historico[-1] is e.Estado.ATIVO and not m.autorizado


def test_ao_vivo_liga_com_o_ze_ja_ativo() -> None:
    from jarvis.nucleo import estados as e

    m = e.Maquina()
    m.tratar(e.Presenca(True), 0.0)
    assert m.tratar(e.AoVivo(True), 1.0) == [e.Bip()] and m.estado is e.Estado.OUVINDO
