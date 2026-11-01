"""Read-only temperatures, percentage and observation timestamp."""

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SemaDataUpdateCoordinator
from .entity import SemaEntity
from .protocol import (
    CONFIG_KEYS,
    CONFIG_PERCENTAGES,
    CONFIG_TEMPERATURES,
    MODE_OPTIONS,
    TEMPERATURE_KEYS,
)
from .runtime import SemaConfigEntry

PARALLEL_UPDATES = 0
OPTIONAL_TEMPERATURES = {"exchanger_temp", "e_temp", "f_temp", "g_temp"}
SENSORS = (
    *(
        SensorEntityDescription(
            key=f"modes.{key}",
            translation_key=key,
            device_class=SensorDeviceClass.ENUM,
            options=list(options),
            icon={
                "operating_mode": "mdi:heat-pump",
                "season": "mdi:weather-partly-snowy-rainy",
                "activity": "mdi:heat-pump-outline",
                "heat_source": "mdi:radiator",
                "dhw_mode": "mdi:water-boiler",
            }[key],
        )
        for key, options in MODE_OPTIONS.items()
    ),
    *(
        SensorEntityDescription(
            key=f"configuration.{key}",
            translation_key=key,
            device_class=SensorDeviceClass.TEMPERATURE
            if key in CONFIG_TEMPERATURES
            else SensorDeviceClass.DURATION
            if key == "dhw_time_limit_minutes"
            else None,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS
            if key in CONFIG_TEMPERATURES
            else PERCENTAGE
            if key in CONFIG_PERCENTAGES
            else UnitOfTime.MINUTES
            if key == "dhw_time_limit_minutes"
            else None,
            entity_category=None
            if key == "reference_temp"
            else EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=key == "reference_temp",
        )
        for key in CONFIG_KEYS
    ),
    SensorEntityDescription(
        key="configuration.schedule",
        translation_key="setback_schedule",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="configuration_observed_at",
        translation_key="configuration_observed_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    *(
        SensorEntityDescription(
            key=f"temperatures.{key}",
            translation_key=key,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC
            if key in OPTIONAL_TEMPERATURES
            else None,
            entity_registry_enabled_default=key not in OPTIONAL_TEMPERATURES,
        )
        for key in TEMPERATURE_KEYS
    ),
    SensorEntityDescription(
        key="power_percent",
        translation_key="power_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
    ),
    SensorEntityDescription(
        key="observed_at",
        translation_key="observed_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SemaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    assert coordinator.info is not None
    async_add_entities(
        SemaSensor(coordinator, description)
        for description in SENSORS
        if description.key == "observed_at"
        or description.key in coordinator.info.capabilities
        or (
            description.key == "configuration_observed_at"
            and any(
                key.startswith("configuration.")
                for key in coordinator.info.capabilities
            )
        )
    )


class SemaSensor(SemaEntity, SensorEntity):
    def __init__(
        self,
        coordinator: SemaDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if self.entity_description.key.startswith("configuration."):
            return self.coordinator.configuration_available
        if self.entity_description.key == "configuration_observed_at":
            return self.coordinator.sema_available
        if self.entity_description.key == "observed_at":
            return self.coordinator.sema_available
        return super().available

    @property
    def native_value(self) -> int | float | str | datetime | None:
        data = self.coordinator.data
        key = self.entity_description.key
        if key.startswith("modes."):
            return data.modes.get(key.removeprefix("modes."))
        if key == "configuration_observed_at":
            return data.configuration.observed_at if data.configuration else None
        if key.startswith("configuration."):
            configuration = data.configuration
            if configuration is None:
                return None
            if key == "configuration.schedule":
                return (
                    sum(len(intervals) for intervals in configuration.schedule.values())
                    if configuration.schedule is not None
                    else None
                )
            return configuration.values.get(key.removeprefix("configuration."))
        if key == "observed_at":
            return data.observed_at
        if key == "power_percent":
            return data.power_percent
        return data.temperatures.get(key.removeprefix("temperatures."))

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        if self.entity_description.key != "configuration.schedule":
            return None
        configuration = self.coordinator.data.configuration
        if (
            not self.available
            or configuration is None
            or configuration.schedule is None
        ):
            return None
        return {
            "schedule": {
                day: [{"from": start, "to": end} for start, end in intervals]
                for day, intervals in configuration.schedule.items()
            }
        }
