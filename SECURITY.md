# Segurança

O Zérvis guarda chaves de API e acessa o computador de quem o usa, então uma falha de segurança
pode ser grave. Obrigado por avisar com cuidado.

## Como avisar

**Não abra uma issue pública.** Use o relato privado do GitHub: aba *Security* do repositório,
*Report a vulnerability*. Conte o que você viu, como reproduzir e o efeito. Respondemos assim que
possível e, corrigido o problema, damos o crédito se você quiser.

## O que vale reportar

- Acesso ao painel, à voz ou às sessões sem a senha e o código de acesso.
- Vazamento de chave, senha ou dado pessoal (em arquivo, log, tela ou rede).
- Execução de comando ou leitura de arquivo fora do que a pessoa aprovou.
- Falha na conferência dos modelos e agentes baixados (SHA-256).

## Boas práticas para quem instala

- O painel escuta só em `127.0.0.1`; num servidor, o acesso é pelo endereço HTTPS do Cloudflare
  que o instalador mostra (convite de uso único, depois senha e código do autenticador) ou por
  túnel SSH. Ligue o código do autenticador logo no primeiro acesso.
- Rode o Zé com um usuário comum, nunca como root.
- Chaves entram pelo painel, não digitadas em comandos de terminal.
