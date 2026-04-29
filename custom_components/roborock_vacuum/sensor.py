"""Capteurs Roborock Vacuum."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VACUUM_STATUS, VACUUM_ERRORS
from .coordinator import RoborockVacuumCoordinator, RoborockData

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoborockSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[RoborockData], Any] = lambda d: None
    is_dock: bool = False  # True = entité liée au dock


# ── Capteurs de l'aspirateur ────────────────────────────────────────────────
VACUUM_SENSOR_DESCRIPTIONS: tuple[RoborockSensorEntityDescription, ...] = (
    RoborockSensorEntityDescription(
        key="battery",
        name="Batterie",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.props.status.battery if d.props and d.props.status else None,
    ),
    RoborockSensorEntityDescription(
        key="status",
        name="Statut",
        value_fn=lambda d: VACUUM_STATUS.get(d.props.status.state, str(d.props.status.state))
        if d.props and d.props.status else None,
    ),
    RoborockSensorEntityDescription(
        key="clean_area",
        name="Surface nettoyée",
        native_unit_of_measurement="m²",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: round(d.props.status.clean_area / 1_000_000, 2)
        if d.props and d.props.status and hasattr(d.props.status, "clean_area") else None,
    ),
    RoborockSensorEntityDescription(
        key="clean_time",
        name="Durée nettoyage",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: round(d.props.status.clean_time / 60, 1)
        if d.props and d.props.status and hasattr(d.props.status, "clean_time") else None,
    ),
    RoborockSensorEntityDescription(
        key="error",
        name="Erreur",
        value_fn=lambda d: VACUUM_ERRORS.get(d.props.status.error_code, str(d.props.status.error_code))
        if d.props and d.props.status and hasattr(d.props.status, "error_code") else None,
    ),
    RoborockSensorEntityDescription(
        key="total_clean_area",
        name="Surface totale nettoyée",
        native_unit_of_measurement="m²",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: round(d.props.clean_summary.clean_area / 1_000_000, 2)
        if d.props and d.props.clean_summary and hasattr(d.props.clean_summary, "clean_area") else None,
    ),
    RoborockSensorEntityDescription(
        key="total_clean_time",
        name="Durée totale nettoyage",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: round(d.props.clean_summary.clean_time / 3600, 1)
        if d.props and d.props.clean_summary and hasattr(d.props.clean_summary, "clean_time") else None,
    ),
    RoborockSensorEntityDescription(
        key="total_clean_count",
        name="Nombre de nettoyages",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.props.clean_summary.clean_count
        if d.props and d.props.clean_summary and hasattr(d.props.clean_summary, "clean_count") else None,
    ),
)

# ── Capteurs du dock ─────────────────────────────────────────────────────────
DOCK_SENSOR_DESCRIPTIONS: tuple[RoborockSensorEntityDescription, ...] = (
    RoborockSensorEntityDescription(
        key="dock_status",
        name="Statut dock",
        is_dock=True,
        value_fn=lambda d: _get_dock_status(d),
    ),
    RoborockSensorEntityDescription(
        key="dust_collection",
        name="Collecte poussière",
        is_dock=True,
        value_fn=lambda d: _get_dust_collection(d),
    ),
)


def _get_dock_status(data: RoborockData) -> str | None:
    """Retourne le statut du dock depuis props.status."""
    try:
        status = data.props.status
        # dock_error_status ou dock_type_status selon la version de la lib
        for attr in ("dock_error_status", "dock_station_status", "dock_type"):
            val = getattr(status, attr, None)
            if val is not None:
                return str(val)
        return None
    except Exception:
        return None


def _get_dust_collection(data: RoborockData) -> str | None:
    """Retourne le mode de collecte de poussière si disponible."""
    try:
        dc = data.props.dust_collection_mode
        if dc is None:
            return None
        for attr in ("mode", "state", "value"):
            val = getattr(dc, attr, None)
            if val is not None:
                return str(val)
        return None
    except Exception:
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoborockVacuumCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[RoborockSensorEntity] = []

    for duid in coordinator.data:
        # Capteurs de l'aspirateur
        for desc in VACUUM_SENSOR_DESCRIPTIONS:
            entities.append(RoborockSensorEntity(coordinator, duid, entry.entry_id, desc))
        # Capteurs du dock
        for desc in DOCK_SENSOR_DESCRIPTIONS:
            entities.append(RoborockSensorEntity(coordinator, duid, entry.entry_id, desc))

    async_add_entities(entities)


class RoborockSensorEntity(CoordinatorEntity[RoborockVacuumCoordinator], SensorEntity):
    """Capteur Roborock (aspirateur ou dock)."""

    _attr_has_entity_name = True
    entity_description: RoborockSensorEntityDescription

    def __init__(
        self,
        coordinator: RoborockVacuumCoordinator,
        duid: str,
        entry_id: str,
        description: RoborockSensorEntityDescription,
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
        model = (
            dev.product.model
            if hasattr(dev, "product") and hasattr(dev.product, "model")
            else self._duid
        )

        if self.entity_description.is_dock:
            # Appareil "Dock" lié au vacuum via via_device
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
    def native_value(self) -> Any:
        try:
            return self.entity_description.value_fn(self._data)
        except Exception:
            return None
