"""
ORM models for the broker database.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Device(Base):
    """Represents a microcontroller / data source."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)       # e.g. "esp32-livingroom"
    url = Column(String, nullable=False)                     # polling endpoint
    poll_interval = Column(Integer, default=5)               # seconds
    config = Column(JSON, nullable=True, default=dict)       # device settings (automation thresholds, state, etc.)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    readings = relationship("Reading", back_populates="device",
                            cascade="all, delete-orphan")


class Reading(Base):
    """A single time-stamped snapshot of sensor data from a device."""
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    payload = Column(JSON, nullable=False)   # raw JSON from the microcontroller

    # Convenience columns — ADC values already converted to final units
    light = Column(Float, nullable=True)             # % (0–100)
    soil_moisture = Column(Float, nullable=True)     # % (0–100)
    temp = Column(Float, nullable=True)              # °C (-40–80)
    ambient_humidity = Column(Float, nullable=True)  # % (0–100)

    device = relationship("Device", back_populates="readings")
