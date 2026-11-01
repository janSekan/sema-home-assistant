"""Lifecycle of the configuration-only prototype with the real HA loader."""

from dataclasses import replace
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sema.client import AuthenticationError, CommunicationError
from custom_components.sema.const import DOMAIN
from custom_components.sema.protocol import ProtocolError


def entry_for(hass, info):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=info.device_uid,
        title="SEMA",
        data={CONF_HOST: "http://sema.local", CONF_ACCESS_TOKEN: "test-only-token"},
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_unload_reload(hass, info, client):
    entry = entry_for(hass, info)
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.info == info
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (AuthenticationError("test failure"), ConfigEntryState.SETUP_ERROR),
        (CommunicationError("test failure"), ConfigEntryState.SETUP_RETRY),
        (ProtocolError("test failure"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_failures(hass, info, client, error, state):
    entry = entry_for(hass, info)
    client.async_get_info.side_effect = error
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is state


async def test_setup_rejects_changed_identity(hass, info, client):
    entry = entry_for(hass, info)
    client.async_get_info.return_value = replace(
        info, device_uid="00000000-0000-4000-8000-000000000002"
    )
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
