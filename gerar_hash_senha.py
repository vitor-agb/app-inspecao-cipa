"""Gera a linha de configuração com hash PBKDF2-SHA256 para a seção [usuarios] de st.secrets.

Execução local: python gerar_hash_senha.py
A senha é lida sem eco no terminal e não é gravada em arquivo.
"""
import getpass
import hashlib
import os
import sys

ITERACOES = 600_000


def gerar_hash(senha):
    # Formato lido por verificar_senha em checklist.py: pbkdf2_sha256$iteracoes$sal_hex$hash_hex
    sal = os.urandom(16)
    derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, ITERACOES)
    return f"pbkdf2_sha256${ITERACOES}${sal.hex()}${derivado.hex()}"


if __name__ == "__main__":
    usuario = input("Usuário: ").strip().lower()
    senha = getpass.getpass("Senha: ")
    if senha != getpass.getpass("Confirme a senha: "):
        sys.exit("As senhas não conferem.")
    print(f'{usuario} = "{gerar_hash(senha)}"')
