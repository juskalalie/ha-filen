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
from .const import CONF_API_KEY, CONF_TWO_FACTOR_CODE, DOMAIN

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
    if not client.api_key:
        raise FilenAuthError("Filen login response did not contain an API key")

    return {
        "title": f"Filen ({email})",
        "email": str(email),
        CONF_API_KEY: client.api_key,
    }


def _entry_data_from_input(
    user_input: dict[str, Any], info: dict[str, str]
) -> dict[str, str]:
    """Build persisted config entry data without storing one-time 2FA codes."""
    return {
        CONF_EMAIL: user_input[CONF_EMAIL],
        CONF_PASSWORD: user_input[CONF_PASSWORD],
        CONF_API_KEY: info[CONF_API_KEY],
    }


class FilenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Filen."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: config_entries.ConfigEntry | None = None

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
                    data=_entry_data_from_input(user_input, info),
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

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle a reauth request."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for fresh credentials and a current two-factor code."""
        errors: dict[str, str] = {}
        if self._reauth_entry is None:
            return self.async_abort(reason="reauth_failed")

        email = self._reauth_entry.data[CONF_EMAIL]

        if user_input is not None:
            validation_data = {
                CONF_EMAIL: email,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_TWO_FACTOR_CODE: user_input.get(CONF_TWO_FACTOR_CODE),
            }
            try:
                info = await validate_input(self.hass, validation_data)
                new_data = _entry_data_from_input(validation_data, info)
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=new_data,
                    title=info["title"],
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except FilenAuthError:
                errors["base"] = "invalid_auth"
            except FilenApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - config flows should show unknown for unexpected errors
                _LOGGER.exception("Unexpected exception while reauthenticating Filen")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PASSWORD,
                        default=self._reauth_entry.data.get(CONF_PASSWORD, ""),
                    ): cv.string,
                    vol.Optional(CONF_TWO_FACTOR_CODE): cv.string,
                }
            ),
            errors=errors,
        )
