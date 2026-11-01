"""Common identity and availability for read-only SEMA entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SemaDataUpdateCoordinator


class SemaEntity(CoordinatorEntity[SemaDataUpdateCoordinator]):
    """All entities subscribe to one coordinator and perform no network I/O."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SemaDataUpdateCoordinator, key: str) -> None:
        super().__init__(coordinator)
        info = coordinator.info
        assert info is not None
        self._attr_unique_id = f"{info.device_uid}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.device_uid)},
            name=info.name,
            manufacturer=info.manufacturer,
            model=info.model,
            sw_version=info.firmware_version,
        )

    @property
    def available(self) -> bool:
        return self.coordinator.measurements_available
