"""
Sensor platform for Filen.io integration.
Displays storage usage information from Filen.io.
"""
import logging
from datetime import timedelta
import async_timeout

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation, UnitOfDataRate
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Update frequency (every 30 minutes)
UPDATE_INTERVAL = timedelta(minutes=30)

async def async_setup_entry(
    hass: HomeAssistant, 
    entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Filen.io sensors based on a config entry."""
    filen_client = hass.data[DOMAIN][entry.entry_id]
    
    # Create update coordinator
    coordinator = FilenDataUpdateCoordinator(hass, filen_client)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Create entities
    entities = [
        FilenStorageUsageSensor(coordinator, "storage_used", "Storage Used"),
        FilenStorageUsageSensor(coordinator, "storage_total", "Storage Total"),
        FilenStorageUsageSensor(coordinator, "storage_percentage", "Storage Usage Percentage"),
        FilenStorageUploadSensor(coordinator, "upload_speed", "Upload Speed"),
    ]
    
    async_add_entities(entities)


class FilenDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Filen.io data."""

    def __init__(self, hass, filen_client):
        """Initialize the data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.filen_client = filen_client
        self.user_info = None

    async def _async_update_data(self):
        """Fetch data from Filen.io."""
        try:
            async with async_timeout.timeout(30):
                storage_data = await self.filen_client.get_storage_usage()
                user_data = await self.filen_client.get_user_info()
                
                # Store user info for device info
                self.user_info = user_data
                
                # Calculate the storage percentage
                storage_percentage = 0
                if storage_data["maxStorage"] > 0:
                    storage_percentage = (storage_data["storage"] / storage_data["maxStorage"]) * 100
                
                return {
                    "storage_used": storage_data["storage"],
                    "storage_total": storage_data["maxStorage"],
                    "storage_percentage": storage_percentage,
                    "upload_speed": storage_data["maxUploadSpeed"],
                    "email": user_data["email"],
                    "plan": user_data["plan"],
                }
        except Exception as err:
            _LOGGER.error(f"Error updating Filen.io data: {err}")
            raise


class FilenStorageUsageSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing Filen.io storage usage."""

    def __init__(self, coordinator, sensor_type, name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.sensor_type = sensor_type
        self._name = name
        self._attr_unique_id = f"filen_{sensor_type}"
        
        if sensor_type == "storage_percentage":
            self._attr_native_unit_of_measurement = "%"
            self._attr_device_class = None
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_icon = "mdi:percent"
        else:
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = UnitOfInformation.BYTES
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_icon = "mdi:cloud"

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.coordinator.user_info:
            email = self.coordinator.data.get("email", "")
            return f"Filen {email} {self._name}"
        return f"Filen {self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(self.sensor_type, 0)
        return 0

    @property
    def extra_state_attributes(self):
        """Return additional information about the sensor."""
        if not self.coordinator.data:
            return {}
        
        # Add relevant attributes
        return {
            "plan": self.coordinator.data.get("plan", "Unknown"),
            "email": self.coordinator.data.get("email", "Unknown"),
        }

    @property
    def device_info(self):
        """Return device information about this entity."""
        if not self.coordinator.user_info:
            return None
            
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.get("email", "unknown"))},
            name=f"Filen.io ({self.coordinator.data.get('email', 'unknown')})",
            manufacturer="Filen",
            model=self.coordinator.data.get("plan", "Unknown"),
            sw_version="1.0.0",
        )


class FilenStorageUploadSensor(FilenStorageUsageSensor):
    """Sensor representing Filen.io upload speed."""

    def __init__(self, coordinator, sensor_type, name):
        """Initialize the upload speed sensor."""
        super().__init__(coordinator, sensor_type, name)
        self._attr_device_class = SensorDeviceClass.DATA_RATE
        self._attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND
        self._attr_icon = "mdi:upload"
