from database import get_user

user = get_user(-1)

if user is None:
    print("Тестовый пользователь не найден.")
else:
    login, password = user
    print("Логин:", login)
    print("Пароль восстановлен:", password == "test_password_123")