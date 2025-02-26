import aiohttp
import logging
import os
from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)
API_UPLOAD_URL = "https://api.filen.io/v1/upload"

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Filen.io upload service."""

    async def handle_upload(call: ServiceCall):
        """Handle the upload service call."""
        file_path = call.data.get("file_path")
        if not os.path.exists(file_path):
            _LOGGER.error("File does not exist: %s", file_path)
            return
        
        with open(file_path, "rb") as file:
            session = aiohttp.ClientSession()
            async with session.post(API_UPLOAD_URL, data={"file": file}) as response:
                if response.status == 200:
                    _LOGGER.info("File uploaded successfully")
                else:
                    _LOGGER.error("Failed to upload file")
            await session.close()

    hass.services.async_register("filen_io", "upload_file", handle_upload)

    return True
