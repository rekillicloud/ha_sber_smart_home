"""Constants for Sber Smart Home."""
import ssl
from pathlib import Path

DOMAIN = "sber_smart_home"

COMPANION_TOKEN_URL = "https://companion.devices.sberbank.ru/v13/smarthome/token"
GATEWAY_API = "https://gateway.iot.sberdevices.ru/gateway/v1"
DEVICE_GROUPS_URL = f"{GATEWAY_API}/device_groups/tree"

AUTH_ENDPOINT = "https://online.sberbank.ru/CSAFront/oidc/authorize.do"
TOKEN_ENDPOINT = "https://online.sberbank.ru:4431/CSAFront/api/service/oidc/v3/token"

CLIENT_ID = "b1f0f0c6-fcb0-4ece-8374-6b614ebe3d42"
REDIRECT_URI = "companionapp://host"

SCAN_INTERVAL = 30

DEFAULT_SSL_CERT_PATH = Path(__file__).parent / "russian_trusted_root_ca.pem"

ssl_context = ssl.create_default_context()
ssl_context.check_verify_flags = ssl.CERT_NONE
ssl_context.load_verify_locations(str(DEFAULT_SSL_CERT_PATH))


ATTRIBUTE_TYPE_MAP = {
    "on_off": {"platform": "switch", "attribute": "on_off"},
    "switch_led": {"platform": "switch", "attribute": "switch_led"},
    "online": {"platform": "sensor", "attribute": "online"},
    "light_brightness": {"platform": "light", "attribute": "brightness"},
    "light_colour_temp": {"platform": "light", "attribute": "color_temp"},
    "light_colour": {"platform": "light", "attribute": "color"},
    "humidity": {"platform": "sensor", "attribute": "humidity", "unit": "%"},
    "temperature": {"platform": "sensor", "attribute": "temperature", "unit": "°C"},
    "power": {"platform": "sensor", "attribute": "power", "unit": "W"},
    "voltage": {"platform": "sensor", "attribute": "voltage", "unit": "V"},
    "current": {"platform": "sensor", "attribute": "current", "unit": "A"},
}

DEVICE_TYPE_MAP = {
    "light": ["SBDV-00055", "light"],
    "switch": ["Janch", "VHub"],
    "sensor": [],
}

CONF_API_TOKEN = "api_token"
CONF_GATEWAY_TOKEN = "gateway_token"
