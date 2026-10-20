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


def test_service_b_process_fault_injection(monkeypatch):
    monkeypatch.setattr(service_b_module, "FAULT_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(service_b_module, "FAULT_ERROR_RATE", 1.0)
    client = TestClient(service_b_app)
    res = client.get("/process")
    assert res.status_code == 500
    assert res.json()["detail"] == "Simulated failure in Service B"


def test_service_a_process_success():
    from unittest.mock import AsyncMock, patch
    import httpx
    from services.service_a.main import breaker

    breaker.close()
    req = httpx.Request("GET", "http://service_b:8002/process")
    mock_resp = httpx.Response(
        200,
        json={"service": "service-b", "message": "Request processed successfully"},
        request=req,
    )
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = TestClient(service_a_app)
        res = client.get("/process")
        assert res.status_code == 200
        data = res.json()
        assert data["service"] == "service-a"
        assert data["message"] == "Request completed through Service B"
        assert data["dependency_response"]["service"] == "service-b"


def test_service_a_process_circuit_breaker():
    from unittest.mock import AsyncMock, patch
    import httpx
    from services.service_a.main import breaker

    breaker.close()
    req = httpx.Request("GET", "http://service_b:8002/process")
    err_resp = httpx.Response(500, json={"detail": "Simulated failure in Service B"}, request=req)

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=err_resp):
        client = TestClient(service_a_app)
        # First 2 failures record HTTPStatusError while breaker remains closed
        for _ in range(2):
            res = client.get("/process")
            assert res.status_code == 503
            assert "HTTPStatusError" in res.json()["detail"]

        # 3rd failure reaches fail_max=3, tripping breaker to open (CircuitBreakerError)
        res3 = client.get("/process")
        assert res3.status_code == 503
        assert "CircuitBreakerError" in res3.json()["detail"]

        # Subsequent requests fail fast immediately
        res4 = client.get("/process")
        assert res4.status_code == 503
        assert "CircuitBreakerError" in res4.json()["detail"]

    breaker.close()


def test_gateway_process_success():
    from unittest.mock import AsyncMock, patch
    import httpx

    expected = {
        "service": "service-a",
        "message": "Request completed through Service B",
        "dependency_response": {
            "service": "service-b",
            "message": "Request processed successfully",
        },
    }
    req = httpx.Request("GET", "http://service_a:8001/process")
    mock_resp = httpx.Response(200, json=expected, request=req)

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
        client = TestClient(gateway_app)
        res = client.get("/process")
        assert res.status_code == 200
        assert res.json() == expected


def test_gateway_process_downstream_failure(caplog):
    import logging
    from unittest.mock import AsyncMock, patch
    import httpx

    req = httpx.Request("GET", "http://service_a:8001/process")
    err_resp = httpx.Response(503, json={"detail": "Service B unavailable"}, request=req)

    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=err_resp):
            client = TestClient(gateway_app)
            res = client.get("/process")
            assert res.status_code == 503
            assert res.json()["detail"] == "Backend service unavailable"
            assert "Downstream service returned error" in caplog.text


def test_gateway_process_downstream_connection_failure(caplog):
    import logging
    from unittest.mock import AsyncMock, patch
    import httpx

    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, side_effect=httpx.ConnectError("connection refused")):
            client = TestClient(gateway_app)
            res = client.get("/process")
            assert res.status_code == 503
            assert res.json()["detail"] == "Backend service unavailable"
            assert "Failed to reach downstream service" in caplog.text


def test_architectural_equivalence_monolith_and_microservices(monkeypatch):
    from monolith.main import app as monolith_app
    import monolith.main as monolith_module
    from unittest.mock import AsyncMock, patch
    import httpx

    monkeypatch.setattr(monolith_module, "FAULT_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(monolith_module, "FAULT_ERROR_RATE", 0.0)

    mono_client = TestClient(monolith_app)
    mono_res = mono_client.get("/process")
    assert mono_res.status_code == 200
    mono_data = mono_res.json()

    req = httpx.Request("GET", "http://service_a:8001/process")
    gw_resp = httpx.Response(200, json=mono_data, request=req)

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=gw_resp):
        gw_client = TestClient(gateway_app)
        gw_res = gw_client.get("/process")
        assert gw_res.status_code == 200
        assert gw_res.json() == mono_data

