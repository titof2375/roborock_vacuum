"""DataUpdateCoordinator pour Roborock Vacuum."""
from __future__ import annotations

import logging
from datetime import timedelta
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)

# Traits rafraîchis à chaque cycle
_TRAITS_TO_REFRESH = (
    "status",
    "clean_summary",
    "consumables",
    "dnd",
    "child_lock",
    "flow_led_status",
    "sound_volume",
    "smart_wash_params",
    "dust_collection_mode",
)


@dataclass
class RoborockData:
    """Données d'un aspirateur (nouveau format API)."""
    device: Any   # roborock.devices.device.RoborockDevice
    props: Any    # roborock.devices.traits.v1.PropertiesApi


class RoborockVacuumCoordinator(DataUpdateCoordinator[dict[str, RoborockData]]):
    """Coordinateur — un entry = un compte, plusieurs aspirateurs possibles."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        user_data_dict: dict,
        base_url: str | None = None,
    ) -> None:
        self._username = username
        self._user_data_dict = user_data_dict
        self._base_url = base_url
        self._manager: Any = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{username}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )

    async def _async_setup(self) -> None:
        """Crée le DeviceManager et connecte tous les appareils."""
        from roborock.data import UserData  # noqa: PLC0415
        from roborock.devices.device_manager import (  # noqa: PLC0415
            UserParams,
            create_device_manager,
        )

        user_data = UserData.from_dict(self._user_data_dict)
        user_params = UserParams(
            username=self._username,
            user_data=user_data,
            base_url=self._base_url,
        )
        session = async_get_clientsession(self.hass)

        _LOGGER.info("Connexion au DeviceManager Roborock pour %s …", self._username)
        self._manager = await create_device_manager(
            user_params,
            session=session,
            prefer_cache=False,
        )
        devices = await self._manager.get_devices()
        _LOGGER.info("%d appareil(s) trouvé(s) pour %s", len(devices), self._username)

    async def _async_update_data(self) -> dict[str, RoborockData]:
        """Rafraîchit le statut de tous les aspirateurs V1."""
        if self._manager is None:
            raise UpdateFailed("DeviceManager non initialisé")

        devices = await self._manager.get_devices()
        result: dict[str, RoborockData] = {}

        for device in devices:
            props = device.v1_properties
            if props is None:
                _LOGGER.debug("Appareil %s ignoré (pas V1 ou non supporté)", device.name)
                continue

            # Enregistrement dans tous les cas — entités "indisponible" si données absentes
            result[device.duid] = RoborockData(device=device, props=props)

            try:
                for trait_name in _TRAITS_TO_REFRESH:
                    trait = getattr(props, trait_name, None)
                    if trait is not None:
                        try:
                            await trait.refresh()
                        except Exception:  # noqa: BLE001
                            pass  # trait non supporté par ce modèle — on ignore
                _LOGGER.debug("Données mises à jour pour %s", device.name)

            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Données partielles pour %s (appareil peut-être en veille) : %s",
                    device.name, err,
                )

        if not result:
            raise UpdateFailed(
                "Aucun aspirateur V1 trouvé. "
                "Vérifiez que votre modèle est pris en charge."
            )
        return result

    async def async_shutdown(self) -> None:
        """Ferme proprement le DeviceManager."""
        if self._manager is not None:
            try:
                await self._manager.close()
            except Exception:  # noqa: BLE001
                pass
            self._manager = None
