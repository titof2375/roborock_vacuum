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
        cls = getattr(mod, class_name, None)
        if cls is not None:
            _LOGGER.debug("✓ %s trouvé dans %s", class_name, module_path)
        return cls
    except ImportError:
        return None


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

        # ── 1. Importer les classes de données (confirmé dans roborock directement) ──
        from roborock import UserData, HomeData  # noqa: PLC0415

        # ── 2. Diagnostic roborock.mqtt ──────────────────────────────────────────────
        try:
            import roborock.mqtt as _mqtt  # noqa: PLC0415
            _LOGGER.warning(
                "roborock.mqtt contenu: %s",
                [x for x in dir(_mqtt) if not x.startswith("_")],
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("roborock.mqtt inaccessible : %s", err)

        # ── 3. Diagnostic roborock.v1 ────────────────────────────────────────────────
        try:
            import roborock.v1 as _v1  # noqa: PLC0415
            _LOGGER.warning(
                "roborock.v1 contenu: %s",
                [x for x in dir(_v1) if not x.startswith("_")],
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("roborock.v1 inaccessible : %s", err)

        # ── 4. Trouver le client MQTT (ordre de priorité) ────────────────────────────
        MQTT_CANDIDATES = [
            ("roborock.mqtt",    "RoborockMqttClient"),
            ("roborock.mqtt",    "RoborockMqttClientV1"),
            ("roborock.v1",      "RoborockMqttClientV1"),
            ("roborock.v1",      "RoborockMqttClient"),
            ("roborock",         "RoborockMqttClient"),
            ("roborock",         "RoborockMqttClientV1"),
        ]

        MqttClient = None
        for module_path, class_name in MQTT_CANDIDATES:
            MqttClient = _try_import(module_path, class_name)
            if MqttClient is not None:
                _LOGGER.info("Client MQTT : %s.%s", module_path, class_name)
                break

        if MqttClient is None:
            raise UpdateFailed(
                "Client MQTT Roborock introuvable. "
                "Consultez les logs roborock.mqtt et roborock.v1 ci-dessus."
            )

        # ── 5. Créer les clients pour chaque appareil ────────────────────────────────
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
                # Essai nouvelle API (sans user_data)
                try:
                    client = MqttClient(device_info=device, product_info=product)
                    _LOGGER.debug("Constructeur sans user_data utilisé")
                except TypeError:
                    # Ancienne API (avec user_data)
                    client = MqttClient(
                        user_data=user_data,
                        device_info=device,
                        product_info=product,
                    )
                    _LOGGER.debug("Constructeur avec user_data utilisé")

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
