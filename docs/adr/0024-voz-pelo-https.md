# 0024 — A voz do navegador dentro do HTTPS do painel (WebSocket)

- Data: 12/10/2026
- Status: **Aceito** (alvo do usuário: o celular falar com o Zé de qualquer lugar, com o Zé no PC ou
  numa VPS, sem app nem Tailscale no celular)

## Contexto
A voz pelo navegador ia pela sala LiveKit (WebRTC, UDP). No teste de 12/10/2026, o Chrome do Android
não mandava o áudio pela VPN do Tailscale: só oferecia o endereço do Wi-Fi e o público, e a ligação
não fechava. Em casa funcionou anunciando o endereço da rede local e liberando o firewall, passos que
nenhum usuário comum faria, e fora de casa não funcionava.

## Decisão
1. **O áudio do navegador vai pelo WebSocket do próprio painel** (`/api/voz/ws`): microfone em PCM de
   16 bits a 16 kHz (AudioWorklet, pedaços de 80 ms); a voz do Piper volta pelo mesmo canal (uma
   mensagem anuncia a taxa, "parar" corta o que não tocou). Onde o HTTPS do painel chega (Wi-Fi, 4G,
   túnel, domínio da VPS), a voz chega junto, sem outra porta, UDP ou TURN.
2. **Segurança do canal:** o mesmo controle do painel (endereço permitido e, de outro aparelho, a
   senha), a origem precisa ser o próprio painel (outro site não abre a voz com o cookie de quem
   entrou) e a primeira mensagem traz o código do painel.
3. **Uma fonte de voz remota por vez:** a nova assume, a anterior é fechada e os quadros dela são
   ignorados (o defeito do áudio intercalado já visto com o LiveKit).
4. **WebSocket mínimo na biblioteca padrão** (`jarvis/transporte/websocket.py`), sem dependência nova.
5. **O LiveKit continua no Zé** para outras portas de entrada (telefone, adiante); o painel deixa de
   carregar o cliente dele (600 KB a menos).
6. **A tela fica ligada durante o ao vivo** (Wake Lock): bloqueada, o navegador para o microfone.

## Consequências
- Sem jitter buffer nem Opus: áudio sem compressão (~256 kbit/s em cada sentido), aceitável no 4G.
- O cancelamento de eco é o do navegador sobre o próprio microfone; com fone, sem efeito.
- O acesso de fora (túnel ou domínio) é o passo seguinte do roteiro.
