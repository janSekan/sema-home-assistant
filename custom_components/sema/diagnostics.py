"""Export only allowlisted technical state, never config or raw device payloads."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import API_VERSION
from .protocol import CONFIG_KEYS, MODE_OPTIONS, STATE_KEYS, TEMPERATURE_KEYS
from .runtime import SemaConfigEntry, SemaRuntimeData

KNOWN_CAPABILITIES = frozenset(
    {
        *(f"temperatures.{key}" for key in TEMPERATURE_KEYS),
        *(f"states.{key}" for key in STATE_KEYS),
        "power_percent",
        *(f"modes.{key}" for key in MODE_OPTIONS),
        *(f"configuration.{key}" for key in CONFIG_KEYS),
        "configuration.schedule",
    }
)


def _error_category(error: BaseException | None) -> str | None:
    if error is None:
        return None
    if isinstance(error, ConfigEntryAuthFailed):
        return "authentication"
    if isinstance(error, ConfigEntryError):
        return "configuration_or_protocol"
    if isinstance(error, UpdateFailed):
        return "update_failed"
    return "other"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SemaConfigEntry
) -> dict[str, Any]:
    """Use cached memory only, including when setup never completed."""
    result: dict[str, Any] = {
        "diagnostics_schema_version": 1,
        "api_version": API_VERSION,
        "entry": {
            "state": entry.state.value,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "polling_disabled": entry.pref_disable_polling,
        },
        "runtime_available": False,
    }
    runtime = getattr(entry, "runtime_data", None)
    if not isinstance(runtime, SemaRuntimeData):
        return result
    result["runtime_available"] = True
    coordinator = runtime.coordinator
    interval = coordinator.update_interval
    result["coordinator"] = {
        "last_update_success": coordinator.last_update_success,
        "sema_available": coordinator.sema_available,
        "snapshot_fresh": coordinator.snapshot_fresh,
        "measurements_available": coordinator.measurements_available,
        "configuration_available": coordinator.configuration_available,
        "update_interval_seconds": interval.total_seconds() if interval else None,
        "error_category": _error_category(coordinator.last_exception),
    }
    info = coordinator.info
    result["device_api"] = (
        None
        if info is None
        else {
            "supported_capabilities": sorted(info.capabilities & KNOWN_CAPABILITIES),
            "recommended_poll_interval_seconds": info.recommended_poll_interval_seconds,
            "max_age_seconds": info.max_age_seconds,
        }
    )
    snapshot = coordinator.data
    result["snapshot"] = (
        None
        if snapshot is None
        else {
            "observation_present": snapshot.observed_at is not None,
            "pump_available": snapshot.pump_available,
            "known_temperatures": [
                key
                for key in TEMPERATURE_KEYS
                if snapshot.temperatures.get(key) is not None
            ],
            "known_states": [
                key for key in STATE_KEYS if snapshot.states.get(key) is not None
            ],
            "power_percent_known": snapshot.power_percent is not None,
            "error_count": len(snapshot.error_codes),
        }
    )
    return result
