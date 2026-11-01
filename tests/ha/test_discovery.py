"""Untrusted mDNS hints must require token entry and authenticated UID matching."""

from dataclasses import replace
from ipaddress import ip_address

import pytest
from homeassistant.config_entries import SOURCE_ZEROCONF
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sema.client import AuthenticationError
from custom_components.sema.const import DOMAIN, ZEROCONF_SERVICE_TYPE


@pytest.fixture
def discovery(info):
    address = ip_address("192.168.1.10")
    return ZeroconfServiceInfo(
        ip_address=address,
        ip_addresses=[address],
        port=80,
        hostname="sema-demo.local.",
        type=ZEROCONF_SERVICE_TYPE,
        name=f"SEMA {info.device_uid}.{ZEROCONF_SERVICE_TYPE}",
        properties={
            "device_uid": info.device_uid,
            "api_version": "1",
            "scheme": "http",
        },
    )


async def start(hass, discovery):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=discovery
    )


async def test_discovery_prompts_only_for_token_and_verifies_uid(
    hass, info, discovery, client, flow_client, skip_setup
):
    result = await start(hass, discovery)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"]["host"] == "http://192.168.1.10"
    assert {str(key) for key in result["data_schema"].schema} == {CONF_ACCESS_TOKEN}
    flow_client.assert_not_called()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "test-only-discovery-token"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "http://192.168.1.10",
        CONF_ACCESS_TOKEN: "test-only-discovery-token",
    }
    assert result["result"].unique_id == info.device_uid
    client.async_get_info.assert_awaited_once()
    client.async_get_state.assert_awaited_once_with(info)


async def test_ipv6_and_custom_port_prefill(hass, discovery, flow_client):
    discovery.ip_address = ip_address("2001:db8::10")
    discovery.port = 8443
    discovery.properties["scheme"] = "https"
    result = await start(hass, discovery)
    assert result["description_placeholders"]["host"] == "https://[2001:db8::10]:8443"
    flow_client.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "_other._tcp.local."),
        ("port", None),
        ("port", "80"),
        ("port", 0),
        ("port", 65536),
        ("ip_address", ip_address("127.0.0.1")),
        ("ip_address", ip_address("0.0.0.0")),
        ("ip_address", ip_address("224.0.0.1")),
        ("ip_address", ip_address("fe80::1")),
        ("api_version", "2"),
        ("api_version", 1),
        ("scheme", "file"),
        ("device_uid", None),
        ("device_uid", "not-a-uid"),
    ],
)
async def test_invalid_hints_are_rejected_without_requests(
    hass, discovery, flow_client, field, value
):
    if field in ("api_version", "scheme", "device_uid"):
        discovery.properties[field] = value
    else:
        setattr(discovery, field, value)
    result = await start(hass, discovery)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery"
    flow_client.assert_not_called()


async def test_existing_entry_is_not_redirected_and_token_not_sent(
    hass, info, discovery, client, flow_client
):
    saved = {
        CONF_HOST: "http://old-address.local",
        CONF_ACCESS_TOKEN: "saved-private-test-token",
    }
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=info.device_uid, title="SEMA", data=saved
    )
    entry.add_to_hass(hass)
    result = await start(hass, discovery)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == saved
    flow_client.assert_not_called()
    client.async_get_info.assert_not_awaited()
    assert saved[CONF_ACCESS_TOKEN] not in repr(result)


async def test_claimed_uid_cannot_pair_different_authenticated_device(
    hass, info, discovery, client, flow_client
):
    client.async_get_info.return_value = replace(
        info, device_uid="00000000-0000-4000-8000-000000000002"
    )
    result = await start(hass, discovery)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "test-only-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "discovery_mismatch"}
    assert not hass.config_entries.async_entries(DOMAIN)
    assert "test-only-token" not in repr(result)


async def test_discovery_auth_error_can_be_corrected(
    hass, discovery, client, flow_client, skip_setup
):
    result = await start(hass, discovery)
    client.async_get_info.side_effect = AuthenticationError("test failure")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "wrong-test-token"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    assert "wrong-test-token" not in repr(result)
    client.async_get_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "correct-test-token"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_pending_announcements_create_only_one_flow(
    hass, discovery, flow_client
):
    first = await start(hass, discovery)
    assert first["type"] is FlowResultType.FORM
    second = await start(hass, discovery)
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
