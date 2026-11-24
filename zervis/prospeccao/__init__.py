"""Prospecção (ADR 0127): o Zé acha empresas da cidade, o dono de cada uma e escreve a ele.

- `apify`: as empresas de um ramo numa cidade, pelo Google Maps (o ator da Apify, com a chave de
  quem usa).
- `dono`: o CNPJ da empresa, o sócio que decide (o quadro de sócios da Receita) e os telefones,
  na ordem em que valem a pena.
- `funil`: o ciclo (achar, qualificar, aprovar, enviar no limite do dia) e o estado de cada
  empresa, que a página Prospecção mostra.
"""
