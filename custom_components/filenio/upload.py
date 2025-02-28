import logging
from homeassistant.core import HomeAssistant, ServiceCall
from .filen_api import FilenClient

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Filen.io upload service."""
    email = config.get("email")
    password = config.get("password")
    client = FilenClient(email, password)

    if await client.login():
        async def handle_upload(call: ServiceCall):
            """Handle the upload service call."""
            file_path = call.data.get("file_path")
            response = await client.upload_file(file_path)
            if response["status"]:
                _LOGGER.info("File uploaded successfully")
            else:
                _LOGGER.error("Failed to upload file")

        hass.services.async_register("filenio", "upload_file", handle_upload)

    return True
