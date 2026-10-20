
from fastapi import FastAPI
from datetime import datetime, timezone
from prometheus_fastapi_instrumentator import Instrumentator
import asyncio
import os

from fastapi import FastAPI, HTTPException


app = FastAPI(title="MicroGuard - Service B")
Instrumentator().instrument(app).expose(app)
FAULT_DELAY_SECONDS = float(os.getenv("FAULT_DELAY_SECONDS", "0"))
FAULT_ERROR_RATE = float(os.getenv("FAULT_ERROR_RATE", "0"))

@app.get("/")
def home():
    return {"service": "service-b", "status": "running"}


@app.get("/health")
def health():
    return {
        "service": "service-b",
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }




import random


@app.get("/process")
async def process():
    if FAULT_DELAY_SECONDS > 0:
        await asyncio.sleep(FAULT_DELAY_SECONDS)

    if FAULT_ERROR_RATE > 0 and random.random() < FAULT_ERROR_RATE:
        raise HTTPException(
            status_code=500,
            detail="Simulated failure in Service B"
        )

    return {
        "service": "service-b",
        "message": "Request processed successfully"
    }

