"""
Broker configuration — edit these values or use a .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Microcontroller ────────────────────────────────────────────────────────────
MC_URL: str = os.getenv("MC_URL", "http://192.168.1.100/data")
MC_POLL_INTERVAL: int = int(os.getenv("MC_POLL_INTERVAL", "5"))   # seconds
MC_TIMEOUT: int = int(os.getenv("MC_TIMEOUT", "3"))               # seconds

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./broker.db")

# ── API Server ─────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# ── MQTT ──────────────────────────────────────────────────────────────────────
MQTT_ENABLED: bool = os.getenv("MQTT_ENABLED", "false").lower() == "true"
MQTT_HOST: str = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX: str = os.getenv("MQTT_TOPIC_PREFIX", "iot/devices")
# Optional broker auth (leave blank if Mosquitto has no password)
MQTT_USERNAME: str = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD: str = os.getenv("MQTT_PASSWORD", "")

# ── Data retention ─────────────────────────────────────────────────────────────
MAX_READINGS_PER_DEVICE: int = int(os.getenv("MAX_READINGS_PER_DEVICE", "10000"))
