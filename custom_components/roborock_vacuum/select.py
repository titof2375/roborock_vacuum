"""Entités Select Roborock — ventilateur, serpillière, passages, pièces, programmation."""
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

CLEAN_PASSES = {1: "1 passage", 2: "2 passages", 3: "3 passages"}
MOP_WASH_FREQ = {0: "Manuel", 10: "Toutes les 10 min",
                 15: "Toutes les 15 min", 25: "Toutes les 25 min"}
DRYING_MODES = {0: "Désactivé", 1: "Mode intelligent", 2: "Mode intense"}

# Jours de récurrence pour la programmation
SCHEDULE_DAYS = {
    "daily":    "Tous les jours",
    "weekdays": "Jours de semaine (L-V)",
    "weekend":  "Week-end (S-D)",
    "mon":      "Lundi seulement",
    "tue":      "Mardi seulement",
    "wed":      "Mercredi seulement",
    "thu":      "Jeudi seulement",
    "fri":      "Vendredi seulement",
    "sat":      "Samedi seulement",
    "sun":      "Dimanche seulement",
}
SCHEDULE_DAYS_MAP = {
    "daily":    [0, 1, 2, 3, 4, 5, 6],
    "weekdays": [1, 2, 3, 4, 5],
    "weekend":  [0, 6],
    "mon":      [1], "tue": [2], "wed": [3], "thu": [4],
    "fri":      [5], "sat": [6], "sun": [0],
}


@dataclass(frozen=True)
class RoborockSelectDescription(SelectEntityDescription):
    options_map: dict = None
    current_fn: Callable[[RoborockData], Any] = lambda d: None
    command: str = ""
    param_fn: Callable[[Any], list] = lambda v: [v]
    is_dock: bool = False
    dynamic: bool = False   # options chargées dynamiquement (pièces)


def _get_fan_speed(d: RoborockData) -> int | None:
    try:
        return d.props.status.fan_power if d.props and d.props.status else None
    except Exception:
        return None


def _get_mop_intensity(d: RoborockData) -> int | None:
    try:
        for attr in ("water_box_custom_mode", "water_box_mode", "mop_intensity"):
            v = getattr(d.props.status, attr, None)
            if v is not None:
                return v
    except Exception:
        pass
    return None


def _get_mop_mode(d: RoborockData) -> int | None:
    try:
        for attr in ("mop_mode", "mop_type"):
            v = getattr(d.props.status, attr, None)
            if v is not None:
                return v
    except Exception:
        pass
    return None


def _get_clean_passes(d: RoborockData) -> int | None:
    try:
        for attr in ("clean_repeat", "repeat_cleaning", "cleaning_repeat"):
            v = getattr(d.props.status, attr, None)
            if v is not None:
                return int(v)
    except Exception:
        pass
    return 1


def _get_mop_wash_freq(d: RoborockData) -> int | None:
    try:
        swp = d.props.smart_wash_params
        if swp is None:
            return None
        if getattr(swp, "smart_wash", 1) == 0:
            return 0
        return getattr(swp, "wash_interval", None)
    except Exception:
        return None


def _get_drying_mode(d: RoborockData) -> int | None:
    try:
        for attr in ("drying_mode", "dry_mode"):
            v = getattr(d.props.status, attr, None)
            if v is not None:
                return int(v)
    except Exception:
        pass
    return None


def _get_schedule_days(d: RoborockData) -> str | None:
    try:
        days = d.schedule.get("day", [])
        for key, val in SCHEDULE_DAYS_MAP.items():
            if sorted(days) == sorted(val):
                return key
        return "daily"
    except Exception:
        return "daily"


