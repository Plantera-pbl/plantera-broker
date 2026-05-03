# Broker

The FastAPI server that receives sensor data, stores it in SQLite, and streams
it to connected clients over WebSocket.

---

## Files

| File | Purpose |
|---|---|
| `main.py` | App entry point — starts the API, scheduler, and MQTT client |
| `config.py` | All settings, loaded from `.env` |
| `database.py` | SQLAlchemy engine and session |
| `models.py` | `Device` and `Reading` database models |
| `scheduler.py` | Polls HTTP devices on a timer |
| `routers.py` | All REST endpoints and the WebSocket endpoint |
| `ws_manager.py` | Broadcasts new readings to WebSocket clients |
| `mqtt_client.py` | Subscribes to an MQTT broker (local Mosquitto or HiveMQ Cloud) and stores incoming readings |
| `mock_mc.py` | Fake microcontroller that serves random sensor data over HTTP on port 8001 |
| `mock_mc_mqtt.py` | Fake microcontroller that publishes random sensor data to Mosquitto |

---

## Setup

```powershell
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and edit if needed (defaults work out of the box
for local testing).

---

## Running

```powershell
python main.py
```

API: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`

**View data links** (open in browser while the broker is running):

| Link | Shows |
|---|---|
| `http://localhost:8000/api/v1/devices` | All registered devices |
| `http://localhost:8000/api/v1/devices/1/readings` | Last 100 readings for device 1 |
| `http://localhost:8000/api/v1/devices/1/readings/latest` | Most recent reading for device 1 |
| `http://localhost:8000/docs` | Interactive API explorer |

---

## Registering devices

Devices are stored in the database. Register each one once after the broker
has started for the first time.

**Arduino Uno (push / MQTT — no polling):**
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/devices `
  -ContentType "application/json" `
  -Body '{"name":"uno","url":"","poll_interval":5}'
```

**HTTP polling device (e.g. mock_mc.py):**
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/devices `
  -ContentType "application/json" `
  -Body '{"name":"mock-mc","url":"http://localhost:8001/data","poll_interval":5}'
```

The response includes an `id` field — note it down, you need it when starting
a serial bridge (`--device-id`).

**List registered devices:**
```powershell
Invoke-RestMethod http://localhost:8000/api/v1/devices
```

**Remove a device:**
```powershell
Invoke-RestMethod -Method Delete http://localhost:8000/api/v1/devices/1
```

---

## Testing without hardware

**HTTP mock** (no Mosquitto needed):  
Start the mock microcontroller in a separate terminal:

```powershell
python mock_mc.py
```

Make sure `MC_URL=http://localhost:8001/data` is set in `.env` — the broker
polls it automatically every 5 seconds.

**MQTT mock — local Mosquitto** (`MQTT_ENABLED=true`, `MQTT_PORT=1883` in `.env`):  
Publishes random readings to a local Mosquitto instance:

```powershell
python mock_mc_mqtt.py --device-id 1
```

**MQTT mock — HiveMQ Cloud** (`MQTT_ENABLED=true`, `MQTT_PORT=8883` in `.env`):  
Create credentials first: HiveMQ Cloud dashboard → your cluster → **Access Management → Credentials → Add**.

Then register a device and run the mock:

```powershell
# Register device (one-time)
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/devices `
  -ContentType "application/json" `
  -Body '{"name":"mock-mqtt","url":"","poll_interval":5}'

# Run mock (replace values with your HiveMQ host and credentials)
python mock_mc_mqtt.py `
  --device-id 1 `
  --mqtt-host YOUR_CLUSTER.s1.eu.hivemq.cloud `
  --mqtt-port 8883 `
  --username YOUR_USERNAME `
  --password YOUR_PASSWORD `
  --interval 5
```

TLS is enabled automatically when port is `8883` — no extra setup needed.

Verify data is arriving:
```powershell
Invoke-RestMethod http://localhost:8000/api/v1/devices/1/readings/latest
```

---

## .env options

| Key | Default | Description |
|---|---|---|
| `MC_URL` | *(blank)* | URL to poll for HTTP devices |
| `MC_POLL_INTERVAL` | `5` | Polling interval in seconds |
| `MC_TIMEOUT` | `3` | HTTP request timeout in seconds |
| `DATABASE_URL` | `sqlite:///./broker.db` | Database connection string |
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | Port |
| `MAX_READINGS_PER_DEVICE` | `10000` | Readings kept per device (0 = unlimited) |
| `MQTT_ENABLED` | `false` | Set to `true` to enable MQTT subscriber |
| `MQTT_HOST` | `localhost` | MQTT broker host (use HiveMQ Cloud hostname for cloud) |
| `MQTT_PORT` | `1883` | `1883` for local Mosquitto, `8883` for HiveMQ Cloud (TLS auto-enabled) |
| `MQTT_TOPIC_PREFIX` | `iot/devices` | Topic prefix (`{prefix}/{device_id}/data`) |
| `MQTT_USERNAME` | *(blank)* | MQTT username (leave blank if none) |
| `MQTT_PASSWORD` | *(blank)* | MQTT password |

---

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/devices` | List all devices |
| `POST` | `/api/v1/devices` | Register a device |
| `DELETE` | `/api/v1/devices/{id}` | Remove a device |
| `GET` | `/api/v1/devices/{id}/readings` | Reading history (`?limit=100&since=<iso>`) |
| `GET` | `/api/v1/devices/{id}/readings/latest` | Most recent reading |
| `POST` | `/api/v1/devices/{id}/push` | Push a reading directly |
| `WS` | `/api/v1/ws` | Live WebSocket feed |
