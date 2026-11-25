"""O combinado entre o Zé e o app de voz do Android (android/, ADR 0024, 0053, 0066, 0086, 0131).

O app é Java, o Zé é Python: nenhum teste de um lado vê o outro. Este confere, pelos dois
códigos, que eles continuam falando a mesma língua: as mensagens do canal de voz nos dois
sentidos, o primeiro recado (taxa e modo), o pareamento, o link do QR, o código de "outro
aparelho assumiu" e os estados que a tela Início mostra. Mudar um lado sem o outro quebraria o
app no celular de quem já o tem instalado; aqui falha antes (docs/plano-design.md).
"""

import re
from pathlib import Path

from zervis.nucleo.voz_tipos import Estado
from zervis.transporte.navegador import ASSUMIDA

RAIZ = Path(__file__).resolve().parent.parent
JAVA = RAIZ / "android" / "app" / "src" / "main" / "java" / "com" / "zervis" / "voz"
ZE = RAIZ / "zervis"

# Do Zé para o app: o que o VozService trata ({"tipo": ...}).
DO_ZE = ["voz", "fim", "parar", "estado", "whatsapp", "ligacao", "imagem"]
# Do app para o Zé: o botão (apertar e soltar) e os botões das notificações.
DO_APP = [
    "apertar",
    "soltar",
    "whatsapp_ouvir",
    "whatsapp_visto",
    "ligacao_atender",
    "ligacao_recusar",
    "ligacao_encerrar",
]


def _java(nome: str) -> str:
    return (JAVA / nome).read_text()


def _python() -> str:
    return "\n".join(p.read_text() for p in ZE.rglob("*.py"))


def test_as_mensagens_do_ze_ao_app_tem_quem_trate_nos_dois_lados() -> None:
    servico = _java("VozService.java")
    python = _python()
    for tipo in DO_ZE:
        assert f'"{tipo}".equals(tipo)' in servico, f"o app não trata mais “{tipo}”"
        enviada = re.search(rf'tipo="{tipo}"|"tipo": "{tipo}"', python)
        assert enviada, f"o Zé não manda mais “{tipo}” ao app"


def test_as_mensagens_do_app_ao_ze_tem_quem_trate_nos_dois_lados() -> None:
    java = "\n".join(_java(n) for n in ("VozService.java", "Ligacao.java"))
    remoto = (ZE / "nucleo" / "servicos" / "remoto.py").read_text()
    for tipo in DO_APP:
        # O botão vai como texto pronto ("{\"tipo\":\"apertar\"}"): as aspas podem vir escapadas.
        assert re.search(rf'\\?"{tipo}\\?"', java), f"o app não manda mais “{tipo}”"
        assert f'"{tipo}"' in remoto, f"o Zé não trata mais “{tipo}”, que o app manda"


def test_o_primeiro_recado_o_pareamento_e_o_link_do_qr() -> None:
    servico, ajustes = _java("VozService.java"), _java("Ajustes.java")
    pareamento, tela = _java("Pareamento.java"), _java("MainActivity.java")
    servidor = (ZE / "portal" / "servidor.py").read_text()
    # O primeiro recado: a taxa do microfone e o modo de ouvir, com os mesmos nomes.
    assert '.put("taxa", TAXA).put("modo", modoDaConexao)' in servico
    assert 'dados.get("taxa"' in servidor and 'dados.get("modo"' in servidor
    assert 'AO_VIVO = "ao_vivo"' in ajustes and 'CHAMADO = "chamado"' in ajustes
    remoto = (ZE / "nucleo" / "servicos" / "remoto.py").read_text()
    assert 'modo == "ao_vivo"' in remoto
    # Os endereços.
    assert '"/voz-app/ws"' in servico and 'caminho == "/voz-app/ws"' in servidor
    assert '"/voz-app/parear"' in pareamento and '"/voz-app/parear"' in servidor
    assert 'getString("chave")' in pareamento and '{"chave": chave}' in servidor
    # O link do QR que o painel mostra e o app abre.
    acesso = (ZE / "portal" / "acoes" / "acesso.py").read_text()
    assert '"zervis-voz://parear?"' in acesso and '{"e": endereco, "c": codigo}' in acesso
    assert 'getQueryParameter("e")' in tela and 'getQueryParameter("c")' in tela
    manifesto = (JAVA.parents[3] / "AndroidManifest.xml").read_text()
    assert 'android:scheme="zervis-voz" android:host="parear"' in manifesto


def test_outro_aparelho_assumiu_e_os_estados_da_tela_inicio() -> None:
    assert f"ASSUMIDA = {ASSUMIDA};" in _java("VozService.java")
    fase = _java("Fase.java")
    for estado in Estado:
        if estado is not Estado.ATIVO:  # "ativo" é o caso padrão: Pronto
            assert f'case "{estado.value}":' in fase, f"a tela Início não mostra “{estado.value}”"
