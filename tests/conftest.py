"""Os testes nunca leem nem escrevem os dados de verdade (docs/plano-distribuicao.md).

Antes de qualquer módulo do Zé ser importado, as três raízes (config, dados, estado) apontam para
uma pasta temporária: sem perfil, sem chaves e sem memória da máquina de quem roda os testes.
"""

import os
import tempfile

os.environ["JARVIS_RAIZ"] = tempfile.mkdtemp(prefix="ze-testes-")
os.environ.pop("JARVIS_PERFIL", None)
os.environ["JARVIS_FUSO"] = "America/Recife"  # as datas dos testes foram escritas nesse fuso

# Os testes do modo imersivo abrem a página num Chromium de verdade (sem tela) e levam minutos:
# rodam à parte, em `make check-imersivo`.
collect_ignore = [] if os.environ.get("ZE_TESTES_IMERSIVO") else ["imersivo"]
