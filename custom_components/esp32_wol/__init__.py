"""The ESP32 WoL Bridge integration.

Written against the Home Assistant 2022.9 API so it runs on older installs.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WolBridgeClient, WolBridgeError
from .const import DOMAIN, PLATFORMS


def get_client(hass: HomeAssistant, entry: ConfigEntry) -> WolBridgeClient:
    """Return the client stored for a config entry."""
    return hass.data[DOMAIN][entry.entry_id]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the bridge from a config entry."""
    settings = {**entry.data, **entry.options}
    client = WolBridgeClient(async_get_clientsession(hass), settings[CONF_HOST], settings.get(CONF_TOKEN))

    try:
        await client.async_get_status()
    except WolBridgeError as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
