# 0137 — Imagem e arquivo no chat, lidos só pelo que foi anexado

- Data: 25/11/2026
- Status: **Aceito** (desenho aprovado em imagens junto com o ADR 0136).
- Segue o ADR 0136 (o Início é a conversa com o Zé).

## Contexto

O chat do Início só aceitava texto. Quem usa quer mandar um print, a foto de uma fachada, um
contrato em PDF ou uma planilha em CSV e perguntar ao Zé sobre eles. O cérebro, por segurança, não
lê arquivos do computador: as ferramentas embutidas dele são só as da internet.

## Decisão

1. **No painel:** o "+" do campo, colar (Ctrl+V) ou arrastar para o chat junta os anexos ao campo:
   miniatura para imagem, nome e tamanho para arquivo, cada um com o × para tirar. Imagens (PNG,
   JPEG, WebP, GIF), PDF e texto (txt, md, csv, json), até 5 por mensagem e 20 MB cada. Ao enviar,
   cada anexo sobe (`POST /api/conversa/anexo`) e o pedido leva os nomes guardados
   (`conversa/escrever` com `anexos`).
2. **A guarda** (`zervis/memoria/anexos.py`): `DADOS/anexos`, um nome único por anexo, 0600,
   escrita atômica. Falha fechado: tipo fora da lista, conteúdo que não bate com a extensão (o
   começo do arquivo), texto fora de UTF-8, arquivo vazio ou grande demais. Depois de 30 dias o
   arquivo sai; o pedido no histórico fica, só com o nome.
3. **O pedido** leva os anexos no fim (`texto [anexos: nome1, nome2]`): é o que vai ao cérebro, à
   memória e ao histórico, sem mudar a máquina de voz. O chat separa o texto e mostra cada anexo
   (nome, tamanho e, numa imagem, a miniatura). Só o anexo, sem texto: "Veja o anexo."
4. **O cérebro lê só o que foi anexado**, pela ferramenta `anexo_ler`: a imagem vai para o modelo
   ver (até 1568 px no maior lado), o PDF e o texto voltam como texto (até 60 mil caracteres; o PDF
   pela `pypdf`). Ela só lê a pasta dos anexos, então passa sem perguntar; o conteúdo é de fora
   (pode ser o documento de outra pessoa), então depois dela nada se executa sem a aprovação
   falada (`DE_FORA`). O pedido com anexo vai sempre ao cérebro completo: a via rápida não tem
   ferramentas.

## Consequências

- Nova dependência: `pypdf` 6.21.4 (BSD-3, sem dependências), registrada em `THIRD_PARTY.md`.
- Um PDF escaneado (só imagem) volta como "sem texto selecionável"; ler a imagem das páginas fica
  para depois, se fizer falta.
- Com a confirmação falada pendente, o anexo espera ("Responda a confirmação antes de anexar").
