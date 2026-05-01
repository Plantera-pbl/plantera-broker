"""
Broker server entry point.

Start with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging

from fastapi import FastAPI
from contextlib import asynccontextmanager

from config import API_HOST, API_PORT
from database import init_db
from scheduler import scheduler, load_all_devices
from routers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    init_db()                # create tables if they don't exist
    load_all_devices()       # schedule every device already in the DB
    scheduler.start()
    yield
    # ── Shutdown ───────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="IoT Broker",
    description="Periodically fetches sensor data from microcontrollers, "
                "stores it in a database, and streams it to client software.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")


# ── Run directly (optional) ────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
