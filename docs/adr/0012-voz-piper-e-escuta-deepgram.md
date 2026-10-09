# 0012 — Voz pelo Piper e escuta pelo Deepgram em streaming (tecnologia do LIGATIA)

- Data: 06/10/2026
- Status: **Aceito** (pedido do usuário: "explorar para uma real substituição"). O Piper como
  serviço à parte foi substituído pelo Piper dentro do Zé ([ADR 0013](0013-agpl-e-piper-dentro-do-ze.md)).

## Contexto
A voz era o gargalo: o pedido só ia ao Whisper depois de o usuário terminar (~2 s de transcrição
na GPU integrada), o Smart Turn cortava pela entonação, e o Cadu do Pocket TTS ocupava 1,7 GB e
levava ~1 s até o primeiro som. O LIGATIA (SaaS do usuário, `~/SAAS_RETOMADA`) roda voz em tempo
real numa VPS de 2 vCPU porque: transcreve em **streaming** (Deepgram nova-3, pt-BR), decide o fim
da fala também pelo texto (turn detector do LiveKit) e fala com o **Piper** local.

## Medições nesta máquina (Ryzen 5 8500G)
| Voz | 1º áudio | Síntese de 6,7 s de fala | RAM |
|---|---|---|---|
| Pocket TTS (Cadu antigo) | ~1 s | ~tempo real | 1,7 GB |
| **Piper `pt_BR-cadu-medium`** | **207 ms** (0,19 s pelo HTTP) | 0,3 s (22x) | **233 MB** no serviço |

## Decisão
1. **Fala: Piper com a voz `pt_BR-cadu-medium`.** Dataset Cadu 1.0 (OHF-Voice/voice-datasets),
   CC0, doado para treinar TTS; os termos proíbem tentar identificar o locutor (verificado em
   06/10/2026). Arquivos do mesmo commit fixado do LIGATIA (`39ab474b…`), sha256 conferidos.
   O `piper-tts` 1.4.2 é **GPL-3.0**: roda como programa separado (`jarvis-piper.service`, o
   servidor HTTP do próprio Piper, só em 127.0.0.1:17871) e o `jarvisd` só fala com ele por HTTP;
   nenhum código do Piper entra no repositório. O Pocket fica como `voz.motor = "pocket"`.
2. **Escuta: Deepgram nova-3 em streaming** (o mesmo do LIGATIA). O texto fica pronto quando o
   o usuário termina de falar. O áudio só vai para a nuvem **depois do "Hey Orca"** e até o pedido
   fechar; com a janela fechada nada sai. O "Hey Orca" continua 100% local. Sem chave ou com o
   Deepgram fora do ar, volta sozinho para o Whisper local, com aviso no log.
   Chave em `~/.config/zervis/deepgram.key` (600, fora do repositório; o `.gitignore` bloqueia
   `KEY_*/`, `*.key`, `key.txt`).
3. **Fim de fala:** endpointing do Deepgram somado ao Smart Turn local. O turn detector por texto do
   LiveKit **não** pode ser usado solto: a licença (LiveKit Model License) restringe ao framework
   LiveKit Agents. Migrar o loop de voz para o LiveKit Agents fica como opção futura (ADR 0005).

## Consequências
- Pocket TTS (`hermes-pocket-tts.service`) parado e desativado em 06/10/2026 com o aval do usuário:
  o JARVIS não o usa mais e o Hermes deve sair de uso (o que vale nele é reaproveitado como projeto).
  Reativar: `systemctl --user enable --now hermes-pocket-tts`.
- Custo do Deepgram: centavos por dia no uso pessoal; aparece no log de consumo.
