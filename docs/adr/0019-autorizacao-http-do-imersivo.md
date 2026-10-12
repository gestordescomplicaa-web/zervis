# 0019 — Autorização HTTP do imersivo

- Data: 12/10/2026
- Status: **Aceito** (melhorias de segurança autorizadas após a avaliação de maturidade)

## Contexto

O painel validava Host e token, mas o imersivo aceitava pedidos que viravam texto do usuário sem
autorização equivalente. Exigir JSON não autentica o remetente; loopback também não elimina o
risco de DNS rebinding. A reprodução com Host e Origin externos gravou um pedido de teclado.

## Decisão

1. Validar Host em todos os acessos e Origin quando fornecido. Aceitar apenas os endereços locais
   e a porta da instância. Clientes de terminal sem Origin continuam funcionando com token.
2. Gerar um token aleatório por instância; conservar o mesmo nos reinícios do processo filho.
   Todo POST e as leituras de estado, configuração e notas exigem `X-Ze-Token`.
3. Entregar o token no HTML local, sem cache. O `fetch` da página o acrescenta apenas para a
   própria origem, inclusive ao receber um objeto Request; nunca para CDNs ou outros servidores.
4. O núcleo passa o token aos cards. Para ferramentas de terminal, o filho publica o token
   atomicamente em `<estado-imersivo>/.http-token`, com permissão 0600.
5. Scripts usam o token dessa pasta e respeitam `ZE_IMERSIVO_ESTADO` e `ZE_IMERSIVO_PORTA`.
   Ausência de token encerra o comando sem enviar pedido. Tokens nunca vão para logs.
6. Recusar tamanhos inválidos antes de ler o corpo; limitar a espera na conexão HTTP.

## Consequências

Clientes antigos de API precisam enviar o token. A página trata isso automaticamente. Imagens,
modelos e arquivos estáticos continuam carregando pelas URLs usuais, com a validação de origem.
Os módulos que autorizam os pedidos entram na zona protegida da manutenção.

Testes cobrem recusa sem token, Host/Origin inválidos, cliente do núcleo, scripts e permissões do
arquivo. Um teste no Chromium usa o cabeçalho da página e o servidor real e verifica que nenhum
token chega a outro servidor local. Nenhum teste exige câmera ou credencial de modelo.
