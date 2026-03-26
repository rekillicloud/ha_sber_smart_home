"""Config flow for Sber Smart Home."""

import logging
import ssl
from typing import Any
import uuid

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    AUTH_ENDPOINT,
    CLIENT_ID,
    DEFAULT_SSL_CERT_PATH,
    DOMAIN,
    REDIRECT_URI,
    TOKEN_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


def get_ssl_context() -> ssl.SSLContext:
    """Create SSL context for Sber API."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_verify_flags = ssl.CERT_NONE
    ssl_context.load_verify_locations(str(DEFAULT_SSL_CERT_PATH))
    return ssl_context


async def exchange_code_for_token(
    auth_code: str, code_verifier: str | None = None
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

    def __init__(self):
        """Initialize flow."""
        self._code_verifier = None
        self._auth_url = None

    def _generate_code_verifier(self) -> str:
        """Generate PKCE code verifier."""
        import base64
        import os

        random_bytes = os.urandom(32)
        return base64.urlsafe_b64encode(random_bytes).decode("rstrip=")

    def _generate_code_challenge(self, verifier: str) -> str:
        """Generate PKCE code challenge from verifier."""
        import base64
        import hashlib

        digest = hashlib.sha256(verifier.encode()).digest()
        return (
            base64.urlsafe_b64encode(digest)
            .decode("rstrip=")
            .replace("+", "-")
            .replace("/", "_")
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - show auth URL."""
        self._code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(self._code_verifier)

        self._auth_url = (
            f"{AUTH_ENDPOINT}"
            f"?response_type=code"
            f"&client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&scope=openid"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&state={uuid.uuid4().hex}"
        )

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "auth_url": self._auth_url,
            },
            data_schema=vol.Schema({}),
        )

    async def async_step_authorized(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle after user authorized."""
        return self.async_show_form(
            step_id="code",
            description_placeholders={},
            data_schema=vol.Schema(
                {
                    vol.Required("code"): str,
                }
            ),
            errors={},
        )

    async def async_step_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle code submission."""
        errors = {}

        if user_input is not None:
            code = user_input.get("code", "").strip()

            if not code:
                errors["code"] = "missing_code"
                return self.async_show_form(
                    step_id="code",
                    data_schema=vol.Schema({vol.Required("code"): str}),
                    errors=errors,
                )

            _LOGGER.info("Exchanging code for token...")

            token_data = await exchange_code_for_token(code, self._code_verifier)

            if not token_data:
                errors["code"] = "invalid_code"
                return self.async_show_form(
                    step_id="code",
                    description_placeholders={
                        "error": "Неверный код. Попробуйте снова."
                    },
                    data_schema=vol.Schema({vol.Required("code"): str}),
                    errors=errors,
                )

            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token", "")
            expires_in = token_data.get("expires_in", 1800)

            _LOGGER.info("Getting gateway token...")

            gateway_token = await get_gateway_token(access_token)

            if not gateway_token:
                errors["base"] = "gateway_token_error"
                return self.async_show_form(
                    step_id="code",
                    data_schema=vol.Schema({vol.Required("code"): str}),
                    errors=errors,
                )

            return self.async_create_entry(
                title="Sber Smart Home",
                data={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "gateway_token": gateway_token,
                    "expires_in": expires_in,
                },
            )

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
        )
