"""
mock_mc_mqtt.py
---------------
Simulates an Arduino Uno by publishing random sensor data to Mosquitto
on a fixed interval.  Use this to test the full MQTT pipeline without
any hardware.

Run alongside the broker (with MQTT_ENABLED=true in .env):
    python mock_mc_mqtt.py

    # Custom device ID or interval:
    python mock_mc_mqtt.py --device-id 2 --interval 3
"""
import argparse
import json
import logging
import os
import random
import sys
import time

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

log = logging.getLogger("mock_mc_mqtt")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Mock MQTT microcontroller")
    parser.add_argument("--device-id",    default=1, type=int, dest="device_id",
                        help="Device ID registered in the broker (default: 1)")
    parser.add_argument("--interval",     default=5, type=float,
                        help="Seconds between readings (default: 5)")
    parser.add_argument("--mqtt-host",    default=os.getenv("MQTT_HOST", "localhost"), dest="mqtt_host")
    parser.add_argument("--mqtt-port",    default=int(os.getenv("MQTT_PORT", "1883")), type=int, dest="mqtt_port")
    parser.add_argument("--topic-prefix", default=os.getenv("MQTT_TOPIC_PREFIX", "iot/devices"), dest="topic_prefix")
    parser.add_argument("--username",     default=os.getenv("MQTT_USERNAME", ""))
    parser.add_argument("--password",     default=os.getenv("MQTT_PASSWORD", ""))
    return parser.parse_args()


def random_reading() -> dict:
    return {
        "light":            random.randint(0, 4095),
        "soil-moisture":    random.randint(0, 4095),
        "temp":             round(random.uniform(-40, 80), 1),
        "ambient-humidity": round(random.uniform(0, 100), 1),
    }


def make_client(args) -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def on_connect(c, userdata, flags, reason_code, properties):
        if reason_code == 0:
            log.info("Connected to Mosquitto at %s:%d", args.mqtt_host, args.mqtt_port)
        else:
            log.error("Connection refused (rc=%s) — is Mosquitto running?", reason_code)

    client.on_connect = on_connect

    if args.username:
        client.username_pw_set(args.username, args.password)

    # Use TLS for cloud brokers (e.g. HiveMQ Cloud uses port 8883)
    if args.mqtt_port == 8883:
        import ssl
        client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

    try:
        client.connect_async(args.mqtt_host, args.mqtt_port, keepalive=60)
    except Exception as e:
        log.error("Cannot reach broker at %s:%d: %s", args.mqtt_host, args.mqtt_port, e)
        sys.exit(1)

    client.loop_start()
    return client


def run(args):
    topic = f"{args.topic_prefix}/{args.device_id}/data"
    log.info("Publishing to topic: %s  every %gs", topic, args.interval)
    log.info("Make sure the broker is running with MQTT_ENABLED=true")

    client = make_client(args)
    time.sleep(1.5)  # wait for connection

    while True:
        data = random_reading()
        result = client.publish(topic, json.dumps(data), qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            log.info("Published: %s", data)
        else:
            log.warning("Publish failed (rc=%s) — is Mosquitto running?", result.rc)
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        run(parse_args())
    except KeyboardInterrupt:
        log.info("Stopped.")
        sys.exit(0)
