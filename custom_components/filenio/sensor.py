import logging
from homeassistant.helpers.entity import Entity
from .filen_api import FilenClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Filen.io sensor."""
    email = config.get("email")
    password = config.get("password")

    client = FilenClient(email, password)
    if await client.login():
        async_add_entities([FilenStorageSensor(client)], True)

class FilenStorageSensor(Entity):
    """Representation of Filen.io storage usage."""

    def __init__(self, client):
        """Initialize the sensor."""
        self._client = client
        self._state = None

    async def async_update(self):
        """Fetch the latest storage usage."""
        data = await self._client.get_storage_info()
        self._state = data["data"]["usedStorage"]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Filen.io Storage"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
