"""
MQTT subscriber for the broker.

Connects to a Mosquitto broker and subscribes to:
    {MQTT_TOPIC_PREFIX}/+/data     (e.g. iot/devices/1/data)

When a message arrives it:
  1. Extracts the device ID from the topic.
  2. Looks up the device in the database by ID.
  3. Converts raw ADC values and stores a Reading row.
  4. Broadcasts the reading to all WebSocket clients.

Only started when MQTT_ENABLED=true in .env.
"""
import asyncio
import json
import logging
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from config import (
    MQTT_HOST, MQTT_PORT, MQTT_TOPIC_PREFIX,
    MQTT_USERNAME, MQTT_PASSWORD,
)
from database import SessionLocal
from models import Device, Reading
from ws_manager import manager

log = logging.getLogger(__name__)

# The running asyncio event loop — set by start() so the paho thread can
# schedule coroutines onto it.
_loop: asyncio.AbstractEventLoop | None = None


# ── ADC conversion (same logic as scheduler.py and routers.py) ───────────────

def _adc_to_pct(raw) -> float | None:
    if raw is None:
        return None
    return round(max(0.0, min(100.0, float(raw) / 4095.0 * 100.0)), 2)


# ── Paho callbacks ────────────────────────────────────────────────────────────

def _on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        topic = f"{MQTT_TOPIC_PREFIX}/+/data"
        client.subscribe(topic)
        log.info("MQTT connected — subscribed to %s", topic)
    else:
        log.error("MQTT connection refused (reason code %s)", reason_code)


def _on_disconnect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        log.warning("MQTT disconnected unexpectedly (rc=%s) — will auto-reconnect", reason_code)


def _on_message(client, userdata, msg):
    """Called by paho in its own thread — hand off to asyncio for DB + WS."""
    topic: str = msg.topic          # e.g. "iot/devices/uno/data"
    payload_bytes: bytes = msg.payload

    try:
        data: dict = json.loads(payload_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        log.warning("Bad MQTT payload on %s: %s", topic, exc)
        return

    # Extract device ID from topic: iot/devices/{id}/data
    parts = topic.split("/")
    if len(parts) < 3:
        log.warning("Unexpected topic format: %s", topic)
        return
    try:
        device_id = int(parts[-2])
    except ValueError:
        log.warning("Device ID in topic is not an integer: %s", topic)
        return

    if _loop and not _loop.is_closed():
        asyncio.run_coroutine_threadsafe(
            _store_and_broadcast(device_id, data), _loop
        )


async def _store_and_broadcast(device_id: int, data: dict):
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            log.warning("MQTT message for unknown device ID %d — register it first", device_id)
            return

        reading = Reading(
            device_id=device.id,
            timestamp=datetime.now(timezone.utc),
            payload=data,
            light=_adc_to_pct(data.get("light")),
            soil_moisture=_adc_to_pct(data.get("soil-moisture")),
            temp=data.get("temp"),
            ambient_humidity=data.get("ambient-humidity"),
        )
        db.add(reading)
        db.commit()
        db.refresh(reading)

        await manager.broadcast({
            "device": device.name,
            "timestamp": reading.timestamp.isoformat(),
            "data": {
                "light":            reading.light,
                "soil_moisture":    reading.soil_moisture,
                "temp":             reading.temp,
                "ambient_humidity": reading.ambient_humidity,
            },
        })

        log.info("MQTT reading stored for '%s' (id=%d): %s", device.name, device_id, data)
    finally:
        db.close()


# ── Lifecycle ─────────────────────────────────────────────────────────────────

_client: mqtt.Client | None = None


def start(loop: asyncio.AbstractEventLoop):
    """Start the paho client in a background thread."""
    global _loop, _client

    _loop = loop

    _client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    _client.on_connect    = _on_connect
    _client.on_disconnect = _on_disconnect
    _client.on_message    = _on_message

    if MQTT_USERNAME:
        _client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Use TLS when connecting to cloud brokers (e.g. HiveMQ Cloud port 8883)
    if MQTT_PORT == 8883:
        import ssl
        _client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

    _client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)

    # loop_start() spins up a background thread that handles reconnects
    _client.loop_start()
    log.info("MQTT client started (host=%s port=%d)", MQTT_HOST, MQTT_PORT)


def stop():
    if _client:
        _client.loop_stop()
        _client.disconnect()
        log.info("MQTT client stopped")


def publish(topic: str, payload: dict, retain: bool = False) -> bool:
    """Publish a JSON payload to an MQTT topic.

    Returns True if the message was queued, False if the client is not ready.
    """
    if not _client:
        log.warning("MQTT publish skipped — client not started (topic=%s)", topic)
        return False
    result = _client.publish(topic, json.dumps(payload), qos=1, retain=retain)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        log.warning("MQTT publish failed (rc=%d, topic=%s)", result.rc, topic)
        return False
    log.info("MQTT published to %s (retain=%s): %s", topic, retain, payload)
    return True
