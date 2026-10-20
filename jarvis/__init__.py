"""Transição: o pacote se chama `zervis` desde 20/10/2026.

As instalações de antes têm `python -m jarvis` na unidade do systemd, e a Central de Atendimento
pode estar no ar como `python -m jarvis.atendimento` na hora da atualização. Estas duas entradas
repassam para o `zervis`; o próximo `make instalar` grava a unidade nova. Nada mais mora aqui.
"""
