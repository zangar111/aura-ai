from pathlib import Path
from cryptography.fernet import Fernet

folder = Path(__file__).resolve().parent / ".secrets"
folder.mkdir(exist_ok=True)

key_path = folder / "platonus.key"

try:
    with key_path.open("xb") as file:
        file.write(Fernet.generate_key())
    print("Ключ шифрования создан.")
except FileExistsError:
    print("Ключ уже существует. Сохраняем прежний.")