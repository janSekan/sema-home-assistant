"""Config-entry lifecycle and shared snapshot coordinator."""

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import SemaClient
from .coordinator import SemaDataUpdateCoordinator
from .protocol import DeviceInfo

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


@dataclass
class SemaRuntimeData:
    client: SemaClient
    coordinator: SemaDataUpdateCoordinator
    connection: tuple[str, str] = field(repr=False)

    @property
    def info(self) -> DeviceInfo | None:
        return self.coordinator.info


type SemaConfigEntry = ConfigEntry[SemaRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: SemaConfigEntry) -> bool:
    """Load info once and obtain the first shared snapshot before adding platforms."""
    connection = (entry.data[CONF_HOST], entry.data[CONF_ACCESS_TOKEN])
    previous = getattr(entry, "runtime_data", None)
    try:
        # HA may retry setup sooner than Retry-After. Retain the client's cooldown
        # across failed attempts; new credentials/address always get a new client.
        client = (
            previous.client
            if isinstance(previous, SemaRuntimeData)
            and previous.connection == connection
            else SemaClient(async_get_clientsession(hass), *connection)
        )
    except ValueError:
        raise ConfigEntryError("Invalid SEMA connection settings") from None
    coordinator = SemaDataUpdateCoordinator(hass, entry, client)
    entry.runtime_data = SemaRuntimeData(client, coordinator, connection)
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SemaConfigEntry) -> bool:
    """Stop snapshot expiry and scheduled polling; HA owns the HTTP session."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.coordinator.async_shutdown()
    return True
