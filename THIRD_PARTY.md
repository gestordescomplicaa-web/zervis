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

## Licenças de referência

- **Hermes Agent** (Nous Research): MIT. Copiar exige manter o aviso de copyright e a licença.
- **Barehands**, **backtalk**, **ai-visualizer**: AGPL-3.0. Não copiar código para o núcleo.
- **ai-memory-vault**: CC BY-SA 4.0. Texto copiado mantém a atribuição e a licença.
