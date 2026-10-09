# 0004 — Ponte de áudio (LiveKit): fora do núcleo por enquanto

- Data: 06/10/2026
- Status: **Substituído por [0005](0005-celular-por-livekit-e-tailscale.md)** no mesmo dia: o usuário quer usar pelo celular.

## Contexto
O usuário viu projetos usando o LiveKit como ponte de áudio. O LiveKit é uma infraestrutura
de áudio e vídeo em tempo real (WebRTC), que também pode rodar local, com um framework de agentes
de voz que traz detecção de turno, interrupção e cancelamento de eco.

O valor dele aparece quando o áudio **sai da máquina**: falar com o JARVIS pelo celular, de
outro cômodo ou de outro computador, ou atender por telefone.

## Decisão
Não entra no núcleo agora. O uso atual é um fone na própria máquina, e o caminho local
(PipeWire → detector pessoal → whisper.cpp → Cadu) já entrega isso sem servidor, salas nem
tokens de sessão.

Para não fechar a porta, a camada de voz é desenhada com um **transporte de áudio trocável**:
- `TransporteLocal` (PipeWire/Pulse), o único implementado agora;
- `TransporteLiveKit`, futuro, para celular e acesso remoto, sem mudar o resto do JARVIS.

## Consequências
- Menos peças para manter e falhar na primeira versão.
- Pegar emprestadas do LiveKit as **ideias** de detecção de turno e de interrupção, que são
  requisitos nossos (R2.4).
- Revisar este ADR quando o usuário quiser usar o JARVIS fora do computador.
