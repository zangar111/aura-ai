from contextlib import contextmanager
from datetime import datetime

from psycopg import Error as DatabaseError
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from config import db_settings
from grade_changes import compare_grades
from security import encrypt_password, decrypt_password

__all__ = ["DatabaseError"]

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool

    if _pool is None:
        _pool = ConnectionPool(
            kwargs=db_settings(),
            min_size=1,
            max_size=5,
            timeout=10,
            open=True,
        )

    return _pool


@contextmanager
def connect():
    """Соединение из пула. При выходе — COMMIT, при ошибке — ROLLBACK."""
    with _get_pool().connection() as connection:
        yield connection


def close_pool():
    global _pool

    if _pool is not None:
        _pool.close()
        _pool = None


def save_dialogue(
    telegram_id: int,
    user_text: str,
    assistant_text: str,
):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.profiles (telegram_id)
                VALUES (%s)
                ON CONFLICT (telegram_id) DO NOTHING
                """,
                (telegram_id,),
            )

            cursor.execute(
                """
                INSERT INTO public.chat_history
                    (telegram_id, role, content)
                VALUES
                    (%s, 'user', %s),
                    (%s, 'assistant', %s)
                """,
                (
                    telegram_id,
                    user_text,
                    telegram_id,
                    assistant_text,
                ),
            )

def get_chat_history(telegram_id: int) -> list[dict[str, str]]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT role, content
                FROM public.chat_history
                WHERE telegram_id = %s
                ORDER BY id DESC
                LIMIT 20
                """,
                (telegram_id,),
            )
            rows = cursor.fetchall()

    return [
        {"role": role, "content": content}
        for role, content in reversed(rows)
    ]

def save_user(telegram_id: int, login: str, password: str):
    encrypted_password = encrypt_password(password)

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.users
                    (telegram_id, platonus_login, password_encrypted)
                VALUES (%s, %s, %s)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    platonus_login = EXCLUDED.platonus_login,
                    password_encrypted = EXCLUDED.password_encrypted
                """,
                (telegram_id, login, encrypted_password),
            )

def get_user(telegram_id: int):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT platonus_login, password_encrypted
                FROM public.users
                WHERE telegram_id = %s
                """,
                (telegram_id,),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    login = row[0]
    password = decrypt_password(row[1])
    return login, password


def create_profile(telegram_id: int):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.profiles (telegram_id)
                VALUES (%s)
                ON CONFLICT (telegram_id) DO NOTHING
                """,
                (telegram_id,),
            )

def save_note(
    telegram_id: int,
    topic: str,
    original_text: str,
    url: str | None = None,
    remind_at: datetime | None = None,
) -> int:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.notes
                    (telegram_id, topic, url, original_text, remind_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (telegram_id, topic, url, original_text, remind_at),
            )
            note_id = cursor.fetchone()[0]

    return note_id

def get_notes(telegram_id: int) -> list[dict]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, topic, url, original_text, remind_at
                FROM public.notes
                WHERE telegram_id = %s
                ORDER BY id DESC
                """,
                (telegram_id,),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "topic": row[1],
            "url": row[2],
            "original_text": row[3],
            "remind_at": row[4],
        }
        for row in rows
    ]

def delete_note(telegram_id: int, note_id: int) -> bool:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM public.notes
                WHERE id = %s AND telegram_id = %s
                RETURNING id
                """,
                (note_id, telegram_id),
            )
            deleted = cursor.fetchone()

    return deleted is not None

def update_note(
    telegram_id: int,
    note_id: int,
    topic: str,
    original_text: str,
    url: str | None,
    remind_at: datetime | None = None,
) -> bool:
    with connect() as connection:
        with connection.cursor() as cursor:
            # При новом времени напоминание должно сработать снова.
            cursor.execute(
                """
                UPDATE public.notes
                SET topic = %s,
                    original_text = %s,
                    url = %s,
                    reminded_at = CASE
                        WHEN remind_at IS DISTINCT FROM %s::timestamptz THEN NULL
                        ELSE reminded_at
                    END,
                    remind_at = %s::timestamptz
                WHERE id = %s AND telegram_id = %s
                RETURNING id
                """,
                (
                    topic,
                    original_text,
                    url,
                    remind_at,
                    remind_at,
                    note_id,
                    telegram_id,
                ),
            )
            updated = cursor.fetchone()

    return updated is not None


def save_grade_snapshot(
    telegram_id: int,
    grades: list[dict],
    *,
    reset: bool = False,
) -> list[dict]:
    """Сохраняет журнал и возвращает найденные изменения.

    reset=True принимает журнал как новую отправную точку
    без сравнения — например, после смены семестра.
    """
    if not isinstance(grades, list) or not grades:
        raise ValueError("Журнал должен быть непустым списком.")

    with connect() as connection:
        with connection.cursor() as cursor:
            # Обновления одного пользователя выполняются по очереди.
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s::bigint)",
                (telegram_id,),
            )

            cursor.execute(
                """
                INSERT INTO public.profiles (telegram_id)
                VALUES (%s)
                ON CONFLICT (telegram_id) DO NOTHING
                """,
                (telegram_id,),
            )

            cursor.execute(
                """
                SELECT grades
                FROM public.grade_snapshots
                WHERE telegram_id = %s
                """,
                (telegram_id,),
            )
            row = cursor.fetchone()
            old_grades = row[0] if row is not None else None

            changes = compare_grades(
                None if reset else old_grades,
                grades,
            )

            if changes:
                cursor.executemany(
                    """
                    INSERT INTO public.grade_changes (
                        telegram_id, subject, stream, column_name,
                        old_value, new_value, kind
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            telegram_id,
                            change["subject"],
                            change["stream"],
                            change["column"],
                            change["old_value"],
                            change["new_value"],
                            change["kind"],
                        )
                        for change in changes
                    ],
                )

            cursor.execute(
                """
                INSERT INTO public.grade_snapshots
                    (telegram_id, grades)
                VALUES (%s, %s)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    grades = EXCLUDED.grades,
                    fetched_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, Jsonb(grades)),
            )

    return changes

def get_grade_snapshot(
    telegram_id: int,
) -> tuple[list[dict], datetime] | None:
    """Последний сохранённый журнал и время его загрузки."""
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT grades, fetched_at
                FROM public.grade_snapshots
                WHERE telegram_id = %s
                """,
                (telegram_id,),
            )
            row = cursor.fetchone()

    return (row[0], row[1]) if row is not None else None


