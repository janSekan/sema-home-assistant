"""Typed v1 payloads, independent of Home Assistant and HTTP transport."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Literal, cast, overload
from uuid import UUID

from .const import API_VERSION

TEMPERATURE_KEYS = (
    "outdoor_temp",
    "indoor_temp",
    "water_temp",
    "heat_temp",
    "equitherm_temp",
    "exchanger_temp",
    "e_temp",
    "f_temp",
    "g_temp",
)
STATE_KEYS = (
    "heating",
    "dhw",
    "defrost",
    "fault",
    "power_on",
    "setback",
    "high_tariff",
)
MODE_OPTIONS = {
    "operating_mode": ("heating", "cooling"),
    "season": ("summer", "winter"),
    "activity": ("heating", "cooling", "off", "defrost", "fault"),
    "heat_source": ("compressor", "bivalent_1", "bivalent_2", "summer"),
    "dhw_mode": ("standby", "heating", "electric_heating"),
}
CONFIG_TEMPERATURES = (
    "reference_temp",
    "min_indoor_cool",
    "max_indoor_heat",
    "min_water_temp",
    "max_water_temp",
    "cooling_water_temp",
    "bivalent_temp",
    "curve_minus20",
    "curve_minus12",
    "curve_minus4",
    "curve_plus4",
    "curve_plus12",
    "curve_plus20",
    "setback_heat",
    "setback_cool",
)
CONFIG_PERCENTAGES = ("limit_water_percent", "limit_heat_percent", "limit_cool_percent")
CONFIG_KEYS = (
    *CONFIG_TEMPERATURES,
    *CONFIG_PERCENTAGES,
    "regulation_constant",
    "dhw_time_limit_minutes",
)
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class SemaError(Exception):
    """Public errors contain no response bodies, credentials or URLs."""


class ProtocolError(SemaError):
    """Invalid response schema."""


class UnsupportedVersion(SemaError):
    """Unsupported or missing device API."""


class IdentityMismatch(SemaError):
    """The address now belongs to a different device."""


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ProtocolError("Expected JSON object")
    return cast(dict[str, object], value)


@overload
def _text(value: object, *, nullable: Literal[False] = False) -> str: ...


@overload
def _text(value: object, *, nullable: Literal[True]) -> str | None: ...


def _text(value: object, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise ProtocolError("Invalid text field")
    return value


def _uid(value: object) -> str:
    try:
        return str(UUID(_text(value)))
    except (ValueError, AttributeError):
        raise ProtocolError("Invalid device identity") from None


def _version(data: Mapping[str, object]) -> None:
    value = data.get("api_version")
    if type(value) is not int:
        raise ProtocolError("Missing or invalid API version")
    if value != API_VERSION:
        raise UnsupportedVersion("Unsupported API version")


def _seconds(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 86400:
        raise ProtocolError("Invalid timing metadata")
    return value


@overload
def _timestamp(value: object, *, nullable: Literal[False] = False) -> datetime: ...


@overload
def _timestamp(value: object, *, nullable: Literal[True]) -> datetime | None: ...


def _timestamp(value: object, *, nullable: bool = False) -> datetime | None:
    if nullable and value is None:
        return None
    try:
        result = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
        if result.utcoffset() != timedelta(0):
            raise ValueError
        return result.astimezone(UTC)
    except ValueError:
        raise ProtocolError("Expected explicit UTC timestamp") from None


def _number(value: object) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError("Invalid numeric field")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ProtocolError("Invalid numeric field")
    return value


def _boolean(value: object) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ProtocolError("Invalid boolean field")
    return value


@dataclass(frozen=True)
class DeviceInfo:
    device_uid: str
    device_id: str | None
    name: str
    manufacturer: str
    model: str
    firmware_version: str | None
    capabilities: frozenset[str]
    recommended_poll_interval_seconds: int
    max_age_seconds: int


@dataclass(frozen=True)
class ConfigurationState:
    available: bool
    observed_at: datetime | None
    max_age_seconds: int
    values: Mapping[str, int | float | None]
    schedule: Mapping[str, tuple[tuple[str, str], ...]] | None

    def is_fresh(self, *, now: datetime | None = None) -> bool:
        if not self.available or self.observed_at is None:
            return False
        age = ((now or datetime.now(UTC)) - self.observed_at).total_seconds()
        return -5 <= age <= self.max_age_seconds


@dataclass(frozen=True)
class DeviceState:
    device_uid: str
    generated_at: datetime
    observed_at: datetime | None
    pump_available: bool | None
    temperatures: Mapping[str, int | float | None]
    power_percent: int | float | None
    states: Mapping[str, bool | None]
    error_codes: tuple[str, ...]
    modes: Mapping[str, str | None] = field(
        default_factory=lambda: MappingProxyType({})
    )
    configuration: ConfigurationState | None = None

    def is_fresh(self, max_age_seconds: int, *, now: datetime | None = None) -> bool:
        """Freshness is separate from transport and pump reachability."""
        if self.observed_at is None:
            return False
        age = ((now or datetime.now(UTC)) - self.observed_at).total_seconds()
        return -5 <= age <= max_age_seconds

    def measurements_available(
        self, info: DeviceInfo, *, now: datetime | None = None
    ) -> bool:
        return self.pump_available is True and self.is_fresh(
            info.max_age_seconds, now=now
        )


def parse_info(payload: object) -> DeviceInfo:
    data = _object(payload)
    _version(data)
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list) or len(capabilities) > 256:
        raise ProtocolError("Invalid capabilities")
    poll = _seconds(data.get("recommended_poll_interval_seconds"))
    max_age = _seconds(data.get("max_age_seconds"))
    if max_age <= poll:
        raise ProtocolError("Invalid timing metadata")
    return DeviceInfo(
        _uid(data.get("device_uid")),
        _text(data.get("device_id"), nullable=True),
        _text(data.get("name")),
        _text(data.get("manufacturer")),
        _text(data.get("model")),
        _text(data.get("firmware_version"), nullable=True),
        frozenset(_text(item) for item in capabilities),
        poll,
        max_age,
    )


def parse_state(payload: object, info: DeviceInfo) -> DeviceState:
    data = _object(payload)
    _version(data)
    uid = _uid(data.get("device_uid"))
    if uid != info.device_uid:
        raise IdentityMismatch("Device identity changed")
    generated = _timestamp(data.get("generated_at"))
    if "observed_at" not in data or "pump_available" not in data:
        raise ProtocolError("Missing snapshot metadata")
    observed = _timestamp(data["observed_at"], nullable=True)
    pump = _boolean(data["pump_available"])
    temperatures = _object(data.get("temperatures"))
    states = _object(data.get("states"))
    temps = {key: _number(temperatures.get(key)) for key in TEMPERATURE_KEYS}
    flags = {key: _boolean(states.get(key)) for key in STATE_KEYS}
    mode_data = _object(data.get("modes", {}))
    modes = {}
    for key, options in MODE_OPTIONS.items():
        value = _text(mode_data.get(key), nullable=True)
        modes[key] = value if value in options else None
    power = _number(data.get("power_percent"))
    if power is not None and not 0 <= power <= 100:
        raise ProtocolError("Invalid percentage")
    if (pump is not True or observed is None) and any(
        value is not None
        for value in (*temps.values(), *flags.values(), *modes.values(), power)
    ):
        raise ProtocolError("Measurements without available snapshot")
    if pump is True and observed is None:
        raise ProtocolError("Available pump without observation")
    if observed and observed > generated + timedelta(seconds=5):
        raise ProtocolError("Observation is newer than response")
    errors = data.get("errors")
    if not isinstance(errors, list) or len(errors) > 128:
        raise ProtocolError("Invalid errors list")
    codes = tuple(_text(_object(item).get("code")) for item in errors)
    return DeviceState(
        uid,
        generated,
        observed,
        pump,
        MappingProxyType(temps),
        power,
        MappingProxyType(flags),
        codes,
        MappingProxyType(modes),
        _configuration(data.get("configuration"), generated),
    )


def _clock(value: object) -> str:
    text = _text(value)
    parts = text.split(":")
    if len(parts) != 2 or any(len(p) != 2 or not p.isdigit() for p in parts):
        raise ProtocolError("Invalid schedule time")
    hour, minute = map(int, parts)
    if not (0 <= hour <= 24 and minute in (0, 10, 20, 30, 40, 50)) or (
        hour == 24 and minute
    ):
        raise ProtocolError("Invalid schedule time")
    return text


def _configuration(payload: object, generated: datetime) -> ConfigurationState | None:
    if payload is None:
        return None
    data = _object(payload)
    available = _boolean(data.get("available"))
    if available is None:
        raise ProtocolError("Missing configuration availability")
    observed = _timestamp(data.get("observed_at"), nullable=True)
    max_age = _seconds(data.get("max_age_seconds"))
    values = _object(data.get("values"))
    numbers = {key: _number(values.get(key)) for key in CONFIG_KEYS}
    for key in CONFIG_PERCENTAGES:
        value = numbers[key]
        if value is not None and not 0 <= value <= 100:
            raise ProtocolError("Invalid configuration percentage")
    schedule = None
    if data.get("schedule") is not None:
        raw = _object(data["schedule"])
        schedule = {}
        for day in DAYS:
            intervals = raw.get(day)
            if not isinstance(intervals, list) or len(intervals) > 4:
                raise ProtocolError("Invalid schedule intervals")
            pairs = []
            for item in intervals:
                interval = _object(item)
                start, end = _clock(interval.get("from")), _clock(interval.get("to"))
                if start >= end:
                    raise ProtocolError("Invalid schedule interval")
                pairs.append((start, end))
            schedule[day] = tuple(pairs)
    if observed is not None and observed > generated + timedelta(seconds=5):
        raise ProtocolError("Configuration is newer than response")
    if (not available or observed is None) and (
        any(v is not None for v in numbers.values()) or schedule is not None
    ):
        raise ProtocolError("Configuration values without available observation")
    if available and observed is None:
        raise ProtocolError("Available configuration without observation")
    return ConfigurationState(
        available,
        observed,
        max_age,
        MappingProxyType(numbers),
        MappingProxyType(schedule) if schedule is not None else None,
    )
