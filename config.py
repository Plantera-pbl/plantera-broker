"""
Broker configuration — edit these values or use a .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Microcontroller ────────────────────────────────────────────────────────────
# URL of the HTTP endpoint exposed by the microcontroller (ESP32/ESP8266, etc.)
# The endpoint must return JSON, e.g. {"temperature": 25.3, "humidity": 60}
MC_URL: str = os.getenv("MC_URL", "http://192.168.1.100/data")
MC_POLL_INTERVAL: int = int(os.getenv("MC_POLL_INTERVAL", "5"))   # seconds
MC_TIMEOUT: int = int(os.getenv("MC_TIMEOUT", "3"))               # seconds

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./broker.db")

# ── API Server ─────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# ── Data retention ─────────────────────────────────────────────────────────────
# Keep at most this many readings per device (0 = unlimited)
MAX_READINGS_PER_DEVICE: int = int(os.getenv("MAX_READINGS_PER_DEVICE", "10000"))
