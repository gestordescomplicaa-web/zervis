"""O navegador do JARVIS: o que é livre, o que pergunta e o que nunca vai por voz."""

from pathlib import Path

from jarvis.cerebro import mcp_externo, navegador

P = navegador.PREFIXO


def test_codigo_e_arquivos_sao_recusados_antes_de_perguntar() -> None:
    for nome in ("browser_run_code_unsafe", "browser_evaluate", "browser_file_upload"):
        assert "Recusado" in str(navegador.prechecar(P + nome, {}))
    assert navegador.prechecar(P + "browser_click", {"element": "Buscar"}) is None
    assert navegador.prechecar("mcp__jarvis__tela_agir", {}) is None


def test_rolar_e_livre_outras_teclas_perguntam() -> None:
    assert navegador.autoaprovar(P + "browser_press_key", {"key": "PageDown"})
    assert not navegador.autoaprovar(P + "browser_press_key", {"key": "Enter"})
    assert not navegador.autoaprovar(P + "browser_click", {})


def test_a_frase_diz_o_que_vai_para_a_pagina_e_esconde_senha() -> None:
    d = navegador.descrever
    assert d(P + "browser_click", {"element": "o botão Pesquisar"}) == (
        "Vou clicar em o botão Pesquisar."
    )
    assert d(
        P + "browser_type", {"element": "a caixa de busca", "text": "automação", "submit": True}
    ) == ('Vou digitar "automação" em a caixa de busca e enviar.')
    frase = d(
        P + "browser_fill_form",
        {"fields": [{"name": "E-mail", "value": "g@x"}, {"name": "Senha", "value": "segredo"}]},
    )
    assert frase == 'Vou preencher E-mail com "g@x"; Senha com uma senha.'
    assert "segredo" not in str(frase)
    assert d(P + "browser_navigate", {"url": "https://x"}) is None  # livre, sem frase
    assert d("WebSearch", {}) is None


def test_o_mcp_toml_do_navegador_e_aceito(tmp_path: Path) -> None:
    arquivo = tmp_path / "mcp.toml"
    arquivo.write_text(
        "[servidores.navegador]\n"
        'comando = "/usr/bin/node"\n'
        'argumentos = ["cli.js", "--headless"]\n'
        'livres = ["browser_navigate", "browser_snapshot"]\n'
    )
    externos = mcp_externo.carregar(arquivo, env={})
    assert externos.servidores["navegador"]["args"] == ["cli.js", "--headless"]
    assert externos.livres == [P + "browser_navigate", P + "browser_snapshot"]


ARVORE = """### Snapshot
```yaml
- generic [ref=e1]:
  - generic [ref=e2]:
    - heading "Automação" [level=1] [ref=e3]
    - paragraph [ref=e4]:
      - text: Automação é um sistema
      - superscript [ref=e5]:
        - link "[1]" [ref=e6] [cursor=pointer]:
          - /url: "#cite_note-1"
      - link "Indústria" [ref=e7] [cursor=pointer]:
        - /url: /wiki/Ind%C3%BAstria
    - textbox "Senha" [ref=e8]: hunter2
    - button "Entrar" [ref=e9] [cursor=pointer]
```"""


def test_enxugar_tira_o_ruido_e_guarda_o_alvo_do_clique() -> None:
    e = navegador.enxugar(ARVORE)
    assert "[cursor=pointer]" not in e and "[1]" not in e and "#cite" not in e
    assert '- heading "Automação" [level=1]' in e  # sem ref: não se clica num título
    assert 'link "Indústria" [ref=e7]' in e and 'button "Entrar" [ref=e9]' in e
    assert "generic" not in e and "superscript" not in e
    assert "Automação é um sistema" in e and "/url: /wiki/Ind%C3%BAstria" in e


def test_mascarar_senha_chave_e_cartao_mas_nao_telefone() -> None:
    m = navegador.mascarar(
        '- textbox "Senha" [ref=e8]: hunter2\n'
        "chave sk-ant-api03-abcdefghijklmnopqrstuvwx e Bearer abcdefghijklmnopqrstuvwxyz123\n"
        "cartão 4111 1111 1111 1111 e telefone 81 99999 9999 1234"
    )
    assert "hunter2" not in m and "sk-ant" not in m and "abcdefghijklmnopqrstuvwxyz123" not in m
    assert "[cartão oculto]" in m and "81 99999 9999 1234" in m


def test_corte_com_indice_e_continuacao(tmp_path: Path) -> None:
    linhas = [f"- paragraph: texto número {i} " + "x" * 80 for i in range(400)]
    linhas[300] = '- heading "Preços" [level=2]'
    cortado = navegador.cortar("\n".join(linhas), tmp_path)
    assert len(cortado) <= navegador.LIMITE
    assert "linha 301: Preços" in cortado  # o índice do que ficou de fora
    leitura = cortado.split('leitura "')[1][:10]
    seguinte = int(cortado.split("e linha ")[1].split(".")[0])
    trecho = navegador.continuar(leitura, seguinte, tmp_path)
    assert trecho.startswith(f"[linhas {seguinte} a ") and f"número {seguinte - 1} " in trecho
    assert navegador.continuar(leitura, 301, tmp_path).split("\n")[1] == linhas[300]
    try:
        navegador.continuar("../etc/xx", 1, tmp_path)
    except ValueError as erro:
        assert "inválida" in str(erro)
    else:
        raise AssertionError("aceitou um nome de leitura fora do padrão")


def test_abrir_a_pagina_ja_traz_o_esboco_e_apaga_o_arquivo_cru(tmp_path: Path) -> None:
    (tmp_path / "page-1.yml").write_text(ARVORE.split("```yaml\n")[1].removesuffix("```"))
    resposta = [
        {
            "type": "text",
            "text": "### Page\n- Page URL: https://x\n### Snapshot\n"
            "- [Snapshot](../../../state/jarvisd/navegador/page-1.yml)",
        }
    ]
    ajustada = navegador.ajustar(P + "browser_navigate", resposta, tmp_path)
    assert isinstance(ajustada, list)
    [bloco] = ajustada
    texto = bloco["text"]
    assert "### Esboço da página" in texto
    assert 'heading "Automação" [level=1]' in texto and 'button "Entrar" [ref=e9]' in texto
    assert "hunter2" not in texto and not (tmp_path / "page-1.yml").exists()
    assert navegador.ajustar("mcp__jarvis__tela_ver", resposta, tmp_path) is None
    em_dict = navegador.ajustar(
        P + "browser_snapshot", {"content": [{"type": "text", "text": ARVORE}]}, tmp_path
    )
    assert isinstance(em_dict, dict)
    assert "[cursor=pointer]" not in em_dict["content"][0]["text"]
