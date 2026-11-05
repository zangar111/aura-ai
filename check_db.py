import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv(
    Path(__file__).with_name(".env"),
    encoding="utf-8-sig",
    interpolate=False,
)

with psycopg.connect(
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    connect_timeout=5,
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user")
        print("Пользователь:", cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM public.users")
        print("Записей в users:", cursor.fetchone()[0])