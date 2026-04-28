"""Roborock Vacuum — intégration custom HACS."""
from __future__ import annotations

import logging
from typing import Any

from roborock.containers import UserData, HomeData
from roborock.web_api import RoborockApiClient
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_EMAIL, CONF_USER_DATA, CONF_HOME_DATA
from .coordinator import RoborockVacuumCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["vacuum", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure l'intégration depuis une config entry."""
    email = entry.data[CONF_EMAIL]
    user_data = UserData.from_dict(entry.data[CONF_USER_DATA])
    home_data_raw = entry.data[CONF_HOME_DATA]

    coordinator = RoborockVacuumCoordinator(
        hass=hass,
        email=email,
        user_data=user_data,
        home_data_raw=home_data_raw,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Impossible de contacter Roborock : {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge une config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: RoborockVacuumCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
