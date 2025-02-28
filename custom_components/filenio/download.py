import logging
from homeassistant.core import HomeAssistant, ServiceCall
from .filen_api import FilenClient

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Filen.io download service."""
    email = config.get("email")
    password = config.get("password")
    client = FilenClient(email, password)

    if await client.login():
        async def handle_download(call: ServiceCall):
            """Handle the download service call."""
            file_id = call.data.get("file_id")
            save_path = call.data.get("save_path")

            success = await client.download_file(file_id, save_path)
            if success:
                _LOGGER.info("File downloaded and decrypted successfully: %s", save_path)
            else:
                _LOGGER.error("Failed to download file")

        hass.services.async_register("filen_io", "download_file", handle_download)

    return True
