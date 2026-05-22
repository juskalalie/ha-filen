"""Home Assistant integration for Filen account and storage sensors."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import FilenApiError, FilenAuthError, FilenClient
from .const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Filen from a config entry."""
    client = FilenClient(
        session=async_get_clientsession(hass),
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        api_key=entry.data.get(CONF_API_KEY),
    )

    try:
        await client.authenticate()
        if client.api_key != entry.data.get(CONF_API_KEY):
            hass.config_entries.async_update_entry(
                entry,
                data={
                    CONF_EMAIL: entry.data[CONF_EMAIL],
                    CONF_PASSWORD: entry.data[CONF_PASSWORD],
                    CONF_API_KEY: client.api_key,
                },
            )
    except FilenAuthError as exc:
        raise ConfigEntryAuthFailed(str(exc)) from exc
    except FilenApiError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
