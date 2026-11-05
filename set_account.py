import getpass

from database import save_user

telegram_id = int(input("Твой Telegram ID: ").strip())
login = input("Логин Platonus: ").strip()
password = getpass.getpass("Пароль Platonus: ")

if telegram_id <= 0 or not login or not password:
    raise SystemExit("ID должен быть положительным, логин и пароль — непустыми.")

save_user(telegram_id, login, password)

print("Данные Platonus сохранены.")