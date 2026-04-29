"""Roborock Vacuum — intégration custom HACS."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    CONF_EMAIL,
    CONF_USERNAME,
    CONF_USER_DATA,
    CONF_BASE_URL,
)
from .coordinator import RoborockVacuumCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["vacuum", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure l'intégration depuis une config entry."""
    # Support anciens config entries (CONF_EMAIL) et nouveaux (CONF_USERNAME)
    username = entry.data.get(CONF_USERNAME) or entry.data.get(CONF_EMAIL, "")
    user_data_dict = entry.data[CONF_USER_DATA]
    base_url = entry.data.get(CONF_BASE_URL)

    coordinator = RoborockVacuumCoordinator(
        hass=hass,
        username=username,
        user_data_dict=user_data_dict,
        base_url=base_url,
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
