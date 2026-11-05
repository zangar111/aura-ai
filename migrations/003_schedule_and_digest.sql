-- Расписание занятий и утренний дайджест.
-- Выполнить один раз от имени владельца таблиц (postgres):
--   psql -U postgres -p 5433 -d aura_ai -f migrations/003_schedule_and_digest.sql

BEGIN;

-- Последнее загруженное расписание пользователя.
CREATE TABLE IF NOT EXISTS public.schedule_snapshots (
    telegram_id bigint PRIMARY KEY
        REFERENCES public.profiles (telegram_id) ON DELETE CASCADE,
    schedule    jsonb NOT NULL CHECK (jsonb_typeof(schedule) = 'object'),
    fetched_at  timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

GRANT SELECT, INSERT, UPDATE ON public.schedule_snapshots TO aura_bot;

-- Настройки дайджеста и напоминаний о парах.
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS digest_enabled   boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS digest_time      time    NOT NULL DEFAULT '07:30',
    ADD COLUMN IF NOT EXISTS lesson_reminders boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS last_digest_on   date;

COMMIT;
