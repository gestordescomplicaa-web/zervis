# 0128 — O Zé conhece todas as suas páginas e os seus eventos

- Data: 24/11/2026
- Status: **Aceito** (pedido de quem usa; teste pela voz depois do merge).
- Amplia os ADRs 0043 e 0045 (o Zé se conhece).

## Contexto

Em 24/11/2026, logo depois da Prospecção entrar (ADR 0127), quem usa perguntou ao Zé se havia
algum disparo acontecendo na aba Prospecção. O Zé respondeu que não conhecia essa aba.

O autoconhecimento só via o que tinha ferramenta (ADR 0045) e a configuração (ADR 0043). A
Prospecção entrou só no painel: sem ferramenta, sem linha nos grupos. O mesmo valia para as
Empresas, para o funil do Instagram em Redes sociais e para a Atividade, onde cai todo
acontecimento do Zé. Nada no projeto obrigava uma página nova a se apresentar ao Zé.

A causa direta foi outra camada: a pergunta ("veja se tá acontecendo algum disparo de
prospecção") ficou na via rápida, o modelo leve que responde sem ferramentas, porque nem "veja"
nem "prospecção" estavam nas listas que mandam o pedido ao cérebro completo. A via rápida, sem o
estado de nada, disse não conhecer a aba.

Quem usa: "o Zérvis é o sistema; ele tem que entender tudo e todos os eventos que existem nele".

## Decisão

1. **O mapa do Zé** (`zervis/nucleo/mapa.py`): cada seção do menu do painel, com o que ela é e as
   ferramentas que leem o estado dela. Vai inteiro no `ze_sobre` ("As minhas páginas"), com a
   regra: perguntado sobre qualquer página, consultar a ferramenta dela; o que aconteceu está na
   `atividade_buscar`; nunca dizer que não conhece uma parte sua.
2. **A regra vigiada:** `tests/test_mapa.py` falha se uma seção do `index.html` não está no mapa,
   se uma linha não tem ferramenta ou cita uma que não existe. O `CLAUDE.md` diz o mesmo a quem
   desenvolve.
3. **As páginas que não tinham voz ganham ferramentas:**
   - Prospecção: `prospeccao_situacao` (o que está acontecendo agora, hoje, o próximo envio, quem
     espera aprovação, quem respondeu; ou tudo de uma empresa), e `prospeccao_aprovar`,
     `prospeccao_descartar`, `prospeccao_marcar`, `prospeccao_buscar` e `prospeccao_ajustar`
     (ligar, enviar sozinho, envios por dia, cidade e ramos). A empresa é achada pelo nome dela
     ou do dono.
   - Empresas: `empresas_listar`.
   - Redes sociais: `redes_situacao` (o funil de comentários e direct do Instagram).
   - Atividade: `atividade_buscar` (por palavras, dias e tipo): todo acontecimento, de qualquer
     parte, com o resultado e as falhas.
4. **Ler passa sem perguntar; agir pede o sim.** As leituras da Prospecção, do funil e da
   Atividade trazem texto de terceiros e contam como entrada de fora (Frente 2): depois delas,
   nada se executa sem a aprovação falada.
5. **A via rápida passa a vez:** cada página do mapa tem as palavras que levam o pedido direto
   ao cérebro completo ("prospecção", "disparo", "instagram", "aconteceu"...), e os verbos de
   consulta ("veja", "checa", "consulta", "aprova") entram na lista. O resumo da via rápida
   lista as páginas e manda passar a vez sobre o estado de qualquer uma. Página com ferramenta
   própria e sem palavras não passa no teste.
6. Os grupos de ferramentas que ainda saíam com o nome do módulo (Projetos 3D, Modo TV,
   Dispositivos, Câmera) ganham a linha em português.

## Consequências

- Página nova no painel exige a linha no mapa e uma ferramenta de leitura no mesmo PR.
- O `ze_sobre` fica cerca de 2 mil caracteres maior; ele só vai ao modelo quando consultado.
- As ferramentas novas ficam sob demanda (ADR 0097): o modelo as acha pela busca quando o pedido
  fala de prospecção, empresas, Instagram ou do que aconteceu.