# ── Descriptions statiques ───────────────────────────────────────────────────
STATIC_SELECT_DESCRIPTIONS: tuple[RoborockSelectDescription, ...] = (
    RoborockSelectDescription(
        key="fan_speed", name="Vitesse ventilateur", icon="mdi:fan",
        options_map=FAN_SPEEDS, current_fn=_get_fan_speed,
        command="set_custom_mode", param_fn=lambda v: [v],
    ),
    RoborockSelectDescription(
        key="mop_intensity", name="Intensité serpillière", icon="mdi:water",
        options_map=MOP_INTENSITIES, current_fn=_get_mop_intensity,
        command="set_water_box_custom_mode", param_fn=lambda v: [v],
    ),
    RoborockSelectDescription(
        key="mop_mode", name="Mode serpillière", icon="mdi:waves",
        options_map=MOP_MODES, current_fn=_get_mop_mode,
        command="set_mop_mode", param_fn=lambda v: [v],
    ),
    RoborockSelectDescription(
        key="clean_passes", name="Nombre de passages", icon="mdi:repeat",
        options_map=CLEAN_PASSES, current_fn=_get_clean_passes,
        command="set_clean_repeat", param_fn=lambda v: [v],
    ),
    RoborockSelectDescription(
        key="mop_wash_frequency", name="Fréquence lavage vadrouille",
        icon="mdi:washing-machine", is_dock=True,
        options_map=MOP_WASH_FREQ, current_fn=_get_mop_wash_freq,
        command="set_smart_wash_params",
        param_fn=lambda v: [{"smart_wash": 0 if v == 0 else 1, "wash_interval": v}],
    ),
    RoborockSelectDescription(
        key="drying_mode", name="Mode séchage dock", icon="mdi:heat-wave",
        is_dock=True, options_map=DRYING_MODES, current_fn=_get_drying_mode,
        command="set_drying_mode", param_fn=lambda v: [{"mode": v}],
    ),
    RoborockSelectDescription(
        key="schedule_days", name="Jours de programmation", icon="mdi:calendar-week",
        options_map=SCHEDULE_DAYS, current_fn=_get_schedule_days,
        command="",  # géré manuellement
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoborockVacuumCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []

    for duid in coordinator.data:
        # Selects statiques
        for desc in STATIC_SELECT_DESCRIPTIONS:
            entities.append(RoborockSelectEntity(coordinator, duid, entry.entry_id, desc))
        # Select dynamique pièces
        entities.append(RoborockRoomSelectEntity(coordinator, duid, entry.entry_id))

    async_add_entities(entities)


def _device_info(data: RoborockData, duid: str, is_dock: bool = False) -> DeviceInfo:
    dev = data.device
    model = dev.product.model if hasattr(dev, "product") else duid
    if is_dock:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{duid}_dock")},
            name=f"{dev.name} Dock",
            manufacturer="Roborock",
            model=f"{model} Dock",
            via_device=(DOMAIN, duid),
        )
    return DeviceInfo(
        identifiers={(DOMAIN, duid)},
        name=dev.name,
        manufacturer="Roborock",
        model=model,
    )


class RoborockSelectEntity(CoordinatorEntity[RoborockVacuumCoordinator], SelectEntity):
    """Select statique Roborock."""

    _attr_has_entity_name = True
    entity_description: RoborockSelectDescription

    def __init__(self, coordinator, duid, entry_id, description):
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
        return _device_info(self._data, self._duid, self.entity_description.is_dock)

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
            # schedule_days : met à jour le timer existant
            if self.entity_description.key == "schedule_days":
                days = SCHEDULE_DAYS_MAP.get(str(code), [0, 1, 2, 3, 4, 5, 6])
                sched = self._data.schedule
                timer_id = sched.get("id", "0")
                params = [[timer_id, ["", {"then_arm": False}], {
                    "enabled": 1 if sched.get("enabled") else 0,
                    "start_hour": sched.get("start_hour", 8),
                    "start_minute": sched.get("start_minute", 0),
                    "day": days,
                }]]
                await self._data.props.command.send("set_timer", params)
            else:
                params = self.entity_description.param_fn(code)
                await self._data.props.command.send(
                    self.entity_description.command, params
                )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Erreur select %s : %s", self.entity_description.key, err)


class RoborockRoomSelectEntity(CoordinatorEntity[RoborockVacuumCoordinator], SelectEntity):
    """Select dynamique des pièces — options rechargées depuis le coordinateur."""

    _attr_has_entity_name = True
    _attr_name = "Pièce à nettoyer"
    _attr_icon = "mdi:floor-plan"

    def __init__(self, coordinator, duid, entry_id):
        super().__init__(coordinator)
        self._duid = duid
        self._attr_unique_id = f"{entry_id}_{duid}_room_select"
        self._attr_options = ["Toutes les pièces"]

    @property
    def _data(self) -> RoborockData:
        return self.coordinator.data[self._duid]

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._data, self._duid)

    @property
    def options(self) -> list[str]:
        rooms = self._data.rooms
        if not rooms:
            return ["Toutes les pièces"]
        return ["Toutes les pièces"] + list(rooms.values())

    @property
    def current_option(self) -> str | None:
        selected = self.coordinator.selected_rooms.get(self._duid)
        if not selected:
            return "Toutes les pièces"
        rooms = self._data.rooms
        if len(selected) == 1 and selected[0] in rooms:
            return rooms[selected[0]]
        return "Toutes les pièces"

    async def async_select_option(self, option: str) -> None:
        if option == "Toutes les pièces":
            self.coordinator.selected_rooms[self._duid] = []
        else:
            room_id = next(
                (k for k, v in self._data.rooms.items() if v == option), None
            )
            if room_id is not None:
                self.coordinator.selected_rooms[self._duid] = [room_id]
        self.async_write_ha_state()
