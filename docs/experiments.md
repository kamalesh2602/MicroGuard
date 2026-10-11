# Load Testing Experiments & Performance Analysis

## Overview

This document analyzes comparative load testing experiments conducted on the MicroGuard platform. We evaluate system behavior under two distinct conditions:
1. **Normal Operation:** Baseline load test with healthy microservices (`FAULT_ERROR_RATE: "0"`, `FAULT_DELAY_SECONDS: "0"`).
2. **Fault Injection:** Load test under downstream failure conditions (`FAULT_ERROR_RATE: "1.0"` on Service B).

The goal of this experiment is to observe how the **Circuit Breaker** on Service A alters request throughput, failure rates, and response time characteristics when a dependency becomes unavailable.

---

## Test Setup & Configuration

Both test runs were conducted using the containerized Locust service targeting the API Gateway:

- **Target URL:** `http://gateway:8000/process`
- **Workload Definition:** [locustfile.py](../locustfile.py)
- **Concurrent Users:** `10`
- **Spawn Rate:** `2` users per second
- **Wait Time Between Requests:** Random uniform between `0.5` and `1.5` seconds
- **Test Execution Environment:** Docker on Windows (Intel/AMD architecture, Linux containers)

---

## Test Scenarios

### Scenario A: Normal Operation
- **Service B Configuration:**
  ```yaml
  FAULT_DELAY_SECONDS: "0"
  FAULT_ERROR_RATE: "0"
  ```
- **Expected Behavior:** All requests travel end-to-end: Gateway → Service A → Service B → Service A → Gateway. Every request returns HTTP `200 OK`. The circuit breaker remains in the **Closed (0)** state.
- **Data Export:** Downloaded from Locust UI as `results/normal_load_stats.csv`.

### Scenario B: Fault Injection
- **Service B Configuration:**
  ```yaml
  FAULT_DELAY_SECONDS: "0"
  FAULT_ERROR_RATE: "1.0"
  ```
- **Expected Behavior:** The first 3 requests reach Service B, receive HTTP `500`, and trip Service A's circuit breaker to **Open (1)**. Subsequent requests fail fast inside Service A with `CircuitBreakerError`, returning HTTP `503 Service Unavailable`.
- **Data Export:** Downloaded from Locust UI as `results/fault_injection_stats.csv`.

---

## The Analysis Pipeline: `analyze_results.py`

MicroGuard provides an automated Pandas data processing script in [analyze_results.py](../analyze_results.py):

```python
import pandas as pd

normal = pd.read_csv("results/normal_load_stats.csv")
fault = pd.read_csv("results/fault_injection_stats.csv")


def get_stats(df, label):
    # Locust's statistics CSV contains an aggregated row.
    row = df[df["Name"] == "Aggregated"]

    if row.empty:
        row = df[df["Name"] == "/process"]

    row = row.iloc[0]

    total = row["Request Count"]
    failures = row["Failure Count"]

    return {
        "Test": label,
        "Requests": int(total),
        "Failures": int(failures),
        "Failure Rate (%)": round(
            failures / total * 100, 2
        ) if total else 0,
        "Average Latency (ms)": row["Average Response Time"],
        "Median Latency (ms)": row["Median Response Time"],
        "P95 Latency (ms)": row["95%"]
        if "95%" in row.index else row.get("95%ile (ms)", None),
        "Requests/sec": row["Requests/s"],
    }


comparison = pd.DataFrame([
    get_stats(normal, "Normal"),
    get_stats(fault, "Fault Injection"),
])

print("\nMicroGuard Load Test Comparison\n")
print(comparison.to_string(index=False))

comparison.to_csv("results/comparison_report.csv", index=False)
print("\nSaved: results/comparison_report.csv")
```

### How the Script Works
1. **Reads Raw CSVs:** Loads `results/normal_load_stats.csv` and `results/fault_injection_stats.csv`.
2. **Filters Aggregated Data:** Locates the summary row (`Name == "Aggregated"`) produced by Locust.
3. **Calculates Summary Metrics:** Computes the failure rate percentage, extracts latency percentiles, and normalizes column headers.
4. **Exports Report:** Prints the formatted comparison table to the terminal and saves it to [results/comparison_report.csv](../results/comparison_report.csv).

### How to Run the Analysis in Windows PowerShell
Run the script using the local virtual environment Python:
```powershell
.venv\Scripts\python.exe analyze_results.py
```
*(Alternatively, if Python or uv is available on your PATH: `python analyze_results.py` or `uv run analyze_results.py`).*

---

## Comparison Report Columns Explained

