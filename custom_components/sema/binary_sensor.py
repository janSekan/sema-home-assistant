"""Read-only pump states and separate transport/freshness diagnostics."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SemaDataUpdateCoordinator
from .entity import SemaEntity
from .runtime import SemaConfigEntry

PARALLEL_UPDATES = 0
DIAGNOSTICS = {"sema_available", "pump_available", "snapshot_fresh"}
BINARY_SENSORS = (
    BinarySensorEntityDescription(
        key="states.heating",
        translation_key="heating",
        icon="mdi:radiator",
    ),
    BinarySensorEntityDescription(
        key="states.dhw",
        translation_key="dhw",
        icon="mdi:water-boiler",
    ),
    BinarySensorEntityDescription(
        key="states.defrost", translation_key="defrost", icon="mdi:snowflake-melt"
    ),
    BinarySensorEntityDescription(
        key="states.fault",
        translation_key="fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="sema_available",
        translation_key="sema_available",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="states.power_on", translation_key="power_on", icon="mdi:power"
    ),
    BinarySensorEntityDescription(
        key="states.setback", translation_key="setback", icon="mdi:weather-night"
    ),
    BinarySensorEntityDescription(
        key="states.high_tariff", translation_key="high_tariff", icon="mdi:cash-clock"
    ),
    BinarySensorEntityDescription(
        key="configuration_fresh",
        translation_key="configuration_fresh",
        icon="mdi:clipboard-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="pump_available",
        translation_key="pump_available",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="snapshot_fresh",
        translation_key="snapshot_fresh",
        icon="mdi:clock-check-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SemaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    assert coordinator.info is not None
    async_add_entities(
        SemaBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.key in DIAGNOSTICS
        or description.key in coordinator.info.capabilities
        or (
            description.key == "configuration_fresh"
            and any(
                key.startswith("configuration.")
                for key in coordinator.info.capabilities
            )
        )
    )


class SemaBinarySensor(SemaEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator: SemaDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        key = self.entity_description.key
        if key == "configuration_fresh":
            return self.coordinator.sema_available
        if key == "sema_available":
            return True
        if key == "snapshot_fresh":
            return self.coordinator.sema_available
        if key == "pump_available":
            # A stale observation cannot confirm the pump's current reachability.
            data = self.coordinator.data
            return self.coordinator.sema_available and (
                data.observed_at is None or self.coordinator.snapshot_fresh
            )
        return super().available

    @property
    def is_on(self) -> bool | None:
        key = self.entity_description.key
        if key == "configuration_fresh":
            configuration = self.coordinator.data.configuration
            return (
                None
                if configuration is None or configuration.observed_at is None
                else self.coordinator.configuration_available
            )
        if key == "sema_available":
            return self.coordinator.sema_available
        if key == "snapshot_fresh":
            return (
                None
                if self.coordinator.data.observed_at is None
                else self.coordinator.snapshot_fresh
            )
        if key == "pump_available":
            return self.coordinator.data.pump_available
        return self.coordinator.data.states.get(key.removeprefix("states."))
