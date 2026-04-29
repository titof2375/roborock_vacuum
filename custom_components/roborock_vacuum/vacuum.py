"""Entité vacuum Roborock."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumEntityFeature,
    VacuumActivity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VACUUM_STATUS, FAN_SPEEDS
from .coordinator import RoborockVacuumCoordinator, RoborockData

_LOGGER = logging.getLogger(__name__)

SUPPORT_ROBOROCK = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.LOCATE
    | VacuumEntityFeature.STATUS
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.SEND_COMMAND
    # BATTERY retiré : déprécié HA 2026.8, capteur "Batterie" séparé utilisé
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoborockVacuumCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RoborockVacuumEntity(coordinator, duid, entry.entry_id)
        for duid in coordinator.data
    ]
    async_add_entities(entities)


class RoborockVacuumEntity(CoordinatorEntity[RoborockVacuumCoordinator], StateVacuumEntity):
    """Représente un aspirateur Roborock."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = SUPPORT_ROBOROCK
    _attr_fan_speed_list = list(FAN_SPEEDS.values())

    def __init__(
        self,
        coordinator: RoborockVacuumCoordinator,
        duid: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._duid = duid
        self._attr_unique_id = f"{entry_id}_{duid}_vacuum"

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
            model=dev.product.model if hasattr(dev, "product") and hasattr(dev.product, "model") else self._duid,
        )

    @property
    def activity(self) -> VacuumActivity | None:
        try:
            code = self._data.props.status.state
        except Exception:
            return None

        cleaning_states = {4, 6, 11, 12, 16}
        returning_states = {5, 18}
        charging_states = {7, 8, 100}
        paused_states = {10}
        error_states = {9}

        if code in cleaning_states:
            return VacuumActivity.CLEANING
        if code in returning_states:
            return VacuumActivity.RETURNING
        if code in charging_states:
            return VacuumActivity.DOCKED
        if code in paused_states:
            return VacuumActivity.PAUSED
        if code in error_states:
            return VacuumActivity.ERROR
        return VacuumActivity.IDLE

    @property
    def fan_speed(self) -> str | None:
        try:
            code = self._data.props.status.fan_power
            return FAN_SPEEDS.get(code, str(code))
        except Exception:
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        try:
            status = self._data.props.status
            attrs["statut_code"] = status.state
            attrs["statut"] = VACUUM_STATUS.get(status.state, str(status.state))
            if hasattr(status, "clean_area") and status.clean_area is not None:
                attrs["surface_nettoyee_m2"] = round(status.clean_area / 1_000_000, 2)
            if hasattr(status, "clean_time") and status.clean_time is not None:
                attrs["duree_nettoyage_min"] = round(status.clean_time / 60, 1)
            if hasattr(status, "error_code") and status.error_code:
                from .const import VACUUM_ERRORS  # noqa: PLC0415
                attrs["erreur"] = VACUUM_ERRORS.get(status.error_code, str(status.error_code))
        except Exception:
            pass
        return attrs

    async def _send(self, command: str, params: list | None = None) -> None:
        """Envoie une commande via le CommandTrait."""
        await self._data.props.command.send(command, params)

    async def async_start(self) -> None:
        await self._send("app_start")
        await self.coordinator.async_request_refresh()

    async def async_stop(self, **kwargs: Any) -> None:
        await self._send("app_stop")
        await self.coordinator.async_request_refresh()

    async def async_pause(self) -> None:
        await self._send("app_pause")
        await self.coordinator.async_request_refresh()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self._send("app_charge")
        await self.coordinator.async_request_refresh()

    async def async_locate(self, **kwargs: Any) -> None:
        await self._send("find_me")

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        code = next((k for k, v in FAN_SPEEDS.items() if v == fan_speed), None)
        if code is not None:
            await self._send("set_custom_mode", [code])
            await self.coordinator.async_request_refresh()

    async def async_send_command(
        self, command: str, params: dict[str, Any] | list[Any] | None = None, **kwargs: Any
    ) -> None:
        await self._send(command, params if isinstance(params, list) else [])
        await self.coordinator.async_request_refresh()
