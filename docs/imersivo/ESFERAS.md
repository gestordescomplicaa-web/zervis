# As esferas do modo imersivo

O imersivo é **visualização ambiente**: o Zé presente e o que importa agora, para olhar de
relance (e, adiante, em óculos). Configurar e decidir fica no painel; comandar, na voz.

| Superfície | Papel |
|---|---|
| Voz | Comandar |
| Painel | Configurar e decidir |
| Imersivo | Ver e mostrar |

## Regras

1. **Uma esfera, uma fonte do Zé.** Nada lido de programas de fora por padrão.
2. **Só aparece com conteúdo.** No primeiro dia: Mapa (com o perfil) e Guia.
3. **Poucas decisões, todas pequenas e reversíveis:** marcar o passo do Foco como feito, abrir e
   fechar, responder sim ou não ao Zé. O resto é "abrir no painel".
4. **Detalhe técnico só no modo desenvolvedor** (`[barehands] desenvolvedor = true` no
   `config.toml`): medidores de CPU, RAM, GPU e VRAM, baterias dos modelos e tokens por resposta.

## As esferas

| Esfera | `kind` | Mostra | Fonte (arquivo em `state/`) | Aparece |
|---|---|---|---|---|
| Centro | (anel) | O Zé: ouvindo, pensando, falando, expressões, a boca na voz | `state`, `expressao.json`, `wave.json`, `mood.json` | sempre |
| Mapa | `brain` | Perfil, memória, skills, sessões e automações; vistas Geral, Trabalho e Foco | `mapa.json`, `trabalho.json`, `foco.json` | sempre |
| Hoje | `hoje` | Abre o Mapa no quadro do Foco | `foco.json` | com frente, ideia ou automação ativa |
| Trabalho | `trabalho` | Abre o Mapa na vista Trabalho (sessões de código) | `trabalho.json` | com sessão |
| Acervo | `media` | Imagens e modelos 3D que o Zé mostra | `<dados>/acervo/imagens` e `<dados>/acervo/3d` (png, jpg, webp, gif; glb, gltf) | com algum arquivo |
| Guia | `notes` | Gestos e primeiros passos | `web/sample-notes` | sempre |

Quais aparecem e o modo desenvolvedor vêm de `orbes.json`, escrito pelo Zé
(`jarvis/rosto/hud.py`, `orbes()`). Sem esse arquivo (Zé parado), a página mostra todas as esferas
do manifesto.

## Manifesto

`jarvis/imersivo/barehands.padrao.json` lista as esferas (id, título, tipo, apelidos falados e
descrição). Quem quiser outras esferas cria `<dados>/imersivo/barehands.json`; a voz e a persona
do Zé leem o mesmo manifesto (`jarvis/rosto/manifesto.py`).
