"""Config flow for Sber Smart Home."""

import logging
import re
import ssl
import uuid

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import (
    AUTH_ENDPOINT,
    CLIENT_ID,
    DEFAULT_SSL_CERT_PATH,
    DOMAIN,
    REDIRECT_URI,
    TOKEN_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

_AUTH_URL = None
_CODE_VERIFIER = None


def _generate_auth_url() -> tuple[str, str]:
    """Generate auth URL with PKCE."""
    import base64
    import hashlib
    import os

    random_bytes = os.urandom(32)
    code_verifier = base64.urlsafe_b64encode(random_bytes).decode().rstrip("=")

    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = (
        base64.urlsafe_b64encode(digest)
        .decode()
        .rstrip("=")
        .replace("+", "-")
        .replace("/", "_")
    )

    auth_url = (
        f"{AUTH_ENDPOINT}"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=openid"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&state={uuid.uuid4().hex}"
    )

    return auth_url, code_verifier


def get_ssl_context() -> ssl.SSLContext:
    """Create SSL context for Sber API."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_verify_flags = ssl.CERT_NONE
    ssl_context.load_verify_locations(str(DEFAULT_SSL_CERT_PATH))
    return ssl_context


async def exchange_code_for_token(auth_code: str, code_verifier: str) -> dict | None:
    """Exchange authorization code for access token."""
    ssl_context = get_ssl_context()

    try:
        async with aiohttp.ClientSession() as session:
            data = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier,
            }

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
        global _AUTH_URL, _CODE_VERIFIER
        if _AUTH_URL is None:
            _AUTH_URL, _CODE_VERIFIER = _generate_auth_url()

    async def async_step_user(self, user_input=None):
        """Initial step - show auth URL and ask for redirect URL."""

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required("redirect_url"): str}),
                description_placeholders={"auth_url": _AUTH_URL},
            )

        redirect_url = user_input.get("redirect_url", "").strip()

        if not redirect_url:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "redirect_url",
                            description="Вставьте ссылку из адресной строки",
                        ): str,
                    }
                ),
                errors={"redirect_url": "missing_url"},
            )

        match = re.search(r"code=([A-F0-9-]+)", redirect_url)
        if not match:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "redirect_url",
                            description="Ссылка должна содержать code=",
                        ): str,
                    }
                ),
                errors={"redirect_url": "invalid_url"},
            )

        code = match.group(1)
        _LOGGER.info("Exchanging code for token...")

        token_data = await exchange_code_for_token(code, _CODE_VERIFIER)

        if not token_data:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "redirect_url",
                            description="Неверный код. Попробуйте снова.",
                        ): str,
                    }
                ),
                errors={"redirect_url": "invalid_code"},
            )

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token", "")
        expires_in = token_data.get("expires_in", 1800)

        _LOGGER.info("Getting gateway token...")

        gateway_token = await get_gateway_token(access_token)

        if not gateway_token:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "redirect_url",
                            description="Не удалось получить токен шлюза",
                        ): str,
                    }
                ),
                errors={"redirect_url": "gateway_token_error"},
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
