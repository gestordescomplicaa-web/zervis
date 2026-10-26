"""Cria a chave que assina o app de voz e a guarda nos segredos do repositório (uma vez só).

    uv run python android/criar-chave.py

A chave fica em `~/.config/zervis/ze-voz/` (0600), como cópia sua, e vai para os segredos
ZE_VOZ_KEYSTORE_B64 e ZE_VOZ_SENHA do repositório pelo `gh`. Com ela, a CI (app-voz.yml) assina
cada versão com a mesma chave, e o celular atualiza por cima. Não roda de novo sobre uma chave
que já existe: trocar de chave obriga a desinstalar o app no celular.
"""

import base64
import datetime
import os
import secrets
import subprocess
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

PASTA = Path.home() / ".config/zervis/ze-voz"


def criar(pasta: Path) -> tuple[bytes, str]:
    senha = secrets.token_urlsafe(24)
    chave = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Ze Voz")])
    agora = datetime.datetime.now(datetime.UTC)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - datetime.timedelta(days=1))
        .not_valid_after(agora + datetime.timedelta(days=365 * 30))
        .sign(chave, hashes.SHA256())
    )
    cifra = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .kdf_rounds(50000)
        .key_cert_algorithm(pkcs12.PBES.PBESv2SHA256AndAES256CBC)
        .hmac_hash(hashes.SHA256())
        .build(senha.encode())
    )
    loja = pkcs12.serialize_key_and_certificates(b"ze-voz", chave, certificado, None, cifra)
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    for arquivo, conteudo in (("assinatura.p12", loja), ("senha", senha.encode())):
        descritor = os.open(pasta / arquivo, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        os.write(descritor, conteudo)
        os.close(descritor)
    return loja, senha


def main() -> int:
    if (PASTA / "assinatura.p12").exists():
        print(f"A chave já existe em {PASTA}: nada foi mudado.")
        return 1
    loja, senha = criar(PASTA)
    for nome, valor in (
        ("ZE_VOZ_KEYSTORE_B64", base64.b64encode(loja).decode()),
        ("ZE_VOZ_SENHA", senha),
    ):
        subprocess.run(["gh", "secret", "set", nome], input=valor, text=True, check=True)  # noqa: S603, S607
    print(f"Chave criada em {PASTA} e guardada nos segredos do repositório.")
    print("A próxima compilação na master (app-voz.yml) já sai assinada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
