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
    """Essaie d'importer une classe, retourne None si introuvable."""
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name, None)
    except ImportError:
        return None


def _log_ha_roborock_imports() -> None:
    """Log les imports de l'intégration Roborock officielle de HA (même librairie)."""
    try:
        import inspect
        import homeassistant.components.roborock.coordinator as _ha  # noqa: PLC0415
        src = inspect.getsource(_ha)
        imports = [l.strip() for l in src.split("\n")
                   if ("import" in l) and ("roborock" in l.lower()) and not l.strip().startswith("#")]
        _LOGGER.warning("HA Roborock coordinator imports: %s", imports[:30])
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Impossible de lire HA coordinator : %s", err)


def _log_submodules(pkg_name: str) -> None:
    """Log les sous-modules d'un package roborock."""
    try:
        import pkgutil  # noqa: PLC0415
        mod = importlib.import_module(pkg_name)
        path = getattr(mod, "__path__", None)
        if path:
            subs = [m.name for m in pkgutil.iter_modules(path, pkg_name + ".")]
            _LOGGER.warning("%s sous-modules: %s | contenu: %s",
                            pkg_name, subs,
                            [x for x in dir(mod) if not x.startswith("_")])
        else:
            _LOGGER.warning("%s n'est pas un package (pas de __path__)", pkg_name)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("%s inaccessible : %s", pkg_name, err)


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
        from roborock import UserData, HomeData  # noqa: PLC0415

        # ── Diagnostics ────────────────────────────────────────────────────────────
        _log_ha_roborock_imports()
        _log_submodules("roborock.mqtt")
        _log_submodules("roborock.protocols")
        _log_submodules("roborock.devices")

        # ── Recherche du client MQTT ───────────────────────────────────────────────
        MQTT_CANDIDATES = [
            ("roborock.mqtt",            "RoborockMqttClient"),
            ("roborock.mqtt",            "RoborockMqttClientV1"),
            ("roborock.mqtt.client",     "RoborockMqttClient"),
            ("roborock.mqtt.client",     "RoborockMqttClientV1"),
            ("roborock.protocols",       "RoborockMqttClient"),
            ("roborock.protocols",       "RoborockMqttClientV1"),
            ("roborock.devices",         "RoborockMqttClient"),
            ("roborock.devices",         "RoborockMqttClientV1"),
            ("roborock",                 "RoborockMqttClient"),
            ("roborock",                 "RoborockMqttClientV1"),
        ]

        MqttClient = None
        for module_path, class_name in MQTT_CANDIDATES:
            MqttClient = _try_import(module_path, class_name)
            if MqttClient is not None:
                _LOGGER.warning("✓ Client MQTT trouvé : %s.%s", module_path, class_name)
                break

        if MqttClient is None:
            raise UpdateFailed(
                "Client MQTT Roborock introuvable. "
                "Voir les logs HA Roborock coordinator imports ci-dessus."
            )

        # ── Connexion aux appareils ────────────────────────────────────────────────
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
                try:
                    client = MqttClient(device_info=device, product_info=product)
                except TypeError:
                    client = MqttClient(
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
        from roborock import HomeData  # noqa: PLC0415

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
                    device=device, product=product, props=props, client=client,
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
