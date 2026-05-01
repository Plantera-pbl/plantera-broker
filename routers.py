"""
REST API routes for devices and readings, plus the WebSocket endpoint.
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Device, Reading
from scheduler import schedule_device, unschedule_device
from ws_manager import manager

router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class DeviceCreate(BaseModel):
    name: str
    url: str
    poll_interval: int = 5   # seconds


class DeviceOut(BaseModel):
    id: int
    name: str
    url: str
    poll_interval: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReadingOut(BaseModel):
    id: int
    device_id: int
    timestamp: datetime
    payload: dict
    light: Optional[float] = None             # % (0–100)
    soil_moisture: Optional[float] = None     # % (0–100)
    temp: Optional[float] = None              # °C
    ambient_humidity: Optional[float] = None  # % (0–100)

    class Config:
        from_attributes = True


# ── Device endpoints ───────────────────────────────────────────────────────────

@router.get("/devices", response_model=List[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).all()


@router.post("/devices", response_model=DeviceOut, status_code=201)
def create_device(body: DeviceCreate, db: Session = Depends(get_db)):
    if db.query(Device).filter(Device.name == body.name).first():
        raise HTTPException(status_code=409, detail="Device name already exists.")
    device = Device(**body.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    schedule_device(device)
    return device


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found.")
    unschedule_device(device_id)
    db.delete(device)
    db.commit()


# ── Reading endpoints ──────────────────────────────────────────────────────────

@router.get("/devices/{device_id}/readings", response_model=List[ReadingOut])
def get_readings(
    device_id: int,
    limit: int = 100,
    since: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """Return the latest readings for a device, optionally filtered by timestamp."""
    if not db.query(Device).filter(Device.id == device_id).first():
        raise HTTPException(status_code=404, detail="Device not found.")

    q = db.query(Reading).filter(Reading.device_id == device_id)
    if since:
        q = q.filter(Reading.timestamp >= since)
    return q.order_by(Reading.timestamp.desc()).limit(limit).all()


@router.get("/devices/{device_id}/readings/latest", response_model=ReadingOut)
def get_latest_reading(device_id: int, db: Session = Depends(get_db)):
    reading = (
        db.query(Reading)
        .filter(Reading.device_id == device_id)
        .order_by(Reading.timestamp.desc())
        .first()
    )
    if not reading:
        raise HTTPException(status_code=404, detail="No readings found.")
    return reading


# ── Push endpoint (used by serial_bridge.py / any device that can POST) ────────

class ReadingPush(BaseModel):
    light: Optional[float] = None             # raw ADC 0-4095
    soil_moisture: Optional[float] = None     # raw ADC 0-4095 (key: soil-moisture)
    temp: Optional[float] = None              # °C
    ambient_humidity: Optional[float] = None  # % (key: ambient-humidity)

    class Config:
        # Accept both hyphenated JSON keys and underscore Python keys
        populate_by_name = True


def _adc_to_pct(raw) -> float | None:
    if raw is None:
        return None
    return round(max(0.0, min(100.0, (float(raw) / 4095.0) * 100.0)), 2)


@router.post("/devices/{device_id}/push", response_model=ReadingOut, status_code=201)
async def push_reading(
    device_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
):
    """
    Accept a JSON reading pushed directly by a device (e.g. via serial_bridge.py).
    Expects raw sensor values:
      {"light": 2048, "soil-moisture": 1024, "temp": 23.5, "ambient-humidity": 61.2}
    """
    from datetime import timezone
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found.")

    reading = Reading(
        device_id=device.id,
        timestamp=datetime.now(timezone.utc),
        payload=body,
        light=_adc_to_pct(body.get("light")),
        soil_moisture=_adc_to_pct(body.get("soil-moisture")),
        temp=body.get("temp"),
        ambient_humidity=body.get("ambient-humidity"),
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

    return reading


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Connect here to receive live sensor data as JSON whenever a new reading
    is fetched from any device.

    Example message:
    {
        "device": "esp32-livingroom",
        "timestamp": "2026-05-01T10:00:00+00:00",
        "data": {"temperature": 24.5, "humidity": 58}
    }
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; client can send pings if needed
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
