"""Shared polling, availability and lifecycle with the real HA coordinator."""

import asyncio
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.sema.client import (
    AuthenticationError,
    CommunicationError,
    RateLimitError,
)
from custom_components.sema.const import DOMAIN
from custom_components.sema.protocol import (
    IdentityMismatch,
    ProtocolError,
    UnsupportedVersion,
    parse_state,
)


@pytest.fixture(autouse=True)
def no_platforms():
    """Exercise coordinator listeners independently of actual entity platforms."""
    with (
        patch("homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ),
    ):
        yield


@pytest.fixture
async def loaded(hass, info, client, freezer):
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
        yield entry, entry.runtime_data.coordinator
        if entry.state is ConfigEntryState.LOADED:
            assert await hass.config_entries.async_unload(entry.entry_id)


async def tick(hass, freezer, seconds):
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def test_one_poll_for_all_listeners_and_no_info_per_poll(
    hass, client, loaded, freezer
):
    _, coordinator = loaded
    first, second = Mock(), Mock()
    remove_first = coordinator.async_add_listener(first)
    remove_second = coordinator.async_add_listener(second)
    assert coordinator.update_interval == timedelta(seconds=30)
    assert client.async_get_state.await_count == 1
    await tick(hass, freezer, 31)
    assert client.async_get_state.await_count == 2
    first.assert_called_once()
    second.assert_called_once()
    client.async_get_info.assert_awaited_once()
    remove_first()
    await tick(hass, freezer, 31)
    assert client.async_get_state.await_count == 3
    remove_second()
    await tick(hass, freezer, 120)
    assert client.async_get_state.await_count == 3


async def test_no_consumers_means_no_background_requests(hass, client, loaded, freezer):
    await tick(hass, freezer, 120)
    client.async_get_state.assert_awaited_once()


async def test_transport_failure_retains_snapshot_but_disables_measurements(
    client, loaded
):
    _, coordinator = loaded
    snapshot = coordinator.data
    assert coordinator.sema_available
    assert coordinator.measurements_available
    client.async_get_state.side_effect = CommunicationError("test failure")
    await coordinator.async_refresh()
    assert not coordinator.sema_available
    assert not coordinator.measurements_available
    assert coordinator.data is snapshot
    client.async_get_state.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.sema_available
    assert coordinator.measurements_available
    client.async_get_info.assert_awaited_once()


async def test_offline_pump_unknown_snapshot_and_partial_fields(client, info, loaded):
    _, coordinator = loaded
    root = Path(__file__).resolve().parents[2] / "fixtures"
    offline = json.loads((root / "state_pump_unavailable.json").read_text())
    client.async_get_state.return_value = parse_state(offline, info)
    await coordinator.async_refresh()
    assert coordinator.sema_available
    assert coordinator.data.pump_available is False
    assert not coordinator.measurements_available
    offline["pump_available"] = None
    client.async_get_state.return_value = parse_state(offline, info)
    await coordinator.async_refresh()
    assert coordinator.sema_available
    assert coordinator.data.pump_available is None
    assert not coordinator.measurements_available
    partial = json.loads((root / "state.json").read_text())
    partial["temperatures"]["equitherm_temp"] = None
    partial["temperatures"]["outdoor_temp"] = 0
    partial["power_percent"] = 0
    client.async_get_state.return_value = parse_state(partial, info)
    await coordinator.async_refresh()
    assert coordinator.measurements_available
    assert coordinator.data.temperatures["equitherm_temp"] is None
    assert coordinator.data.temperatures["outdoor_temp"] == 0
    assert coordinator.data.power_percent == 0
    assert coordinator.data.states["fault"] is False


async def test_stale_response_is_transport_success_not_fresh_measurement(
    client, loaded
):
    _, coordinator = loaded
    snapshot = coordinator.data
    client.async_get_state.return_value = replace(
        snapshot, observed_at=snapshot.observed_at - timedelta(seconds=61)
    )
    await coordinator.async_refresh()
    assert coordinator.sema_available
    assert coordinator.data.pump_available is True
    assert not coordinator.snapshot_fresh
    assert not coordinator.measurements_available
    client.async_get_state.return_value = snapshot
    await coordinator.async_refresh()
    assert coordinator.measurements_available


async def test_expiry_notifies_while_http_request_is_pending(
    hass, client, loaded, freezer
):
    _, coordinator = loaded
    listener = Mock()
    coordinator.async_add_listener(listener)
    started, release = asyncio.Event(), asyncio.Event()
    original = coordinator.data

    async def delayed_snapshot(_info):
        started.set()
        await release.wait()
        return replace(
            original, observed_at=dt_util.utcnow(), generated_at=dt_util.utcnow()
        )

    client.async_get_state.side_effect = delayed_snapshot
    task = asyncio.create_task(coordinator.async_refresh())
    try:
        await started.wait()
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass, dt_util.utcnow())
        await asyncio.sleep(0)
        listener.assert_called_once()
        assert not task.done()
        assert coordinator.sema_available
        assert not coordinator.measurements_available
        release.set()
        await task
        assert coordinator.measurements_available
    finally:
        release.set()
        await task


