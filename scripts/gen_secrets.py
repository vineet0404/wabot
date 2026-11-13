"""Production ke secrets banata hai. Output .env.production me paste karo. Kisi ko mat dikhao.

Chalao: python scripts/gen_secrets.py
Sirf cryptography chahiye (pip install cryptography).
"""

import secrets
import string

from cryptography.fernet import Fernet


def random_text(n):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def main():
    print(f"DJANGO_SECRET_KEY={secrets.token_urlsafe(64)}")
    print(f"FIELD_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
    print(f"POSTGRES_PASSWORD={random_text(32)}")
    print(f"META_VERIFY_TOKEN={random_text(32)}")
    print(f"ADMIN_URL=panel-{random_text(10).lower()}/")


if __name__ == "__main__":
    main()
