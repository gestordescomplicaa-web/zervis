# Plano: câmera de vigia (12/11/2026)

O pedido do usuário: o Zé fica de olho numa câmera Wi-Fi da casa. Quando ela detecta movimento
(o sensor é da própria câmera), o Zé tira uma foto e guarda com o horário. Ele **não avisa**:
não fala, não manda notificação nem foto ao celular. A foto fica guardada para quando o usuário
quiser ver, no painel ou pedindo por voz.

## O que já se sabe da câmera do usuário

Os dados do aparelho dele não entram no código. O endereço, o usuário e a senha vêm do cadastro
no painel.

- Ele usa o app **iCSee**, que é da linha Xiongmai (XMEye). O chip Wi-Fi é da AltoBeam. Na rede
  local, a câmera abre a porta 80 (página "Web Viewer"), a 554 (RTSP) e a 34567 (protocolo
  próprio da Xiongmai, chamado "DVRIP" ou "Sofia"). Não abre ONVIF (as portas 8899 e 2020
  estão fechadas).
- Feito: ver a [ADR 0087](adr/0087-camera-de-vigia.md). Na câmera real, o alarme aos clientes
  da rede vinha desligado de fábrica, o evento de pessoa se chama `appEventHumanDetectAlarm` e a
  câmera tem três lentes. As credenciais e o IP continuam fora do repositório.

## Como funciona

1. **Escutar o sensor, sem analisar vídeo.** O Zé abre uma conexão TCP na porta 34567 e fica
   nela. Os passos são:
   - Fazer o login. A mensagem é a 1000, com `EncryptType: MD5` e a senha no hash da Sofia: o
     MD5 da senha, e então, para i de 0 a 7, o caractere `(d[2i]+d[2i+1]) % 62` do alfabeto
     `0-9A-Za-z`.
   - Mandar a mensagem 1006 (KeepAlive) a cada `AliveInterval` segundos.
   - Assinar os alarmes com a mensagem 1500 (Guard).
   - A câmera passa a empurrar a mensagem 1504 com `AlarmInfo`, que traz os campos `Event`
     (`MotionDetect`, `HumanDetect`…), `Status` (`Start` ou `Stop`) e `Channel`.
   - Cabeçalho de 20 bytes, little-endian: `0xFF`, versão, 2 bytes reservados, sessão, sequência,
     total, atual, código da mensagem (2 bytes) e tamanho (4 bytes). O corpo é JSON terminado em
     `\n\0`.
   - Se a conexão cair, reconectar sozinho com espera crescente, de 5 s até 60 s, como o vigia
     da impressora.
   - A referência é o projeto `python-dvr` (MIT). Escreva código próprio. Se copiar algum trecho,
     registre a autoria em `THIRD_PARTY.md`.
2. **A foto.** Só no `Status: Start`, peça a foto pela mensagem 1560 (snapshot), que devolve um
   JPEG. Se a câmera não responder a ela, o plano B é pegar um quadro do RTSP com o `ffmpeg` do
   sistema, se estiver disponível, sem adicionar dependência ao projeto.
3. **O horário.** O nome do arquivo leva a data e a hora local (`AAAAMMDD-HHMMSS.jpg`, pelo
   `zervis/fuso.py`), e o painel mostra a hora junto da foto. Essas câmeras já gravam a hora
   na imagem (o OSD). Confira se ela está ligada e certa. Não é preciso desenhar a hora com
   Pillow, que também não é dependência hoje.
4. **Sem rajada.** Um movimento longo gera vários `Start`. Tire no máximo uma foto a cada
   30 s, com esse intervalo ajustável no cadastro.
5. **Guardar.** As fotos vão para `<dados>/camera/fotos/`, na pasta XDG do usuário, com
   permissão 0700. Guarde um limite fixo de fotos (por exemplo 500) e apague as mais velhas,
   como faz o `Vigia.guardar_foto` da impressora.

## Onde entra no código (seguindo o vigia da impressora)

- `zervis/camera.py`:
  - O cadastro, em `lugares.CONFIG / "camera.json"`, com permissão 0600. Guarda `ip`,
    `usuario`, `senha` e `intervalo_s`.
  - O cliente da Sofia: `entrar`, `manter_viva`, `assinar_alarmes` e `foto`.
  - A descoberta na rede: procura quem abre a porta 34567 na sub-rede, como o `descobrir()` de
    `impressora3d.py`.
- `zervis/camera_vigia.py`: a thread com a conexão aberta, a reconexão, o intervalo entre fotos,
  `guardar_foto` e `fotos()`. Use `zervis/impressora_vigia.py` como modelo, mas **sem** chamar
  `avisar` nem `mostrar`.
- Na montagem do núcleo, faça como `zervis/nucleo/oficina3d.py`: crie o vigia, ligue o
  `ao_mudar` do cadastro a `vigia.iniciar` e, por fim, chame `vigia.iniciar()`.
- Ferramenta do cérebro em `zervis/cerebro/ferramentas/`:
  - `camera_foto`: tira uma foto agora e devolve o caminho e a hora.
  - `camera_movimentos`: devolve as últimas fotos, com as horas.
  - Só mande a imagem ao celular por `imagem_ao_aparelho` (ADR 0086) quando o usuário **pedir**
    ("Zé, me mostra a câmera").
- Painel, numa seção "Câmera":
  - O cadastro, com endereço, usuário e senha (o campo da senha nunca mostra o valor salvo).
  - Os botões "Procurar na rede", "Testar conexão" e "Salvar", e o liga/desliga "Fotos por
    movimento".
  - A galeria das fotos, da mais nova para a mais velha, com data e hora.
  - Siga o texto de produto do `CLAUDE.md`. Por exemplo: "Câmera", "Conectada" / "Sem conexão",
    "Usuário ou senha inválidos.".
- ADR nova: `docs/adr/0087-camera-de-vigia.md`, com linha no índice e no `CHANGELOG.md`.

## Testes

- Uma câmera falsa em `tests/`: um servidor TCP local que fala a Sofia. Ele aceita o login,
  responde ao KeepAlive, empurra um 1504 `Start` e devolve um JPEG pequeno na 1560.
- Os casos a cobrir:
  - O movimento gera exatamente uma foto, com o horário no nome.
  - Um segundo `Start` dentro do intervalo não gera foto.
  - O `Stop` não gera foto.
  - A senha errada (Ret diferente de 100 e de 515) aparece como "Usuário ou senha inválidos.",
    sem novas tentativas em seguida.
  - Depois que a conexão cai, a câmera volta sozinha.
  - O limite de fotos é respeitado.
  - O vigia **nunca** chama `avisar` nem `mostrar`.
- `tests/test_usuario.py` continua passando, ou seja, nenhum IP nem senha fixo. Rode
  `make check` antes do commit.

## Pronto quando

- O usuário cadastra a câmera no painel, "Testar conexão" dá "Conectada" e ele passa na frente
  dela.
- Em segundos aparece uma foto nova, com a hora certa, na galeria.
- O Zé não fala nada, e nada chega ao celular sem pedido.
- Por voz, "Zé, me mostra a última foto da câmera" mostra a foto.
