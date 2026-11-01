"""Protocol validation without HA or external dependencies."""

import copy
import json
import unittest
from datetime import timedelta
from pathlib import Path

from custom_components.sema.protocol import (
    IdentityMismatch,
    ProtocolError,
    UnsupportedVersion,
    parse_info,
    parse_state,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture(name):
    return json.loads((ROOT / "fixtures" / name).read_text())


class ProtocolTests(unittest.TestCase):
    def test_extended_configuration_is_independent_and_old_payload_stays_supported(
        self,
    ):
        info = parse_info(fixture("info_extended.json"))
        payload = fixture("state_extended.json")
        data = parse_state(payload, info)
        self.assertEqual(data.modes["season"], "winter")
        self.assertEqual(data.configuration.values["reference_temp"], 21)
        self.assertEqual(data.configuration.schedule["mon"], (("06:00", "08:00"),))
        for group in ("temperatures", "states", "modes"):
            payload[group] = dict.fromkeys(payload[group])
        payload["pump_available"] = False
        payload["power_percent"] = None
        data = parse_state(payload, info)
        self.assertTrue(data.configuration.is_fresh(now=data.generated_at))
        self.assertFalse(data.measurements_available(info, now=data.generated_at))
        self.assertIsNone(parse_state(fixture("state.json"), self.info).configuration)

    def test_extended_configuration_schema_and_unknown_modes(self):
        info = parse_info(fixture("info_extended.json"))
        payload = fixture("state_extended.json")
        payload["modes"]["season"] = "future-season"
        self.assertIsNone(parse_state(payload, info).modes["season"])
        for key, value in (
            ("reference_temp", True),
            ("reference_temp", float("nan")),
            ("limit_heat_percent", 101),
        ):
            bad = copy.deepcopy(payload)
            bad["configuration"]["values"][key] = value
            with self.assertRaises(ProtocolError):
                parse_state(bad, info)
        for interval in (
            {"from": "25:00", "to": "26:00"},
            {"from": "06:00", "to": "05:00"},
            {"from": "06:01", "to": "07:00"},
        ):
            bad = copy.deepcopy(payload)
            bad["configuration"]["schedule"]["mon"] = [interval]
            with self.assertRaises(ProtocolError):
                parse_state(bad, info)
        payload["configuration"]["available"] = False
        with self.assertRaises(ProtocolError):
            parse_state(payload, info)

    def setUp(self):
        self.info_data = fixture("info.json")
        self.info = parse_info(self.info_data)
        self.data = fixture("state.json")

    def test_fixtures_preserve_false_zero_and_unknown(self):
        self.data["power_percent"] = 0
        self.data["temperatures"]["outdoor_temp"] = 0
        state = parse_state(self.data, self.info)
        self.assertEqual(state.power_percent, 0)
        self.assertEqual(state.temperatures["outdoor_temp"], 0)
        self.assertIs(state.states["fault"], False)
        self.assertIsNone(state.temperatures["e_temp"])
        offline = parse_state(fixture("state_pump_unavailable.json"), self.info)
        self.assertFalse(offline.measurements_available(self.info))
        self.assertIs(offline.pump_available, False)
        with self.assertRaises(TypeError):
            state.temperatures["e_temp"] = 1

    def test_freshness_uses_observation_and_rejects_future_clock(self):
        state = parse_state(self.data, self.info)
        observed = state.observed_at
        self.assertTrue(state.measurements_available(self.info, now=observed))
        self.assertTrue(state.is_fresh(60, now=observed + timedelta(seconds=60)))
        self.assertFalse(state.is_fresh(60, now=observed + timedelta(seconds=61)))
        self.assertFalse(state.is_fresh(60, now=observed - timedelta(seconds=6)))
        self.data["generated_at"] = "2026-11-01T13:00:00Z"
        stale = parse_state(self.data, self.info)
        self.assertFalse(
            stale.measurements_available(self.info, now=stale.generated_at)
        )

    def test_empty_snapshot_and_partial_data(self):
        data = fixture("state_pump_unavailable.json")
        data["pump_available"] = None
        state = parse_state(data, self.info)
        self.assertIsNone(state.pump_available)
        self.assertFalse(state.is_fresh(60))
        self.data["temperatures"]["equitherm_temp"] = None
        del self.data["states"]["heating"]
        state = parse_state(self.data, self.info)
        self.assertEqual(state.temperatures["indoor_temp"], 22.3)
        self.assertIsNone(state.states["heating"])

    def test_additive_fields_and_unknown_capabilities_are_accepted(self):
        self.info_data["capabilities"] = ["future.sensor"]
        self.info_data["firmware_version"] = None
        self.info_data["device_id"] = None
        info = parse_info(self.info_data)
        self.assertEqual(info.capabilities, {"future.sensor"})
        self.data["future"] = {"anything": True}
        self.data["temperatures"]["future"] = "new meaning"
        self.assertEqual(parse_state(self.data, info).device_uid, info.device_uid)

    def test_version_and_identity(self):
        for payload, parser in [
            (self.info_data, parse_info),
            (self.data, lambda d: parse_state(d, self.info)),
        ]:
            payload["api_version"] = 2
            with self.assertRaises(UnsupportedVersion):
                parser(payload)
            payload["api_version"] = True
            with self.assertRaises(ProtocolError):
                parser(payload)
        self.data["api_version"] = 1
        self.data["device_uid"] = "00000000-0000-4000-8000-000000000002"
        with self.assertRaises(IdentityMismatch):
            parse_state(self.data, self.info)

    def test_malformed_info(self):
        for key, value in [
            ("api_version", None),
            ("device_uid", "address"),
            ("capabilities", "temperature"),
            ("capabilities", [1]),
            ("recommended_poll_interval_seconds", True),
            ("max_age_seconds", 10),
            ("name", ""),
            ("model", 12),
        ]:
            with self.subTest(key=key, value=value):
                data = copy.deepcopy(self.info_data)
                data[key] = value
                with self.assertRaises(ProtocolError):
                    parse_info(data)

    def test_malformed_state(self):
        for key, value in [
            ("generated_at", "2026-11-01T12:00:00"),
            ("generated_at", "2026-11-01T13:00:00+01:00"),
            ("observed_at", None),
            ("observed_at", "2026-11-01T13:00:00Z"),
            ("pump_available", 1),
            ("pump_available", False),
            ("temperatures", []),
            ("states", []),
            ("errors", {}),
            ("errors", [{"code": 1}]),
            ("power_percent", True),
            ("power_percent", -1),
            ("power_percent", 101),
            ("power_percent", float("inf")),
        ]:
            with self.subTest(key=key, value=value):
                data = copy.deepcopy(self.data)
                data[key] = value
                with self.assertRaises(ProtocolError):
                    parse_state(data, self.info)
        for value in ("22°C", True, float("nan"), 10**400):
            self.data["temperatures"]["indoor_temp"] = value
            with self.assertRaises(ProtocolError):
                parse_state(self.data, self.info)
        self.data = fixture("state.json")
        self.data["states"]["heating"] = "false"
        with self.assertRaises(ProtocolError):
            parse_state(self.data, self.info)
