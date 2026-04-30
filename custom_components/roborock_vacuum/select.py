"""Entités Select Roborock — vitesse ventilateur, serpillière."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FAN_SPEEDS, MOP_INTENSITIES, MOP_MODES
from .coordinator import RoborockVacuumCoordinator, RoborockData

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoborockSelectDescription(SelectEntityDescription):
    options_map: dict[int, str] = None          # code → label
    current_fn: Callable[[RoborockData], int | None] = lambda d: None
    command: str = ""
    param_fn: Callable[[int], list] = lambda v: [v]


SELECT_DESCRIPTIONS: tuple[RoborockSelectDescription, ...] = (
    RoborockSelectDescription(
        key="fan_speed",
        name="Vitesse ventilateur",
        options_map=FAN_SPEEDS,
        current_fn=lambda d: d.props.status.fan_power
        if d.props and d.props.status else None,
        command="set_custom_mode",
        param_fn=lambda v: [v],
    ),
    RoborockSelectDescription(
        key="mop_intensity",
        name="Intensité serpillière",
        options_map=MOP_INTENSITIES,
        current_fn=lambda d: _get_mop_intensity(d),
        command="set_water_box_custom_mode",
        param_fn=lambda v: [v],
    ),
    RoborockSelectDescription(
        key="mop_mode",
        name="Mode serpillière",
        options_map=MOP_MODES,
        current_fn=lambda d: _get_mop_mode(d),
        command="set_mop_mode",
        param_fn=lambda v: [v],
    ),
)


def _get_mop_intensity(data: RoborockData) -> int | None:
    try:
        status = data.props.status
        for attr in ("water_box_custom_mode", "water_box_mode", "mop_intensity"):
            val = getattr(status, attr, None)
            if val is not None:
                return val
        return None
    except Exception:
        return None


def _get_mop_mode(data: RoborockData) -> int | None:
    try:
        status = data.props.status
        for attr in ("mop_mode", "mop_type"):
            val = getattr(status, attr, None)
            if val is not None:
                return val
        return None
    except Exception:
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoborockVacuumCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RoborockSelectEntity(coordinator, duid, entry.entry_id, desc)
        for duid in coordinator.data
        for desc in SELECT_DESCRIPTIONS
    ]
    async_add_entities(entities)


class RoborockSelectEntity(CoordinatorEntity[RoborockVacuumCoordinator], SelectEntity):
    """Entité select Roborock."""

    _attr_has_entity_name = True
    entity_description: RoborockSelectDescription

    def __init__(
        self,
        coordinator: RoborockVacuumCoordinator,
        duid: str,
        entry_id: str,
        description: RoborockSelectDescription,
    ) -> None:
        super().__init__(coordinator)
        self._duid = duid
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{duid}_{description.key}"
        self._attr_options = list(description.options_map.values())

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
    def current_option(self) -> str | None:
        try:
            code = self.entity_description.current_fn(self._data)
            return self.entity_description.options_map.get(code)
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        code = next(
            (k for k, v in self.entity_description.options_map.items() if v == option),
            None,
        )
        if code is None:
            return
        try:
            params = self.entity_description.param_fn(code)
            await self._data.props.command.send(self.entity_description.command, params)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Erreur select %s : %s", self.entity_description.key, err)
