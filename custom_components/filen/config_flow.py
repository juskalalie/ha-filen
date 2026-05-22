"""Config flow for the Filen integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .client import FilenApiError, FilenAuthError, FilenClient
from .const import CONF_TWO_FACTOR_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TWO_FACTOR_CODE): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect to Filen."""
    client = FilenClient(
        session=async_get_clientsession(hass),
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        two_factor_code=data.get(CONF_TWO_FACTOR_CODE),
    )
    await client.authenticate()
    account_data = await client.async_get_account_data()

    email = account_data.get("email") or data[CONF_EMAIL]
    return {"title": f"Filen ({email})", "email": str(email)}


class FilenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Filen."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(info["email"].lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )
            except FilenAuthError:
                errors["base"] = "invalid_auth"
            except FilenApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - config flows should show unknown for unexpected errors
                _LOGGER.exception("Unexpected exception while configuring Filen")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
