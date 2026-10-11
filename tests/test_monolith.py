import pytest
from starlette.testclient import TestClient
from monolith.main import app
import monolith.main as monolith_module


@pytest.fixture
def client():
    return TestClient(app)


def test_monolith_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "microguard-monolith"
    assert data["status"] == "running"


def test_monolith_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "microguard-monolith"
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_monolith_metrics(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    # Instrumentator provides Prometheus metrics text
    assert "http_requests" in response.text or "http_request_duration_seconds" in response.text or "process_cpu_seconds_total" in response.text or "# HELP" in response.text


def test_monolith_process_success(client, monkeypatch):
    monkeypatch.setattr(monolith_module, "FAULT_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(monolith_module, "FAULT_ERROR_RATE", 0.0)

    response = client.get("/process")
    assert response.status_code == 200
    data = response.json()

    assert data["service"] == "service-a"
    assert data["message"] == "Request completed through Service B"
    assert "dependency_response" in data

    dep = data["dependency_response"]
    assert dep["service"] == "service-b"
    assert dep["message"] == "Request processed successfully"


def test_monolith_process_fault_injection(client, monkeypatch):
    monkeypatch.setattr(monolith_module, "FAULT_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(monolith_module, "FAULT_ERROR_RATE", 1.0)

    response = client.get("/process")
    assert response.status_code == 500
    assert response.json()["detail"] == "Simulated failure in internal component B"
