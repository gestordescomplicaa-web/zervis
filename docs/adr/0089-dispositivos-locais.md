# 0089 — Dispositivos locais: o núcleo genérico e as integrações por pacote

- Data: 13/11/2026
- Status: **Proposta**. As fases estão em [plano-dispositivos.md](../plano-dispositivos.md).

## Contexto

Em uma semana, o Zé ganhou a impressora Bambu (ADR 0083, 0085), o Modo TV (0084) e a câmera
iCSee (0087, 0088), cada uma com aba, código e testes dentro do núcleo. Funcionam, mas são os
aparelhos de uma pessoa. Quem baixa o Zé vê abas de aparelhos que não tem, e cada aparelho novo
vira código no núcleo.

O que esses trabalhos deixaram de genérico vale para qualquer aparelho:
- foto ou aviso por evento;
- imagem no celular (0086);
- um aparelho como canal de voz, com agente isolado para quem não é o dono e ponte com o celular
  (0088).

O usuário propôs inverter a lógica: um "Integrar dispositivos" que lê a rede, pergunta o que a
pessoa quer de cada aparelho e abre uma sessão de código para cada integração.

Fato que pesa na decisão: o repositório é público, e a instalação do zero (`git clone` do README)
recebe a `master`, não a última versão publicada. Só a atualização vai para a versão publicada.

## Decisão

1. **O núcleo não conhece aparelhos.** Ele tem quatro coisas:
   - o registro de dispositivos (SQLite; credenciais no cofre);
   - a descoberta na rede local, a pedido;
   - o barramento local, por onde uma integração avisa, mostra imagem, abre canal de voz e
     guarda arquivos;
   - o painel **Dispositivos**, que desenha a interface declarada por cada integração.
2. **Cada aparelho é uma integração no formato de pacote da ADR 0033:** manifesto, conector MCP
   e skill. Roda em processo próprio, nunca dentro do Zé, e não injeta HTML no painel. As
   permissões são por ferramenta e começam pedindo confirmação.
3. **Integrações oficiais** ficam em `integracoes/` no repositório, como catálogo:
   - Bambu, iCSee/Xiongmai e TV, migradas do núcleo;
   - Home Assistant, pelo MCP dele.

   Só se instalam quando o aparelho é achado e a pessoa escolhe.
4. **Integração nova por sessão de código** (ADR 0015), numa pasta isolada, com briefing e regras
   fixas:
   - nunca tentar senha;
   - testar no aparelho com a pessoa junto;
   - entregar pacote.

   Entra pela tela de aprovação da ADR 0033.
5. **Quem baixa recebe a versão publicada.** O instalador faz checkout da última versão publicada
   depois do `git clone`, e a `master` é desenvolvimento. Até a seção Dispositivos existir, as
   abas de aparelho só aparecem com o aparelho cadastrado.

## Consequências

- O núcleo encolhe: `impressora3d.py`, `impressora_vigia.py`, `camera.py`, `camera_vigia.py`,
  `tv/` e `atendimento/camera_fala.py` viram integrações. O que é genérico neles fica no
  barramento.
- No PC de quem já usa, a migração precisa ser transparente: os cadastros atuais entram no
  registro sem perder nada.
- A varredura e a integração gerada são novas superfícies de risco. Elas ficam a pedido, na
  rede privada, registradas, em processo próprio e no sandbox quando a Frente 2 entregar.
- As fases 0 e 1 cabem no congelamento de funções do plano de maturidade, porque são correção e
  reorganização. As fases 2 a 5 vêm depois da 0.5.0.
