"""Sensor platform for Filen account and storage information."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

import async_timeout
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .client import FilenApiError, FilenClient
from .const import (
    ATTR_ACCOUNT_ID,
    ATTR_AVATAR_URL,
    ATTR_BASE_FOLDER_UUID,
    ATTR_DISPLAY_NAME,
    ATTR_EMAIL,
    ATTR_IS_PREMIUM,
    ATTR_NICK_NAME,
    ATTR_PLAN_NAMES,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

BYTES_PER_GIGABYTE = 1_000_000_000


def _bytes_to_gigabytes(value: Any) -> float | None:
    """Convert a byte value returned by Filen into decimal gigabytes."""
    if value is None:
        return None

    try:
        return round(float(value) / BYTES_PER_GIGABYTE, 2)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class FilenSensorEntityDescription(SensorEntityDescription):
    """Describes a Filen sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSOR_DESCRIPTIONS: tuple[FilenSensorEntityDescription, ...] = (
    FilenSensorEntityDescription(
        key="storage_used",
        translation_key="storage_used",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _bytes_to_gigabytes(data.get("storage_used")),
    ),
    FilenSensorEntityDescription(
        key="storage_total",
        translation_key="storage_total",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _bytes_to_gigabytes(data.get("storage_total")),
    ),
    FilenSensorEntityDescription(
        key="storage_percentage",
        translation_key="storage_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:cloud-percent",
        value_fn=lambda data: data.get("storage_percentage"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Filen sensors based on a config entry."""
    client: FilenClient = entry.runtime_data
    coordinator = FilenDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        FilenAccountSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class FilenDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and cache Filen account data."""

    def __init__(self, hass: HomeAssistant, client: FilenClient) -> None:
        """Initialize the data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch account/storage data from Filen."""
        try:
            async with async_timeout.timeout(30):
                return await self.client.async_get_account_data()
        except FilenApiError as err:
            raise UpdateFailed(f"Error communicating with Filen: {err}") from err


class FilenAccountSensor(CoordinatorEntity[FilenDataUpdateCoordinator], SensorEntity):
    """Sensor representing one Filen account/storage value."""

    entity_description: FilenSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FilenDataUpdateCoordinator,
        entry: ConfigEntry,
        description: FilenSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Filen",
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional account details."""
        data = self.coordinator.data or {}
        attrs = {
            ATTR_EMAIL: data.get("email"),
            ATTR_ACCOUNT_ID: data.get("account_id"),
            ATTR_IS_PREMIUM: data.get("is_premium"),
            ATTR_BASE_FOLDER_UUID: data.get("base_folder_uuid"),
            ATTR_AVATAR_URL: data.get("avatar_url"),
            ATTR_DISPLAY_NAME: data.get("display_name"),
            ATTR_NICK_NAME: data.get("nick_name"),
            ATTR_PLAN_NAMES: data.get("plan_names"),
        }
        return {key: value for key, value in attrs.items() if value not in (None, "", [])}
