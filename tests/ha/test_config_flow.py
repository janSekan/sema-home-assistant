"""Exercise real HA flow management rather than mocked ConfigFlow classes."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry

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

INPUT = {CONF_HOST: "http://sema.local", CONF_ACCESS_TOKEN: "test-only-token"}


def add_entry(hass, info):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=info.device_uid, title="SEMA", data=INPUT
    )
    entry.add_to_hass(hass)
    return entry


async def test_user_form_and_success(hass, info, client, flow_client, skip_setup):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **INPUT,
            CONF_HOST: " http://sema.local/ ",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == info.name
    assert result["data"] == INPUT
    assert result["result"].unique_id == info.device_uid
    client.async_get_state.assert_awaited_once_with(info)
    skip_setup.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (AuthenticationError("test failure"), "invalid_auth"),
        (CommunicationError("test failure"), "cannot_connect"),
        (UnsupportedVersion("test failure"), "unsupported_version"),
        (ProtocolError("test failure"), "invalid_response"),
        (IdentityMismatch("test failure"), "identity_mismatch"),
        (RateLimitError(60), "rate_limited"),
    ],
)
async def test_errors_and_recovery(
    hass, info, client, flow_client, skip_setup, error, key
):
    client.async_get_info.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": key}
    assert INPUT[CONF_ACCESS_TOKEN] not in repr(result)
    client.async_get_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_invalid_url_never_contacts_device(hass, flow_client):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={**INPUT, CONF_HOST: "http://user:password@sema.local/path"},
    )
    assert result["errors"] == {CONF_HOST: "invalid_url"}
    flow_client.assert_not_called()


async def test_duplicate_uid_does_not_change_existing_entry(hass, info, flow_client):
    entry = add_entry(hass, info)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={**INPUT, CONF_HOST: "http://new-address.local"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == INPUT
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize("source", [SOURCE_REAUTH, SOURCE_RECONFIGURE])
async def test_update_same_entry_and_reload(hass, info, client, flow_client, source):
    entry = add_entry(hass, info)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=dict(entry.data) if source == SOURCE_REAUTH else None,
    )
    assert result["type"] is FlowResultType.FORM
    assert INPUT[CONF_ACCESS_TOKEN] not in repr(result)
    updated = {
        CONF_HOST: "http://new-address.local",
        CONF_ACCESS_TOKEN: "new-test-only-token",
    }
    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], updated
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == (
        "reauth_successful" if source == SOURCE_REAUTH else "reconfigure_successful"
    )
    assert entry.data == updated
    assert entry.unique_id == info.device_uid
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    reload.assert_awaited_once_with(entry.entry_id)


@pytest.mark.parametrize("token_input", [{}, {CONF_ACCESS_TOKEN: ""}])
async def test_reconfigure_keeps_token_when_omitted(
    hass, info, flow_client, token_input
):
    entry = add_entry(hass, info)
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
            data={CONF_HOST: "http://new-address.local", **token_input},
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == INPUT[CONF_ACCESS_TOKEN]


@pytest.mark.parametrize("source", [SOURCE_REAUTH, SOURCE_RECONFIGURE])
async def test_update_rejects_different_device(hass, info, client, flow_client, source):
    entry = add_entry(hass, info)
    client.async_get_info.return_value = replace(
        info, device_uid="00000000-0000-4000-8000-000000000002"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=dict(entry.data) if source == SOURCE_REAUTH else None,
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data == INPUT
    assert entry.unique_id == info.device_uid


async def test_pump_offline_does_not_prevent_pairing(
    hass, info, client, flow_client, skip_setup
):
    fixture = (
        Path(__file__).resolve().parents[2] / "fixtures/state_pump_unavailable.json"
    )
    client.async_get_state.return_value = parse_state(
        json.loads(fixture.read_text()), info
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_state_endpoint_error_is_reported(hass, client, flow_client):
    client.async_get_state.side_effect = UnsupportedVersion("State endpoint missing")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=INPUT
    )
    assert result["errors"] == {"base": "unsupported_version"}


async def test_flow_with_real_client_and_http_responses(
    hass, aioclient_mock, skip_setup
):
    root = Path(__file__).resolve().parents[2] / "fixtures"
    aioclient_mock.get(
        INPUT[CONF_HOST] + "/device-api/v1/info",
        json=json.loads((root / "info.json").read_text()),
        headers={"Content-Type": "application/json"},
    )
    aioclient_mock.get(
        INPUT[CONF_HOST] + "/device-api/v1/state",
        json=json.loads((root / "state.json").read_text()),
        headers={"Content-Type": "application/json"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=INPUT
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert aioclient_mock.call_count == 2
    assert all(
        call[3]["Authorization"] == "Bearer " + INPUT[CONF_ACCESS_TOKEN]
        for call in aioclient_mock.mock_calls
    )


@pytest.mark.parametrize("source", [SOURCE_REAUTH, SOURCE_RECONFIGURE])
async def test_failed_update_keeps_original_credentials(
    hass, info, client, flow_client, source
):
    entry = add_entry(hass, info)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=dict(entry.data) if source == SOURCE_REAUTH else None,
    )
    client.async_get_info.side_effect = AuthenticationError("test failure")
    new_data = {
        CONF_HOST: "http://new-address.local",
        CONF_ACCESS_TOKEN: "new-bad-test-token",
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], new_data)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data == INPUT
    assert new_data[CONF_ACCESS_TOKEN] not in repr(result)
    assert INPUT[CONF_ACCESS_TOKEN] not in repr(result)


@pytest.mark.parametrize(
    ("language", "label"),
    [("sk", "Token pre Home Assistant"), ("en", "Home Assistant token")],
)
async def test_translations_load_in_ha(hass, language, label):
    translations = await async_get_translations(hass, language, "config", {DOMAIN})
    assert (
        translations[f"component.{DOMAIN}.config.step.user.data.access_token"] == label
    )
    assert translations[f"component.{DOMAIN}.config.error.invalid_auth"]
    assert translations[f"component.{DOMAIN}.config.abort.unique_id_mismatch"]
