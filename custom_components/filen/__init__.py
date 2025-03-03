"""
Home Assistant integration for Filen.io cloud storage service.
This integration allows you to authenticate with Filen.io and interact with your files.
"""
import logging
import hashlib
import base64
import json
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryAuthFailed

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)

DOMAIN = "filen"
API_BASE_URL = "https://gateway.filen.io"

# Config schema
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

# Supported platforms
PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Filen component."""
    if DOMAIN not in config:
        return True

    hass.data.setdefault(DOMAIN, {})
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Filen from a config entry."""
    session = aiohttp.ClientSession()
    
    filen_client = FilenClient(
        session=session,
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )
    
    try:
        await filen_client.authenticate()
    except Exception as exc:
        await session.close()
        raise ConfigEntryAuthFailed from exc
    
    hass.data[DOMAIN][entry.entry_id] = filen_client
    
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    
    if unload_ok:
        filen_client = hass.data[DOMAIN].pop(entry.entry_id)
        await filen_client.session.close()
    
    return unload_ok

class FilenClient:
    """Filen API client."""
    
    def __init__(self, session, email, password):
        """Initialize the Filen client."""
        self.session = session
        self.email = email
        self.password = password
        self.apikey = None
        self.metadata_key = None
        self.master_key = None
        self.auth_info = None
    
    async def authenticate(self):
        """Authenticate with Filen.io and obtain the API key."""
        # Step 1: Get authentication info
        auth_info = await self._get_auth_info()
        self.auth_info = auth_info
        _LOGGER.info("get auth")
        
        # Step 2: Calculate password hash
        password_hash = self._calculate_password_hash(
            self.password, 
            auth_info["salt"]
        )
        _LOGGER.info("pass hash")
        
        # Step 3: Login
        login_data = {
            "email": self.email,
            "password": password_hash,
            "twoFactorCode": "",  # Leave empty if 2FA is not enabled
            "authVersion": 2
        }
        _LOGGER.info("login_data")
        
        async with self.session.post(f"{API_BASE_URL}/v3/login", json=login_data) as response:
            if response.status != 200:
                response_text = await response.text()
                _LOGGER.error(f"Failed to login: {response_text}")
                raise ConfigEntryAuthFailed(f"Failed to login: {response_text}")
            
            login_response = await response.json()
            
            if login_response.get("status") != True:  # Fixed boolean value
                raise ConfigEntryAuthFailed(login_response.get("message", "Unknown error"))
            
            # Store the API key for future requests
            self.apikey = login_response["data"]["apiKey"]
            self.metadata_key = login_response["data"]["metadataKey"]
            self.master_key = login_response["data"]["masterKeys"][0]
            
            _LOGGER.info("Successfully authenticated with Filen.io")
            return True
    
    async def _get_auth_info(self):
        """Get authentication information from Filen.io."""
        data = {"email": self.email}
        
        async with self.session.post(f"{API_BASE_URL}/v3/auth/info", json=data) as response:
            if response.status != 200:
                response_text = await response.text()
                _LOGGER.error(f"Failed to get auth info: {response_text}")
                raise ConfigEntryAuthFailed(f"Failed to get auth info: {response_text}")
            
            response_data = await response.json()
            
            if response_data.get("status") != True:  # Fixed boolean value
                raise ConfigEntryAuthFailed(response_data.get("message", "Unknown error"))
            
            return response_data["data"]
    
    def _calculate_password_hash(self, password, salt):
        """Calculate password hash using SHA512."""
        # First round: SHA512(password + salt)
        first_hash = hashlib.sha512((password + salt).encode()).hexdigest()
        
        # Second round: SHA512(first_hash + salt)
        second_hash = hashlib.sha512((first_hash + salt).encode()).hexdigest()
        
        return second_hash
    
    async def get_user_info(self):
        """Get user information."""
        if not self.apikey:
            await self.authenticate()
        
        data = {"apiKey": self.apikey}
        
        async with self.session.post(f"{API_BASE_URL}/v3/user/info", json=data) as response:
            if response.status != 200:
                response_text = await response.text()
                _LOGGER.error(f"Failed to get user info: {response_text}")
                raise Exception(f"Failed to get user info: {response_text}")
            
            response_data = await response.json()
            
            if response_data.get("status") != True:  # Fixed boolean value
                raise Exception(response_data.get("message", "Unknown error"))
            
            return response_data["data"]
    
    async def get_storage_usage(self):
        """Get storage usage information."""
        if not self.apikey:
            await self.authenticate()
        
        data = {"apiKey": self.apikey}
        
        async with self.session.post(f"{API_BASE_URL}/v3/user/storage", json=data) as response:
            if response.status != 200:
                response_text = await response.text()
                _LOGGER.error(f"Failed to get storage info: {response_text}")
                raise Exception(f"Failed to get storage info: {response_text}")
            
            response_data = await response.json()
            
            if response_data.get("status") != True:  # Fixed boolean value
                raise Exception(response_data.get("message", "Unknown error"))
            
            return response_data["data"]
