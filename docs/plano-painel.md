# Plano — o painel do Zé (09/10/2026)

Pedido do usuário: uma interface prática, rápida e simples, com as partes organizadas num menu
lateral (cérebro e chaves, skills, memória, automações, Foco, configurações), para quem nem
sempre quer usar a voz ou os gestos. O modo imersivo (Barehands, câmera, pinça, avatar) segue
como está, como outra opção, e é o caminho futuro para óculos de realidade virtual (WebXR).

## Princípios

1. **O Zé é um agente; as telas são portas.** Toda função mora no núcleo (`jarvisd`). O painel,
   o modo imersivo, o celular ou os óculos só mostram e pedem. Função feita uma vez serve a
   todas as portas; nada de regra de negócio dentro de uma tela.
2. **Rápido por carregar pouco.** HTML, CSS e JavaScript puros, sem framework, sem build e sem
   nada vindo da internet: o código próprio do painel abaixo de 120 KB (era 100 KB; subiu em
   12/10/2026 com a voz pelo navegador e o botão de falar), aberto em menos de 1 s. A pressa
   não vem da linguagem (o navegador desenha), vem de não carregar câmera, rastreador, 3D nem
   bibliotecas. Uma janela própria, se ele quiser, vem depois empacotando a mesma página com o
   Tauri (Rust, leve), sem reescrever.
3. **A voz é do núcleo.** Os dois modos (chamado com "Ei Zé" e tempo real, como uma ligação)
   funcionam com qualquer porta aberta, ou com nenhuma.
4. **Segredo não volta.** Chave colada no painel vai direto a um arquivo `0600` do Zé
   (`~/.config/zervis/chaves/<motor>.key`) e nunca é devolvida: a tela só sabe se existe e os
   quatro últimos caracteres. Não passa pelo Barehands, nem pelo `state/`, nem pelo backup.

## Regras de tela (redesenho de 09/10/2026)

1. Tudo em português; só nomes que não se traduzem ficam como são (um modelo, uma ferramenta).
2. Cada página: título, no máximo uma linha curta e a ação principal no canto.
3. O que aparece dá para mexer: ligar e desligar, remover com confirmação na própria tela,
   editar.
4. Detalhe técnico (comando, caminho) fica escondido em "Detalhes".
5. Menu em grupos: Início e Imersão; Trabalho (Foco, Sessões, Automações); O Zé (Memória,
   Skills, Conectores); Ajustes (Modelos, Voz).

## Arquitetura

- `jarvis/portal/servidor.py`: HTTP da biblioteca padrão, só em `127.0.0.1:8795`, numa thread
  do `jarvisd`. Protegido contra outros sites do navegador: o `Host` precisa ser local e todo
  pedido de API leva um token por sessão, entregue só na própria página (outro site não
  consegue lê-la).
- `jarvis/portal/acoes.py`: a ponte entre a API e o núcleo (o que ler, o que mudar).
- `jarvis/portal/web/`: `index.html`, `painel.css`, `painel.js`.
- As escolhas da via rápida feitas no painel ficam em `~/.local/state/zervis/via-rapida.json`
  (por cima da config, como a escolha do cérebro) e valem na hora, sem reiniciar.

## A aba Imersão (pedido do usuário, 09/10/2026)

O modo imersivo mora dentro do painel, numa aba: a mesma página do Barehands numa moldura
(`iframe`), com permissão de câmera, carregada só quando a aba é aberta e desligável (solta
câmera, rastreador e GPU). Fora da aba ela continua viva para o Zé poder mostrar algo: quando
ele manda um comando para a tela, a aba vem à frente. A janela do painel conta como a janela do
Zé (presença e foco no Hyprland). A janela imersiva avulsa continua existindo, mas não deve
rodar junto com a aba (as duas disputariam a câmera).

## Fatias

1. **Base e Cérebro e chaves** (esta): servidor, página, menu lateral com as seções; a seção
   Cérebro troca motor e modelo da via rápida, guarda a chave e testa o tempo da primeira
   palavra. Skills, memória, automações e Foco já aparecem para ler; o resto mostra o que vem.
2. **Conversa por texto e ações**: conversar com o Zé pelo painel (a mesma conversa da voz),
   marcar o V do Foco, pausar automações, aprovar sugestões.
3. **O Zé ao lado, sem câmera**: o avatar do modo imersivo numa coluna, opcional, sem o
   rastreador de mãos; e "abre o painel" por voz.

Cada fatia: testes, conferência na janela real e commit próprio. A voz em tempo real (barge-in,
como no Ligatia) é a fase de voz seguinte, no núcleo, independente do painel.
