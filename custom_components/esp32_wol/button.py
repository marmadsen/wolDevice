"""Button platform: send a magic packet."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import get_client
from .api import WolBridgeClient, WolBridgeError
from .const import CONF_TARGET_MAC, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the wake button."""
    mac = ({**entry.data, **entry.options}).get(CONF_TARGET_MAC) or None
    async_add_entities([WakeButton(get_client(hass, entry), entry, mac)])


class WakeButton(ButtonEntity):
    """Pressing it wakes the target PC."""

    _attr_has_entity_name = True
    _attr_name = "Wake"
    _attr_icon = "mdi:power"

    def __init__(self, client: WolBridgeClient, entry: ConfigEntry, mac: str | None) -> None:
        self._client = client
        self._mac = mac
        self._attr_unique_id = f"{entry.entry_id}_wake"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="DIY",
            model="ESP32-S3 W5500 WoL bridge",
            configuration_url=f"http://{({**entry.data, **entry.options})[CONF_HOST]}/",
        )

    async def async_press(self) -> None:
        try:
            await self._client.async_wake(self._mac)
        except WolBridgeError as err:
            raise HomeAssistantError(str(err)) from err
