import asyncio
from datetime import datetime, timezone
import os
import random

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="MicroGuard - Monolithic Baseline")

Instrumentator().instrument(app).expose(app)

FAULT_DELAY_SECONDS = float(os.getenv("FAULT_DELAY_SECONDS", "0"))
FAULT_ERROR_RATE = float(os.getenv("FAULT_ERROR_RATE", "0"))


@app.get("/")
def home():
    return {"service": "microguard-monolith", "status": "running"}


@app.get("/health")
def health():
    return {
        "service": "microguard-monolith",
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _execute_stage_b() -> dict:
    """Internal reproduction of Service B business logic without network hops."""
    if FAULT_DELAY_SECONDS > 0:
        await asyncio.sleep(FAULT_DELAY_SECONDS)

    if FAULT_ERROR_RATE > 0 and random.random() < FAULT_ERROR_RATE:
        raise HTTPException(
            status_code=500,
            detail="Simulated failure in internal component B",
        )

    return {
        "service": "service-b",
        "message": "Request processed successfully",
    }


async def _execute_stage_a() -> dict:
    """Internal reproduction of Service A business logic without network hops.

    Per fair-comparison requirements, the monolith does not include a circuit
    breaker to artificially mimic distributed microservice fault handling.
    """
    dependency_response = await _execute_stage_b()
    return {
        "service": "service-a",
        "message": "Request completed through Service B",
        "dependency_response": dependency_response,
    }


@app.get("/process")
async def process():
    """Unified request pipeline executing the operations in-process.

    Executes Stage A and Stage B directly within the same event loop,
    eliminating HTTP serialization, connection pooling, and network transport.
    """
    return await _execute_stage_a()
