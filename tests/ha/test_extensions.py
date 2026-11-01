"""Revision 2 read-only entities, independent expiry and confidential schedule."""

import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.sema.diagnostics import async_get_config_entry_diagnostics
from custom_components.sema.protocol import parse_info, parse_state

ROOT = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
async def extended(hass, client, freezer):
    freezer.move_to("2026-11-01T12:00:00Z")
    info = parse_info(json.loads((ROOT / "info_extended.json").read_text()))
    payload = json.loads((ROOT / "state_extended.json").read_text())
    payload["generated_at"] = payload["observed_at"] = payload["configuration"][
        "observed_at"
    ] = dt_util.utcnow().isoformat()
    client.async_get_info.return_value = info
    client.async_get_state.return_value = parse_state(payload, info)
    entry = MockConfigEntry(
        domain="sema",
        unique_id=info.device_uid,
        data={CONF_HOST: "http://sema.local", CONF_ACCESS_TOKEN: "test-only"},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        records = {
            r.unique_id.removeprefix(info.device_uid + "_"): r
            for r in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        yield entry, records, payload
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_modes_configuration_and_schedule_are_read_only(hass, extended, client):
    entry, records, payload = extended
    assert len(records) == 49

    def state(key):
        return hass.states.get(records[key].entity_id)

    assert state("states.power_on").state == "on"
    assert state("states.setback").state == "off"
    assert state("modes.season").state == "winter"
    assert state("modes.activity").attributes["device_class"] == "enum"
    reference = state("configuration.reference_temp")
    assert float(reference.state) == 21
    assert "state_class" not in reference.attributes
    assert reference.attributes["unit_of_measurement"] == "°C"
    registry = er.async_get(hass)
    for key in (
        "configuration.schedule",
        "configuration.limit_heat_percent",
        "configuration.curve_minus20",
    ):
        assert records[key].disabled_by is er.RegistryEntryDisabler.INTEGRATION
        registry.async_update_entity(records[key].entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert state("configuration.schedule").state == "1"
    assert state("configuration.schedule").attributes["schedule"]["mon"] == [
        {"from": "06:00", "to": "08:00"}
    ]
    assert "state_class" not in state("configuration.limit_heat_percent").attributes
    exported = json.dumps(await async_get_config_entry_diagnostics(hass, entry))
    assert "06:00" not in exported
    assert 'schedule"' not in exported.replace('configuration.schedule"', "")
    assert all(r.domain in ("sensor", "binary_sensor") for r in records.values())
    assert client.async_get_state.await_count == 2


async def test_configuration_expires_independently_of_fast_snapshot(
    hass, extended, client, freezer
):
    entry, records, payload = extended
    coordinator = entry.runtime_data.coordinator
    payload["observed_at"] = (dt_util.utcnow() - timedelta(seconds=80)).isoformat()
    client.async_get_state.return_value = parse_state(payload, coordinator.info)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert (
        hass.states.get(records["temperatures.outdoor_temp"].entity_id).state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get(records["configuration.reference_temp"].entity_id).state
        != "unavailable"
    )
    # Stop scheduled polls so only the cache-expiry timer can notify listeners.
    hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    freezer.tick(timedelta(seconds=901))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get(records["configuration.reference_temp"].entity_id).state
        == STATE_UNAVAILABLE
    )
    assert hass.states.get(records["configuration_fresh"].entity_id).state == "off"


async def test_sk_mode_labels_are_loaded_by_home_assistant(hass, extended):
    translations = await async_get_translations(hass, "sk", "entity", {"sema"})
    assert translations["component.sema.entity.sensor.season.state.winter"] == "Zima"
    assert (
        translations["component.sema.entity.sensor.dhw_mode.state.electric_heating"]
        == "Elektrický ohrev TÚV"
    )
