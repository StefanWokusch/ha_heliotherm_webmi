"""Config flow for Heliotherm WebMI."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import HeliothermWebMIClient, WebMIError
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_USE_SUBSCRIPTIONS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_SUBSCRIPTIONS,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Heliotherm WebMI."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            port = int(user_input[CONF_PORT])
            unique_id = HeliothermWebMIClient._normalize_base_url(
                user_input[CONF_HOST],
                port,
            )
            if self._host_already_configured(unique_id):
                return self.async_abort(reason="already_configured")

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            api = HeliothermWebMIClient(
                async_get_clientsession(self.hass),
                host=user_input[CONF_HOST],
                port=port,
            )
            try:
                await api.info()
            except WebMIError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=DEFAULT_SCAN_INTERVAL,
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                    vol.Required(
                        CONF_USE_SUBSCRIPTIONS,
                        default=DEFAULT_USE_SUBSCRIPTIONS,
                    ): cv.boolean,
                }
            ),
            errors=errors,
        )

    def _host_already_configured(self, normalized_base_url: str) -> bool:
        """Return true if an equivalent WebMI host is already configured."""
        for entry in self._async_current_entries():
            try:
                entry_base_url = HeliothermWebMIClient._normalize_base_url(
                    entry.data[CONF_HOST],
                    int(entry.data.get(CONF_PORT, DEFAULT_PORT)),
                )
            except (KeyError, TypeError, ValueError):
                continue
            if entry_base_url == normalized_base_url:
                return True
        return False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Heliotherm WebMI options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL,
                            self.config_entry.data.get(
                                CONF_SCAN_INTERVAL,
                                DEFAULT_SCAN_INTERVAL,
                            ),
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                    vol.Required(
                        CONF_USE_SUBSCRIPTIONS,
                        default=self.config_entry.options.get(
                            CONF_USE_SUBSCRIPTIONS,
                            self.config_entry.data.get(
                                CONF_USE_SUBSCRIPTIONS,
                                DEFAULT_USE_SUBSCRIPTIONS,
                            ),
                        ),
                    ): cv.boolean,
                }
            ),
        )
