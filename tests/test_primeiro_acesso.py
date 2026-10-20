"""O primeiro acesso a um Zé num servidor: endereço seguro e convite, sem túnel SSH."""

from pathlib import Path

from zervis.portal import primeiro_acesso, tunel
from zervis.portal.senha import Acesso


def _acesso(tmp_path: Path) -> Acesso:
    return Acesso(tmp_path / "painel.json", tmp_path / "acessos.json")


def test_instalacao_nova_mostra_endereco_e_convite(tmp_path: Path) -> None:
    acesso = _acesso(tmp_path)
    registro, escolha = tmp_path / "cf.log", tmp_path / "tunel.json"
    registro.write_text("https://antigo-que-nao-vale.trycloudflare.com\n")
    reinicios: list[int] = []

    def reiniciar() -> None:  # o Zé sobe e o cloudflared anota o endereço novo
        reinicios.append(1)
        registro.write_text("INF |  https://novo-endereco.trycloudflare.com  |\n")

    linhas = primeiro_acesso.preparar(
        acesso, reiniciar, registro, escolha, dormir=lambda s: None, tunel_no_ar=lambda: False
    )
    assert reinicios == [1] and tunel.escolhido(escolha) and acesso.convite_valido
    assert linhas[0] == "Abra no navegador: https://novo-endereco.trycloudflare.com"
    assert linhas[1].startswith("Código de primeiro acesso: ") and "1 hora" in linhas[1]
    convite = linhas[1].split(": ", 1)[1].split()[0]
    acesso.criar_acesso(convite, "uma senha boa")
    assert acesso.tem_senha


def test_sem_endereco_cai_no_tunel_ssh_com_o_mesmo_convite(tmp_path: Path) -> None:
    acesso = _acesso(tmp_path)
    linhas = primeiro_acesso.preparar(
        acesso,
        lambda: None,
        tmp_path / "cf.log",
        tmp_path / "tunel.json",
        espera_s=0,
        tunel_no_ar=lambda: False,
    )
    assert "não respondeu" in linhas[0] and "ssh -N -L" in linhas[1]
    assert linhas[2].startswith("Código de primeiro acesso: ")


def test_reinstalar_com_senha_criada_nao_gera_convite(tmp_path: Path) -> None:
    acesso = _acesso(tmp_path)
    acesso.definir("uma senha boa")
    registro, escolha = tmp_path / "cf.log", tmp_path / "tunel.json"
    tunel.escolher(True, escolha)
    registro.write_text("https://o-de-sempre.trycloudflare.com\n")
    linhas = primeiro_acesso.preparar(acesso, lambda: None, registro, escolha)
    assert linhas == [
        "O acesso ao painel já foi criado.",
        "Abra https://o-de-sempre.trycloudflare.com e entre com a senha.",
    ]
    assert not acesso.convite_valido
