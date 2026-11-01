"""Configure a SEMA device by its persistent identity, never by its IP."""

from typing import Any
from uuid import UUID

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from yarl import URL

from .client import (
    AuthenticationError,
    CommunicationError,
    RateLimitError,
    SemaClient,
    normalize_base_url,
)
from .const import DOMAIN, ZEROCONF_SERVICE_TYPE
from .protocol import DeviceInfo, IdentityMismatch, ProtocolError, UnsupportedVersion


class SemaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Manual setup, credential replacement and address changes."""

    VERSION = 1

    def __init__(self) -> None:
        self._client: SemaClient | None = None
        self._connection: tuple[str, str] | None = None
        self._discovered_uid: str | None = None
        self._discovered_host = ""

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Treat unauthenticated mDNS data only as a hint for explicit pairing."""
        try:
            address = discovery_info.ip_address
            props = discovery_info.properties
            port = discovery_info.port
            scheme = props.get("scheme")
            if (
                discovery_info.type != ZEROCONF_SERVICE_TYPE
                or props.get("api_version") != "1"
                or scheme not in ("http", "https")
                or type(port) is not int
                or not 1 <= port <= 65535
                or address.is_unspecified
                or address.is_multicast
                or address.is_loopback
                or address.is_link_local
            ):
                raise ValueError
            uid = str(UUID(props["device_uid"]))
            host = normalize_base_url(
                str(URL.build(scheme=scheme, host=str(address), port=port))
            )
        except (KeyError, ValueError, TypeError, AttributeError):
            return self.async_abort(reason="invalid_discovery")
        self._discovered_uid = uid
        self._discovered_host = host
        await self.async_set_unique_id(uid)
        # Never send saved credentials to an address claimed by an mDNS packet.
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": f"SEMA {uid[:8]}"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_form("discovery_confirm", user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_form("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_form("reconfigure", user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_form("reauth_confirm", user_input)

    async def _async_validate(self, data: dict[str, str]) -> DeviceInfo:
        connection = (data[CONF_HOST], data[CONF_ACCESS_TOKEN])
        if self._client is None or self._connection != connection:
            self._client = SemaClient(async_get_clientsession(self.hass), *connection)
            self._connection = connection
        info = await self._client.async_get_info()
        # Validate both endpoints; an offline pump does not prevent pairing.
        await self._client.async_get_state(info)
        return info

    async def _async_form(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        entry = None
        if step_id == "reconfigure":
            entry = self._get_reconfigure_entry()
        elif step_id == "reauth_confirm":
            entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        host = entry.data[CONF_HOST] if entry else self._discovered_host
        if user_input is not None:
            if step_id != "discovery_confirm":
                host = user_input[CONF_HOST]
            try:
                normalized_host = normalize_base_url(host)
            except ValueError:
                errors[CONF_HOST] = "invalid_url"
            else:
                token = user_input.get(CONF_ACCESS_TOKEN, "")
                if not token and entry and step_id == "reconfigure":
                    token = entry.data[CONF_ACCESS_TOKEN]
                data = {CONF_HOST: normalized_host, CONF_ACCESS_TOKEN: token}
                try:
                    info = await self._async_validate(data)
                    if (
                        self._discovered_uid is not None
                        and info.device_uid != self._discovered_uid
                    ):
                        raise DiscoveryMismatch
                except (AuthenticationError, ValueError):
                    errors["base"] = "invalid_auth"
                except CommunicationError:
                    errors["base"] = "cannot_connect"
                except UnsupportedVersion:
                    errors["base"] = "unsupported_version"
                except IdentityMismatch:
                    errors["base"] = "identity_mismatch"
                except ProtocolError:
                    errors["base"] = "invalid_response"
                except RateLimitError:
                    errors["base"] = "rate_limited"
                except DiscoveryMismatch:
                    errors["base"] = "discovery_mismatch"
                else:
                    await self.async_set_unique_id(info.device_uid)
                    if entry:
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            entry, data_updates=data
                        )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=info.name, data=data)

        token_key = (
            vol.Optional(CONF_ACCESS_TOKEN)
            if step_id == "reconfigure"
            else vol.Required(CONF_ACCESS_TOKEN)
        )
        fields: dict[vol.Marker, Any] = {}
        if step_id != "discovery_confirm":
            fields[vol.Required(CONF_HOST, default=host)] = str
        fields[token_key] = TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
        schema = vol.Schema(fields)
        # Never place a saved or failed token in schema defaults, placeholders or context.
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders={"host": host}
            if step_id == "discovery_confirm"
            else None,
        )


class DiscoveryMismatch(Exception):
    """The authenticated device is different from the advertised hint."""
