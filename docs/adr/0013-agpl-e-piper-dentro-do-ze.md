# 0013 — Licença AGPL-3 e o Piper dentro do Zé

- Data: 09/10/2026
- Status: **Aceito** (decisão do usuário: "quero que ele esteja junto do código, não como algo
  separado"; quem baixar o Zé já recebe a voz)
- Substitui, da ADR 0012, o Piper como serviço HTTP à parte

## Contexto
A voz (Cadu pelo Piper) rodava num serviço separado (`piper.http_server`, porta 17871), instalado à
mão. Para o Zé ser fácil de instalar do zero, a voz tem que vir com ele. O `piper-tts` é GPL-3:
rodá-lo dentro do processo torna o conjunto distribuído uma obra GPL. O imersivo (Barehands) é
AGPL-3 e também deveria poder vir embutido.

## Decisão
1. **O Zérvis é AGPL-3.0-or-later** (`LICENSE`). A AGPL-3 é compatível com a GPL-3 (seção 13 de
   ambas), então o Piper e, no futuro, o Barehands podem ser combinados com o Zé. Código MIT e
   Apache-2.0 de terceiros continua entrando com aviso em `THIRD_PARTY.md`.
2. **Piper como dependência Python** (`piper-tts==1.4.2` no `pyproject.toml`, com o espeak-ng
   embutido, 24 MB) e usado dentro do processo (`jarvis/voz/piper.py`). Sem serviço à parte.
3. **A voz `pt_BR-cadu-medium` (CC0, 63 MB) é baixada na primeira subida**, da revisão fixa
   `39ab474b…` do repositório oficial rhasspy/piper-voices, e conferida por SHA-256
   (`jarvis/preparar.py`), como os modelos de som. Não entra no git.
4. **Uma thread do onnxruntime por núcleo físico, até 4.**

## Medições (Ryzen 5 8500G, 6 núcleos e 12 threads, mesmas três frases, 09/10/2026)
| Motor | Primeiro som (mediana) | Pior |
|---|---|---|
| Piper por HTTP (serviço à parte) | 318 ms | 487 ms |
| Piper dentro do Zé, threads padrão (12) | 268 ms | 322 ms |
| **Piper dentro do Zé, 4 threads** | **154 ms** | **196 ms** |

Carga da voz: ~0,8 s, feita em segundo plano ao subir. Memória do processo com a voz: ~310 MB.

## Consequências
- Quem distribuir uma versão modificada do Zé, ou oferecê-la pela rede, tem que abrir o código.
- O motor de voz segue trocável (`voz.motor`): um motor por chave de API (Cartesia, ElevenLabs) ou
  outro local pode entrar com o mesmo formato de fluxo (float32 frase a frase).
- O motor "pocket" (Pocket TTS, serviço externo) saiu.
