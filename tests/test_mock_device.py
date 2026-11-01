"""Smoke tests for the local simulator, not for a real HA integration."""

import json
import unittest
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools.mock_device import DEMO_TOKEN, make_server


class MockDeviceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(port=0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def read(self, path, token=DEMO_TOKEN, method="GET"):
        headers = {} if token is None else {"Authorization": "Bearer " + token}
        request = Request(self.base + path, headers=headers, method=method)
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, json.load(response)
        except HTTPError as response:
            with response:
                return response.code, json.load(response)

    def test_requires_token_even_on_loopback(self):
        for token in [None, "invalid"]:
            self.assertEqual(self.read("/device-api/v1/state", token=token)[0], 401)
        self.assertEqual(self.read("/device-api/v1/info")[0], 200)

    def test_snapshot_identity_and_false_is_not_unknown(self):
        _, info = self.read("/device-api/v1/info")
        code, state = self.read("/device-api/v1/state")
        self.assertEqual(code, 200)
        self.assertEqual(state["device_uid"], info["device_uid"])
        self.assertTrue(state["pump_available"])
        self.assertIs(state["states"]["fault"], False)
        self.assertIsNone(state["temperatures"]["e_temp"])
        self.assertEqual(state["generated_at"], state["observed_at"])

    def test_unknown_endpoints_and_writes(self):
        self.assertEqual(self.read("/device-api/v1/provisioning")[0], 404)
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            self.assertEqual(self.read("/device-api/v1/state", method=method)[0], 405)

    def test_pump_offline_keeps_transport_but_no_invented_values(self):
        server = make_server(port=0, pump_offline=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/device-api/v1/state",
                headers={"Authorization": "Bearer " + DEMO_TOKEN},
            )
            with urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
                state = json.load(response)
            self.assertFalse(state["pump_available"])
            self.assertIsNone(state["observed_at"])
            self.assertTrue(
                all(value is None for value in state["temperatures"].values())
            )
            self.assertTrue(all(value is None for value in state["states"].values()))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
