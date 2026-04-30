"""Entités Switch Roborock — verrouillage enfant, LED."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RoborockVacuumCoordinator, RoborockData

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoborockSwitchDescription(SwitchEntityDescription):
    current_fn: Callable[[RoborockData], bool | None] = lambda d: None
    command_on: str = ""
    command_off: str = ""
    params_on: list = None
    params_off: list = None


def _get_child_lock(data: RoborockData) -> bool | None:
    try:
        cl = data.props.child_lock
        if cl is None:
            return None
        for attr in ("lock_status", "status", "value"):
            val = getattr(cl, attr, None)
            if val is not None:
                return bool(val)
        return None
    except Exception:
        return None


def _get_led(data: RoborockData) -> bool | None:
    try:
        led = data.props.flow_led_status
        if led is None:
            return None
        for attr in ("status", "value", "led_status"):
            val = getattr(led, attr, None)
            if val is not None:
                return bool(val)
        return None
    except Exception:
        return None


SWITCH_DESCRIPTIONS: tuple[RoborockSwitchDescription, ...] = (
    RoborockSwitchDescription(
        key="child_lock",
        name="Verrouillage enfant",
        icon="mdi:account-child-outline",
        current_fn=_get_child_lock,
        command_on="set_child_lock",
        command_off="set_child_lock",
        params_on=[{"lock_status": 1}],
        params_off=[{"lock_status": 0}],
    ),
    RoborockSwitchDescription(
        key="flow_led",
        name="LED indicateur",
        icon="mdi:led-outline",
        current_fn=_get_led,
        command_on="set_flow_led_status",
        command_off="set_flow_led_status",
        params_on=[{"status": 1}],
        params_off=[{"status": 0}],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoborockVacuumCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RoborockSwitchEntity(coordinator, duid, entry.entry_id, desc)
        for duid in coordinator.data
        for desc in SWITCH_DESCRIPTIONS
    ]
    async_add_entities(entities)


class RoborockSwitchEntity(CoordinatorEntity[RoborockVacuumCoordinator], SwitchEntity):
    """Switch Roborock."""

    _attr_has_entity_name = True
    entity_description: RoborockSwitchDescription

    def __init__(
        self,
        coordinator: RoborockVacuumCoordinator,
        duid: str,
        entry_id: str,
        description: RoborockSwitchDescription,
    ) -> None:
        super().__init__(coordinator)
        self._duid = duid
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{duid}_{description.key}"

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
    def is_on(self) -> bool | None:
        try:
            return self.entity_description.current_fn(self._data)
        except Exception:
            return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        try:
            await self._data.props.command.send(
                self.entity_description.command_on,
                self.entity_description.params_on or [],
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Erreur switch on %s : %s", self.entity_description.key, err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self._data.props.command.send(
                self.entity_description.command_off,
                self.entity_description.params_off or [],
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Erreur switch off %s : %s", self.entity_description.key, err)
