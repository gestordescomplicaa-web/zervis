# 0070 — Estado só em SQLite: avisos, pendências, leads, prioridade e ligações

- Data: 06/11/2026
- Status: **Aceito** (testado no `make check`; a importação conferida com cópias dos arquivos
  reais de uma instalação em uso, todos os registros mantidos).

## Contexto

Jobs, sessões e Atividade já estavam em SQLite. Cinco registros ainda eram listas JSON regravadas
inteiras a cada mudança: a fila de avisos, as pendências da revisão, os leads do WhatsApp, a lista
de prioridade e as ligações. Duas instâncias (ou dois processos, como o painel e o núcleo) que liam
e regravavam ao mesmo tempo perdiam a escrita de uma delas, e um arquivo cortado no meio virava
lista vazia sem aviso. É o terceiro item da Frente 1 do
[plano de maturidade](../plano-maturidade.md).

## Decisão

1. **Uma lista em SQLite** (`zervis/dados/lista.py`): os mesmos registros, num banco próprio ao
   lado (`avisos.db`, `pendencias.db`, `whatsapp-pendentes.db`, `whatsapp-prioridade.db`,
   `ligacoes.db`), 0600, em WAL. Ler e regravar acontecem dentro de uma transação, então ninguém
   escreve no meio, nem outro processo.
2. **A importação é uma vez só e tolerante:** o JSON de antes entra no banco e fica guardado em
   `.antes-do-sqlite/`. Um arquivo cortado não impede o Zé de subir: entra vazio, e o arquivo
   continua ao lado para conferir.
3. **O comportamento não muda:** cada registro mantém a mesma interface, as mesmas regras de
   validade e a mesma ordem.
4. **Fica em arquivo, de propósito:** a configuração que a pessoa edita (`<config>/*.json`) e o
   `status.json` de 1 Hz, que scripts como o reinício seguro leem por fora.

## Consequências

- Escritas simultâneas de processos diferentes não se perdem mais
  (`tests/test_estado_em_sqlite.py`, com dois processos gravando 40 avisos cada).
- O `make check` confere que os cinco registros nascem em SQLite, privados, e que nenhum JSON
  novo é criado.
