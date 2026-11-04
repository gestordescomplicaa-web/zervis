# 0063 — O cérebro local: um modelo do Ollama, com as ferramentas e a aprovação do Zé

- Data: 04/11/2026
- Status: **Em validação** (testado com o Ollama de verdade nesta máquina; falta o uso no dia a
  dia, por voz).

## Contexto

O pedido: o Zé funcionando sem gastar os tokens dos planos. A análise de 03/11/2026 (com medições
nesta máquina, um Ryzen 5 8500G com a Radeon 740M integrada e ~9 a 12 GiB de RAM livres) achou
o Gemma 4 E4B na GPU integrada: 10 de 10 pedidos certos com as 55 ferramentas reais do Zé, em
2,2 s (mediana), porque o Ollama reaproveita a leitura do começo do prompt (persona e ferramentas)
entre pedidos. Ler isso do zero leva ~1 minuto. O Zé já tinha o resto (roteador, aprovação,
memória, avaliação); faltava um cérebro que falasse com o Ollama.

## Decisão

1. **`LocalBrain` (`zervis/cerebro/local.py`)**, como o `CodexBrain`: herda a política de
   aprovação do `ClaudeBrain` (`_pode_usar`: livres, pré-checagem, frase da aprovação, frase
   exata) e usa o mesmo cliente MCP (`FerramentasCodex`) com o servidor `jarvis` e os conectores.
   O laço é o do Ollama (`/api/chat`, em fluxo): o modelo fala ou pede ferramentas, o Zé roda
   cada uma pela aprovação de sempre, registra na Atividade e devolve o resultado (com imagens,
   que o Gemma 4 vê), até 8 rodadas.
2. **O começo do prompt nunca muda numa conversa** (persona, memória curta, regras do local e
   ferramentas), o modelo fica carregado (`keep_alive` de 4 h) e o cérebro lê esse começo em
   segundo plano ao subir: o primeiro pedido espera essa leitura, os outros saem em segundos.
3. **Regras do modelo local** no fim da persona, porque com a persona inteira o Gemma dizia "vou
   consultar" sem chamar a ferramenta e inventava o resultado (teste de 04/11/2026): dado que ele
   não tem vem de ferramenta, antes de responder; nunca inventar; a data do pedido não se repete
   (e a que ele copiar no começo da resposta é cortada antes da voz).
4. **Uma opção do catálogo, "Local"**, no painel (Modelos → Cérebro, com os modelos instalados no
   Ollama), na janela do Zé e pela voz ("muda para o local", "usa o Gemma", "usa o Ollama").
   Config: `modelo_local` (gemma4:e4b), `local_endereco` (só loopback) e `local_contexto` (32768).
   A via rápida não fica na frente dele: ela gastaria o plano que o local poupa. Com o Ollama
   fora do ar, a troca é recusada; falhando no meio, a reserva de contas do Claude e do Codex
   assume, como nos outros cérebros.
5. **O Ollama desta máquina** ganhou um ajuste do serviço (`~/.config/systemd/user/
   ollama.service.d/zervis.conf`): a GPU integrada ligada (`OLLAMA_IGPU_ENABLE=1`), um modelo e
   um pedido por vez. Apagar o arquivo desfaz.

## Depois

- Subir sozinho para a nuvem o que o local não resolve (código, cenas da Imersão), com o motivo.
- Descer para o local quando a bateria de um plano acabar.
- Guarda de memória livre: descarregar o modelo quando a RAM apertar.
- A bateria `zervis avaliar` contra o local.
