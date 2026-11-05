import asyncio
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from aiohttp.test_utils import TestClient, TestServer

from conftest import make_row
from dashboard import build_subjects
from webapp_server import create_app, telegram_user_id

TOKEN = "123456:test-token"


def init_data(user_id=42, token=TOKEN, age_seconds=0, with_user=True):
    params = {"auth_date": str(int(time.time()) - age_seconds), "query_id": "q"}

    if with_user:
        params["user"] = json.dumps({"id": user_id, "first_name": "T"}, separators=(",", ":"))

    check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(params)


def test_valid_init_data_gives_user_id():
    assert telegram_user_id(TOKEN, init_data(user_id=7)) == 7


@pytest.mark.parametrize(
    "data",
    [
        init_data(token="999:other-bot"),  # подписано другим ботом
        init_data(age_seconds=2 * 24 * 3600),  # устарело
        init_data(with_user=False),
        init_data().replace("%22id%22%3A42", "%22id%22%3A43"),  # подменён id
        "",
    ],
)
def test_bad_init_data_is_rejected(data):
    with pytest.raises(ValueError):
        telegram_user_id(TOKEN, data)


def run_client(check):
    async def load_dashboard(user_id):
        return {"user": user_id, "subjects": []}

    async def main():
        client = TestClient(TestServer(create_app(TOKEN, load_dashboard)))
        await client.start_server()
        try:
            await check(client)
        finally:
            await client.close()

    asyncio.run(main())


def test_api_returns_only_own_data():
    async def check(client):
        response = await client.get("/api/me", headers={"Authorization": f"tma {init_data(user_id=5)}"})
        assert response.status == 200
        assert (await response.json())["user"] == 5

    run_client(check)


def test_api_rejects_missing_or_forged_auth():
    async def check(client):
        assert (await client.get("/api/me")).status == 401
        forged = init_data(token="999:other-bot")
        response = await client.get("/api/me", headers={"Authorization": f"tma {forged}"})
        assert response.status == 401

    run_client(check)


def test_index_page_is_served_with_version():
    async def check(client):
        response = await client.get("/")
        text = await response.text()
        assert response.status == 200
        assert "{{version}}" not in text and "/static/app.js?v=" in text
        assert (await client.get("/static/app.js")).status == 200

    run_client(check)


def test_journal_button_only_for_stable_address():
    from grades_service import chart_button
    from webapp_server import set_public_url

    def buttons():
        return [button.text for button in chart_button("ru").inline_keyboard[0]]

    try:
        set_public_url("https://temp.trycloudflare.com", stable=False)
        assert buttons() == ["📈 График прогресса"]

        set_public_url("https://aura.example.kz", stable=True)
        assert buttons() == ["📈 График прогресса", "📱 Журнал"]
    finally:
        set_public_url(None)


def test_build_subjects_for_mini_app():
    subjects, last_week = build_subjects([
        make_row(stream="BT 1-L", **{"1": "н.п.", "2": "90", "ТК1": "80"}),
        make_row(stream="BT 1-Lab", **{"1": "70", "16": "80"}),
    ])

    [subject] = subjects
    assert subject["name"] == "Блокчейн технологии"
    assert subject["average"] == 80.0
    assert subject["absences"] == 1
    assert last_week == 16
    lecture = next(t for t in subject["types"] if t["type"] == "L")
    assert lecture["weeks"] == {"1": "absent", "2": 90.0}
    assert lecture["totals"] == {"ТК1": "80"}
