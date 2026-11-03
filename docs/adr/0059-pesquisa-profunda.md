# 0059 — Pesquisa profunda: buscador próprio, leitor de páginas, CNPJ e o vigia das fontes

- Data: 03/11/2026
- Status: **Em validação** (testado na internet de verdade: o SearXNG preparado e de pé em 1,2 s,
  uma pesquisa com cinco páginas lidas em 3,8 s, as duas fontes do CNPJ; falta a pessoa usar por
  voz no dia a dia).

## Contexto

O `internet_pesquisar` (ADR 0044) devolve um resumo pronto, feito por outro modelo: bom para "o
que aconteceu hoje", raso para "quem são os concorrentes da loja X", "levanta tudo sobre esse
fornecedor", "qual o CNPJ e quem são os sócios". Pedido de 03/11/2026: o Zé tem que ajudar em
basicamente tudo do trabalho, buscando dados na internet, com ferramentas gratuitas e de confiança.
A preocupação dele: são habilidades que dependem de projetos de fora, então precisam ser fáceis de
manter e avisar quando quebram.

Avaliados: Firecrawl (o melhor fica no serviço pago; hospedar exige vários serviços), Crawl4AI
(34 dependências, entre elas um fork do litellm, o patchright e o playwright-stealth: muito para
vigiar), SearXNG e Trafilatura. Docker ficou de fora: o grupo `docker` daria poder de
administrador a qualquer processo do usuário, inclusive às sessões de código.

## Decisão

1. **Tomadas, não acoplamento**: o Zé fala com o buscador e com o leitor por interfaces pequenas
   (`zervis/pesquisa/`). Trocar um projeto de fora é trocar uma tomada, não a habilidade.
2. **O buscador é o SearXNG (AGPL-3.0, como o Zé), rodando na máquina, só para o Zé**
   (`buscador.py`): baixado na primeira vez, num commit fixado e conferido pelo SHA-256; um
   ambiente Python só dele, montado pelo `uv`; processo filho ouvindo só em 127.0.0.1, numa porta
   livre, com um segredo novo a cada subida e os motores da rede Tor desligados. Atualizar é
   trocar `COMMIT` e `SHA256` num commit testado. Sem chave, sem cota, sem conta.
3. **O leitor é o Trafilatura 2.3.1 (Apache-2.0, 7 dependências)** (`leitor.py`): a página vem
   pela mesma trava de rede do print (ADR 0058), só HTTPS, redirecionamento só para HTTPS. Página
   que só monta com JavaScript abre no Chromium do Zé (`capturas.renderizar`, `--dump-dom`),
   atrás da mesma trava. Página de bloqueio ("Just a moment", 403) não vira fonte. O texto passa
   pela máscara de segredos do navegador.
4. **CNPJ** (`cnpj.py`): BrasilAPI (MIT) e, se ela falhar, minhareceita.org (o mesmo formato).
   Gratuitos e sem chave. Aceita o CNPJ alfanumérico (julho de 2026) e confere os dígitos antes de
   perguntar. Os sócios vêm com nome, qualificação e data, sem o CPF.
5. **A pesquisa profunda** (`profunda.py`): o cérebro dá 2 a 4 consultas; elas rodam juntas, os
   resultados se juntam pela posição (RRF), no máximo duas páginas por site, e as primeiras são
   lidas ao mesmo tempo, com um teto de 50 s. De cada página vão os trechos com mais palavras da
   pergunta, escolhidos sem gastar token; a leitura inteira fica para `navegador_continuar`. O
   relatório vai para `DADOS/pesquisas/`.
6. **Plano B automático**: sem o buscador (preparando, sem `uv`, fora do ar), a ferramenta usa a
   pesquisa resumida pela conta do Codex (ADR 0044) e diz isso. Sem o Chromium, o leitor fica no
   texto direto e depois no texto corrido. Sem a BrasilAPI, o minhareceita.org.
7. **O vigia das fontes** (`saude.py`): uma vez por semana (e quando a pessoa pergunta "está tudo
   funcionando?"), cada fonte de fora é testada com um pedido pequeno: o buscador, o leitor, o
   Chromium, as duas fontes do CNPJ, a Wikimedia, e o WhatsApp e o Instagram quando estão em uso.
   O resultado fica em `ESTADO/fontes.json`. O Zé fala quando uma fonte quebra ou volta, não toda
   semana a mesma coisa.
8. **Ferramentas, livres** (só leem a internet e só gravam na pasta do Zé): `pesquisa_profunda`,
   `pagina_ler`, `empresa_cnpj` e `fontes_saude`, no grupo "Pesquisa profunda".
9. **O limite**: empresas, mercado, concorrentes, fornecedores e figuras públicas. Dossiê de
   pessoa comum, não (regra da persona): nada de levantar endereço, família, rotina ou perfis de
   alguém sem vida pública.

## Depois

- Ler PDF (relatórios de empresa, editais) pelo mesmo leitor.
- Desligar o SearXNG depois de um tempo parado, se a memória da máquina pedir.
