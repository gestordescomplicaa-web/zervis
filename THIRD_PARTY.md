# Código de terceiros

Regras de licença em [docs/03-reaproveitamento.md](docs/03-reaproveitamento.md). Todo trecho
copiado ou adaptado de outro projeto entra aqui **no mesmo commit** em que entra no código, e o
arquivo copiado leva um cabeçalho citando a origem.

| Arquivo no Zé | Origem | Licença | Autoria |
|---|---|---|---|
| `jarvis/voz/ativacao.py` (VAD e features em fluxo) | openWakeWord 0.6.0, `openwakeword/vad.py` e `utils.py` (`AudioFeatures`) | Apache-2.0 | David Scripka |
| `~/.local/share/zervis/modelos/silero_vad.onnx` (fora do repositório) | Silero VAD, distribuído com o openWakeWord | MIT | Silero Team |
| `jarvis/voz/fim_de_turno.py` (uso do modelo) | Smart Turn, `inference.py` e `audio_utils.py` (github.com/pipecat-ai/smart-turn) | BSD-2-Clause | Daily |
| `jarvis/voz/fim_de_turno.py` (log-mel do Whisper em numpy) | transformers, `WhisperFeatureExtractor` e `audio_utils.mel_filter_bank` | Apache-2.0 | Hugging Face |
| `~/.local/share/zervis/modelos/smart-turn-v3.2-cpu.onnx` (fora do repositório; HF `pipecat-ai/smart-turn-v3`, revisão `f766f81d`, sha256 `2bb02631…967e4f`) | Smart Turn v3.2 | BSD-2-Clause | Daily |
| `~/.local/share/zervis/modelos/melspectrogram.onnx`, `embedding_model.onnx` (fora do repositório) | openWakeWord 0.6.0 (conversão do `speech_embedding` do Google) | Apache-2.0 | David Scripka; Google |
| `jarvis/habilidades/revisao.py` (critérios do prompt de revisão, adaptados e traduzidos) | Hermes Agent, `agent/background_review.py` (`_MEMORY_ROUTING_BLOCK`, `_LESSON_LAYER_BLOCK`, `_DO_NOT_CAPTURE_BLOCK`, `_SKILL_REVIEW_PROMPT`) | MIT | Nous Research |
| `jarvis/memoria/curta.py` (ideia da varredura; padrões reescritos, sem cópia de código) | Hermes Agent, `tools/memory_tool_store.py` (`_scan_memory_content`) | MIT | Nous Research |
| `~/.local/share/zervis/modelos/pt_BR-cadu-medium.onnx` (fora do repositório, baixado por `jarvis/preparar.py`; rhasspy/piper-voices `39ab474b`, sha256 `765f0809…bdb535`) | Voz Cadu do Piper (dataset Cadu 1.0, OHF-Voice/voice-datasets) | CC0-1.0 | Open Home Foundation |
| O navegador do Zé (`~/.config/zervis/mcp.toml`) executa o `@playwright/mcp` 0.0.83, instalado em `~/.local/share/zervis/navegador-mcp`, como programa separado (nenhum código copiado; a ideia de navegador em segundo plano lido pela árvore de acessibilidade vem do `browser` do Hermes Agent) | Playwright MCP (Microsoft) | Apache-2.0 | Microsoft |
| `jarvis/voz/modelos/ei_ze.npz` (o chamado universal "Ei Zé"; pesos treinados por `jarvis/voz/treino_universal.py` com áudio sintetizado pelas vozes do Piper, baixadas só no treino; nenhum áudio vai no repositório) | Vozes do Piper (rhasspy/piper-voices): faber, jeff, cadu e tugão (OHF-Voice/voice-datasets); edresson (TTS-Portuguese-Corpus); libritts_r (LibriTTS-R, openslr 141); vctk (CSTR VCTK Corpus); mls fr_FR (Multilingual LibriSpeech, openslr 94) | CC0-1.0 (faber, jeff, cadu, tugão); CC BY 4.0 (edresson, LibriTTS-R, VCTK, MLS) | Open Home Foundation; Edresson Casanova; Google (LibriTTS-R); University of Edinburgh, CSTR (VCTK); Meta AI (MLS) |
| `jarvis/voz/piper.py` usa o `piper-tts` 1.4.2 como dependência Python, dentro do processo (nenhum código copiado; o Zé é AGPL-3, compatível; ADR 0013) | Piper (OHF-Voice/piper1-gpl) | GPL-3.0-or-later | Open Home Foundation / Michael Hansen |
| `jarvis/imersivo/` (servidor, `maos.py`, a página e o Guia em `web/`, `bin/`) e `tests/imersivo/` | Barehands (github.com/jaredrhod/barehands), na versão modificada por gdautomacao.ia (fork `jarvis-ze-front`, commit `19debe6`, 09/10/2026) | AGPL-3.0-or-later | Jared Rhodenizer (obra original); gdautomacao.ia (modificações) |
| `jarvis/imersivo/web/avatar/jarvis-chimpanze.*` e projeções `.png` (o holograma do Zé) | Criado no Blender para o Zé | AGPL-3.0-or-later, como o Zé | gdautomacao.ia |
| `jarvis/imersivo/web/avatar/cabeca.glb` | Exemplos do three.js (r160), `LeePerrySmith` ("Infinite, 3D Head Scan"); ver `LICENSE-cabeca.txt` | CC BY 3.0 | Lee Perry-Smith |
| `~/.local/share/zervis/ai-memory/<versão>/` (fora do repositório; baixado por `jarvis/memoria/aimemory.py` quando a máquina não tem o ai-memory; v2.6.3, sha256 `933be9bb…` x86_64 e `e4e01409…` aarch64), rodado como programa separado e ligado às sessões pelos hooks dele | ai-memory (github.com/akitaonrails/ai-memory) | MIT | Fabio Akita |
| `jarvis/portal/web/vendor/xterm/` (`xterm.js` e `xterm.css` 6.0.0, `addon-fit.js` 0.11.0, sem mudanças; licença em `LICENSE`) | xterm.js (github.com/xtermjs/xterm.js) | MIT | The xterm.js authors |
| `jarvis/portal/web/vendor/livekit/livekit-client.umd.js` (livekit-client 2.22.4, sem mudanças, conferido pelo `integrity` do npm; licença em `LICENSE`) | LiveKit client SDK (github.com/livekit/client-sdk-js) | Apache-2.0 | LiveKit, Inc. |
| `~/.local/share/zervis/cloudflared/<versão>/` (fora do repositório; baixado por `jarvis/portal/tunel.py` quando a pessoa ativa o acesso pelo celular e a máquina não tem o `cloudflared`; 2026.10.0, sha256 `d33ff2d1…` amd64 e `e6422b9d…` arm64), rodado como programa separado | cloudflared (github.com/cloudflare/cloudflared) | Apache-2.0 | Cloudflare, Inc. |
| `jarvis/nucleo/laco.py` usa o `segno` 1.6.6 como dependência Python para o QR do acesso pelo celular (nenhum código copiado) | segno (github.com/heuer/segno) | BSD-3-Clause | Lars Heuer |
| `jarvis/portal/web/icones/ze-192.webp`, `ze-512.webp` (ícone do app) e `jarvis/portal/web/imagens/holograma.webp` (a Imersão no celular), recortados de `jarvis/imersivo/web/avatar/jarvis-chimpanze-referencia.png` | Criado no Blender para o Zé | AGPL-3.0-or-later, como o Zé | gdautomacao.ia |
| `jarvis/transporte/remoto.py` usa o SDK de tempo real `livekit` 1.1.20 como dependência Python (nenhum código copiado) | LiveKit Python SDK (github.com/livekit/python-sdks) | Apache-2.0 | LiveKit, Inc. |
| `~/.local/share/zervis/livekit/<versão>/` (fora do repositório; baixado por `jarvis/transporte/servidor_livekit.py` quando a máquina não tem o `livekit-server`; v1.13.9, sha256 `0b7fa208…` amd64 e `c5e4e5a6…` arm64), rodado como programa separado | LiveKit server (github.com/livekit/livekit) | Apache-2.0 | LiveKit, Inc. |

