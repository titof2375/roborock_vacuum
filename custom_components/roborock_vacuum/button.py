"""Entités Button Roborock — reset consommables, dock, nettoyage pièce."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

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
    params: list = field(default_factory=list)
    is_dock: bool = False
    custom_action: str = ""   # action spéciale (ex: "clean_room")


BUTTON_DESCRIPTIONS: tuple[RoborockButtonDescription, ...] = (
    # ── Nettoyage ────────────────────────────────────────────────────────────
    RoborockButtonDescription(
        key="spot_clean",
        name="Nettoyage ponctuel (spot)",
        icon="mdi:target",
        command="app_spot",
    ),
    RoborockButtonDescription(
        key="clean_room",
        name="Nettoyer la pièce sélectionnée",
        icon="mdi:floor-plan",
        custom_action="clean_room",
    ),
    # ── Reset consommables ───────────────────────────────────────────────────
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
    # ── Dock ─────────────────────────────────────────────────────────────────
    RoborockButtonDescription(
        key="dock_auto_empty",
        name="Vider le bac",
        icon="mdi:delete-empty",
        command="app_start_collect_dust",
        is_dock=True,
    ),
    RoborockButtonDescription(
        key="dock_start_wash",
        name="Démarrer auto-lavage dock",
        icon="mdi:washing-machine",
        command="app_start_wash",
        is_dock=True,
    ),
    RoborockButtonDescription(
        key="dock_stop_wash",
        name="Arrêter auto-lavage dock",
        icon="mdi:washing-machine-off",
        command="app_stop_wash",
        is_dock=True,
    ),
    RoborockButtonDescription(
        key="dock_start_drying",
        name="Démarrer séchage dock",
        icon="mdi:heat-wave",
        command="start_drying",
        is_dock=True,
    ),
    RoborockButtonDescription(
        key="dock_stop_drying",
        name="Arrêter séchage dock",
        icon="mdi:stop",
        command="stop_drying",
        is_dock=True,
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
    """Bouton Roborock."""

    _attr_has_entity_name = True
    entity_description: RoborockButtonDescription

    def __init__(self, coordinator, duid, entry_id, description):
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

    async def async_press(self) -> None:
        try:
            if self.entity_description.custom_action == "clean_room":
                await self._action_clean_room()
            else:
                await self._data.props.command.send(
                    self.entity_description.command,
                    self.entity_description.params or [],
                )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Erreur %s : %s", self.entity_description.key, err)

    async def _action_clean_room(self) -> None:
        """Nettoie la(les) pièce(s) sélectionnée(s) via le select Pièce à nettoyer."""
        selected = self.coordinator.selected_rooms.get(self._duid, [])
        if not selected:
            # Aucune pièce sélectionnée → nettoyage complet
            _LOGGER.info("Aucune pièce sélectionnée — nettoyage complet")
            await self._data.props.command.send("app_start", [])
            return
        # Nettoyage des pièces sélectionnées
        segments = [{"id": rid, "order": i + 1, "repeats": 1}
                    for i, rid in enumerate(selected)]
        _LOGGER.info("Nettoyage pièces : %s", segments)
        await self._data.props.command.send("app_segment_clean", segments)
