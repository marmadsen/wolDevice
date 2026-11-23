"""Config and options flow for the ESP32 WoL Bridge integration.

Written against the Home Assistant 2022.9 API so it runs on older installs.
"""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WolBridgeAuthError, WolBridgeClient, WolBridgeError
from .const import CONF_TARGET_MAC, DEFAULT_NAME, DOMAIN

MAC_PATTERN = re.compile("^[0-9A-Fa-f]{2}([:-][0-9A-Fa-f]{2}){5}$")


def _clean(value: Any) -> str:
    return str(value or "").strip()


async def _validate(hass: HomeAssistant, host: str, token: str) -> None:
    client = WolBridgeClient(async_get_clientsession(hass), host, token)
    await client.async_get_status()


def _optional_fields(defaults: dict[str, Any]) -> dict[Any, Any]:
    return {
        vol.Optional(CONF_TOKEN, description={"suggested_value": defaults.get(CONF_TOKEN, "")}): str,
        vol.Optional(CONF_TARGET_MAC, description={"suggested_value": defaults.get(CONF_TARGET_MAC, "")}): str,
    }


def _check_optional(user_input: dict[str, Any], errors: dict[str, str]) -> dict[str, Any]:
    data: dict[str, Any] = {
        CONF_TOKEN: _clean(user_input.get(CONF_TOKEN)),
        CONF_TARGET_MAC: _clean(user_input.get(CONF_TARGET_MAC)).upper(),
    }
    if data[CONF_TARGET_MAC] and not MAC_PATTERN.match(data[CONF_TARGET_MAC]):
        errors[CONF_TARGET_MAC] = "invalid_mac"
    return data


class WolBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = _clean(user_input[CONF_HOST])
            name = _clean(user_input.get(CONF_NAME)) or DEFAULT_NAME
            data = _check_optional(user_input, errors)
            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()
            if not errors:
                try:
                    await _validate(self.hass, host, data[CONF_TOKEN])
                except WolBridgeAuthError:
                    errors[CONF_TOKEN] = "invalid_auth"
                except WolBridgeError:
                    errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(title=name, data={CONF_HOST: host, **data})

        defaults = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
                vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
                **_optional_fields(defaults),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return WolBridgeOptionsFlow(config_entry)


class WolBridgeOptionsFlow(config_entries.OptionsFlow):
    """Let the user change the host, token and target MAC."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            host = _clean(user_input.get(CONF_HOST)) or current[CONF_HOST]
            data = {CONF_HOST: host, **_check_optional(user_input, errors)}
            if not errors:
                try:
                    await _validate(self.hass, host, data[CONF_TOKEN])
                except WolBridgeAuthError:
                    errors[CONF_TOKEN] = "invalid_auth"
                except WolBridgeError:
                    errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(title="", data=data)
            current = {**current, **user_input}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current.get(CONF_HOST, "")): str,
                **_optional_fields(current),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
