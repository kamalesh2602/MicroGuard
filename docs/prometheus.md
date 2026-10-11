# Prometheus Metrics & Monitoring Guide

## What is Prometheus and Why Do We Use It?

**Prometheus** is an open-source, time-series monitoring system and database. Unlike traditional logging systems that record text messages when events happen, Prometheus records **numerical metrics over time**.

In MicroGuard, Prometheus provides the telemetry backbone for:
- Monitoring request throughput across all microservices.
- Detecting error rate spikes (HTTP 5xx server errors).
- Monitoring the real-time state of Service A's circuit breaker (Closed, Open, Half-Open).
- Enabling Grafana to render live graphs and alert conditions.

---

## Metric Fundamentals: A Beginner Primer

### What is a Metric?
A **metric** is a numeric measurement recorded at a specific timestamp, uniquely identified by a metric name and optional key-value labels.
For example:
```text
http_requests_total{handler="/process", method="GET", status="2xx"} 2020.0
```
- **Metric Name:** `http_requests_total` (what is being measured).
- **Labels:** `{handler="/process", method="GET", status="2xx"}` (dimensional attributes that allow filtering and grouping).
- **Value:** `2020.0` (the recorded number).

### Metric Types in MicroGuard
1. **Counter:** A cumulative metric that only ever increases or resets to zero on restart (e.g., `http_requests_total`). Counters are used to calculate rates of events per second.
2. **Gauge:** A numerical value that can go up and down (e.g., memory usage, active connections, or `microguard_circuit_breaker_state`).
3. **Histogram:** Samples observations (typically request durations or latencies) and counts them into configurable buckets (e.g., `http_request_duration_seconds`).

### What is a Scrape?
Prometheus is a **pull-based** monitoring system. Instead of microservices sending metrics to Prometheus, Prometheus periodically sends an HTTP GET request to each service's `/metrics` endpoint to collect (or **scrape**) the current values of all exposed metrics.

---

## Scrape Configuration: `monitoring/prometheus.yml`

MicroGuard's Prometheus configuration is defined in [monitoring/prometheus.yml](../monitoring/prometheus.yml):

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: "gateway"
    metrics_path: /metrics
    static_configs:
      - targets: ["gateway:8000"]

  - job_name: "service_a"
    metrics_path: /metrics
    static_configs:
      - targets: ["service_a:8001"]

  - job_name: "service_b"
    metrics_path: /metrics
    static_configs:
      - targets: ["service_b:8002"]
```

### Configuration Breakdown
- **`global.scrape_interval: 5s`:** Prometheus scrapes every target every 5 seconds. In production systems, scrape intervals are typically 15s to 60s. We use 5s in MicroGuard so that rapid state changes during short load tests (such as a 10-second circuit breaker trip) appear on dashboards almost immediately.
- **`scrape_configs`:** Defines three scrape jobs named `gateway`, `service_a`, and `service_b`.
- **`targets`:** Uses Docker Compose internal hostnames (`gateway:8000`, `service_a:8001`, `service_b:8002`). Prometheus resolves these hostnames via Docker's embedded DNS.
- **`metrics_path: /metrics`:** The HTTP endpoint on each FastAPI service that outputs Prometheus text exposition format.

---

## Why Services Expose `/metrics`

Each FastAPI service initializes the `prometheus-fastapi-instrumentator` library at application startup:

```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="MicroGuard - API Gateway")
Instrumentator().instrument(app).expose(app)
```

This single line of code:
1. Adds ASGI middleware that intercepts all incoming requests to record response status codes, execution latencies, and payload sizes.
2. Exposes the `/metrics` endpoint serving all metrics in the standard Prometheus exposition format.

In addition, **Service A** defines a custom Prometheus gauge to expose its circuit breaker state:

```python
from prometheus_client import Gauge

circuit_state = Gauge(
    "microguard_circuit_breaker_state",
    "Circuit breaker state: 0=closed, 1=open, 2=half-open",
)
```

Whenever the circuit breaker changes state, its listener updates this gauge immediately.

---

## Actual Metrics Collected in MicroGuard

When scraping the services, Prometheus collects the following metrics:

### 1. HTTP Application Metrics (from `Instrumentator`)
- **`http_requests_total` (Counter):** Total requests handled, partitioned by `handler` (e.g. `/process`, `/metrics`), `method` (`GET`), and `status` (`2xx`, `5xx`).
- **`http_request_duration_seconds` (Histogram):** Latency distribution bucketed by handler and method (`le="0.1"`, `le="0.5"`, `le="1.0"`, `le="+Inf"`).
- **`http_request_duration_highr_seconds` (Histogram):** High-resolution latency histogram without API-specific labels, with granular buckets (`0.01s`, `0.025s`, `0.05s`, `0.1s`, etc.) designed for accurate percentile calculations.
- **`http_request_size_bytes` & `http_response_size_bytes` (Summary):** Payload sizes for incoming requests and outgoing responses.

### 2. Custom Fault-Tolerance Metric (from Service A)
- **`microguard_circuit_breaker_state` (Gauge):** Tracks the protective state of the circuit breaker:
  - `0`: **Closed** (healthy, requests pass to Service B).
  - `1`: **Open** (tripped, requests fail fast immediately).
  - `2`: **Half-Open** (testing recovery with a trial probe).

### 3. Python Runtime & Process Metrics
- **`process_cpu_seconds_total` (Counter):** Cumulative CPU time consumed by the service process.
- **`process_resident_memory_bytes` (Gauge):** Physical RAM occupied by the process.
- **`python_gc_objects_collected_total` (Counter):** Python garbage collection tracking.
- **`python_info` (Gauge):** Python version metadata (e.g., Python 3.12.15).

---

## Exploring the Prometheus Web UI

Prometheus includes a built-in web management interface accessible at:
👉 **`http://localhost:9090`**

