# MicroGuard — Microservices Monitoring & Fault-Tolerance Platform

MicroGuard is a local-first microservices platform designed to demonstrate **fault tolerance**, **cascading failure prevention**, and **real-time observability** in distributed cloud architectures.

Built with Python (FastAPI), Docker Compose, Prometheus, Grafana, and Locust, MicroGuard illustrates how an upstream service uses the **Circuit Breaker** pattern to protect itself from an unstable downstream dependency, and how the entire system's health is monitored in real time.

---

## Architecture Overview

MicroGuard implements both a synchronous three-tier microservice pipeline and an equivalent **monolithic baseline** for empirical performance comparison:

```mermaid
flowchart LR
    Client(["Load Generator / Client<br/>(Locust / Browser)"]) -->|"Port 8000"| GW["API Gateway<br/>(FastAPI :8000)"]
    GW -->|"Docker Network<br/>http://service_a:8001"| SA["Service A<br/>(Circuit Breaker<br/>FastAPI :8001)"]
    SA -->|"Docker Network<br/>http://service_b:8002"| SB["Service B<br/>(Fault Injection Target<br/>FastAPI :8002)"]

    Client -.->|"Port 8001 (Baseline)"| MONO["Monolith Baseline<br/>(In-Process Execution<br/>FastAPI :8001)"]

    subgraph Observability ["Observability Stack"]
        PROM["Prometheus<br/>(Scraper :9090)"]
        GRAF["Grafana<br/>(Dashboard :3000)"]
        PROM -->|"Scrape /metrics"| GW
        PROM -->|"Scrape /metrics"| SA
        PROM -->|"Scrape /metrics"| SB
        PROM -->|"Scrape /metrics"| MONO
        GRAF -->|"PromQL Queries"| PROM
    end

    subgraph Testing ["Load Generation"]
        LOCUST["Locust<br/>(Web UI :8089)"]
        LOCUST -->|"Target Gateway"| GW
        LOCUST -.->|"Target Monolith"| MONO
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
├── analyze_resources.py         # Pandas script comparing CPU and memory utilization
├── measure_resources.ps1        # PowerShell sampler collecting Docker stats during benchmarks
├── steps_for_demo.md            # Step-by-step copy-paste walkthrough for live demos
├── locustfile.py                # Locust load testing scenario definition
├── README.md                    # Project landing page and documentation hub
│
├── docs/                        # Complete technical documentation suite
│   ├── architecture.md          # System architecture, topology, and request lifecycle
│   ├── resource-utilization.md  # CPU and memory profiling guide and measurement units
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
│   ├── comparison_report.csv    # Consolidated Pandas comparison output
│   ├── resource_comparison_report.csv # Architecture CPU/memory comparison report
│   └── locust_architecture_report.csv # Architecture workload/latency comparison report
│
├── tests/
│   ├── conftest.py              # Test configuration and pythonpath setup
│   ├── test_microservices.py    # Unit tests for microservices pipeline
│   ├── test_monolith.py         # Unit tests for monolithic baseline
│   ├── test_analyze_results.py  # Unit tests for load test analysis pipeline
│   └── test_resource_measurement.py # Unit tests for resource profiling pipeline
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
1. Enable 100% failure rate on Service B and recreate the container in PowerShell:
   ```powershell
   $env:FAULT_ERROR_RATE = "1.0"; docker compose up -d service_b
   ```
   *(Alternatively, set `FAULT_ERROR_RATE: "1.0"` under `service_b` in `docker-compose.yml` and run `docker compose up -d service_b`).*
2. Send 5 requests through the Gateway:
   ```powershell
   1..5 | ForEach-Object { curl.exe -s http://localhost:8000/process }
   ```
3. **Observe:**
   - Requests 1–3: Service B returns HTTP 500 internal errors, Service A logs failures, and the Gateway returns HTTP `503` (`{"detail":"Backend service unavailable"}`).
   - On the 3rd failure (`fail_max=3`), Service A's circuit breaker trips to **Open**.
   - Requests 4 and 5: Service A fails fast immediately with `CircuitBreakerError` without reaching Service B, and the Gateway returns HTTP `503` in milliseconds.
4. Verify the circuit breaker state:
   - In Grafana ([http://localhost:3000](http://localhost:3000)), watch the **Circuit Breaker State** panel flash **Open** in bright red.
   - Or query Prometheus directly in PowerShell:
     ```powershell
     curl.exe -s "http://localhost:9090/api/v1/query?query=microguard_circuit_breaker_state"
     ```
     The query output will report `"value": [timestamp, "1"]`.

---

### Test 4: Safe Restoration to Normal Operation
1. Reset `FAULT_ERROR_RATE` back to `"0"` and recreate `service_b` in PowerShell:
   ```powershell
   $env:FAULT_ERROR_RATE = "0"; docker compose up -d service_b
   ```
   *(Alternatively, reset `FAULT_ERROR_RATE: ${FAULT_ERROR_RATE:-0}` in `docker-compose.yml` and run `docker compose up -d service_b`).*
2. Wait **10 seconds** (the configured cooldown period) for the circuit breaker to enter **Half-Open (2)**:
   ```powershell
   Start-Sleep -Seconds 10
   ```
3. Send a single probe request through the Gateway:
   ```powershell
   curl.exe -s http://localhost:8000/process
   ```
4. The request succeeds with HTTP 200, and the circuit breaker resets to **Closed** (0):
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
5. Confirm that the Prometheus metric has reset to `0`:
   ```powershell
   curl.exe -s "http://localhost:9090/api/v1/query?query=microguard_circuit_breaker_state"
   ```
   Grafana will show the panel return to **Closed** in green.

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

### Test 6: Analyze Test Results with Pandas
Run the included analysis script in PowerShell:
```powershell
.venv\Scripts\python.exe analyze_results.py
```
*(or `python analyze_results.py`)*

Output:
```text
MicroGuard Load Test Comparison

           Test  Requests  Failures  Failure Rate (%)  Average Latency (ms)  Median Latency (ms)  P95 Latency (ms)  Requests/sec
         Normal       380         0              0.00                 43.79                 35.0              82.0          9.01
Fault Injection       484       458             94.63                 35.76                 21.0              77.0          9.37

Saved report to: results/comparison_report.csv
```

---

### Test 7: Measure Resource Utilization (CPU & Memory Profiling)

MicroGuard includes a native Docker statistics collection script ([`measure_resources.ps1`](measure_resources.ps1)) and analysis pipeline ([`analyze_resources.py`](analyze_resources.py)) to evaluate resource efficiency without third-party APM overhead.

#### 1. Measure the Monolith Baseline
Run a 30-second benchmark targeting the Monolith while collecting 1-second `docker stats` samples:
```powershell
powershell -ExecutionPolicy Bypass -File .\measure_resources.ps1 -DurationSeconds 30 -Target "monolith" -RunLocust
```

#### 2. Measure the Microservices Pipeline
Run the identical 30-second benchmark workload targeting the Microservices Gateway:
```powershell
powershell -ExecutionPolicy Bypass -File .\measure_resources.ps1 -DurationSeconds 30 -Target "microservices" -RunLocust
```

#### 3. Compare Both Architecture Runs
Pass the generated CSV files (or the included benchmark sample files) to `analyze_resources.py` and `analyze_results.py`:
```powershell
# Resource comparison (CPU & Memory)
.venv\Scripts\python.exe analyze_resources.py --monolith results/resource_usage_monolith_20261011_213219.csv --microservices results/resource_usage_microservices_20261011_213256.csv

# Workload and latency comparison
.venv\Scripts\python.exe analyze_results.py --monolith results/monolith_20261011_213219_stats.csv --microservices results/microservices_20261011_213256_stats.csv
```

Outputs:

**Resource Utilization Summary (`analyze_resources.py`):**
```text
Comparing Monolith [results/resource_usage_monolith_20261011_213219.csv] vs Microservices [results/resource_usage_microservices_20261011_213256.csv]...

           Metric  Monolith Baseline  Microservices Combined  Delta (%)  Ratio (MS / Mono)
     Mean CPU (%)               2.35                   34.02     1349.9              14.50
     Peak CPU (%)               3.27                   45.09     1278.9              13.79
Mean Memory (MiB)              47.81                  152.33      218.6               3.19
Peak Memory (MiB)              48.04                  152.67      217.8               3.18

Saved comparison report to: results/resource_comparison_report.csv
```

**Workload & Latency Benchmark (`analyze_results.py`):**
```text
MicroGuard Architecture Benchmark: Monolith vs Microservices

                  Test  Requests  Failures  Failure Rate (%)  Average Latency (ms)  Median Latency (ms)  P95 Latency (ms)  Requests/sec
     Monolith Baseline       291         0               0.0                  4.60                  4.0               8.0         10.00
Microservices Pipeline       257         0               0.0                 55.26                 45.0             110.0          8.83

Saved report to: results/locust_architecture_report.csv
```

> [!NOTE]
> Application totals strictly measure the Monolith container against the sum of the Gateway, Service A, and Service B. Infrastructure containers (Prometheus, Grafana, and Locust) are reported separately and excluded from application totals.

---

### Test 8: Run Automated Unit Tests
Execute the full pytest test suite covering microservices, monolith baseline, circuit breaker behavior, and analysis pipelines:
```powershell
.venv\Scripts\python.exe -m pytest
```
*(or `python -m pytest`)*

> [!NOTE]
> On Windows environments with Application Control policies, invoking `python -m pytest` is recommended over calling `pytest.exe` directly.

Output:
```text
tests\test_analyze_results.py .....                                      [ 19%]
tests\test_microservices.py ...........                                  [ 61%]
tests\test_monolith.py .....                                             [ 80%]
tests\test_resource_measurement.py .....                                 [100%]
======================= 26 passed in 5.36s =======================
```

---

## Detailed Documentation Hub

For in-depth explanations, configuration breakdowns, and troubleshooting procedures, refer to the documentation suite in [`docs/`](docs/) and project guides:

- 🚀 [**Live Demo Quick-Reference**](steps_for_demo.md) — Step-by-step copy-paste command checklist for live demonstrations.

- 📖 [**Architecture & Request Lifecycle**](docs/architecture.md) — Detailed service topologies, API endpoints, and sequence diagrams.
- 📊 [**Resource Utilization Guide**](docs/resource-utilization.md) — CPU/memory measurement units, sampling methodology, and comparative analysis.
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
