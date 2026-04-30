"""Entité Number Roborock — volume sonore."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RoborockVacuumCoordinator, RoborockData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoborockVacuumCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RoborockVolumeEntity(coordinator, duid, entry.entry_id)
        for duid in coordinator.data
    ]
    async_add_entities(entities)


class RoborockVolumeEntity(CoordinatorEntity[RoborockVacuumCoordinator], NumberEntity):
    """Volume sonore de l'aspirateur (0–100 %)."""

    _attr_has_entity_name = True
    _attr_name = "Volume sonore"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:volume-high"

    def __init__(
        self,
        coordinator: RoborockVacuumCoordinator,
        duid: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._duid = duid
        self._attr_unique_id = f"{entry_id}_{duid}_volume"

    @property
    def _data(self) -> RoborockData:
        return self.coordinator.data[self._duid]

    @property
    def device_info(self) -> DeviceInfo:
        dev = self._data.device
        return DeviceInfo(
            identifiers={(DOMAIN, self._duid)},
            name=dev.name,
            manufacturer="Roborock",
            model=dev.product.model if hasattr(dev, "product") else self._duid,
        )

    @property
    def native_value(self) -> float | None:
        try:
            sv = self._data.props.sound_volume
            if sv is None:
                return None
            for attr in ("volume", "value", "level"):
                val = getattr(sv, attr, None)
                if val is not None:
                    return float(val)
            return None
        except Exception:
            return None

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._data.props.command.send(
                "change_sound_volume", [int(value)]
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Erreur volume : %s", err)