def get_grade_changes_since(telegram_id: int, days: int) -> list[dict]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT subject, stream, column_name,
                       old_value, new_value, kind, detected_at
                FROM public.grade_changes
                WHERE telegram_id = %s
                  AND detected_at >=
                      CURRENT_TIMESTAMP - make_interval(days => %s::int)
                ORDER BY detected_at DESC, id DESC
                LIMIT 100
                """,
                (telegram_id, days),
            )
            rows = cursor.fetchall()

    return [
        {
            "subject": row[0],
            "stream": row[1],
            "column": row[2],
            "old_value": row[3],
            "new_value": row[4],
            "kind": row[5],
            "detected_at": row[6],
        }
        for row in rows
    ]


def get_recent_grade_changes(
    telegram_id: int,
) -> list[dict]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (
                    subject, stream, column_name
                )
                    subject,
                    stream,
                    column_name,
                    old_value,
                    new_value,
                    kind,
                    detected_at
                FROM public.grade_changes
                WHERE telegram_id = %s
                  AND detected_at >=
                      CURRENT_TIMESTAMP - INTERVAL '24 hours'
                ORDER BY
                    subject,
                    stream,
                    column_name,
                    detected_at DESC,
                    id DESC
                """,
                (telegram_id,),
            )
            rows = cursor.fetchall()

    return [
        {
            "subject": row[0],
            "stream": row[1],
            "column": row[2],
            "old_value": row[3],
            "new_value": row[4],
            "kind": row[5],
            "detected_at": row[6],
        }
        for row in rows
    ]


def get_pending_grade_changes(telegram_id: int) -> list[dict]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    subject,
                    stream,
                    column_name,
                    old_value,
                    new_value,
                    kind
                FROM public.grade_changes
                WHERE telegram_id = %s
                  AND notified_at IS NULL
                ORDER BY detected_at, id
                LIMIT 200
                """,
                (telegram_id,),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "subject": row[1],
            "stream": row[2],
            "column": row[3],
            "old_value": row[4],
            "new_value": row[5],
            "kind": row[6],
        }
        for row in rows
    ]

def mark_grade_changes_notified(
    telegram_id: int,
    change_ids: list[int],
) -> None:
    if not change_ids:
        return

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.grade_changes
                SET notified_at = CURRENT_TIMESTAMP
                WHERE telegram_id = %s
                  AND id = ANY(%s::bigint[])
                  AND notified_at IS NULL
                """,
                (telegram_id, change_ids),
            )

def get_timezone(telegram_id: int) -> str | None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT timezone_name FROM public.profiles "
                "WHERE telegram_id = %s",
                (telegram_id,),
            )
            row = cursor.fetchone()

    return row[0] if row is not None else None


def get_language(telegram_id: int) -> str | None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT language_code FROM public.profiles "
                "WHERE telegram_id = %s",
                (telegram_id,),
            )
            row = cursor.fetchone()

    return row[0] if row is not None else None


