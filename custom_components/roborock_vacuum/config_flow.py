"""Config flow pour Roborock Vacuum — authentification email + code OTP."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from roborock.web_api import RoborockApiClient
from roborock.exceptions import RoborockException

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_EMAIL, CONF_USER_DATA, CONF_HOME_DATA

_LOGGER = logging.getLogger(__name__)


class RoborockVacuumConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow en 2 étapes : email → code OTP."""

    VERSION = 1

    def __init__(self) -> None:
        self._email: str = ""
        self._client: RoborockApiClient | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape 1 : saisie de l'adresse email."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL].strip()
            session = async_get_clientsession(self.hass)
            self._client = RoborockApiClient(username=self._email, session=session)
            try:
                await self._client.request_code()
            except RoborockException as err:
                _LOGGER.error("Erreur envoi code Roborock : %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Erreur inattendue : %s", err)
                errors["base"] = "unknown"
            else:
                return await self.async_step_code()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_EMAIL): str}),
            errors=errors,
        )

    async def async_step_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape 2 : saisie du code reçu par email."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input["code"].strip()
            try:
                user_data = await self._client.code_login(code)
                home_data = await self._client.get_home_data_v2(user_data)
            except RoborockException as err:
                _LOGGER.error("Code Roborock invalide : %s", err)
                errors["base"] = "invalid_code"
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Erreur inattendue : %s", err)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(self._email)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._email,
                    data={
                        CONF_EMAIL:     self._email,
                        CONF_USER_DATA: user_data.as_dict(),
                        CONF_HOME_DATA: home_data.as_dict(),
                    },
                )

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
            description_placeholders={"email": self._email},
        )
