import logging
from homeassistant.core import HomeAssistant, ServiceCall
from .filen_api import FilenClient

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Filen.io file and folder moving services."""
    email = config.get("email")
    password = config.get("password")
    client = FilenClient(email, password)

    if await client.login():
        async def handle_move_file(call: ServiceCall):
            """Handle move file service call."""
            file_id = call.data.get("file_id")
            destination_folder_id = call.data.get("destination_folder_id")

            response = await client.move_file(file_id, destination_folder_id)
            if response.get("status"):
                _LOGGER.info("File moved successfully: %s → %s", file_id, destination_folder_id)
            else:
                _LOGGER.error("Failed to move file")

        async def handle_move_folder(call: ServiceCall):
            """Handle move folder service call."""
            folder_id = call.data.get("folder_id")
            destination_folder_id = call.data.get("destination_folder_id")

            response = await client.move_folder(folder_id, destination_folder_id)
            if response.get("status"):
                _LOGGER.info("Folder moved successfully: %s → %s", folder_id, destination_folder_id)
            else:
                _LOGGER.error("Failed to move folder")

        # Register services
        hass.services.async_register("filen_io", "move_file", handle_move_file)
        hass.services.async_register("filen_io", "move_folder", handle_move_folder)

    return True
