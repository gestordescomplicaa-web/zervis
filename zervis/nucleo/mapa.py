"""O mapa do Zé (ADR 0128): cada página do painel, o que ela é e como o Zé a consulta.

Caso de 24/11/2026: perguntado "está havendo disparo na prospecção?", o Zé disse que não conhecia
essa aba. Ela tinha entrado no painel sem ferramenta e sem linha no autoconhecimento. O painel é o
Zé visto de fora: toda página é uma parte dele, e ele precisa saber o que é e como ler o estado
dela, pela voz.

Regra (vigiada por `tests/test_mapa.py`): toda seção do menu do painel (`index.html`) tem uma
linha aqui, com pelo menos uma ferramenta que exista; a página que se abre por dentro de outra
(`dentro`, como a Voz em Ajustes) também. Página nova sem linha não passa no
`make check`. O texto vai para o `ze_sobre`, que o cérebro consulta sobre qualquer parte do Zé.
"""

from typing import NamedTuple


class Pagina(NamedTuple):
    titulo: str
    o_que_e: str
    consultar: tuple[str, ...]  # as ferramentas que leem o estado dela (e agem, quando há)
    # Palavras (sem acento) que, num pedido, mandam direto ao cérebro completo, que tem as
    # ferramentas: a via rápida não sabe o estado das páginas (caso de 24/11/2026, "disparo de
    # prospecção" ficou na via rápida, que disse não conhecer a aba).
    assuntos: tuple[str, ...] = ()
    # A página de onde ela se abre, quando não está no menu (a Voz se abre em Ajustes, ADR 0135).
    dentro: str = ""


