# Métricas do site

O Zé lê como o site aparece no Google (Search Console) e quem o visita (Google Analytics 4), só
leitura (ADR 0094). Pela voz: "quantas pessoas visitaram o site esta semana?", "o blog está sendo
lido?", "quantos clicaram no WhatsApp?", "que buscas trazem gente ao site?". Em Marketing, o cartão
"Métricas do site" mostra os últimos 28 dias.

O acesso é uma conta de serviço do Google Cloud, sua. Leva uns 10 minutos, uma vez só.

## 1. A etiqueta do GA4 no site

O Search Console não precisa de nada no site. As visitas precisam da etiqueta do GA4.

1. Em [analytics.google.com](https://analytics.google.com), crie uma propriedade para o site e um
   fluxo de dados da Web com o endereço dele. Deixe a "medição otimizada" ligada: ela registra as
   páginas vistas, a rolagem e os cliques para fora (o WhatsApp, por exemplo).
2. Copie o **ID de medição** (começa com `G-`).
3. Ponha a etiqueta no site. Num site Next.js na Vercel, com o componente que lê
   `NEXT_PUBLIC_GA_ID`: em Settings → Environment Variables, crie `NEXT_PUBLIC_GA_ID` com o ID e
   faça um novo deploy.

Diga na política de privacidade do site que ele usa cookies de análise.

## 2. A conta de serviço

1. Em [console.cloud.google.com](https://console.cloud.google.com), crie um projeto (ou use um).
2. Em APIs e serviços → Biblioteca, ative:
   - **Google Search Console API**
   - **Google Analytics Data API**
   - **Google Analytics Admin API** (só para o Zé achar a propriedade sozinho; dispensável se o
     `zervis.json` declarar `ga4`)
3. Em IAM e administrador → Contas de serviço, crie uma conta (nome: `ze-metricas`). Não precisa
   de papel no projeto.
4. Na conta criada, em Chaves → Adicionar chave → JSON. O arquivo baixa sozinho.

## 3. Liberar a conta

Copie o e-mail da conta (termina em `iam.gserviceaccount.com`).

- **Search Console**: na propriedade do site, Configurações → Usuários e permissões → Adicionar
  usuário, com o e-mail e a permissão **Restrita**.
- **GA4**: Administrador → Gerenciamento de acesso à propriedade → +, com o e-mail e o papel
  **Leitor**.

## 4. No Zé

Em Marketing → Métricas do site, cole o conteúdo do JSON e clique em **Salvar**. O Zé confere a
chave no Google e guarda só o e-mail e a chave privada em `<config>/google-metricas.json` (0600).
Depois, apague o arquivo baixado.

## O que o site declara

No `zervis.json` do site (`docs/integrar-site.md`):

```json
{
  "zervis": 1,
  "metricas": {
    "dominio": "minhaempresa.com.br",
    "blog": "/blog/",
    "ga4": "123456789"
  }
}
```

Tudo é opcional. Sem `dominio`, vale o único site que a conta vê no Search Console; sem `ga4` (o
número da propriedade, não o `G-`), a única propriedade que ela vê no GA4.

## Mensagens

| Mensagem | O que fazer |
|---|---|
| Chave inválida. | A chave foi apagada ou o JSON está errado: gere outra. |
| Ative a … no Google Cloud. | Ative a API dita no passo 2. |
| Sem permissão no Google para a conta de serviço. | Libere o e-mail no passo 3. |
| Nenhum site do Search Console liberado para a conta. | Passo 3, no Search Console. |
| O Search Console não tem o site … liberado. | O domínio do `zervis.json` não bate com a propriedade liberada. |
| Nenhuma propriedade do GA4 liberada para a conta. | Passo 3, no GA4. |
| Declare a propriedade do GA4 no zervis.json. | A conta vê mais de uma: declare `ga4`. |