async def test_retry_backoff_and_recovery(hass, client, loaded, freezer):
    _, coordinator = loaded
    coordinator.async_add_listener(Mock())
    client.async_get_state.side_effect = CommunicationError("test failure")
    await coordinator.async_refresh()
    for delay in (30, 60, 120, 240, 300):
        calls = client.async_get_state.await_count
        await tick(hass, freezer, delay - 2)
        assert client.async_get_state.await_count == calls
        await tick(hass, freezer, 3)
        assert client.async_get_state.await_count == calls + 1
    client.async_get_state.side_effect = None
    client.async_get_state.return_value = replace(
        coordinator.data, observed_at=dt_util.utcnow(), generated_at=dt_util.utcnow()
    )
    await coordinator.async_refresh()
    assert coordinator.measurements_available
    calls = client.async_get_state.await_count
    await tick(hass, freezer, 31)
    assert client.async_get_state.await_count == calls + 1


async def test_rate_limit_honors_retry_after(hass, client, loaded, freezer):
    _, coordinator = loaded
    coordinator.async_add_listener(Mock())
    client.async_get_state.side_effect = RateLimitError(120)
    await coordinator.async_refresh()
    calls = client.async_get_state.await_count
    await tick(hass, freezer, 119)
    assert client.async_get_state.await_count == calls
    client.async_get_state.side_effect = None
    await tick(hass, freezer, 2)
    assert client.async_get_state.await_count == calls + 1


async def test_revoked_token_starts_reauth_and_stops_polling(
    hass, client, loaded, freezer
):
    entry, coordinator = loaded
    coordinator.async_add_listener(Mock())
    client.async_get_state.side_effect = AuthenticationError("test failure")
    with patch(
        "homeassistant.config_entries.ConfigEntry.async_start_reauth_if_available"
    ) as reauth:
        await coordinator.async_refresh()
        reauth.assert_called_once_with(hass)
    assert not coordinator.sema_available
    assert not coordinator.measurements_available
    calls = client.async_get_state.await_count
    await tick(hass, freezer, 120)
    assert client.async_get_state.await_count == calls


@pytest.mark.parametrize(
    "error",
    [IdentityMismatch("test"), UnsupportedVersion("test"), ProtocolError("test")],
)
async def test_invalid_updates_cannot_replace_snapshot(client, loaded, error):
    _, coordinator = loaded
    snapshot = coordinator.data
    client.async_get_state.side_effect = error
    await coordinator.async_refresh()
    assert not coordinator.sema_available
    assert not coordinator.measurements_available
    assert coordinator.data is snapshot


async def test_unload_cancels_polling_and_expiry(hass, client, loaded, freezer):
    entry, coordinator = loaded
    listener = Mock()
    coordinator.async_add_listener(listener)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await tick(hass, freezer, 120)
    client.async_get_state.assert_awaited_once()
    listener.assert_not_called()


async def test_unload_cancels_inflight_scheduled_request(hass, client, loaded, freezer):
    entry, coordinator = loaded
    coordinator.async_add_listener(Mock())
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def blocked(_info):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    client.async_get_state.side_effect = blocked
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await started.wait()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert cancelled.is_set()
    assert coordinator._unsub_refresh is None
    assert coordinator._unsub_expiry is None
    assert not coordinator.measurements_available
    calls = client.async_get_state.await_count
    await tick(hass, freezer, 120)
    assert client.async_get_state.await_count == calls


async def test_setup_retry_does_not_bypass_retry_after(
    hass, info, aioclient_mock, freezer
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=info.device_uid,
        title="SEMA",
        data={CONF_HOST: "http://sema.local", CONF_ACCESS_TOKEN: "test-only-token"},
    )
    entry.add_to_hass(hass)
    aioclient_mock.get(
        "http://sema.local/device-api/v1/info",
        status=429,
        headers={"Retry-After": "120"},
    )
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    original_client = entry.runtime_data.client
    assert aioclient_mock.call_count == 1
    await tick(hass, freezer, 6)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.runtime_data.client is original_client
    assert aioclient_mock.call_count == 1


async def test_device_recommended_slower_poll_interval(hass, info, client, freezer):
    freezer.move_to("2026-11-01T12:00:00Z")
    client.async_get_info.return_value = replace(
        info, recommended_poll_interval_seconds=90, max_age_seconds=180
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
    coordinator = entry.runtime_data.coordinator
    assert coordinator.update_interval == timedelta(seconds=90)
    coordinator.async_add_listener(Mock())
    await tick(hass, freezer, 60)
    client.async_get_state.assert_awaited_once()
    await tick(hass, freezer, 31)
    assert client.async_get_state.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("availability", [False, None])
async def test_cold_start_without_available_pump(hass, info, client, availability):
    root = Path(__file__).resolve().parents[2] / "fixtures"
    payload = json.loads((root / "state_pump_unavailable.json").read_text())
    payload["pump_available"] = availability
    client.async_get_state.return_value = parse_state(payload, info)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=info.device_uid,
        title="SEMA",
        data={CONF_HOST: "http://sema.local", CONF_ACCESS_TOKEN: "test-only-token"},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.sema.runtime.SemaClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data.coordinator
    assert coordinator.sema_available
    assert coordinator.data.pump_available is availability
    assert not coordinator.measurements_available
    assert await hass.config_entries.async_unload(entry.entry_id)
