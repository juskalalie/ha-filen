import logging
from homeassistant.core import HomeAssistant, ServiceCall
from .filen_api import FilenClient

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Filen.io folder management services."""
    email = config.get("email")
    password = config.get("password")
    client = FilenClient(email, password)

    if await client.login():
        async def handle_create_folder(call: ServiceCall):
            """Handle folder creation service call."""
            folder_name = call.data.get("folder_name")
            parent_folder_id = call.data.get("parent_folder_id", None)

            response = await client.create_folder(folder_name, parent_folder_id)
            if response.get("status"):
                _LOGGER.info("Folder created successfully: %s", folder_name)
            else:
                _LOGGER.error("Failed to create folder")

        async def handle_list_folders(call: ServiceCall):
            """Handle list folders service call."""
            folders = await client.list_folders()
            if folders.get("status"):
                _LOGGER.info("Folders: %s", folders["data"])
            else:
                _LOGGER.error("Failed to list folders")

        async def handle_delete_folder(call: ServiceCall):
            """Handle folder deletion service call."""
            folder_id = call.data.get("folder_id")

            response = await client.delete_folder(folder_id)
            if response.get("status"):
                _LOGGER.info("Folder deleted successfully: %s", folder_id)
            else:
                _LOGGER.error("Failed to delete folder")

        # Register services
        hass.services.async_register("filen_io", "create_folder", handle_create_folder)
        hass.services.async_register("filen_io", "list_folders", handle_list_folders)
        hass.services.async_register("filen_io", "delete_folder", handle_delete_folder)

    return True
