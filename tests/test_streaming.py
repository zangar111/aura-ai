import asyncio
from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessageDraft

import ai_client
import streaming
from streaming import DraftStreamer, stop_generation


class FakeBot:
    def __init__(self, fail_with=None):
        self.drafts = []
        self.fail_with = fail_with

    async def send_message_draft(self, chat_id, draft_id, text, parse_mode, can_stop, keep_on_stop):
        if self.fail_with:
            raise self.fail_with
        self.drafts.append(text)
        assert can_stop and keep_on_stop


def test_thinking_status_and_throttled_text(monkeypatch):
    monkeypatch.setattr(streaming, "UPDATE_INTERVAL", 0.2)
    bot = FakeBot()

    async def run():
        async with DraftStreamer(bot, chat_id=1, language="kk") as streamer:
            await streamer.on_event("tool", "get_grades")
            # 50 обновлений подряд — в Telegram уйдёт только последнее.
            for size in range(1, 51):
                await streamer.on_event("text", "**Жауап** " + "сөз " * size)
            await asyncio.sleep(0.1)

    asyncio.run(run())

    assert bot.drafts[0] == ""  # «Thinking…»
    assert bot.drafts[1] == "<i>📊 Бағаларды қарап жатырмын…</i>"
    assert len(bot.drafts) == 3
    assert bot.drafts[2].startswith("<b>Жауап</b> сөз")


def test_stop_button_marks_streamer():
    bot = FakeBot()

    async def run():
        async with DraftStreamer(bot, chat_id=7, language="ru") as streamer:
            assert stop_generation(7, streamer.draft_id)
            assert streamer.should_stop()
            await streamer.on_event("text", "больше не показываем")
            return streamer

    streamer = asyncio.run(run())

    assert bot.drafts == [""]
    assert streamer.stopped_label == "⏹ Остановлено"
    # Ответ закончен — повторное нажатие ни на что не влияет.
    assert not stop_generation(7, streamer.draft_id)


def test_muted_after_grades_table():
    bot = FakeBot()

    async def run():
        async with DraftStreamer(bot, chat_id=1, language="kk") as streamer:
            streamer.muted = True
            await streamer.on_event("text", "Кесте жіберілді")
            await asyncio.sleep(0.05)

    asyncio.run(run())
    assert bot.drafts == [""]


def test_drafts_disabled_when_telegram_refuses():
    error = TelegramBadRequest(
        method=SendMessageDraft(chat_id=1, draft_id=1),
        message="Bad Request: method is not available",
    )
    bot = FakeBot(fail_with=error)

    async def run():
        async with DraftStreamer(bot, chat_id=1, language="kk") as streamer:
            await streamer.on_event("tool", "get_schedule")
            return streamer

    assert asyncio.run(run()).enabled is False


# ---------- Поток от ИИ ----------

def chunk(content=None, tool_calls=None, reasoning=None):
    delta = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        reasoning_content=reasoning,
        model_extra={},
    )
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def tool_part(index, id=None, name=None, arguments=None):
    return SimpleNamespace(
        index=index,
        id=id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class FakeStream:
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for item in self.chunks:
            yield item

    async def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.requests.append([dict(m) for m in kwargs["messages"]])
        assert kwargs["stream"] is True
        return FakeStream(self.rounds.pop(0))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def run_ask(monkeypatch, rounds, should_stop=None):
    client = FakeClient(rounds)
    monkeypatch.setattr(ai_client, "AsyncOpenAI", lambda **kwargs: client)
    monkeypatch.setattr(ai_client, "ai_settings", lambda: {"api_key": "k", "base_url": "u", "model": "m"})

    events, executed = [], []

    async def on_event(kind, value):
        events.append((kind, value))

    async def execute(name, arguments):
        executed.append((name, arguments))
        return {"ok": True}

    from datetime import datetime
    from zoneinfo import ZoneInfo

    answer = asyncio.run(ai_client.ask_ai(
        "?", execute_tool=execute, now=datetime(2026, 10, 23, 10, 0, tzinfo=ZoneInfo("Asia/Almaty")),
        on_event=on_event, should_stop=should_stop,
    ))
    return answer, events, executed, client


def test_tool_call_assembled_from_pieces(monkeypatch):
    rounds = [
        [
            chunk(reasoning="думаю…"),
            chunk(tool_calls=[tool_part(0, id="c1", name="get_sch", arguments='{"da')]),
            chunk(tool_calls=[tool_part(0, name="edule", arguments='y": "today"}')]),
        ],
        [chunk(content="Бүгін "), chunk(content="3 сабақ.")],
    ]
    answer, events, executed, client = run_ask(monkeypatch, rounds)

    assert executed == [("get_schedule", '{"day": "today"}')]
    assert answer == "Бүгін 3 сабақ."
    assert events == [("tool", "get_schedule"), ("text", "Бүгін "), ("text", "Бүгін 3 сабақ.")]

    # Во второй запрос ушли вызов функции, размышления и результат.
    assistant = client.requests[1][-2]
    assert assistant["tool_calls"][0]["function"]["name"] == "get_schedule"
    assert assistant["reasoning_content"] == "думаю…"
    assert client.requests[1][-1]["role"] == "tool"


def test_stop_returns_partial_text(monkeypatch):
    state = {"stop": False}

    rounds = [[chunk(content="Бірінші "), chunk(content="екінші "), chunk(content="үшінші")]]

    def should_stop():
        # «Нажали стоп» после первого кусочка.
        was = state["stop"]
        state["stop"] = True
        return was

    answer, events, executed, _ = run_ask(monkeypatch, rounds, should_stop=should_stop)
    assert answer == "Бірінші екінші "
