
import os
from datetime import timedelta

import httpx
from aiobreaker import CircuitBreaker, CircuitBreakerListener
from fastapi import FastAPI, HTTPException
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator


app = FastAPI(title="MicroGuard - Service A")

Instrumentator().instrument(app).expose(app)

SERVICE_B_URL = os.getenv(
    "SERVICE_B_URL",
    "http://127.0.0.1:8002",
)

circuit_state = Gauge(
    "microguard_circuit_breaker_state",
    "Circuit breaker state: 0=closed, 1=open, 2=half-open",
)


class CircuitStateMetrics(CircuitBreakerListener):
    def state_change(self, breaker, old, new):
        state = str(new).lower()

        if "half" in state:
            circuit_state.set(2)
        elif "open" in state:
            circuit_state.set(1)
        else:
            circuit_state.set(0)


breaker = CircuitBreaker(
    fail_max=3,
    timeout_duration=timedelta(seconds=10),
)

breaker.add_listener(CircuitStateMetrics())
circuit_state.set(0)


@app.get("/")
def home():
    return {"service": "service-a", "status": "running"}


@app.get("/health")
def health():
    return {"service": "service-a", "status": "healthy"}


async def call_service_b():
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.get(f"{SERVICE_B_URL}/process")
        response.raise_for_status()
        return response.json()


@app.get("/process")
async def process():
    try:
        dependency_response = await breaker.call_async(call_service_b)

        return {
            "service": "service-a",
            "message": "Request completed through Service B",
            "dependency_response": dependency_response,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Service B unavailable or circuit breaker open: "
                f"{type(exc).__name__}"
            ),
        )
