
import logging
import os

import httpx
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="MicroGuard - API Gateway")

Instrumentator().instrument(app).expose(app)

SERVICE_A_URL = os.getenv("SERVICE_A_URL", "http://127.0.0.1:8001")


@app.get("/")
def home():
    return {"service": "microguard-gateway", "status": "running"}


@app.get("/health")
def health():
    return {"service": "microguard-gateway", "status": "healthy"}


@app.get("/process")
async def process():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{SERVICE_A_URL}/process")
            response.raise_for_status()

        return response.json()

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Downstream service returned error: status=%s, url=%s/process, detail=%s",
            exc.response.status_code,
            SERVICE_A_URL,
            exc.response.text,
        )
        raise HTTPException(
            status_code=503,
            detail="Backend service unavailable",
        )
    except httpx.RequestError as exc:
        logger.error(
            "Failed to reach downstream service at %s/process: %s",
            SERVICE_A_URL,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Backend service unavailable",
        )
