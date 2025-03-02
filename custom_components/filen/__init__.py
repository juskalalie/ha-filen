"""
Home Assistant integration for Filen.io cloud storage.
This integration allows you to upload and download files from your Filen.io account.
"""
import asyncio
import logging
import os
import voluptuous as vol
import hashlib
import base64
import json
import time
import aiohttp
from datetime import timedelta
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN = "filen"
SCAN_INTERVAL = timedelta(minutes=30)

# Configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Services
SERVICE_UPLOAD_FILE = "upload_file"
SERVICE_DOWNLOAD_FILE = "download_file"
SERVICE_LIST_FILES = "list_files"

ATTR_LOCAL_PATH = "local_path"
ATTR_REMOTE_PATH = "remote_path"
ATTR_FOLDER_UUID = "folder_uuid"

SERVICE_UPLOAD_FILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LOCAL_PATH): cv.string,
        vol.Required(ATTR_FOLDER_UUID): cv.string,
    }
)

SERVICE_DOWNLOAD_FILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_REMOTE_PATH): cv.string,
        vol.Required(ATTR_LOCAL_PATH): cv.string,
    }
)

SERVICE_LIST_FILES_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_FOLDER_UUID): cv.string,
    }
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Filen component."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Filen from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    filen = FilenApi(hass, email, password)
    try:
        await filen.login()
    except Exception as err:
        _LOGGER.error("Failed to login to Filen.io: %s", err)
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = filen

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPLOAD_FILE,
        filen.handle_upload_file,
        schema=SERVICE_UPLOAD_FILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DOWNLOAD_FILE,
        filen.handle_download_file,
        schema=SERVICE_DOWNLOAD_FILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_FILES,
        filen.handle_list_files,
        schema=SERVICE_LIST_FILES_SCHEMA,
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Filen config entry."""
    # Unregister services
    for service in [SERVICE_UPLOAD_FILE, SERVICE_DOWNLOAD_FILE, SERVICE_LIST_FILES]:
        hass.services.async_remove(DOMAIN, service)

    hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True

class FilenApi:
    """Wrapper for the Filen.io API."""

    def __init__(self, hass: HomeAssistant, email: str, password: str):
        """Initialize the API client."""
        self.hass = hass
        self.email = email
        self.password = password
        self.auth_token = None
        self.master_key = None
        self.session = aiohttp.ClientSession()
        self.api_base_url = "https://api.filen.io"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    def _hash_password(self, password: str) -> str:
        """Hash the password using SHA512."""
        return hashlib.sha512(password.encode()).hexdigest()

    async def login(self) -> None:
        """Log in to Filen.io and get an auth token."""
        hashed_password = self._hash_password(self.password)

        login_data = {
            "email": self.email,
            "password": hashed_password,
            "twoFactorCode": None,  # Optional 2FA code
            "authVersion": 2
        }

        try:
            response = await self.session.post(
                f"{self.api_base_url}/v3/login",
                json=login_data
            )
            data = await response.json()

            if not data.get("status"):
                raise Exception(data.get("message", "Unknown login error"))

            self.auth_token = data.get("data", {}).get("apiKey")
            
            # For simplicity, we're storing the master key as is
            # In a real implementation, you would need to decrypt it properly
            self.master_key = data.get("data", {}).get("masterKeys")
            
            _LOGGER.info("Successfully logged in to Filen.io")
        except Exception as err:
            _LOGGER.error("Failed to login to Filen.io: %s", err)
            raise

    async def handle_upload_file(self, call: ServiceCall) -> None:
        """Handle the file upload service call."""
        local_path = call.data[ATTR_LOCAL_PATH]
        folder_uuid = call.data[ATTR_FOLDER_UUID]
        
        try:
            if not os.path.exists(local_path):
                raise Exception(f"Local file not found: {local_path}")
                
            await self.upload_file(local_path, folder_uuid)
            _LOGGER.info("Successfully uploaded file %s to Filen.io", local_path)
        except Exception as err:
            _LOGGER.error("Failed to upload file to Filen.io: %s", err)

    async def handle_download_file(self, call: ServiceCall) -> None:
        """Handle the file download service call."""
        remote_path = call.data[ATTR_REMOTE_PATH]
        local_path = call.data[ATTR_LOCAL_PATH]
        
        try:
            await self.download_file(remote_path, local_path)
            _LOGGER.info("Successfully downloaded file %s from Filen.io to %s", remote_path, local_path)
        except Exception as err:
            _LOGGER.error("Failed to download file from Filen.io: %s", err)

    async def handle_list_files(self, call: ServiceCall) -> None:
        """Handle the list files service call."""
        folder_uuid = call.data.get(ATTR_FOLDER_UUID, "base")
        
        try:
            files = await self.list_files(folder_uuid)
            _LOGGER.info("Files in folder %s: %s", folder_uuid, files)
            
            # You could create a persistent notification here with the file list
            self.hass.components.persistent_notification.create(
                f"Files in folder {folder_uuid}:\n" + "\n".join([f"- {file['name']}" for file in files]),
                title="Filen.io Files",
                notification_id=f"filen_files_{folder_uuid}"
            )
        except Exception as err:
            _LOGGER.error("Failed to list files from Filen.io: %s", err)

    async def upload_file(self, local_path: str, folder_uuid: str) -> Dict[str, Any]:
        """Upload a file to Filen.io."""
        if not self.auth_token:
            await self.login()

        file_name = os.path.basename(local_path)
        file_size = os.path.getsize(local_path)
        file_mime = "application/octet-stream"  # You might want to determine this properly
        
        # Step 1: Get upload info
        upload_info_data = {
            "apiKey": self.auth_token,
            "uuid": folder_uuid,
            "name": file_name,
            "size": file_size,
            "chunks": 1  # Simple implementation with 1 chunk
        }
        
        response = await self.session.post(
            f"{self.api_base_url}/v3/upload/prepare",
            json=upload_info_data
        )
        
        upload_info = await response.json()
        if not upload_info.get("status"):
            raise Exception(upload_info.get("message", "Upload preparation failed"))
        
        upload_key = upload_info["data"]["uploadKey"]
        
        # Step 2: Upload the file 
        # In a real implementation, you would need to encrypt the file before uploading
        # For simplicity, we'll just upload the raw file
        with open(local_path, "rb") as file:
            file_content = file.read()
            
            upload_data = {
                "uploadKey": upload_key,
                "chunk": 1,  # Assuming only 1 chunk for simplicity
            }
            
            files = {
                "file": (file_name, file_content, file_mime)
            }
            
            # This is simplified, in a real implementation you'd use multipart form data
            form = aiohttp.FormData()
            form.add_field("uploadKey", upload_key)
            form.add_field("chunk", "1")
            form.add_field("file", file_content, filename=file_name, content_type=file_mime)
            
            response = await self.session.post(
                f"{self.api_base_url}/v3/upload",
                data=form
            )
            
            data = await response.json()
            if not data.get("status"):
                raise Exception(data.get("message", "File upload failed"))
            
            return data

    async def download_file(self, remote_path: str, local_path: str) -> None:
        """Download a file from Filen.io."""
        if not self.auth_token:
            await self.login()
            
        # First, we need to find the file metadata
        # This would involve listing files and finding the one with matching name
        # For simplicity, we assume remote_path is the file UUID
        
        # Get file metadata
        file_info_data = {
            "apiKey": self.auth_token,
            "uuid": remote_path
        }
        
        response = await self.session.post(
            f"{self.api_base_url}/v3/file/info",
            json=file_info_data
        )
        
        file_info = await response.json()
        if not file_info.get("status"):
            raise Exception(file_info.get("message", "Could not get file info"))
        
        # Get download link
        download_data = {
            "apiKey": self.auth_token,
            "uuid": remote_path
        }
        
        response = await self.session.post(
            f"{self.api_base_url}/v3/download/file",
            json=download_data
        )
        
        download_info = await response.json()
        if not download_info.get("status"):
            raise Exception(download_info.get("message", "Could not get download link"))
        
        # Download the file
        # In a real implementation, you would also need to decrypt the file after downloading
        download_url = download_info["data"]["downloadURL"]
        
        async with self.session.get(download_url) as response:
            content = await response.read()
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            
            with open(local_path, "wb") as file:
                file.write(content)

    async def list_files(self, folder_uuid: str = "base") -> List[Dict[str, Any]]:
        """List files in a folder."""
        if not self.auth_token:
            await self.login()
            
        list_data = {
            "apiKey": self.auth_token,
            "uuid": folder_uuid,
            "skipCache": True
        }
        
        response = await self.session.post(
            f"{self.api_base_url}/v3/dir/content",
            json=list_data
        )
        
        data = await response.json()
        if not data.get("status"):
            raise Exception(data.get("message", "Could not list files"))
        
        return data.get("data", {}).get("files", [])
