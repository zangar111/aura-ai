-- Исходная схема базы Aura AI (снята с рабочей базы 2026-10-22).
-- Выполнять от имени владельца базы. На существующей базе ничего не меняет.

BEGIN;

CREATE TABLE IF NOT EXISTS public.profiles (
    telegram_id   bigint PRIMARY KEY,
    timezone_name text,
    language_code text,
    created_at    timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.users (
    telegram_id        bigint PRIMARY KEY,
    platonus_login     text NOT NULL,
    password_encrypted text NOT NULL
);

CREATE TABLE IF NOT EXISTS public.notes (
    id            bigserial PRIMARY KEY,
    telegram_id   bigint NOT NULL REFERENCES public.profiles (telegram_id),
    topic         text NOT NULL,
    url           text,
    original_text text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.chat_history (
    id          bigserial PRIMARY KEY,
    telegram_id bigint NOT NULL REFERENCES public.profiles (telegram_id),
    role        text NOT NULL CHECK (role IN ('user', 'assistant')),
    content     text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS chat_history_user_id_idx
    ON public.chat_history (telegram_id, id DESC);

CREATE TABLE IF NOT EXISTS public.grade_snapshots (
    telegram_id bigint PRIMARY KEY
        REFERENCES public.profiles (telegram_id) ON DELETE CASCADE,
    grades      jsonb NOT NULL CHECK (jsonb_typeof(grades) = 'array'),
    fetched_at  timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.grade_changes (
    id          bigserial PRIMARY KEY,
    telegram_id bigint NOT NULL
        REFERENCES public.profiles (telegram_id) ON DELETE CASCADE,
    subject     text NOT NULL,
    stream      text NOT NULL,
    column_name text NOT NULL,
    old_value   text NOT NULL,
    new_value   text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('new', 'updated', 'removed')),
    detected_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notified_at timestamptz
);

CREATE INDEX IF NOT EXISTS grade_changes_user_time_idx
    ON public.grade_changes (telegram_id, detected_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS grade_changes_pending_idx
    ON public.grade_changes (detected_at, id)
    WHERE notified_at IS NULL;

-- Права пользователя бота (роль aura_bot должна существовать).
GRANT SELECT, INSERT, UPDATE, DELETE ON public.users, public.notes TO aura_bot;
GRANT SELECT, INSERT, UPDATE ON public.profiles TO aura_bot;
GRANT SELECT, INSERT ON public.chat_history TO aura_bot;
GRANT SELECT, INSERT, UPDATE ON public.grade_snapshots, public.grade_changes TO aura_bot;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO aura_bot;

COMMIT;
