"""
Config flow for Filen.io integration.
"""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from . import FilenApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class FilenFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Filen.io."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Try to log in with the provided credentials
                async with FilenApi(self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]) as filen:
                    await filen.login()

                # If login is successful, create the config entry
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )
            except Exception as error:
                _LOGGER.exception("Error authenticating with Filen.io: %s", error)
                errors["base"] = "auth"

        # Show the form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
        )
