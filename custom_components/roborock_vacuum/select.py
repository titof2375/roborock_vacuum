"""Entités Select Roborock — ventilateur, serpillière, passages."""
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

# Nombre de passages de nettoyage
CLEAN_PASSES = {1: "1 passage", 2: "2 passages", 3: "3 passages"}

# Fréquence d'auto-lavage vadrouille (minutes, 0 = manuel)
MOP_WASH_FREQ = {
    0:  "Manuel",
    10: "Toutes les 10 min",
    15: "Toutes les 15 min",
    25: "Toutes les 25 min",
}

# Mode séchage dock
DRYING_MODES = {
    0: "Désactivé",
    1: "Mode intelligent",
    2: "Mode intense",
}


@dataclass(frozen=True)
class RoborockSelectDescription(SelectEntityDescription):
    options_map: dict = None
    current_fn: Callable[[RoborockData], Any] = lambda d: None
    command: str = ""
    param_fn: Callable[[Any], list] = lambda v: [v]
    is_dock: bool = False


def _get_fan_speed(data: RoborockData) -> int | None:
    try:
        return data.props.status.fan_power if data.props and data.props.status else None
    except Exception:
        return None


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


def _get_clean_passes(data: RoborockData) -> int | None:
    try:
        status = data.props.status
        for attr in ("clean_repeat", "repeat_cleaning", "cleaning_repeat"):
            val = getattr(status, attr, None)
            if val is not None:
                return int(val)
        return 1  # défaut = 1 passage
    except Exception:
        return 1


def _get_mop_wash_freq(data: RoborockData) -> int | None:
    try:
        swp = data.props.smart_wash_params
        if swp is None:
            return None
        # smart_wash=0 → manuel, sinon wash_interval donne la fréquence
        smart = getattr(swp, "smart_wash", None)
        if smart == 0:
            return 0
        interval = getattr(swp, "wash_interval", None)
        return interval
    except Exception:
        return None


def _get_drying_mode(data: RoborockData) -> int | None:
    try:
        status = data.props.status
        for attr in ("drying_mode", "dry_mode"):
            val = getattr(status, attr, None)
            if val is not None:
                return int(val)
        return None
    except Exception:
        return None


SELECT_DESCRIPTIONS: tuple[RoborockSelectDescription, ...] = (
    # ── Aspirateur ───────────────────────────────────────────────────────────
    RoborockSelectDescription(
        key="fan_speed",
        name="Vitesse ventilateur",
        icon="mdi:fan",
        options_map=FAN_SPEEDS,
        current_fn=_get_fan_speed,
        command="set_custom_mode",
        param_fn=lambda v: [v],
    ),
    RoborockSelectDescription(
        key="mop_intensity",
        name="Intensité serpillière",
        icon="mdi:water",
        options_map=MOP_INTENSITIES,
        current_fn=_get_mop_intensity,
        command="set_water_box_custom_mode",
        param_fn=lambda v: [v],
    ),
    RoborockSelectDescription(
        key="mop_mode",
        name="Mode serpillière",
        icon="mdi:waves",
        options_map=MOP_MODES,
        current_fn=_get_mop_mode,
        command="set_mop_mode",
        param_fn=lambda v: [v],
    ),
    RoborockSelectDescription(
        key="clean_passes",
        name="Nombre de passages",
        icon="mdi:repeat",
        options_map=CLEAN_PASSES,
        current_fn=_get_clean_passes,
        command="set_clean_repeat",
        param_fn=lambda v: [v],
    ),
    # ── Dock ─────────────────────────────────────────────────────────────────
    RoborockSelectDescription(
        key="mop_wash_frequency",
        name="Fréquence lavage vadrouille",
        icon="mdi:washing-machine",
        is_dock=True,
        options_map=MOP_WASH_FREQ,
        current_fn=_get_mop_wash_freq,
        command="set_smart_wash_params",
        param_fn=lambda v: [{"smart_wash": 0 if v == 0 else 1, "wash_interval": v}],
    ),
    RoborockSelectDescription(
        key="drying_mode",
        name="Mode séchage dock",
        icon="mdi:heat-wave",
        is_dock=True,
        options_map=DRYING_MODES,
        current_fn=_get_drying_mode,
        command="set_drying_mode",
        param_fn=lambda v: [{"mode": v}],
    ),
)


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
        model = dev.product.model if hasattr(dev, "product") else self._duid
        if self.entity_description.is_dock:
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
