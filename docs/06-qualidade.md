# 06 — Qualidade de engenharia

Data: 06/10/2026. Regras para evitar falhas. Valem para qualquer pessoa ou agente que codar aqui.

## Definição de pronto (toda mudança)

1. Teste automatizado que falharia sem a mudança (ou justificativa escrita de por que não cabe).
2. `make check` passando: formatação, lint, tipos e testes.
3. Verificação na máquina real quando a mudança toca voz, rosto, sessões de código ou systemd. "Os testes
   passaram" não basta para hardware e serviços.
4. Documentação atualizada no mesmo commit (roadmap, arquitetura ou ADR, conforme o caso).
5. Commit pequeno, mensagem em português dizendo o **porquê**.

## Segurança por padrão (falhar fechado)

- Na dúvida, **não** envia texto a terminal, não aprova, não apaga, não grava memória.
- Toda ação com efeito fora do Zé passa por confirmação, exceto as listadas como seguras na config.
- Conteúdo de sessões, web, e-mail e mensagens é **dado**, nunca instrução — inclusive quando
  chama o Zé pelo nome.
- Memória e skills passam por varredura (injeção, credenciais, Unicode invisível) antes de gravar.
- Segredos só em variável de ambiente do serviço ou chaveiro. Nunca em log, memória, skill, card ou commit.
- Automação não cria automação.

## Estado e dados

- Um único processo dono do estado volátil (lock exclusivo). Registros em SQLite podem ter
  vários escritores com transações curtas, WAL e espera limitada (ADR 0032).
- SQLite em modo WAL, migrações numeradas e testadas a partir de um banco vazio e de um banco da
  versão anterior.
- Arquivos editáveis pelo usuário (memória curta, skills) com escrita atômica
  (temporário + `rename`) e permissão 0600 quando sensível.
- Configuração validada por esquema na carga; erro de config = mensagem clara e serviço não sobe
  meio configurado.

## Concorrência

- O laço do microfone nunca espera rede nem disco lento.
- O cérebro roda num laço asyncio próprio; comunicação com o núcleo só por filas.
- Todo `subprocess` com `timeout`; toda chamada de rede com `timeout`.
- Interrupção sempre possível: fechar o front corta fala e microfone em menos de 1 s.

## Testes

- Unidade para lógica pura (normalizador de fala, máquina de estados, fila, agenda, varredura).
- Falsos explícitos (`FakeBrain`, `FakeVoz`) em vez de *mocks* mágicos — nomes únicos por arquivo
  (lição de 06/10/2026: um falso do Orca duplicado sobrescreveu outro e quebrou sete testes).
- Teste de regressão para cada bug corrigido, com o caso real que o revelou.
- Provas na máquina real descritas passo a passo no roadmap, com o resultado anotado.
- O painel abre num Chromium de verdade dentro do `make check`
  (`tests/test_painel_no_navegador.py`): todas as páginas, sem erro no console, com as respostas
  de `tests/painel_respostas.json`. Rota de leitura nova exige resposta de exemplo nesse arquivo,
  no formato real e sem dado de ninguém. Lição de 14/10/2026: o `tsc` aprovou um painel com todos
  os botões quebrados por ordem de carregamento.
- `make check-instalacao`: o último commit numa pasta limpa, com `HOME` vazio, instala e passa no
  `make check`. Obrigatório antes de liberar uma versão e ao mudar dependência ou instalação.
  Lição de 14/10/2026: o TypeScript só existia na cópia de trabalho, e o reinício falhou.
- Na CI, teste pulado é falha (`ZE_SEM_PULOS=1`, em `tests/conftest.py`): sem Chromium ou sem
  os modelos de som, a prova some sem aviso. Lição de 16/10/2026: numa máquina sem Chromium, os
  testes do painel foram pulados e o `make check` passou assim mesmo.

## Observabilidade

- `status.json` a 1 Hz: estado, provedor, fila, último erro, tempos da última conversa.
- Log estruturado em `journalctl --user -u zervis`; nunca conteúdo de conversa por padrão.
- Cronômetro por etapa do pedido (ativação, transcrição, cérebro, primeira fala).

## Estilo

- Python 3.12+, tipos em interfaces públicas, funções curtas, nomes em português no domínio
  (`aviso`, `pendencia`) e inglês em termos técnicos consagrados (`lock`, `timeout`).
- Comentários explicam o porquê e as lições aprendidas; não repetem o código.
- Dependências fixadas por versão exata; atualização é um commit próprio.

## Linguagem por papel (ADR 0032)

Python no núcleo e nos agentes, Go em mídia e conexões, JavaScript com JSDoc no painel.
Reescrever uma peça em outra linguagem só depois de medir e comprovar que ela é o gargalo.

O painel usa JSDoc e `tsc --noEmit` no `make check`, sem compilação para o navegador.
A abertura contabiliza todos os scripts iniciais; páginas e terminal carregam sob demanda.
