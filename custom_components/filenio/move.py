import logging
from homeassistant.core import HomeAssistant, ServiceCall
from .filen_api import FilenClient

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Filen.io file and folder moving services with improved error handling."""
    email = config.get("email")
    password = config.get("password")
    client = FilenClient(email, password)

    async def show_notification(message, title="Filen.io"):
        """Send a notification to Home Assistant."""
        hass.services.async_call("persistent_notification", "create", {
            "title": title,
            "message": message,
        })

    if await client.login():
        async def handle_move_file(call: ServiceCall):
            """Handle move file service call with improved error handling."""
            file_id = call.data.get("file_id")
            destination_folder_id = call.data.get("destination_folder_id")

            response = await client.move_file(file_id, destination_folder_id)
            if response:
                message = f"✅ File {file_id} moved to {destination_folder_id} successfully."
                _LOGGER.info(message)
                await show_notification(message)
            else:
                message = f"❌ Failed to move file {file_id}. Check logs for details."
                _LOGGER.error(message)
                await show_notification(message)

        async def handle_move_folder(call: ServiceCall):
            """Handle move folder service call with improved error handling."""
            folder_id = call.data.get("folder_id")
            destination_folder_id = call.data.get("destination_folder_id")

            response = await client.move_folder(folder_id, destination_folder_id)
            if response:
                message = f"✅ Folder {folder_id} moved to {destination_folder_id} successfully."
                _LOGGER.info(message)
                await show_notification(message)
            else:
                message = f"❌ Failed to move folder {folder_id}. Check logs for details."
                _LOGGER.error(message)
                await show_notification(message)

        # Register services
        hass.services.async_register("filen_io", "move_file", handle_move_file)
        hass.services.async_register("filen_io", "move_folder", handle_move_folder)

    return True
