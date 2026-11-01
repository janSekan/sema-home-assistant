"""Real HA platforms, registries, availability and shared read-only polling."""

import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.sema.client import AuthenticationError, CommunicationError
from custom_components.sema.const import DOMAIN
from custom_components.sema.protocol import parse_state

ROOT = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
async def entities(hass, info, client, freezer):
    freezer.move_to("2026-11-01T12:00:00Z")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=info.device_uid,
        title="SEMA",
        data={CONF_HOST: "http://sema.local", CONF_ACCESS_TOKEN: "test-only-token"},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        records = {
            record.unique_id.removeprefix(info.device_uid + "_"): record
            for record in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        yield entry, records
        if entry.state is ConfigEntryState.LOADED:
            assert await hass.config_entries.async_unload(entry.entry_id)


def state(hass, records, key):
    result = hass.states.get(records[key].entity_id)
    assert result is not None
    return result


async def refresh(hass, entry):
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()


async def test_values_units_classes_and_shared_device(hass, info, entities):
    entry, records = entities
    assert len(records) == 18
    temperature = state(hass, records, "temperatures.outdoor_temp")
    assert float(temperature.state) == 5.5
    assert temperature.attributes["unit_of_measurement"] == "°C"
    assert temperature.attributes["device_class"] == "temperature"
    assert temperature.attributes["state_class"] == "measurement"
    power = state(hass, records, "power_percent")
    assert float(power.state) == 35
    assert power.attributes["unit_of_measurement"] == "%"
    assert "device_class" not in power.attributes
    assert power.attributes["state_class"] == "measurement"
    assert state(hass, records, "states.heating").state == "on"
    assert state(hass, records, "states.dhw").state == "off"
    assert state(hass, records, "states.fault").attributes["device_class"] == "problem"
    assert state(hass, records, "observed_at").attributes["device_class"] == "timestamp"
    device_ids = {record.device_id for record in records.values()}
    assert len(device_ids) == 1
    device = dr.async_get(hass).async_get(next(iter(device_ids)))
    assert device.identifiers == {(DOMAIN, info.device_uid)}
    assert device.sw_version == info.firmware_version
    assert all(
        record.entity_category == "diagnostic"
        for key, record in records.items()
        if key in ("observed_at", "sema_available", "pump_available", "snapshot_fresh")
    )
    assert all(
        record.domain in ("sensor", "binary_sensor") for record in records.values()
    )
    assert all(
        "test-only-token" not in repr(current.attributes)
        for current in hass.states.async_all(["sensor", "binary_sensor"])
    )


async def test_optional_temperatures_disabled_until_enabled(hass, entities):
    entry, records = entities
    registry = er.async_get(hass)
    for key in ("exchanger_temp", "e_temp", "f_temp", "g_temp"):
        record = records["temperatures." + key]
        assert record.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(record.entity_id) is None
        registry.async_update_entity(record.entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert float(state(hass, records, "temperatures.exchanger_temp").state) == 33.1
    for key in ("e_temp", "f_temp", "g_temp"):
        assert state(hass, records, "temperatures." + key).state == STATE_UNKNOWN


async def test_zero_false_and_partial_unknown_are_preserved(hass, client, entities):
    entry, records = entities
    data = json.loads((ROOT / "state.json").read_text())
    data["temperatures"]["outdoor_temp"] = 0
    data["temperatures"]["equitherm_temp"] = None
    data["power_percent"] = 0
    data["states"]["heating"] = None
    client.async_get_state.return_value = parse_state(data, entry.runtime_data.info)
    await refresh(hass, entry)
    assert float(state(hass, records, "temperatures.outdoor_temp").state) == 0
    assert float(state(hass, records, "power_percent").state) == 0
    assert state(hass, records, "states.heating").state == STATE_UNKNOWN
    assert state(hass, records, "states.fault").state == "off"
    assert state(hass, records, "temperatures.equitherm_temp").state == STATE_UNKNOWN
    assert float(state(hass, records, "temperatures.indoor_temp").state) == 22.3


@pytest.mark.parametrize("available", [False, None])
async def test_offline_or_unknown_pump_keeps_sema_connected(
    hass, client, entities, available
):
    entry, records = entities
    data = json.loads((ROOT / "state_pump_unavailable.json").read_text())
    data["pump_available"] = available
    client.async_get_state.return_value = parse_state(data, entry.runtime_data.info)
    await refresh(hass, entry)
    assert state(hass, records, "temperatures.outdoor_temp").state == STATE_UNAVAILABLE
    assert state(hass, records, "states.fault").state == STATE_UNAVAILABLE
    assert state(hass, records, "sema_available").state == "on"
    assert state(hass, records, "pump_available").state == (
        "off" if available is False else STATE_UNKNOWN
    )
    assert state(hass, records, "snapshot_fresh").state == STATE_UNKNOWN
    assert state(hass, records, "observed_at").state == STATE_UNKNOWN


async def test_stale_snapshot_expires_entities_even_with_http_success(
    hass, client, entities, freezer
):
    entry, records = entities
    observed = state(hass, records, "observed_at").state
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert state(hass, records, "temperatures.outdoor_temp").state == STATE_UNAVAILABLE
    assert state(hass, records, "states.heating").state == STATE_UNAVAILABLE
    assert state(hass, records, "sema_available").state == "on"
    assert state(hass, records, "pump_available").state == STATE_UNAVAILABLE
    assert state(hass, records, "snapshot_fresh").state == "off"
    assert state(hass, records, "observed_at").state == observed


async def test_transport_failure_and_recovery(hass, client, entities):
    entry, records = entities
    client.async_get_state.side_effect = CommunicationError("test failure")
    await refresh(hass, entry)
    assert state(hass, records, "sema_available").state == "off"
    for key in (
        "temperatures.outdoor_temp",
        "states.fault",
        "pump_available",
        "snapshot_fresh",
        "observed_at",
    ):
        assert state(hass, records, key).state == STATE_UNAVAILABLE
    client.async_get_state.side_effect = None
    await refresh(hass, entry)
    assert state(hass, records, "sema_available").state == "on"
    assert float(state(hass, records, "temperatures.outdoor_temp").state) == 5.5


async def test_one_http_poll_for_all_active_entities(hass, client, entities, freezer):
    entry, records = entities
    assert len(hass.states.async_all(["sensor", "binary_sensor"])) == 14
    client.async_get_state.assert_awaited_once()
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert client.async_get_state.await_count == 2
    client.async_get_info.assert_awaited_once()


async def test_unsupported_capabilities_do_not_create_measurement_entities(
    hass, info, client
):
    client.async_get_info.return_value = replace(
        info,
        capabilities=frozenset(
            {"temperatures.outdoor_temp", "states.heating", "future.sensor"}
        ),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=info.device_uid,
        title="SEMA",
        data={CONF_HOST: "http://sema.local", CONF_ACCESS_TOKEN: "test-only-token"},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    records = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert {
        record.unique_id.removeprefix(info.device_uid + "_") for record in records
    } == {
        "temperatures.outdoor_temp",
        "states.heating",
        "observed_at",
        "sema_available",
        "pump_available",
        "snapshot_fresh",
    }
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_reconfigure_preserves_entity_and_device_registry(hass, client, entities):
    entry, records = entities
    before = {
        key: (record.entity_id, record.unique_id, record.device_id)
        for key, record in records.items()
    }
    with patch("custom_components.sema.config_flow.SemaClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
            data={CONF_HOST: "http://new-address.local"},
        )
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()
    after = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(after) == len(before)
    assert {
        (record.entity_id, record.unique_id, record.device_id) for record in after
    } == set(before.values())


async def test_failed_platform_unload_keeps_coordinator_active(hass, entities):
    from custom_components.sema.runtime import async_unload_entry

    entry, records = entities
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await async_unload_entry(hass, entry)
    assert entry.runtime_data.coordinator.measurements_available
    assert float(state(hass, records, "temperatures.outdoor_temp").state) == 5.5


async def test_real_platform_unload_stops_requests(hass, client, entities, freezer):
    entry, records = entities
    assert await hass.config_entries.async_unload(entry.entry_id)
    calls = client.async_get_state.await_count
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert client.async_get_state.await_count == calls
    assert all(
        (current := hass.states.get(record.entity_id)) is None
        or current.state == STATE_UNAVAILABLE
        for record in records.values()
    )


@pytest.mark.parametrize(
    ("language", "label"), [("en", "Outdoor temperature"), ("sk", "Vonkajšia teplota")]
)
async def test_localized_entity_names(hass, info, client, language, label):
    await hass.config.async_update(language=language)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=info.device_uid,
        title="SEMA",
        data={CONF_HOST: "http://sema.local", CONF_ACCESS_TOKEN: "test-only-token"},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    record = next(
        record
        for record in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if record.unique_id.endswith("_temperatures.outdoor_temp")
    )
    assert hass.states.get(record.entity_id).name.endswith(label)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_revoked_token_marks_entities_unavailable_and_starts_reauth(
    hass, client, entities, freezer
):
    entry, records = entities
    client.async_get_state.side_effect = AuthenticationError("test failure")
    await refresh(hass, entry)
    assert any(
        flow["context"]["source"] == "reauth"
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )
    assert state(hass, records, "sema_available").state == "off"
    assert state(hass, records, "temperatures.outdoor_temp").state == STATE_UNAVAILABLE
    calls = client.async_get_state.await_count
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert client.async_get_state.await_count == calls


async def test_renamed_public_device_id_does_not_change_identity(
    hass, client, entities
):
    entry, records = entities
    original = {
        (record.entity_id, record.unique_id, record.device_id)
        for record in records.values()
    }
    client.async_get_info.return_value = replace(
        entry.runtime_data.info, device_id="renamed-device", name="Renamed SEMA"
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    records_after = er.async_entries_for_config_entry(
        er.async_get(hass), entry.entry_id
    )
    assert {
        (record.entity_id, record.unique_id, record.device_id)
        for record in records_after
    } == original
