import logging
import aiohttp
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

API_URL = "https://api.filen.io/v1/user"

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Filen.io sensor."""
    async_add_entities([FilenStorageSensor(hass)], True)

class FilenStorageSensor(Entity):
    """Representation of Filen.io storage usage."""

    def __init__(self, hass):
        """Initialize the sensor."""
        self._hass = hass
        self._state = None

    async def async_update(self):
        """Fetch the latest storage usage."""
        session = aiohttp.ClientSession()
        async with session.get(f"{API_URL}/storage") as response:
            if response.status == 200:
                data = await response.json()
                self._state = data.get("usedStorage", "Unknown")
            else:
                _LOGGER.error("Failed to fetch Filen.io storage info")
        await session.close()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Filen.io Storage"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
