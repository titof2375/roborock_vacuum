"""DataUpdateCoordinator pour Roborock Vacuum."""
from __future__ import annotations

import logging
from datetime import timedelta
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockData:
    """Données d'un aspirateur."""
    device: Any
    product: Any
    props: Any
    client: Any


def _import_home_data() -> Any:
    """Importe HomeData en testant plusieurs chemins selon la version."""
    try:
        from roborock.containers import HomeData
        return HomeData
    except ImportError:
        pass
    try:
        from roborock import HomeData  # type: ignore[no-redef]
        return HomeData
    except ImportError:
        pass
    raise UpdateFailed(
        "python-roborock incompatible : HomeData introuvable. "
        "Vérifiez la version installée (>=2.8.0,<3.0.0 recommandé)."
    )


def _import_user_data() -> Any:
    """Importe UserData en testant plusieurs chemins selon la version."""
    try:
        from roborock.containers import UserData
        return UserData
    except ImportError:
        pass
    try:
        from roborock import UserData  # type: ignore[no-redef]
        return UserData
    except ImportError:
        pass
    raise UpdateFailed("python-roborock incompatible : UserData introuvable.")


class RoborockVacuumCoordinator(DataUpdateCoordinator[dict[str, RoborockData]]):
    """Coordinateur — un entry = un compte, plusieurs aspirateurs possibles."""

    def __init__(
        self,
        hass: HomeAssistant,
        email: str,
        user_data_dict: dict,
        home_data_raw: dict,
    ) -> None:
        self._email = email
        self._user_data_dict = user_data_dict
        self._home_data_raw = home_data_raw
        self._clients: dict[str, Any] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{email}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )

    async def _async_setup(self) -> None:
        """Initialise les clients MQTT pour chaque appareil."""
        try:
            from roborock.version_1_apis import RoborockMqttClientV1
        except ImportError as err:
            raise UpdateFailed(f"python-roborock incompatible : {err}") from err

        UserData = _import_user_data()
        HomeData = _import_home_data()

        user_data = UserData.from_dict(self._user_data_dict)
        home_data = HomeData.from_dict(self._home_data_raw)

        for device in home_data.devices + home_data.received_devices:
            product = next(
                (p for p in home_data.products if p.id == device.product_id),
                None,
            )
            if product is None:
                continue
            try:
                client = RoborockMqttClientV1(
                    user_data=user_data,
                    device_info=device,
                    product_info=product,
                )
                await client.async_connect()
                self._clients[device.duid] = client
                _LOGGER.info("Connecté à %s (%s)", device.name, device.duid)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Impossible de connecter %s : %s", device.name, err)

    async def _async_update_data(self) -> dict[str, RoborockData]:
        """Récupère le statut de tous les aspirateurs."""
        HomeData = _import_home_data()
        home_data = HomeData.from_dict(self._home_data_raw)
        result: dict[str, RoborockData] = {}

        for device in home_data.devices + home_data.received_devices:
            client = self._clients.get(device.duid)
            if client is None:
                continue

            product = next(
                (p for p in home_data.products if p.id == device.product_id),
                None,
            )
            if product is None:
                continue

            try:
                props = await client.get_prop()
                result[device.duid] = RoborockData(
                    device=device,
                    product=product,
                    props=props,
                    client=client,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Erreur lecture %s : %s", device.name, err)

        if not result:
            raise UpdateFailed("Aucun aspirateur disponible")

        return result

    async def async_shutdown(self) -> None:
        """Déconnecte tous les clients."""
        for client in self._clients.values():
            try:
                await client.async_disconnect()
            except Exception:  # noqa: BLE001
                pass
        self._clients.clear()
