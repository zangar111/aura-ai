from functools import cache

from cryptography.fernet import Fernet

from config import SECRETS_DIR

key_path = SECRETS_DIR / "platonus.key"


@cache
def get_cipher() -> Fernet:
    # Ключ читается при первом использовании, а не при импорте:
    # так модули можно импортировать в тестах без ключа.
    return Fernet(key_path.read_bytes())


def encrypt_password(password: str) -> str:
    return get_cipher().encrypt(password.encode("utf-8")).decode("ascii")


def decrypt_password(encrypted_password: str) -> str:
    return get_cipher().decrypt(encrypted_password.encode("ascii")).decode("utf-8")


if __name__ == "__main__":
    original = "test_password_123"
    encrypted = encrypt_password(original)
    restored = decrypt_password(encrypted)

    print("Шифрование работает:", restored == original)
