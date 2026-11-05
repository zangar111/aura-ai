"""Cloudflare Tunnel для теста Mini App с этого компьютера.

Telegram открывает Mini App только по https. Бесплатный «быстрый»
туннель Cloudflare даёт временный адрес вида
https://<слова>.trycloudflare.com, который ведёт на локальный сервер.
Адрес меняется при каждом запуске — бот сам подставляет новый.
"""

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
CONNECTED_MARK = "Registered tunnel connection"

# QUIC (UDP) часто блокируют провайдеры и Wi-Fi сети;
# http2 идёт через обычный порт 443 и работает почти везде.
PROTOCOL = os.getenv("CLOUDFLARED_PROTOCOL", "http2")

KNOWN_PATHS = [
    Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe"),
    Path(r"C:\Program Files\cloudflared\cloudflared.exe"),
]


def find_cloudflared() -> str | None:
    configured = os.getenv("CLOUDFLARED_PATH")

    if configured and Path(configured).exists():
        return configured

    found = shutil.which("cloudflared")

    if found:
        return found

    return next((str(path) for path in KNOWN_PATHS if path.exists()), None)


class QuickTunnel:
    def __init__(self, port: int):
        self.port = port
        self.url: str | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task | None = None

    async def start(self, timeout: float = 60) -> str:
        executable = find_cloudflared()

        if executable is None:
            raise RuntimeError(
                "cloudflared не найден. Установи: "
                "winget install --id Cloudflare.cloudflared"
            )

        self._process = await asyncio.create_subprocess_exec(
            executable,
            "tunnel",
            "--no-autoupdate",
            "--protocol",
            PROTOCOL,
            "--url",
            f"http://127.0.0.1:{self.port}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        loop = asyncio.get_running_loop()
        found = loop.create_future()
        connected = loop.create_future()
        self._reader = asyncio.create_task(self._read_output(found, connected))

        try:
            self.url = await asyncio.wait_for(found, timeout)
            # Адрес выдаётся сразу, но работает только после подключения.
            await asyncio.wait_for(connected, timeout)
        except asyncio.TimeoutError:
            await self.stop()
            raise RuntimeError(
                "cloudflared не подключился за минуту. "
                "Проверь интернет или попробуй CLOUDFLARED_PROTOCOL=quic."
            )

        logger.info("Mini App: туннель %s", self.url)
        return self.url

    async def _read_output(self, found: asyncio.Future, connected: asyncio.Future):
        # Вывод нужно читать постоянно, иначе cloudflared застрянет.
        async for raw in self._process.stdout:
            line = raw.decode(errors="replace").strip()
            match = URL_PATTERN.search(line)

            if match and not found.done():
                found.set_result(match.group(0))

            if CONNECTED_MARK in line and not connected.done():
                connected.set_result(True)

            if " ERR " in line:
                logger.warning("cloudflared: %s", line)

        for future in (found, connected):
            if not future.done():
                future.set_exception(RuntimeError("cloudflared завершился."))

    async def stop(self):
        if self._process is not None and self._process.returncode is None:
            self._process.terminate()

            try:
                await asyncio.wait_for(self._process.wait(), 10)
            except asyncio.TimeoutError:
                self._process.kill()

        if self._reader is not None:
            self._reader.cancel()
