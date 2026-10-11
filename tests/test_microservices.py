import pytest
from starlette.testclient import TestClient
from services.service_b.main import app as service_b_app
import services.service_b.main as service_b_module
from services.service_a.main import app as service_a_app
from gateway.main import app as gateway_app


def test_service_b_root_and_health():
    client = TestClient(service_b_app)
    r1 = client.get("/")
    assert r1.status_code == 200
    assert r1.json()["service"] == "service-b"

    r2 = client.get("/health")
    assert r2.status_code == 200
    assert r2.json()["service"] == "service-b"
    assert "timestamp" in r2.json()


def test_service_b_process_normal(monkeypatch):
    monkeypatch.setattr(service_b_module, "FAULT_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(service_b_module, "FAULT_ERROR_RATE", 0.0)
    client = TestClient(service_b_app)
    res = client.get("/process")
    assert res.status_code == 200
    assert res.json() == {
        "service": "service-b",
        "message": "Request processed successfully",
    }


def test_service_a_root_and_health():
    client = TestClient(service_a_app)
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200


def test_gateway_root_and_health():
    client = TestClient(gateway_app)
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
