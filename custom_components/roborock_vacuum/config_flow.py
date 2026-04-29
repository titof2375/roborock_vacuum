"""Config flow pour Roborock Vacuum — authentification email + code OTP."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_USERNAME, CONF_USER_DATA, CONF_BASE_URL

_LOGGER = logging.getLogger(__name__)


class RoborockVacuumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow en 2 étapes : email → code OTP."""

    VERSION = 2

    def __init__(self) -> None:
        self._username: str = ""
        self._client: Any = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Étape 1 : saisie de l'adresse email."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input["username"].strip()
            try:
                from roborock.web_api import RoborockApiClient  # noqa: PLC0415
            except ImportError:
                errors["base"] = "cannot_connect"
                _LOGGER.error("python-roborock non installé ou incompatible")
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({vol.Required("username"): str}),
                    errors=errors,
                )

            session = async_get_clientsession(self.hass)
            self._client = RoborockApiClient(username=self._username, session=session)
            try:
                await self._client.request_code()
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Erreur envoi code Roborock : %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_code()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("username"): str}),
            errors=errors,
        )

    async def async_step_code(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Étape 2 : saisie du code reçu par email."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input["code"].strip()
            try:
                # Essayer la nouvelle méthode d'abord, puis l'ancienne
                if hasattr(self._client, "code_login_v4"):
                    user_data = await self._client.code_login_v4(code)
                else:
                    user_data = await self._client.code_login(code)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Code Roborock invalide : %s", err)
                errors["base"] = "invalid_code"
            else:
                await self.async_set_unique_id(self._username)
                self._abort_if_unique_id_configured()

                user_data_dict = (
                    user_data.as_dict()
                    if hasattr(user_data, "as_dict")
                    else dict(user_data)
                )

                # base_url accélère les reconnexions futures (optionnel)
                base_url: str | None = None
                try:
                    base_url = await self._client.base_url
                except Exception:  # noqa: BLE001
                    pass

                return self.async_create_entry(
                    title=self._username,
                    data={
                        CONF_USERNAME: self._username,
                        CONF_USER_DATA: user_data_dict,
                        CONF_BASE_URL: base_url,
                    },
                )

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
            description_placeholders={"email": self._username},
        )