def set_language(telegram_id: int, language_code: str):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.profiles (telegram_id, language_code)
                VALUES (%s, %s)
                ON CONFLICT (telegram_id)
                DO UPDATE SET language_code = EXCLUDED.language_code
                """,
                (telegram_id, language_code),
            )


def get_due_reminders(
    limit: int = 50,
    exclude_ids: list[int] | None = None,
) -> list[dict]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, telegram_id, topic, url, original_text
                FROM public.notes
                WHERE remind_at <= CURRENT_TIMESTAMP
                  AND reminded_at IS NULL
                  AND NOT (telegram_id = ANY(%s::bigint[]))
                ORDER BY remind_at, id
                LIMIT %s
                """,
                (exclude_ids or [], limit),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "telegram_id": row[1],
            "topic": row[2],
            "url": row[3],
            "original_text": row[4],
        }
        for row in rows
    ]


def mark_reminded(note_id: int) -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.notes SET reminded_at = CURRENT_TIMESTAMP "
                "WHERE id = %s",
                (note_id,),
            )


def check_schema() -> list[str]:
    """Возвращает файлы миграций, которые ещё не выполнены."""
    missing = []

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND (
                      (table_name = 'notes'
                       AND column_name IN ('remind_at', 'reminded_at'))
                      OR (table_name = 'profiles'
                       AND column_name IN ('digest_enabled', 'digest_time',
                                           'lesson_reminders', 'last_digest_on'))
                      OR table_name = 'schedule_snapshots'
                  )
                """
            )
            columns = cursor.fetchall()

    if sum(1 for table, _ in columns if table == "notes") != 2:
        missing.append("migrations/002_reminders_and_disconnect.sql")

    if (
        sum(1 for table, _ in columns if table == "profiles") != 4
        or not any(table == "schedule_snapshots" for table, _ in columns)
    ):
        missing.append("migrations/003_schedule_and_digest.sql")

    return missing


def save_schedule(telegram_id: int, schedule: dict):
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.profiles (telegram_id)
                VALUES (%s)
                ON CONFLICT (telegram_id) DO NOTHING
                """,
                (telegram_id,),
            )
            cursor.execute(
                """
                INSERT INTO public.schedule_snapshots (telegram_id, schedule)
                VALUES (%s, %s)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    schedule = EXCLUDED.schedule,
                    fetched_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, Jsonb(schedule)),
            )


def get_schedule(telegram_id: int) -> tuple[dict, datetime] | None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT schedule, fetched_at
                FROM public.schedule_snapshots
                WHERE telegram_id = %s
                """,
                (telegram_id,),
            )
            row = cursor.fetchone()

    return (row[0], row[1]) if row is not None else None


DIGEST_FIELDS = ("digest_enabled", "digest_time", "lesson_reminders")


def get_digest_settings(telegram_id: int) -> dict:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.profiles (telegram_id)
                VALUES (%s)
                ON CONFLICT (telegram_id) DO NOTHING
                """,
                (telegram_id,),
            )
            cursor.execute(
                """
                SELECT digest_enabled, digest_time, lesson_reminders
                FROM public.profiles
                WHERE telegram_id = %s
                """,
                (telegram_id,),
            )
            row = cursor.fetchone()

    return dict(zip(DIGEST_FIELDS, row))


def update_digest_settings(telegram_id: int, **changes):
    fields = {key: value for key, value in changes.items() if key in DIGEST_FIELDS}

    if not fields:
        return

    # Имена столбцов — только из DIGEST_FIELDS, значения — параметрами.
    assignments = ", ".join(f"{name} = %s" for name in fields)

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE public.profiles SET {assignments} WHERE telegram_id = %s",
                (*fields.values(), telegram_id),
            )


def get_schedule_recipients() -> list[dict]:
    """Пользователи с расписанием и их настройки дайджеста."""
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.telegram_id, p.timezone_name, p.language_code,
                       p.digest_enabled, p.digest_time, p.lesson_reminders,
                       p.last_digest_on, s.schedule
                FROM public.profiles AS p
                JOIN public.schedule_snapshots AS s USING (telegram_id)
                WHERE p.telegram_id > 0
                """
            )
            rows = cursor.fetchall()

    names = (
        "telegram_id", "timezone_name", "language_code", "digest_enabled",
        "digest_time", "lesson_reminders", "last_digest_on", "schedule",
    )
    return [dict(zip(names, row)) for row in rows]


def mark_digest_sent(telegram_id: int, day) -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.profiles SET last_digest_on = %s WHERE telegram_id = %s",
                (day, telegram_id),
            )


def get_notes_due_between(telegram_id: int, start: datetime, end: datetime) -> list[dict]:
    """Напоминания по заметкам в промежутке — для дайджеста."""
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT topic, remind_at
                FROM public.notes
                WHERE telegram_id = %s
                  AND remind_at >= %s AND remind_at < %s
                ORDER BY remind_at
                LIMIT 10
                """,
                (telegram_id, start, end),
            )
            rows = cursor.fetchall()

    return [{"topic": row[0], "remind_at": row[1]} for row in rows]


def get_connected_user_ids() -> list[int]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT telegram_id
                FROM public.users
                WHERE telegram_id > 0
                ORDER BY telegram_id
                """
            )
            rows = cursor.fetchall()

    return [row[0] for row in rows]