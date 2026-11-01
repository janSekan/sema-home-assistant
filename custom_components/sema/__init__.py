"""Read-only SEMA sensors using a shared snapshot coordinator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .runtime import SemaConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: SemaConfigEntry) -> bool:
    """Load HA-specific lifecycle only when running under HA."""
    from .runtime import async_setup_entry as setup_entry

    return await setup_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: SemaConfigEntry) -> bool:
    """Unload the entry without closing HA's shared HTTP session."""
    from .runtime import async_unload_entry as unload_entry

    return await unload_entry(hass, entry)
