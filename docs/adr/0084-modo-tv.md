# 0084 — O Modo TV: uma página leve na TV da casa

- Data: 12/11/2026
- Status: **Aceita** (`tests/test_tela_tv.py`; a prova na TV de quem usa, uma Samsung de 2021 com
  Tizen 6, em 12/11/2026).

## Contexto

Quem usa quer pedir pelo celular ("mostra na TV o suporte de celular") e ver a resposta na TV da
sala. A Imersão inteira abriu na TV sem nenhum erro (o navegador dela é o motor do Chrome 120, com
WebGL2), mas a 4 quadros por segundo: o macaco holográfico, os brilhos e o anel pesam demais para
o processador da TV. A peça sólida sozinha rodou a 31 quadros em 1080p e a 58 em meia resolução.

O navegador da Samsung não aceita um endereço mandado pela rede (o "deep link" e o "native
launch" da API dela abrem o navegador sem a página), mas abre e fecha pela API REST da porta
8001, sem pareamento.

## Decisão

1. **Uma página própria para a TV**, leve: a peça em 3D sólido girando em 75% da resolução, com o
   nome e as medidas embaixo; um relógio grande quando não há nada; e um anel que pulsa quando o
   Zé fala. A Imersão do computador não muda.
2. **Servida na rede da casa** por um servidor pequeno do Zé (porta 8798), só com o Modo TV ligado,
   só para endereços privados e só com a chave da configuração (`<config>/tv.json`, permissão do
   dono). A página pergunta o estado duas vezes por segundo e lê os modelos do Acervo, só de `3d/`
   e só `.glb`. Não há nada para escrever nela.
3. **Abrir na TV**: quem usa define, uma vez, o endereço da página como página inicial do
   navegador da TV; o Zé abre e fecha o navegador pela API REST. Já aberta (a página perguntou há
   menos de 5 segundos), não abre de novo.
4. **Pela voz**: `tela_tv_mostrar` (a peça de um projeto 3D, ou um modelo do Acervo) e
   `tela_tv_fechar`, livres como a própria tela do Zé. No painel: o cartão Modo TV em Perfil e o
   botão "Mostrar na TV" nos Projetos 3D.

## Consequências

- O firewall da máquina precisa liberar a porta 8798 para a rede da casa, uma vez.
- Se o IP da máquina mudar, o endereço da página inicial da TV muda junto: vale fixar o IP no
  roteador.
- A voz continua saindo onde sai hoje (o celular ou o computador); o som pela TV fica para depois.
