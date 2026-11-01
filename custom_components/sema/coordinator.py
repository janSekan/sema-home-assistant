"""One snapshot and polling schedule for all consumers of a SEMA entry."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import AuthenticationError, CommunicationError, RateLimitError, SemaClient
from .const import DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN
from .protocol import (
    DeviceInfo,
    DeviceState,
    IdentityMismatch,
    ProtocolError,
    UnsupportedVersion,
)

_LOGGER = logging.getLogger(__name__)


class SemaDataUpdateCoordinator(DataUpdateCoordinator[DeviceState]):
    """Keep transport success independent of pump availability and freshness."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: SemaClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        self.client = client
        self.info: DeviceInfo | None = None
        self._failures = 0
        self._unsub_expiry: Callable[[], None] | None = None

    @property
    def sema_available(self) -> bool:
        """A valid info/state exchange succeeded; the pump may still be offline."""
        return (
            not self._shutdown_requested
            and self.last_update_success
            and self.data is not None
        )

    @property
    def snapshot_fresh(self) -> bool:
        """Do not use generated_at to make an old observation look current."""
        return (
            self.data is not None
            and self.info is not None
            and self.data.is_fresh(self.info.max_age_seconds, now=dt_util.utcnow())
        )

    @property
    def measurements_available(self) -> bool:
        """Shared availability gate for future pump measurement entities."""
        return (
            self.sema_available
            and self.snapshot_fresh
            and self.data.pump_available is True
        )

    @property
    def configuration_available(self) -> bool:
        return bool(
            self.sema_available
            and self.data.configuration is not None
            and self.data.configuration.is_fresh(now=dt_util.utcnow())
        )

    def _connection_failure(
        self, message: str, retry_after: float | None = None
    ) -> UpdateFailed:
        self._failures += 1
        interval = self.update_interval
        assert interval is not None
        base = interval.total_seconds()
        backoff = min(base * 2 ** min(self._failures - 1, 4), max(base, 300))
        return UpdateFailed(message, retry_after=max(backoff, retry_after or 0))

    async def _async_setup(self) -> None:
        try:
            info = await self.client.async_get_info()
        except AuthenticationError:
            raise ConfigEntryAuthFailed("SEMA HA token is invalid or revoked") from None
        except RateLimitError as err:
            raise self._connection_failure(
                "SEMA is limiting requests", err.retry_after_seconds
            ) from None
        except CommunicationError:
            raise self._connection_failure("Cannot communicate with SEMA") from None
        except (IdentityMismatch, ProtocolError, UnsupportedVersion):
            raise ConfigEntryError(
                "SEMA device API is incompatible or invalid"
            ) from None
        assert self.config_entry is not None
        if info.device_uid != self.config_entry.unique_id:
            raise ConfigEntryError(
                "SEMA device identity changed; check the configured address"
            )
        self.info = info
        self.update_interval = timedelta(
            seconds=max(
                DEFAULT_SCAN_INTERVAL_SECONDS, info.recommended_poll_interval_seconds
            )
        )

    async def _async_update_data(self) -> DeviceState:
        assert self.info is not None
        try:
            snapshot = await self.client.async_get_state(self.info)
        except AuthenticationError:
            raise ConfigEntryAuthFailed("SEMA HA token is invalid or revoked") from None
        except RateLimitError as err:
            raise self._connection_failure(
                "SEMA is limiting requests", err.retry_after_seconds
            ) from None
        except CommunicationError:
            raise self._connection_failure("Cannot communicate with SEMA") from None
        except (IdentityMismatch, ProtocolError, UnsupportedVersion):
            raise ConfigEntryError(
                "SEMA device API identity, version or response is invalid"
            ) from None
        self._failures = 0
        return snapshot

    @callback
    def _async_refresh_finished(self) -> None:
        """Notify consumers at expiry even while the next HTTP request is pending."""
        self._cancel_expiry()
        if not self.sema_available:
            return
        assert self.info is not None
        deadlines = []
        if self.snapshot_fresh and self.data.observed_at is not None:
            deadlines.append(
                self.data.observed_at
                + timedelta(seconds=self.info.max_age_seconds, microseconds=1)
            )
        configuration = self.data.configuration
        if (
            self.configuration_available
            and configuration is not None
            and configuration.observed_at is not None
        ):
            deadlines.append(
                configuration.observed_at
                + timedelta(seconds=configuration.max_age_seconds, microseconds=1)
            )
        if not deadlines:
            return
        deadline = min(deadlines)
        self._unsub_expiry = async_track_point_in_utc_time(
            self.hass, self._expire, deadline
        )

    @callback
    def _expire(self, _now: datetime) -> None:
        self._unsub_expiry = None
        # No network call, no fabricated values and no change to transport status.
        if not self._shutdown_requested:
            self.async_update_listeners()
            self._async_refresh_finished()

    @callback
    def _schedule_refresh(self) -> None:
        # A request cancelled during entry unload still runs the base refresh's
        # finally block. Do not let it recreate a timer after shutdown.
        if not self._shutdown_requested:
            super()._schedule_refresh()

    @callback
    def _cancel_expiry(self) -> None:
        if self._unsub_expiry is not None:
            self._unsub_expiry()
            self._unsub_expiry = None

    async def async_shutdown(self) -> None:
        self._cancel_expiry()
        await super().async_shutdown()
