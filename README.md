# MicroGuard — Microservices Monitoring & Fault-Tolerance Platform

MicroGuard is a local-first microservices platform designed to demonstrate **fault tolerance**, **cascading failure prevention**, and **real-time observability** in distributed cloud architectures.

Built with Python (FastAPI), Docker Compose, Prometheus, Grafana, and Locust, MicroGuard illustrates how an upstream service uses the **Circuit Breaker** pattern to protect itself from an unstable downstream dependency, and how the entire system's health is monitored in real time.

---

## Architecture Overview

MicroGuard implements both a synchronous three-tier microservice pipeline and an equivalent **monolithic baseline** for empirical performance comparison:

```mermaid
flowchart LR
    Client(["Load Generator / Client\n(Locust / Browser)"]) -->|Port 8000| GW["API Gateway\n(FastAPI :8000)"]
    GW -->|Docker Network\nhttp://service_a:8001| SA["Service A\n(Circuit Breaker\nFastAPI :8001)"]
    SA -->|Docker Network\nhttp://service_b:8002| SB["Service B\n(Fault Injection Target\nFastAPI :8002)"]

    Client -.->|Port 8001 (Baseline)| MONO["Monolith Baseline\n(In-Process Execution\nFastAPI :8001)"]

    subgraph Observability ["Observability Stack"]
        PROM["Prometheus\n(Scraper :9090)"]
        GRAF["Grafana\n(Dashboard :3000)"]
        PROM -->|Scrape /metrics| GW
        PROM -->|Scrape /metrics| SA
        PROM -->|Scrape /metrics| SB
        PROM -->|Scrape /metrics| MONO
        GRAF -->|PromQL Queries| PROM
    end

    subgraph Testing ["Load Generation"]
        LOCUST["Locust\n(Web UI :8089)"]
        LOCUST -->|Target Gateway| GW
        LOCUST -.->|Target Monolith| MONO
    end
```

### Request Flow
1. **API Gateway (`gateway/main.py`):** Public entry point on host port `8000`. Receives client requests and forwards them to Service A via asynchronous HTTP (`httpx`).
2. **Service A (`services/service_a/main.py`):** Intermediate orchestrator on internal port `8001`. Protects calls to Service B with an `aiobreaker` Circuit Breaker (`fail_max=3`, `timeout_duration=10s`). Exposes the breaker state via a Prometheus gauge.
3. **Service B (`services/service_b/main.py`):** Leaf downstream dependency on internal port `8002`. Simulates backend work with configurable fault injection (`FAULT_DELAY_SECONDS`, `FAULT_ERROR_RATE`).
4. **Monolith Baseline (`monolith/main.py`):** Self-contained comparative baseline on host port `8001`. Executes Stage A and Stage B business logic directly in-process without network hops or circuit breakers, returning an equivalent response payload.
5. **Prometheus (`monitoring/prometheus.yml`):** Scrapes HTTP and system metrics from all services (Gateway, Service A, Service B, Monolith) every 5 seconds.
6. **Grafana:** Visualizes request throughput, HTTP 5xx errors, and the circuit breaker state in real time.
7. **Locust (`locustfile.py`):** Generates concurrent user traffic targeting either the Gateway or Monolith to evaluate comparative latency, throughput, and stability.

---

## Implemented Features

- **Microservices Pipeline:** Lightweight, asynchronous REST services built with FastAPI and Uvicorn.
- **Monolithic Baseline:** In-process reference architecture under `monolith/` for fair empirical benchmarking against distributed microservices.
- **Dual-Target Load Testing:** Configurable Locust test scenario capable of targeting either the Gateway (`:8000`) or Monolith (`:8001`) via CLI flag, environment variable, or Web UI.
- **Circuit Breaker Pattern:** Implemented in Service A using `aiobreaker`. Trips after 3 consecutive downstream failures (`fail_max=3`), remaining open for a 10-second cooldown (`timeout_duration=10s`).
- **Fast Failure Isolation:** When the circuit breaker is open, Service A fails fast within milliseconds with an HTTP `503`, preventing thread and connection starvation.
- **Full Observability Instrumentation:** Automated metrics exposure on `/metrics` across all services including the monolith using `prometheus-fastapi-instrumentator`.
- **Custom Circuit Breaker Telemetry:** Prometheus gauge metric `microguard_circuit_breaker_state` tracking state changes (0 = Closed, 1 = Open, 2 = Half-Open).
- **Interactive Grafana Dashboards:** Pre-configured dashboard featuring Request Rate by Service, HTTP 5xx Error Rate, and Circuit Breaker State with custom value mappings.
- **Configurable Fault Injection:** Adjust error rate (`FAULT_ERROR_RATE`) and latency (`FAULT_DELAY_SECONDS`) in Service B and the monolith via environment variables.
- **Containerized Load Testing:** Locust load test runs inside a Linux Docker container to bypass host Windows Application Control DLL restrictions.
- **Automated Experiment Analysis:** Python script (`analyze_results.py`) using Pandas to parse Locust CSV outputs and generate summary reports.
- **Interactive Grafana Dashboards:** Pre-configured dashboard featuring Request Rate by Service, HTTP 5xx Error Rate, and Circuit Breaker State with custom value mappings.
- **Configurable Fault Injection:** Adjust error rate (`FAULT_ERROR_RATE`) and latency (`FAULT_DELAY_SECONDS`) in Service B via environment variables.
- **Containerized Load Testing:** Locust load test runs inside a Linux Docker container to bypass host Windows Application Control DLL restrictions.
- **Automated Experiment Analysis:** Python script (`analyze_results.py`) using Pandas to parse Locust CSV outputs and generate summary reports.

