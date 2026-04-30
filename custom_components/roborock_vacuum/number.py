"""Entités Number Roborock — volume, horaires DND, durée séchage."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RoborockVacuumCoordinator, RoborockData

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoborockNumberDescription:
    key: str
    name: str
    icon: str
    min_value: float
    max_value: float
    step: float
    unit: str | None
    mode: NumberMode
    current_fn: Callable[[RoborockData], float | None]
    set_command: str
    set_param_fn: Callable[[RoborockData, float], list]
    is_dock: bool = False


def _dnd_attr(data: RoborockData, attr: str, default: float) -> float | None:
    try:
        dnd = data.props.dnd
        if dnd is None:
            return None
        return float(getattr(dnd, attr, default))
    except Exception:
        return None


def _dnd_full_params(data: RoborockData) -> dict:
    try:
        dnd = data.props.dnd
        if dnd is None:
            return {"enabled": 0, "start_hour": 22, "start_minute": 0,
                    "end_hour": 7, "end_minute": 0}
        return {
            "enabled": getattr(dnd, "enabled", 0),
            "start_hour": getattr(dnd, "start_hour", 22),
            "start_minute": getattr(dnd, "start_minute", 0),
            "end_hour": getattr(dnd, "end_hour", 7),
            "end_minute": getattr(dnd, "end_minute", 0),
        }
    except Exception:
        return {"enabled": 0, "start_hour": 22, "start_minute": 0,
                "end_hour": 7, "end_minute": 0}


def _get_volume(data: RoborockData) -> float | None:
    try:
        sv = data.props.sound_volume
        if sv is None:
            return None
        for attr in ("volume", "value", "level"):
            val = getattr(sv, attr, None)
            if val is not None:
                return float(val)
        return None
    except Exception:
        return None


def _get_drying_time(data: RoborockData) -> float | None:
    try:
        status = data.props.status
        for attr in ("drying_time", "dry_time", "drying_duration"):
            val = getattr(status, attr, None)
            if val is not None:
                return float(val)
        return None
    except Exception:
        return None


NUMBER_DESCRIPTIONS: tuple[RoborockNumberDescription, ...] = (
    # ── Volume ───────────────────────────────────────────────────────────────
    RoborockNumberDescription(
        key="volume",
        name="Volume sonore",
        icon="mdi:volume-high",
        min_value=0, max_value=100, step=1,
        unit=PERCENTAGE,
        mode=NumberMode.SLIDER,
        current_fn=_get_volume,
        set_command="change_sound_volume",
        set_param_fn=lambda d, v: [int(v)],
    ),
    # ── DND horaires ─────────────────────────────────────────────────────────
    RoborockNumberDescription(
        key="dnd_start_hour",
        name="DND heure début",
        icon="mdi:sleep",
        min_value=0, max_value=23, step=1,
        unit=None,
        mode=NumberMode.BOX,
        current_fn=lambda d: _dnd_attr(d, "start_hour", 22),
        set_command="set_dnd_timer",
        set_param_fn=lambda d, v: [{**_dnd_full_params(d), "start_hour": int(v)}],
    ),
    RoborockNumberDescription(
        key="dnd_start_minute",
        name="DND minute début",
        icon="mdi:sleep",
        min_value=0, max_value=59, step=1,
        unit=None,
        mode=NumberMode.BOX,
        current_fn=lambda d: _dnd_attr(d, "start_minute", 0),
        set_command="set_dnd_timer",
        set_param_fn=lambda d, v: [{**_dnd_full_params(d), "start_minute": int(v)}],
    ),
    RoborockNumberDescription(
        key="dnd_end_hour",
        name="DND heure fin",
        icon="mdi:sleep-off",
        min_value=0, max_value=23, step=1,
        unit=None,
        mode=NumberMode.BOX,
        current_fn=lambda d: _dnd_attr(d, "end_hour", 7),
        set_command="set_dnd_timer",
        set_param_fn=lambda d, v: [{**_dnd_full_params(d), "end_hour": int(v)}],
    ),
    RoborockNumberDescription(
        key="dnd_end_minute",
        name="DND minute fin",
        icon="mdi:sleep-off",
        min_value=0, max_value=59, step=1,
        unit=None,
        mode=NumberMode.BOX,
        current_fn=lambda d: _dnd_attr(d, "end_minute", 0),
        set_command="set_dnd_timer",
        set_param_fn=lambda d, v: [{**_dnd_full_params(d), "end_minute": int(v)}],
    ),
    # ── Dock ─────────────────────────────────────────────────────────────────
    RoborockNumberDescription(
        key="drying_time",
        name="Durée séchage",
        icon="mdi:heat-wave",
        min_value=30, max_value=240, step=10,
        unit=UnitOfTime.MINUTES,
        mode=NumberMode.SLIDER,
        is_dock=True,
        current_fn=_get_drying_time,
        set_command="set_drying_time",
        set_param_fn=lambda d, v: [{"time": int(v)}],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoborockVacuumCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RoborockNumberEntity(coordinator, duid, entry.entry_id, desc)
        for duid in coordinator.data
        for desc in NUMBER_DESCRIPTIONS
    ]
    async_add_entities(entities)


class RoborockNumberEntity(CoordinatorEntity[RoborockVacuumCoordinator], NumberEntity):
    """Entité number Roborock."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RoborockVacuumCoordinator,
        duid: str,
        entry_id: str,
        description: RoborockNumberDescription,
    ) -> None:
        super().__init__(coordinator)
        self._duid = duid
        self._desc = description
        self._attr_unique_id = f"{entry_id}_{duid}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_native_min_value = description.min_value
        self._attr_native_max_value = description.max_value
        self._attr_native_step = description.step
        self._attr_native_unit_of_measurement = description.unit
        self._attr_mode = description.mode

    @property
    def _data(self) -> RoborockData:
        return self.coordinator.data[self._duid]

    @property
    def device_info(self) -> DeviceInfo:
        dev = self._data.device
        model = dev.product.model if hasattr(dev, "product") else self._duid
        if self._desc.is_dock:
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self._duid}_dock")},
                name=f"{dev.name} Dock",
                manufacturer="Roborock",
                model=f"{model} Dock",
                via_device=(DOMAIN, self._duid),
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self._duid)},
            name=dev.name,
            manufacturer="Roborock",
            model=model,
        )

    @property
    def native_value(self) -> float | None:
        try:
            return self._desc.current_fn(self._data)
        except Exception:
            return None

    async def async_set_native_value(self, value: float) -> None:
        try:
            params = self._desc.set_param_fn(self._data, value)
            await self._data.props.command.send(self._desc.set_command, params)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Erreur number %s : %s", self._desc.key, err)
