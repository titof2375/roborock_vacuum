"""Entité Time Roborock — heure de la programmation."""
from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
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
        RoborockScheduleTimeEntity(coordinator, duid, entry.entry_id)
        for duid in coordinator.data
    ]
    async_add_entities(entities)


class RoborockScheduleTimeEntity(CoordinatorEntity[RoborockVacuumCoordinator], TimeEntity):
    """Heure de démarrage du nettoyage programmé."""

    _attr_has_entity_name = True
    _attr_name = "Heure programmation"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, duid, entry_id):
        super().__init__(coordinator)
        self._duid = duid
        self._attr_unique_id = f"{entry_id}_{duid}_schedule_time"

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
    def native_value(self) -> dt_time | None:
        try:
            sched = self._data.schedule
            if not sched:
                return dt_time(8, 0)
            return dt_time(
                int(sched.get("start_hour", 8)),
                int(sched.get("start_minute", 0)),
            )
        except Exception:
            return dt_time(8, 0)

    async def async_set_value(self, value: dt_time) -> None:
        """Met à jour l'heure du timer Roborock en conservant les autres paramètres."""
        try:
            sched = self._data.schedule
            timer_id = sched.get("id", "0")
            from .select import SCHEDULE_DAYS_MAP  # noqa: PLC0415
            days = sched.get("day", [0, 1, 2, 3, 4, 5, 6])
            params = [[timer_id, ["", {"then_arm": False}], {
                "enabled": 1 if sched.get("enabled") else 0,
                "start_hour": value.hour,
                "start_minute": value.minute,
                "day": days,
            }]]
            await self._data.props.command.send("set_timer", params)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Erreur set_timer heure : %s", err)