---

## Technology Stack

| Technology | Role in MicroGuard |
| :--- | :--- |
| **Python 3.12** | Core programming language for all microservices and analysis scripts. |
| **FastAPI** | High-performance asynchronous web framework for REST API endpoints. |
| **Uvicorn** | ASGI web server hosting each FastAPI service. |
| **httpx** | Async HTTP client for inter-service communication with explicit timeouts. |
| **aiobreaker** | Async Circuit Breaker library providing state management (Closed, Open, Half-Open). |
| **Docker & Docker Compose** | Multi-container orchestration, internal bridge networking, and environment isolation. |
| **uv** | Modern Python package and environment manager used in image builds. |
| **Prometheus** | Time-series metrics engine scraping service `/metrics` endpoints every 5 seconds. |
| **Grafana** | Analytics platform providing real-time visual dashboards and status panels. |
| **Locust** | Load-testing tool defining simulated user traffic scenarios in Python. |
| **Pandas** | Data analysis library processing Locust CSV exports in `analyze_results.py`. |

---

## Repository Structure

```text
microguard/
├── Dockerfile                   # Shared multi-stage Python 3.12 container image build
├── docker-compose.yml           # Docker Compose orchestration for all services
├── pyproject.toml               # Python project configuration and dependencies
├── uv.lock                      # Exact locked dependency versions
├── analyze_results.py           # Pandas script comparing normal vs fault load tests
├── locustfile.py                # Locust load testing scenario definition
├── README.md                    # Project landing page and documentation hub
│
├── docs/                        # Complete technical documentation suite
│   ├── architecture.md          # System architecture, topology, and request lifecycle
│   ├── docker.md                # Docker guide, container networking, and commands
│   ├── prometheus.md            # Prometheus scraping, metrics, and PromQL queries
│   ├── grafana.md               # Grafana dashboards, panels, and value mappings
│   ├── locust.md                # Load testing guide, metrics glossary, and CSV exports
│   ├── fault-tolerance.md       # Circuit breaker mechanics, states, and fault injection
│   └── experiments.md           # Load test experimental results and data interpretation
│
├── gateway/
│   └── main.py                  # API Gateway service (Port 8000)
│
├── monolith/
│   ├── __init__.py              # Monolith package initialization
│   └── main.py                  # Standalone Monolith Baseline service (Port 8001)
│
├── services/
│   ├── service_a/
│   │   └── main.py              # Service A with aiobreaker circuit breaker (Port 8001)
│   └── service_b/
│       └── main.py              # Service B with simulated fault injection (Port 8002)
│
├── monitoring/
│   └── prometheus.yml           # Prometheus scrape jobs and target definitions
│
├── results/
│   ├── normal_load_stats.csv    # Locust export: Normal baseline test run
│   ├── fault_injection_stats.csv# Locust export: Fault-injected test run
│   └── comparison_report.csv    # Consolidated Pandas comparison output
│
├── tests/
│   ├── conftest.py              # Test configuration and pythonpath setup
│   ├── test_microservices.py    # Unit tests for microservices pipeline
│   └── test_monolith.py         # Unit tests for monolithic baseline
│
└── src/
    └── microguard/              # Python package metadata
        └── __init__.py
```

---

## Prerequisites

Before running MicroGuard locally, ensure you have:
1. **Windows 10 / 11** with PowerShell 5.1 or PowerShell 7.
2. **Docker Desktop for Windows** (with WSL 2 backend enabled and running).
3. **Python 3.12** (Optional, only needed to run `analyze_results.py` or `pytest` outside Docker).

---

## Quickstart Guide (Windows PowerShell)

