"""
Periodic fetch scheduler.

- Uses APScheduler to poll every device on its configured interval.
- Stores each reading in the database.
- Broadcasts the latest reading to all connected WebSocket clients.
- Enforces MAX_READINGS_PER_DEVICE to prevent unbounded DB growth.
"""
import logging
from datetime import datetime, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from config import MC_TIMEOUT, MAX_READINGS_PER_DEVICE
from database import SessionLocal
from models import Device, Reading
from ws_manager import manager   # WebSocket connection manager

log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


# ── Core fetch logic ───────────────────────────────────────────────────────────

async def fetch_and_store(device_id: int):
    """Poll one device, persist the reading, and broadcast to WS clients."""
    db: Session = SessionLocal()
    try:
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            return

        try:
            async with httpx.AsyncClient(timeout=MC_TIMEOUT) as client:
                resp = await client.get(device.url)
                resp.raise_for_status()
                data: dict = resp.json()
        except Exception as exc:
            log.warning("Failed to fetch from device '%s': %s", device.name, exc)
            return

        # Convert raw ADC (0-4095) → percentage for light and soil-moisture
        def adc_to_pct(raw) -> float | None:
            if raw is None:
                return None
            return round(max(0.0, min(100.0, (float(raw) / 4095.0) * 100.0)), 2)

        reading = Reading(
            device_id=device.id,
            timestamp=datetime.now(timezone.utc),
            payload=data,
            light=adc_to_pct(data.get("light")),
            soil_moisture=adc_to_pct(data.get("soil-moisture")),
            temp=data.get("temp"),
            ambient_humidity=data.get("ambient-humidity"),
        )
        db.add(reading)
        db.commit()
        db.refresh(reading)

        # Enforce retention limit
        if MAX_READINGS_PER_DEVICE > 0:
            _prune_old_readings(db, device.id)

        # Push converted values to WebSocket subscribers
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

        log.info("Stored reading from '%s': %s", device.name, data)

    finally:
        db.close()


def _prune_old_readings(db: Session, device_id: int):
    """Delete oldest rows beyond the retention cap."""
    total = db.query(Reading).filter(Reading.device_id == device_id).count()
    excess = total - MAX_READINGS_PER_DEVICE
    if excess > 0:
        oldest_ids = (
            db.query(Reading.id)
            .filter(Reading.device_id == device_id)
            .order_by(Reading.timestamp.asc())
            .limit(excess)
            .all()
        )
        ids = [r.id for r in oldest_ids]
        db.query(Reading).filter(Reading.id.in_(ids)).delete(synchronize_session=False)
        db.commit()


# ── Scheduler management ───────────────────────────────────────────────────────

def schedule_device(device: Device):
    """Add (or replace) a polling job for a device."""
    job_id = f"poll_device_{device.id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        fetch_and_store,
        trigger="interval",
        seconds=device.poll_interval,
        id=job_id,
        args=[device.id],
        replace_existing=True,
    )
    log.info("Scheduled polling for '%s' every %ds", device.name, device.poll_interval)


def unschedule_device(device_id: int):
    """Remove the polling job for a device."""
    job_id = f"poll_device_{device_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def load_all_devices():
    """Called at startup to schedule every device already in the DB."""
    db: Session = SessionLocal()
    try:
        devices = db.query(Device).all()
        for device in devices:
            schedule_device(device)
    finally:
        db.close()