| Column Name | Unit | Explanation |
| :--- | :--- | :--- |
| **Test** | String | Name of the experimental condition (`Normal` vs `Fault Injection`). |
| **Requests** | Integer | Total number of HTTP requests issued by Locust during the test run. |
| **Failures** | Integer | Total count of requests that returned a non-200 HTTP status code. |
| **Failure Rate (%)** | Percent | Percentage of failing requests: `(Failures / Requests) * 100`. |
| **Average Latency (ms)** | Milliseconds | The mathematical mean response time across all processed requests. |
| **Median Latency (ms)** | Milliseconds | 50th percentile (P50) response time. Half of all requests were faster than this. |
| **P95 Latency (ms)** | Milliseconds | 95th percentile response time. Represents the threshold below which 95% of requests completed. |
| **Requests/sec** | Req/sec | System throughput (requests per second, RPS) achieved during the test run. |

---

## Observed Experimental Results

> [!NOTE]
> The numbers below represent **one observed test run** recorded in this repository. They are demonstration observations from local testing, not universal cloud production benchmarks.

### Comparison Table (`results/comparison_report.csv`)

| Test | Requests | Failures | Failure Rate (%) | Average Latency (ms) | Median Latency (ms) | P95 Latency (ms) | Requests/sec |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Normal** | 380 | 0 | 0.00% | 43.79 | 35 | 82 | 9.01 |
| **Fault Injection** | 484 | 458 | 94.63% | 35.76 | 21 | 77 | 9.37 |

---

## Detailed Data Interpretation

### 1. Failure Rate Dynamics
- **Normal Operation:** Produced **0 failures across 380 requests (0.0% failure rate)**. This confirms that under healthy baseline conditions, the three-tier chain handles 10 concurrent virtual users reliably with zero dropped requests.
- **Fault Injection:** Produced **458 failures across 484 requests (94.63% failure rate)**.
  - The remaining 26 successful requests occurred during initial startup before faults were introduced or during recovery trial probes when the breaker momentarily checked downstream status.
  - The overwhelming failure rate demonstrates that Service B's failure was successfully detected and isolated.

### 2. The Fast-Failure Phenomenon (Understanding Latency Changes)
Comparing the latency metrics reveals an important architectural insight:

| Latency Metric | Normal Operation | Fault Injection | Change |
| :--- | :--- | :--- | :--- |
| **Average Latency** | 43.79 ms | 35.76 ms | -18.3% |
| **Median Latency (P50)** | 35 ms | 21 ms | -40.0% |
| **P95 Latency** | 82 ms | 77 ms | -6.1% |

**Why did latency decrease during a failure scenario?**
- In **Normal Operation**, each request must execute the full synchronous chain: Gateway → Service A → Service B → Service A → Gateway. This involves two inter-container network round-trips over the bridge network, resulting in a median latency of **35 ms**.
- In **Fault Injection**, once the circuit breaker trips to **Open**, Service A **aborts the request immediately in memory** with `CircuitBreakerError` without initiating any network connection to Service B.
- Consequently, the median response time dropped to **21 ms**.

> [!CAUTION]
> **Do not confuse lower latency with better performance!**
> A median latency of 21 ms during fault injection does **not** indicate improved system performance. The requests were failing fast (`HTTP 503`), not doing useful work. Fast failure is valuable because it frees up system threads and connection buffers, but the service is still unavailable from the client's perspective.

### 3. Throughput (Requests Per Second)
- **Normal Operation:** ~9.01 requests/sec
- **Fault Injection:** ~9.37 requests/sec
- In both runs, throughput was bounded primarily by the Locust client configuration (10 users with `wait_time = between(0.5, 1.5)` seconds, yielding roughly 1 request per user per second).
- The slightly higher RPS during fault injection (~9.37 vs ~9.01) occurred because virtual users received instant 503 responses and entered their wait intervals faster.

---

## Limitations & Methodological Caveats

When evaluating these results, consider the following methodological boundaries:
1. **Different Total Request Counts:** The Normal test captured 380 requests, while the Fault Injection test captured 484 requests because the tests were manually stopped after slightly different run durations (~42 seconds vs ~52 seconds).
2. **Local Machine Variable Load:** Tests were executed locally on Windows with Docker Desktop sharing host CPU and memory with background OS tasks, rather than an isolated cloud benchmark environment.
3. **Absence of Fallback Responses:** In this implementation, the circuit breaker returns an HTTP 503 fast failure. In advanced production systems, an open circuit breaker often returns a cached fallback or degraded payload rather than an outright error.
4. **Single-Node Topology:** All containers ran on the same physical host machine. Network latency between containers reflects local loopback virtual switching, not real datacenter network hops.

---

## Related Documentation

- Architectural structure: [Architecture Guide](architecture.md)
- Docker configuration: [Docker Guide](docker.md)
- Prometheus metric definitions: [Prometheus Monitoring](prometheus.md)
- Grafana dashboard panels: [Grafana Dashboards](grafana.md)
- Load testing guide: [Locust Load Testing](locust.md)
- Circuit breaker mechanics: [Fault Tolerance & Circuit Breakers](fault-tolerance.md)
- Main project page: [Root README](../README.md)