### 1. Launch All Services with Docker Compose
Open Windows PowerShell in the project root directory and start the entire stack:

```powershell
docker compose up -d
```

Verify that all 7 containers are running:
```powershell
docker compose ps
```

You should see:
- `microguard-gateway-1` (Up, port `8000`)
- `microguard-monolith-1` (Up, port `8001`)
- `microguard-service_a-1` (Up, internal port `8001`)
- `microguard-service_b-1` (Up, internal port `8002`)
- `microguard-prometheus-1` (Up, port `9090`)
- `microguard-grafana-1` (Up, port `3000`)
- `microguard-locust-1` (Up, port `8089`)

---

## Local Service URLs

| Interface / Service | Local URL | Default Credentials / Notes |
| :--- | :--- | :--- |
| **API Gateway** | [http://localhost:8000](http://localhost:8000) | Public API ingress (`/`, `/health`, `/process`, `/metrics`) |
| **Monolith Baseline** | [http://localhost:8001](http://localhost:8001) | Standalone baseline (`/`, `/health`, `/process`, `/metrics`) |
| **Prometheus Web UI** | [http://localhost:9090](http://localhost:9090) | Scrape targets at `/targets`, PromQL query editor at `/graph` |
| **Grafana Dashboards** | [http://localhost:3000](http://localhost:3000) | Username: `admin` \| Password: `admin` |
| **Locust Load Tester** | [http://localhost:8089](http://localhost:8089) | Default target: `http://gateway:8000` (or `http://monolith:8001`) |

---

## How to Test the System

### Test 1: Verify Microservices Pipeline Operation
1. Send a request to the Gateway from PowerShell:
   ```powershell
   curl.exe -s http://localhost:8000/process
   ```
2. You will receive an HTTP 200 response confirming the end-to-end chain completed:
   ```json
   {
     "service": "service-a",
     "message": "Request completed through Service B",
     "dependency_response": {
       "service": "service-b",
       "message": "Request processed successfully"
     }
   }
   ```
3. Open Grafana at [http://localhost:3000](http://localhost:3000) to confirm the **Circuit Breaker State** displays **Closed** in green.

---

### Test 2: Verify Monolith Baseline Operation
1. Send requests to the Monolith on port `8001`:
   ```powershell
   # Health check
   curl.exe -s http://localhost:8001/health

   # Unified processing endpoint
   curl.exe -s http://localhost:8001/process
   ```
2. You will receive an equivalent HTTP 200 response with the exact same response schema, processed in-process:
   ```json
   {
     "service": "service-a",
     "message": "Request completed through Service B",
     "dependency_response": {
       "service": "service-b",
       "message": "Request processed successfully"
     }
   }
   ```
3. Inspect Prometheus metrics exposed by the monolith:
   ```powershell
   curl.exe -s http://localhost:8001/metrics
   ```

---

### Test 3: Inject Faults & Observe Circuit Breaker Trip (Microservices)
1. In `docker-compose.yml`, change `FAULT_ERROR_RATE` under `service_b` to `"1.0"`:
   ```yaml
   service_b:
     environment:
       FAULT_DELAY_SECONDS: "0"
       FAULT_ERROR_RATE: "1.0"
   ```
2. Recreate `service_b` in PowerShell:
   ```powershell
   docker compose up -d service_b
   ```
3. Send 5 requests:
   ```powershell
   1..5 | ForEach-Object { curl.exe -s http://localhost:8000/process }
   ```
4. **Observe:** The first 3 requests receive 500 from Service B. On the 3rd failure, the breaker trips to **Open**. Subsequent requests immediately return HTTP `503` fast failures.
5. In Grafana ([http://localhost:3000](http://localhost:3000)), watch the **Circuit Breaker State** panel flash **Open** in bright red.

---

### Test 4: Safe Restoration to Normal Operation
1. Reset `FAULT_ERROR_RATE` back to `"0"` in `docker-compose.yml`:
   ```yaml
   service_b:
     environment:
       FAULT_DELAY_SECONDS: "0"
       FAULT_ERROR_RATE: "0"
   ```
2. Recreate `service_b`:
   ```powershell
   docker compose up -d service_b
   ```
3. Wait **10 seconds** (the configured cooldown period).
4. Send a request to trigger the trial probe:
   ```powershell
   curl.exe -s http://localhost:8000/process
   ```
5. The request succeeds, and the circuit breaker resets to **Closed** (0).

---

### Test 5: Running Load Tests with Locust (Gateway vs. Monolith)

The Locust setup is designed to evaluate both architectures under identical workloads without maintaining duplicate scripts.

#### Option A: Interactive Web UI (Default)
1. Open Locust in your browser: [http://localhost:8089](http://localhost:8089).
2. Set **Host** to either:
   - Microservices Gateway: `http://gateway:8000`
   - Monolith Baseline: `http://monolith:8001`
3. Set **Number of users** to `10` and **Spawn rate** to `2`.
4. Click **Start swarming**.
5. Observe throughput and response times. The monolith exhibits significantly lower P95 latency due to zero network serialization hops.
6. Click **Stop** when finished and export statistics under **Download Data → Download request statistics CSV**.

#### Option B: Environment Variable Configuration
Reconfigure the containerized Locust target using `LOCUST_HOST`:
```powershell
# Target the Monolithic Baseline:
$env:LOCUST_HOST="http://monolith:8001"; docker compose up -d locust

# Switch back to the Microservices Gateway:
$env:LOCUST_HOST="http://gateway:8000"; docker compose up -d locust
```

#### Option C: Headless Benchmarks via Docker
Run fixed-duration comparative benchmarks directly from PowerShell:
```powershell
# Benchmark Monolith Baseline:
docker compose run --rm locust -f /mnt/locust/locustfile.py --host http://monolith:8001 --headless -u 10 -r 2 --run-time 30s --csv /mnt/locust/results/monolith_load

# Benchmark Microservices Gateway:
docker compose run --rm locust -f /mnt/locust/locustfile.py --host http://gateway:8000 --headless -u 10 -r 2 --run-time 30s --csv /mnt/locust/results/gateway_load
```

> [!NOTE]
> Locust is run inside Docker (`locustio/locust`) rather than directly on the Windows host machine to avoid security policy blocks on Windows C-extension DLLs required by `gevent`. If running Locust locally outside Docker, use `locust -f locustfile.py --host http://localhost:8001` or `--target-service monolith-local`.

---

### Test 5: Analyze Test Results with Pandas
Run the included analysis script in PowerShell:
```powershell
.venv\Scripts\python.exe analyze_results.py
```
*(or `python analyze_results.py`)*

Output:
```text
MicroGuard Load Test Comparison

           Test  Requests  Failures  Failure Rate (%)  Average Latency (ms)  Median Latency (ms)  P95 Latency (ms)  Requests/sec
         Normal       380         0              0.00             43.790278                   35                82      9.013171
Fault Injection       484       458             94.63             35.760761                   21                77      9.368385

Saved: results/comparison_report.csv
```

---

## Detailed Documentation Hub

For in-depth explanations, configuration breakdowns, and troubleshooting procedures, refer to the documentation suite in [`docs/`](docs/):

- 📖 [**Architecture & Request Lifecycle**](docs/architecture.md) — Detailed service topologies, API endpoints, and sequence diagrams.
- 🐳 [**Docker & Container Orchestration**](docs/docker.md) — Container fundamentals, Compose networking, named volumes, and PowerShell commands.
- 📈 [**Prometheus Metrics & Monitoring**](docs/prometheus.md) — Scrape configurations, metric types, and PromQL query walkthroughs.
- 📊 [**Grafana Dashboards & Visualizations**](docs/grafana.md) — Panel explanations, PromQL queries, value mappings, and persistence.
- 🦗 [**Locust Load Testing Guide**](docs/locust.md) — Load testing terminology, `locustfile.py` implementation, and Windows Docker setup.
- 🛡️ [**Fault Tolerance & Circuit Breakers**](docs/fault-tolerance.md) — `aiobreaker` mechanics, state transitions, and fault injection workflows.
- 🧪 [**Load Test Experiments & Analysis**](docs/experiments.md) — Experimental methodology, data analysis, and result interpretation.

---

## Known Limitations & Future Enhancements

The current implementation provides a local-first demonstration of fault-tolerance patterns. Planned future improvements include:

- [ ] **Retry Mechanisms with Jitter:** Adding intelligent retries with exponential backoff on transient network faults before tripping the circuit breaker.
- [ ] **Graceful Fallbacks:** Returning degraded or cached data instead of raw HTTP 503 errors when the circuit breaker is open.
- [ ] **Distributed Tracing:** Integrating OpenTelemetry with Jaeger or Zipkin to visualize request traces across service boundaries.
- [ ] **Database Integration:** Replacing in-memory simulation with a persistent datastore (e.g., PostgreSQL) and caching layer (e.g., Redis).
- [ ] **Container Orchestration:** Deploying on Kubernetes (K3s/Minikube) using Helm charts and declarative manifests.
- [ ] **Automated CI/CD:** Building automated testing pipelines with GitHub Actions.
- [ ] **Cloud Deployment:** Provisioning cloud infrastructure on AWS, GCP, or Azure.
