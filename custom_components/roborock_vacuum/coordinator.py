"""DataUpdateCoordinator pour Roborock Vacuum."""
from __future__ import annotations

import importlib
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


def _try_import(module_path: str, class_name: str) -> Any | None:
    """Essaie d'importer une classe depuis un module, retourne None si introuvable."""
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name, None)
    except ImportError:
        return None


def _log_roborock_contents() -> None:
    """Log le contenu du module roborock pour diagnostic."""
    try:
        import roborock as _rb
        import pkgutil
        modules = [m.name for m in pkgutil.iter_modules(_rb.__path__, _rb.__name__ + ".")]
        version = getattr(_rb, "__version__", "inconnue")
        _LOGGER.warning(
            "python-roborock version=%s | sous-modules=%s | contenu principal=%s",
            version,
            modules,
            [x for x in dir(_rb) if not x.startswith("_")],
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Impossible d'inspecter python-roborock : %s", err)


def _import_class(class_name: str, candidates: list[str]) -> Any:
    """Importe une classe en testant plusieurs chemins."""
    for module_path in candidates:
        cls = _try_import(module_path, class_name)
        if cls is not None:
            _LOGGER.debug("Importé %s depuis %s", class_name, module_path)
            return cls
    _log_roborock_contents()
    raise UpdateFailed(
        f"python-roborock incompatible : {class_name} introuvable. "
        "Consultez les logs pour voir les modules disponibles."
    )


def _get_HomeData() -> Any:
    return _import_class("HomeData", [
        "roborock.containers",
        "roborock",
        "roborock.api",
        "roborock.protocol",
    ])


def _get_UserData() -> Any:
    return _import_class("UserData", [
        "roborock.containers",
        "roborock",
        "roborock.api",
    ])


def _get_MqttClientV1() -> Any:
    return _import_class("RoborockMqttClientV1", [
        "roborock.version_1_apis",
        "roborock",
        "roborock.api",
        "roborock.mqtt",
        "roborock.cloud_api",
        "roborock.local_api",
    ])


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
        RoborockMqttClientV1 = _get_MqttClientV1()
        UserData = _get_UserData()
        HomeData = _get_HomeData()

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
        HomeData = _get_HomeData()
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
