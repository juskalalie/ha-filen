"""
Config flow for Filen.io integration.
"""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect to Filen.io."""
    from . import FilenClient
    import aiohttp
    
    session = aiohttp.ClientSession()
    
    try:
        client = FilenClient(
            session=session, 
            email=data[CONF_EMAIL],
            password=data[CONF_PASSWORD],
        )
        
        await client.authenticate()
        user_info = await client.get_user_info()
        
        return {"title": f"Filen.io ({user_info['email']})"}
    except Exception as e:
        _LOGGER.error(f"Could not authenticate with Filen.io: {e}")
        raise CannotConnect from e
    finally:
        await session.close()


class FilenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Filen.io."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Check if this email is already configured
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""