### 1. Checking Scrape Target Health
1. In your browser, open `http://localhost:9090`.
2. Click on the top navigation bar: **Status ▾** → **Targets** (or navigate directly to `http://localhost:9090/targets`).
3. You should see three scrape pools:
   - `gateway (1/1 up)`
   - `service_a (1/1 up)`
   - `service_b (1/1 up)`
4. Each target should have a blue badge showing **State: UP**, indicating Prometheus is successfully scraping `/metrics` every 5 seconds.

### 2. Executing PromQL Queries
1. Click **Graph** in the top navigation bar.
2. In the **Expression** box, type any metric or PromQL query (e.g. `microguard_circuit_breaker_state`).
3. Click the **Execute** button.
4. Toggle between the **Table** tab (shows current value) and **Graph** tab (plots value over time).

---

## PromQL Queries Explained Piece by Piece

The queries configured in the MicroGuard Grafana dashboard are explained below:

### Query 1: Request Rate by Service
```promql
sum by (job) (
  rate(http_requests_total{handler!="/metrics"}[1m])
)
```
- `http_requests_total`: Selects the total request counter.
- `{handler!="/metrics"}`: Label filter that **excludes** Prometheus's own scrape requests from the count, so you only observe actual application traffic.
- `[1m]`: A range vector selector specifying a 1-minute rolling time window.
- `rate(...)`: Calculates the per-second average rate of increase over the 1-minute window.
- `sum by (job) (...)`: Aggregates the rates across different HTTP methods and status codes, grouping the output by the `job` label (`gateway`, `service_a`, `service_b`).
- **Result:** Throughput in requests per second (RPS) for each microservice.

---

### Query 2: HTTP 5xx Error Rate
```promql
sum by (job) (
  rate(http_requests_total{status=~"5..", handler!="/metrics"}[1m])
)
```
- `status=~"5.."`: Uses a regular expression match (`=~`) to capture any HTTP status code starting with `5` (e.g., `500 Internal Server Error`, `503 Service Unavailable`).
- `{handler!="/metrics"}`: Excludes Prometheus scrape requests.
- `[1m]`: 1-minute time window.
- `rate(...)`: Per-second rate of failing requests.
- `sum by (job)`: Groups failure rates by service name.
- **Result:** Error rate (errors/sec) per service. A spike indicates downstream failures or circuit breaker trips.

---

### Query 3: Circuit Breaker State
```promql
microguard_circuit_breaker_state
```
- **Type:** Gauge (instantaneous value).
- Because only Service A exposes this gauge, it returns a single time series with `job="service_a"`.
- Values:
  - `0` → Breaker is Closed (healthy).
  - `1` → Breaker is Open (failing fast).
  - `2` → Breaker is Half-Open (trial probe).

---

## How to Verify the Circuit Breaker State Metric

You can verify the metric dynamically using PowerShell:

### Step 1: Check Baseline State (Closed = 0)
```powershell
curl.exe -s "http://localhost:9090/api/v1/query?query=microguard_circuit_breaker_state"
```
The JSON response will show `"value": [timestamp, "0"]`.

### Step 2: Trip the Breaker (Open = 1)
Inject 100% failure in `docker-compose.yml` (`FAULT_ERROR_RATE: "1.0"`), recreate `service_b` (`docker compose up -d service_b`), and send 5 requests:
```powershell
1..5 | ForEach-Object { curl.exe -s http://localhost:8000/process }
```
Re-run the Prometheus query:
```powershell
curl.exe -s "http://localhost:9090/api/v1/query?query=microguard_circuit_breaker_state"
```
The value will now be `"1"`.

### Step 3: Observe Recovery (Half-Open = 2 → Closed = 0)
Restore `FAULT_ERROR_RATE: "0"`, restart Service B, wait 10 seconds for the cooldown timer, and send a single request:
```powershell
curl.exe -s http://localhost:8000/process
```
The breaker probes Service B, succeeds, and resets to `"0"`.

---

## Troubleshooting Guide

### Target Shows "DOWN" in Status -> Targets
1. **Container Stopped:** Run `docker compose ps` to check if `gateway`, `service_a`, or `service_b` has exited.
2. **Network Disconnection:** Ensure all services are on the same Compose bridge network.
3. **Port Misconfiguration:** Verify that `prometheus.yml` lists the internal container ports (`8000`, `8001`, `8002`), not host ports.
4. **Inspect Prometheus Logs:**
   ```powershell
   docker compose logs prometheus
   ```

### PromQL Query Returns "No Data"
1. **Traffic Has Not Been Sent:** Counters like `http_requests_total` only appear in memory after at least one request has hit the endpoint. Hit the endpoint once:
   ```powershell
   curl.exe -s http://localhost:8000/process
   ```
2. **Rate Window Insufficient:** The `rate(...[1m])` function requires at least two data points within the 1-minute window to calculate a derivative. Wait at least 10 seconds after sending requests before expecting `rate()` to show data.

---

## Related Documentation

- Architectural design: [Architecture Guide](architecture.md)
- Docker setup: [Docker Guide](docker.md)
- Visualizing metrics: [Grafana Dashboards](grafana.md)
- Load testing: [Locust Load Testing](locust.md)
- Circuit breaker mechanics: [Fault Tolerance & Circuit Breakers](fault-tolerance.md)
- Experiment results: [Load Test Experiments](experiments.md)
- Main project page: [Root README](../README.md)
