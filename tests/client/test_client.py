"""Real loopback HTTP tests with aiohttp; no HA runtime or live SEMA."""

import asyncio
import json
import unittest
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch

import aiohttp
from aiohttp import web

from custom_components.sema.client import (
    AuthenticationError,
    CommunicationError,
    RateLimitError,
    SemaClient,
    _retry_after,
    normalize_base_url,
)
from custom_components.sema.protocol import ProtocolError, UnsupportedVersion
from tools.mock_device import DEMO_TOKEN, make_server

ROOT = Path(__file__).resolve().parents[2]


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = aiohttp.ClientSession()
        self.addAsyncCleanup(self.session.close)
        self.calls = []
        self.status = 200
        self.headers = {}
        self.body = None
        self.delay = 0
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", self.handle)
        runner = web.AppRunner(app)
        await runner.setup()
        self.addAsyncCleanup(runner.cleanup)
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = runner.addresses[0][1]
        self.base = f"http://127.0.0.1:{port}"
        self.client = SemaClient(self.session, self.base, DEMO_TOKEN)

    async def handle(self, request):
        self.calls.append(
            (request.method, request.path, request.headers.get("Authorization"))
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.body is not None:
            return web.Response(
                status=self.status, body=self.body, headers=self.headers
            )
        name = "info.json" if request.path.endswith("/info") else "state.json"
        return web.json_response(
            json.loads((ROOT / "fixtures" / name).read_text()),
            status=self.status,
            headers=self.headers,
        )

    async def test_read_only_session_and_identity(self):
        info = await self.client.async_get_info()
        state = await self.client.async_get_state(info)
        self.assertEqual(info.device_uid, state.device_uid)
        self.assertEqual(
            self.calls,
            [
                ("GET", "/device-api/v1/info", "Bearer " + DEMO_TOKEN),
                ("GET", "/device-api/v1/state", "Bearer " + DEMO_TOKEN),
            ],
        )
        self.assertFalse(self.session.closed)
        self.assertNotIn(DEMO_TOKEN, repr(self.client))

    async def test_http_errors_do_not_expose_credentials_or_body(self):
        for code, exception in [
            (401, AuthenticationError),
            (403, AuthenticationError),
            (404, UnsupportedVersion),
            (500, CommunicationError),
            (503, CommunicationError),
            (418, ProtocolError),
        ]:
            self.status = code
            self.body = DEMO_TOKEN.encode()
            with self.subTest(code=code), self.assertRaises(exception) as caught:
                await self.client.async_get_info()
            self.assertNotIn(DEMO_TOKEN, str(caught.exception))
            self.assertNotIn(self.base, str(caught.exception))

    async def test_redirect_not_followed(self):
        self.status = 302
        self.headers = {"Location": self.base + "/credential-sink"}
        with self.assertRaises(ProtocolError):
            await self.client.async_get_info()
        self.assertEqual(len(self.calls), 1)

    async def test_rate_limit_prevents_requests_until_deadline(self):
        self.status = 429
        self.headers = {"Retry-After": "120"}
        with self.assertRaises(RateLimitError) as caught:
            await self.client.async_get_info()
        self.assertEqual(caught.exception.retry_after_seconds, 120)
        with self.assertRaises(RateLimitError):
            await self.client.async_get_info()
        self.assertEqual(len(self.calls), 1)
        self.status = 200
        clock = SimpleNamespace(monotonic=lambda: self.client._retry_at + 1)
        with patch("custom_components.sema.client.time", clock):
            await self.client.async_get_info()
        self.assertEqual(len(self.calls), 2)

    async def test_retry_after_http_date_and_invalid_value(self):
        future = datetime.now(UTC) + timedelta(seconds=120)
        seconds = _retry_after(format_datetime(future, usegmt=True))
        self.assertGreater(seconds, 118)
        self.assertLessEqual(seconds, 120)
        for value in (None, "garbage", "-1", "NaN", "Infinity"):
            self.assertEqual(_retry_after(value), 30)

    async def test_json_size_and_content_validation(self):
        for body, content_type in [
            (b"<html>login</html>", "text/html"),
            (b"{broken", "application/json"),
            (b'{"api_version":NaN}', "application/json"),
            (b" " * 65537, "application/json"),
            (b"[]", "application/json"),
        ]:
            self.body = body
            self.headers = {"Content-Type": content_type}
            with self.subTest(body=body[:20]), self.assertRaises(ProtocolError):
                await self.client.async_get_info()

    async def test_timeout_transport_failure_and_cancellation(self):
        self.delay = 0.1
        client = SemaClient(self.session, self.base, DEMO_TOKEN, timeout_seconds=0.01)
        with self.assertRaises(CommunicationError):
            await client.async_get_info()
        task = asyncio.create_task(self.client.async_get_info())
        await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        with patch.object(
            self.session, "get", side_effect=aiohttp.ClientConnectionError(DEMO_TOKEN)
        ):
            with self.assertRaises(CommunicationError) as caught:
                await self.client.async_get_info()
            self.assertNotIn(DEMO_TOKEN, str(caught.exception))
            self.assertTrue(caught.exception.__suppress_context__)

    async def test_existing_loopback_simulator_online_and_offline(self):
        for offline, extended in (
            (False, False),
            (True, False),
            (False, True),
            (True, True),
        ):
            server = make_server(port=0, pump_offline=offline, extended=extended)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client = SemaClient(
                    self.session, f"http://127.0.0.1:{server.server_port}", DEMO_TOKEN
                )
                info = await client.async_get_info()
                state = await client.async_get_state(info)
                self.assertIs(state.pump_available, not offline)
                self.assertEqual(state.measurements_available(info), not offline)
                if extended:
                    self.assertTrue(state.configuration.is_fresh())
                    self.assertEqual(state.configuration.values["reference_temp"], 21)
                    self.assertEqual(
                        state.modes["season"], None if offline else "winter"
                    )
                bad = SemaClient(
                    self.session, f"http://127.0.0.1:{server.server_port}", "invalid"
                )
                with self.assertRaises(AuthenticationError):
                    await bad.async_get_info()
            finally:
                await asyncio.to_thread(server.shutdown)
                server.server_close()
                thread.join(timeout=2)

    async def test_url_and_token_validation(self):
        self.assertEqual(
            normalize_base_url(" http://sema.local:8124/ "), "http://sema.local:8124"
        )
        self.assertEqual(
            normalize_base_url("https://[::1]:8124/"), "https://[::1]:8124"
        )
        for value in (
            "sema.local",
            "ftp://sema",
            "http://user:secret@sema",
            "http://sema/path",
            "http://sema?token=secret",
            "http://sema/#fragment",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_base_url(value)
        for token in ("", "bad\r\nheader", "token with spaces"):
            with self.assertRaises(ValueError):
                SemaClient(self.session, self.base, token)
