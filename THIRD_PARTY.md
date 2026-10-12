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
| `jarvis/voz/piper.py` usa o `piper-tts` 1.4.2 como dependência Python, dentro do processo (nenhum código copiado; o Zé é AGPL-3, compatível; ADR 0013) | Piper (OHF-Voice/piper1-gpl) | GPL-3.0-or-later | Open Home Foundation / Michael Hansen |
| `jarvis/imersivo/` (servidor, `maos.py`, a página e o Guia em `web/`, `bin/`) e `tests/imersivo/` | Barehands (github.com/jaredrhod/barehands), na versão modificada por gdautomacao.ia (fork `jarvis-ze-front`, commit `19debe6`, 09/10/2026) | AGPL-3.0-or-later | Jared Rhodenizer (obra original); gdautomacao.ia (modificações) |
| `jarvis/imersivo/web/avatar/jarvis-chimpanze.*` e projeções `.png` (o holograma do Zé) | Criado no Blender para o Zé | AGPL-3.0-or-later, como o Zé | gdautomacao.ia |
| `jarvis/imersivo/web/avatar/cabeca.glb` | Exemplos do three.js (r160), `LeePerrySmith` ("Infinite, 3D Head Scan"); ver `LICENSE-cabeca.txt` | CC BY 3.0 | Lee Perry-Smith |
| `~/.local/share/zervis/ai-memory/<versão>/` (fora do repositório; baixado por `jarvis/memoria/aimemory.py` quando a máquina não tem o ai-memory; v2.6.3, sha256 `933be9bb…` x86_64 e `e4e01409…` aarch64), rodado como programa separado e ligado às sessões pelos hooks dele | ai-memory (github.com/akitaonrails/ai-memory) | MIT | Fabio Akita |
| `jarvis/portal/web/vendor/xterm/` (`xterm.js` e `xterm.css` 6.0.0, `addon-fit.js` 0.11.0, sem mudanças; licença em `LICENSE`) | xterm.js (github.com/xtermjs/xterm.js) | MIT | The xterm.js authors |

## Licenças de referência

- **Hermes Agent** (Nous Research): MIT. Copiar exige manter o aviso de copyright e a licença.
- **Barehands**: AGPL-3.0, compatível com o Zé (ADR 0013); embutido em `jarvis/imersivo/` (ADR 0014), com os avisos de autoria nos arquivos.
- **backtalk**, **ai-visualizer**: AGPL-3.0. Entram só com aviso de autoria, como o Barehands.
- **ai-memory-vault**: CC BY-SA 4.0. Texto copiado mantém a atribuição e a licença.