PAGINAS: dict[str, Pagina] = {
    "inicio": Pagina(
        "Início",
        "a conversa com o Zé (ADR 0136): o chat inteiro, falado ou escrito, dia a dia com a data "
        "(rolando para cima vêm os dias anteriores, ADR 0139), com as respostas, os avisos e as "
        "aprovações pedidas pelo WhatsApp, e as sugestões quando o dia começa; ao "
        "lado, o que precisa de quem usa (leads, sessões paradas, revisões), o que o Zé está "
        "fazendo agora, o foco e os números de hoje",
        ("ze_sobre", "atividade_buscar", "historico_buscar"),
    ),
    "imersao": Pagina(
        "Imersão",
        "a tela do Zé: o rosto, as cenas, os hologramas e as apresentações",
        ("tela_ver", "tela_agir", "tela_explicar"),
        ("imersao", "holograma", "cena"),
    ),
    "foco": Pagina(
        "Foco",
        "as frentes de trabalho de quem usa: a atual, as ativas, as paradas e as ideias",
        ("foco_ver",),
        ("foco", "frente", "frentes"),
    ),
    "sessoes": Pagina(
        "Sessões",
        "as sessões de código com os agentes (Claude, Codex), o que cada uma fez e o estado",
        ("sessoes_listar", "sessao_ler"),
        ("sessao", "sessoes"),
    ),
    "automacoes": Pagina(
        "Automações",
        "lembretes, perguntas agendadas, artigos, vídeos, carrosséis e ligações que o Zé roda "
        "sozinho; cada uma se edita (quando, os temas, publicar sozinho)",
        ("automacoes_listar",),
        ("automacao", "automacoes", "lembrete", "lembretes", "agendado", "agendada"),
    ),
    "atendimento": Pagina(
        "Redes sociais",
        "o WhatsApp conectado (caixa, leads, prioridade), o Instagram e o funil de comentários "
        "e direct, e o agente que atende clientes",
        ("whatsapp_conversas", "whatsapp_leads", "redes_situacao", "instagram_perfil"),
        (
            "whatsapp",
            "zap",
            "instagram",
            "insta",
            "comentario",
            "comentarios",
            "comentou",
            "direct",
            "lead",
            "leads",
            "atendente",
        ),
    ),
    "empresas": Pagina(
        "Empresas",
        "as empresas que quem usa gere, com o grupo de WhatsApp e a vitrine de cada uma",
        ("empresas_listar",),
        ("empresas", "grupo", "grupos", "vitrine"),
    ),
    "projetos3d": Pagina(
        "Projetos 3D",
        "peças para imprimir, a prévia em holograma e a impressora",
        ("projetos3d_listar", "impressora_status"),
        ("impressora", "impressao", "imprimir", "3d"),
    ),
    "dispositivos": Pagina(
        "Dispositivos",
        "os aparelhos da casa ligados ao Zé (câmera, impressora, TV)",
        ("dispositivos_listar",),
        ("dispositivo", "dispositivos", "camera", "tv"),
    ),
    "marketing": Pagina(
        "Marketing",
        "o site e o blog (por PR), os posts e os vídeos do Instagram, as métricas do site e o "
        "funil do Instagram",
        ("marketing_situacao", "marketing_posts", "marketing_videos", "site_google"),
        (
            "marketing",
            "blog",
            "artigo",
            "artigos",
            "post",
            "posts",
            "reels",
            "video",
            "videos",
            "carrossel",
        ),
    ),
    "prospeccao": Pagina(
        "Prospecção",
        "empresas da cidade achadas no Google Maps, quem decide em cada uma, a nota, a mensagem "
        "e o envio pelo WhatsApp no limite do dia",
        ("prospeccao_situacao",),
        (
            "prospeccao",
            "prospectar",
            "prospectando",
            "prospectadas",
            "disparo",
            "disparos",
            "disparando",
            "abordagem",
            "abordagens",
        ),
    ),
    "pesquisas": Pagina(
        "Pesquisas",
        "tudo o que o Zé pesquisou, com as fontes",
        ("pesquisas_guardadas", "pesquisa_guardada"),
        ("pesquisas", "pesquisa"),
    ),
    "memoria": Pagina(
        "Memória",
        "o que o Zé lembra de quem usa e de si",
        ("memoria", "historico_buscar"),
        ("memoria", "lembra"),
    ),
    "skills": Pagina(
        "Skills",
        "os procedimentos do jeito de quem usa e as sugestões",
        ("skills_ver", "sugestoes_listar"),
        ("skill", "skills"),
    ),
    "conectores": Pagina(
        "Conectores",
        "as integrações com outros sistemas (n8n, navegador e outros)",
        ("conectores_listar",),
        ("conector", "conectores", "n8n", "integracao", "integracoes"),
    ),
    "atividade": Pagina(
        "Atividade",
        "tudo o que o Zé executou, de qualquer parte, com o resultado e as falhas",
        ("atividade_buscar",),
        ("atividade", "aconteceu", "falhou", "falhas", "executou", "evento", "eventos"),
    ),
    "melhorias": Pagina(
        "Autodesenvolvimento",
        "o diagnóstico do que deu errado e as melhorias do próprio código, por PR",
        ("ze_sobre", "modo_manutencao"),
        ("autodesenvolvimento", "manutencao", "melhoria", "melhorias"),
    ),
    "ajustes": Pagina(
        "Ajustes",
        "tudo o que se configura no Zé, por assunto e com busca: perfil, modelos, voz, conectores, "
        "redes sociais, marketing, prospecção e atualizações",
        ("ze_sobre",),
        ("ajuste", "ajustes", "configuracao", "configuracoes"),
    ),
    "perfil": Pagina(
        "Perfil",
        "o nome, o jeito de quem usa, o fuso e a abertura do dia",
        ("ze_sobre",),
        dentro="ajustes",
    ),
    "modelos": Pagina(
        "Modelos",
        "o cérebro, as respostas rápidas, as contas e o reconhecimento de fala",
        ("ze_sobre",),
        dentro="ajustes",
    ),
    "voz": Pagina(
        "Voz",
        "a voz do Zé, o modo de fala, a ativação, os avisos e o acesso pelo celular",
        ("ze_sobre",),
        dentro="ajustes",
    ),
    "atualizacoes": Pagina(
        "Atualizações",
        "as versões novas do Zé e de onde vêm",
        ("atualizacoes_ver",),
        ("atualizacao", "atualizacoes", "versao"),
        dentro="ajustes",
    ),
}


def assuntos() -> frozenset[str]:
    """Todas as palavras que mandam um pedido ao cérebro completo (a via rápida usa)."""
    return frozenset(w for p in PAGINAS.values() for w in p.assuntos)


def texto() -> str:
    """As páginas, para o `ze_sobre`: o Zé sabe que cada uma é parte dele e como lê-la."""
    linhas = [
        "## As minhas páginas (o painel)",
        "Cada página é uma parte de mim. Perguntado sobre qualquer uma, consulte a ferramenta dela "
        "(entre parênteses) e responda com o que vier; o que aconteceu em qualquer parte está em "
        "atividade_buscar. Nunca diga que não conhece uma página.",
    ]
    linhas += [
        f"- **{p.titulo}**{f' (em {PAGINAS[p.dentro].titulo})' if p.dentro else ''} "
        f"({', '.join(p.consultar)}): {p.o_que_e}."
        for p in PAGINAS.values()
    ]
    return "\n".join(linhas)
