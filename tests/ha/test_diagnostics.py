"""Diagnostics must not leak identity, configuration, telemetry or exceptions."""

import json
from dataclasses import replace
from unittest.mock import patch

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.sema.const import DOMAIN
from custom_components.sema.diagnostics import async_get_config_entry_diagnostics


async def test_unloaded_entry_exports_no_config(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Private customer name",
        unique_id="private-uid",
        data={
            CONF_HOST: "http://private-house.local",
            CONF_ACCESS_TOKEN: "private-test-token",
        },
        options={"unexpected-secret-key": "private-options-secret"},
    )
    entry.add_to_hass(hass)
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert not data["runtime_available"]
    serialized = json.dumps(data)
    for secret in (
        "Private customer name",
        "private-uid",
        "private-house.local",
        "private-test-token",
        "private-options-secret",
        "unexpected-secret-key",
    ):
        assert secret not in serialized


async def test_cached_export_omits_freeform_data_and_does_not_request_network(
    hass, info, client
):
    secrets = [
        "Private customer",
        "private-device-id",
        "private-firmware-label",
        "private-house.local",
        "private-test-token",
        "private-capability",
        "private-error-text",
    ]
    client.async_get_info.return_value = replace(
        info,
        name=secrets[0],
        device_id=secrets[1],
        firmware_version=secrets[2],
        capabilities=info.capabilities | {secrets[5]},
    )
    client.async_get_state.return_value = replace(
        client.async_get_state.return_value, error_codes=(secrets[6],)
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=info.device_uid,
        title=secrets[0],
        data={CONF_HOST: "http://" + secrets[3], CONF_ACCESS_TOKEN: secrets[4]},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
    client.reset_mock()
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["runtime_available"]
    assert data["snapshot"]["error_count"] == 1
    assert "temperatures.outdoor_temp" in data["device_api"]["supported_capabilities"]
    serialized = json.dumps(data)
    for secret in (
        *secrets,
        info.device_uid,
        entry.entry_id,
        "2026-11-01T12:00:00",
        "22.3",
    ):
        assert secret not in serialized
    client.async_get_info.assert_not_awaited()
    client.async_get_state.assert_not_awaited()
    entry.runtime_data.coordinator.last_exception = ConfigEntryAuthFailed(
        "private-test-token private-house.local"
    )
    entry.runtime_data.coordinator.last_update_success = False
    failed = await async_get_config_entry_diagnostics(hass, entry)
    assert failed["coordinator"]["error_category"] == "authentication"
    assert "private-test-token" not in json.dumps(failed)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_failed_setup_without_snapshot_is_supported(hass, info, client):
    client.async_get_info.side_effect = ConfigEntryAuthFailed("private-test-token")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=info.device_uid,
        title="Private name",
        data={
            CONF_HOST: "http://private.local",
            CONF_ACCESS_TOKEN: "private-test-token",
        },
    )
    entry.add_to_hass(hass)
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["snapshot"] is None
    assert data["device_api"] is None
    assert not data["coordinator"]["sema_available"]
    assert "private-test-token" not in json.dumps(data)


async def test_ha_diagnostics_download_endpoint(hass, hass_client, info, client):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=info.device_uid,
        title="Private home",
        data={
            CONF_HOST: "http://private-house.local",
            CONF_ACCESS_TOKEN: "private-test-token",
        },
    )
    entry.add_to_hass(hass)
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
    data = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert data["api_version"] == 1
    assert data["runtime_available"]
    serialized = json.dumps(data)
    for secret in (
        "Private home",
        "private-house.local",
        "private-test-token",
        info.device_uid,
    ):
        assert secret not in serialized
    assert await hass.config_entries.async_unload(entry.entry_id)
