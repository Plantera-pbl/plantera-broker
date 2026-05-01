"""
Broker server entry point.

Start with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import API_HOST, API_PORT
from database import init_db
from scheduler import scheduler, load_all_devices
from routers import router
from config import MQTT_ENABLED

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    init_db()
    load_all_devices()
    scheduler.start()
    if MQTT_ENABLED:
        import mqtt_client
        mqtt_client.start(asyncio.get_running_loop())
    yield
    # ── Shutdown ───────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    if MQTT_ENABLED:
        import mqtt_client
        mqtt_client.stop()


app = FastAPI(
    title="IoT Broker",
    description="Periodically fetches sensor data from microcontrollers, "
                "stores it in a database, and streams it to client software.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow requests from the local web app (opened as file:// or any origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


# ── Run directly (optional) ────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
