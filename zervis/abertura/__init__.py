"""A abertura do Zé (ADR 0078): ao abrir o programa, a Imersão toca a música de abertura e o Zé
apresenta o dia, em painéis e em voz: a saudação, o clima, a agenda, as automações de hoje, as
sessões de código que pedem continuidade, o WhatsApp sem resposta e as manchetes do Brasil.

- `ajustes`: ligada ou não, a cidade do clima e a música (os dados de quem usa, fora do código);
- `clima` e `noticias`: as fontes de fora, sem chave e sem tokens (Open-Meteo e RSS);
- `panorama`: o dia em dados e as falas, montados só com o que existe (painel vazio não entra);
- `servico`: o Zé grava o panorama para a Imersão e fala cada parte quando a página pede.
"""
