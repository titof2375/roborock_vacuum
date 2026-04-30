"""Entités Button Roborock — remise à zéro des consommables."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RoborockVacuumCoordinator, RoborockData

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoborockButtonDescription(ButtonEntityDescription):
    command: str = ""
    params: list = None


BUTTON_DESCRIPTIONS: tuple[RoborockButtonDescription, ...] = (
    RoborockButtonDescription(
        key="reset_main_brush",
        name="Réinitialiser brosse principale",
        icon="mdi:brush",
        command="reset_consumable",
        params=[{"consumable": "main_brush_work_time"}],
    ),
    RoborockButtonDescription(
        key="reset_side_brush",
        name="Réinitialiser brosse latérale",
        icon="mdi:brush-variant",
        command="reset_consumable",
        params=[{"consumable": "side_brush_work_time"}],
    ),
    RoborockButtonDescription(
        key="reset_filter",
        name="Réinitialiser filtre",
        icon="mdi:air-filter",
        command="reset_consumable",
        params=[{"consumable": "filter_work_time"}],
    ),
    RoborockButtonDescription(
        key="reset_sensor",
        name="Réinitialiser capteur obstacle",
        icon="mdi:eye",
        command="reset_consumable",
        params=[{"consumable": "sensor_dirty_time"}],
    ),
    RoborockButtonDescription(
        key="reset_mop",
        name="Réinitialiser serpillière",
        icon="mdi:mop",
        command="reset_consumable",
        params=[{"consumable": "mop_work_time"}],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoborockVacuumCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RoborockButtonEntity(coordinator, duid, entry.entry_id, desc)
        for duid in coordinator.data
        for desc in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities)


class RoborockButtonEntity(CoordinatorEntity[RoborockVacuumCoordinator], ButtonEntity):
    """Bouton reset consommable Roborock."""

    _attr_has_entity_name = True
    entity_description: RoborockButtonDescription

    def __init__(
        self,
        coordinator: RoborockVacuumCoordinator,
        duid: str,
        entry_id: str,
        description: RoborockButtonDescription,
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

    async def async_press(self) -> None:
        try:
            await self._data.props.command.send(
                self.entity_description.command,
                self.entity_description.params or [],
            )
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Reset %s effectué", self.entity_description.key)
        except Exception as err:
            _LOGGER.warning("Erreur reset %s : %s", self.entity_description.key, err)
