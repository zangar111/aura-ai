-- Напоминания по заметкам и команда /disconnect.
-- Выполнить один раз от имени владельца таблиц (postgres):
--   psql -U postgres -d aura_ai -f migrations/002_reminders_and_disconnect.sql

BEGIN;

ALTER TABLE public.notes
    ADD COLUMN IF NOT EXISTS remind_at timestamptz,
    ADD COLUMN IF NOT EXISTS reminded_at timestamptz;

CREATE INDEX IF NOT EXISTS notes_due_reminders_idx
    ON public.notes (remind_at)
    WHERE remind_at IS NOT NULL AND reminded_at IS NULL;

-- /disconnect удаляет сохранённый журнал пользователя.
GRANT DELETE ON public.grade_snapshots, public.grade_changes TO aura_bot;

COMMIT;
