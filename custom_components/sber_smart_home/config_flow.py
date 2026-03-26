"""Config flow for Sber Smart Home."""

import asyncio
import logging
import ssl
import time
from pathlib import Path
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_CODE
from homeassistant.helpers import aiohttp_client

from .const import (
    AUTH_ENDPOINT,
    CLIENT_ID,
    DEFAULT_SSL_CERT_PATH,
    DOMAIN,
    REDIRECT_URI,
    TOKEN_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("access_token"): str,
    }
)


def get_ssl_context() -> ssl.SSLContext:
    """Create SSL context for Sber API."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_verify_flags = ssl.CERT_NONE
    ssl_context.load_verify_locations(str(DEFAULT_SSL_CERT_PATH))
    return ssl_context


async def exchange_code_for_token(
    auth_code: str, code_verifier: str = None
) -> dict | None:
    """Exchange authorization code for access token."""
    ssl_context = get_ssl_context()

    try:
        async with aiohttp.ClientSession() as session:
            data = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
            }
            if code_verifier:
                data["code_verifier"] = code_verifier

            async with session.post(
                TOKEN_ENDPOINT,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                ssl=ssl_context,
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    _LOGGER.info("Token obtained successfully")
                    return result
                else:
                    text = await response.text()
                    _LOGGER.error("Token exchange failed: %s %s", response.status, text)
    except Exception as e:
        _LOGGER.error("Token exchange error: %s", e)

    return None


async def get_gateway_token(access_token: str) -> str | None:
    """Get gateway token from Sber API."""
    ssl_context = get_ssl_context()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://companion.devices.sberbank.ru/v13/smarthome/token",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": "Salute+prod%2F24.08.1.15602+(Android+34;Google+sdk_gphone64_arm64)",
                },
                ssl=ssl_context,
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("token")
    except Exception as e:
        _LOGGER.error("Failed to get gateway token: %s", e)

    return None


class SberSmartHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sber Smart Home."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            access_token = user_input.get("access_token", "")

            if access_token:
                gateway_token = await get_gateway_token(access_token)

                if gateway_token:
                    return self.async_create_entry(
                        title="Sber Smart Home",
                        data={
                            "access_token": access_token,
                            "gateway_token": gateway_token,
                        },
                    )
                else:
                    errors["base"] = "invalid_gateway_token"
            else:
                errors["base"] = "invalid_access_token"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={
                "auth_url": f"{AUTH_ENDPOINT}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=openid",
                "instructions": (
                    "1. Откройте ссылку ниже в браузере\n"
                    "2. Войдите в аккаунт Сбер\n"
                    "3. Скопируйте code из URL после redirect (companionapp://host?code=XXX&state=YYY)\n"
                    "4. Вставьте код в поле ниже\n"
                    "5. Дождитесь получения токена (автоматически)"
                ),
            },
            errors=errors,
        )