Os modelos de som acima (Silero, openWakeWord, Smart Turn e a voz Cadu) também ficam, idênticos e
conferidos pelo SHA-256, na release `modelos-1` de `gestordescomplicaa-web/zervis-modelos`, com os
avisos de licença em `LICENCAS.md` (ADR 0034, ponto 13).

O Codex (github.com/openai/codex, Apache-2.0, OpenAI) é baixado pelo Zé quando a máquina não tem
nenhum (`jarvis/cerebro/agentes_nativos.py`; versão 0.163.0, SHA-256 `beb339e8…` x86_64 e
`a7261e65…` aarch64), com o auxiliar `codex-code-mode-host` da mesma versão (SHA-256
`31426312…` x86_64 e `284356ae…` aarch64), sem mudanças, e roda como programa separado. O Claude Code usado é o que vem
no `claude-agent-sdk`, instalado do PyPI como dependência (ADR 0035).

## Licenças de referência

- **Hermes Agent** (Nous Research): MIT. Copiar exige manter o aviso de copyright e a licença.
- **Barehands**: AGPL-3.0, compatível com o Zé (ADR 0013); embutido em `jarvis/imersivo/` (ADR 0014), com os avisos de autoria nos arquivos.
- **backtalk**, **ai-visualizer**: AGPL-3.0. Entram só com aviso de autoria, como o Barehands.
- **ai-memory-vault**: CC BY-SA 4.0. Texto copiado mantém a atribuição e a licença.
| `jarvis/atendimento/wacalls/` (servidor em Go; licença em `LICENSE`), sem o cliente React e sem os vetores de referência do codec | WaCalls (github.com/JotaDev66/WaCalls), na versão modificada no Ligatia por gdautomacao.ia (captura passiva de mensagens, envio transacional, PCM por WebSocket, autenticação interna); no Zé: nome do aparelho, QR na lista de sessões e sem QR no terminal | MIT (original); AGPL-3.0-or-later (modificações) | jotadev66 (obra original); gdautomacao.ia (modificações) |
| `jarvis/atendimento/wacalls/internal/voip/media/mlow/` (codec MLow do WhatsApp em Go puro; licença em `LICENSE` da pasta) | meowcaller, pacote `mlow` (github.com/purpshell/meowcaller), portado de whatsapp-rust (github.com/oxidezap/whatsapp-rust) | MIT | Rajeh Taher |
| Módulos Go baixados na compilação do WaCalls (fora do repositório; versões em `jarvis/atendimento/wacalls/go.sum`): whatsmeow, pion/webrtc, modernc.org/sqlite, zerolog, protobuf | tulir/whatsmeow; pion/webrtc; modernc.org/sqlite; rs/zerolog; protocolbuffers/protobuf-go | MPL-2.0 (whatsmeow); MIT (pion, zerolog); BSD-3-Clause (sqlite, protobuf) | Tulir Asokan; The Pion community; The Sqlite Authors / Jan Mercl; Olivier Poitrey; The Go Authors |

## TypeScript — ferramenta de desenvolvimento

[TypeScript](https://github.com/microsoft/TypeScript), Microsoft e colaboradores, Apache-2.0.
Verifica os comentários JSDoc do painel com `checkJs` e `noEmit`; não entra na página nem exige
compilação na instalação do usuário. Dependência de desenvolvimento fixada em `package-lock.json`.
