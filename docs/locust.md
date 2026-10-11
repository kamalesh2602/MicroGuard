# Locust Load Testing Guide

## What is Load Testing and Why Do We Use Locust?

**Load testing** is the practice of simulating real-world concurrent user traffic against a software system to evaluate its performance, throughput, stability, and failure handling under pressure.

In MicroGuard, load testing serves two critical functions:
1. **Validating Baseline Capacity:** Measuring system response times and throughput when all microservices are healthy.
2. **Exercising Fault-Tolerance Mechanisms:** Simulating high traffic while faults are injected into downstream services to observe circuit breaker trips, fast failure response times, and system recovery.

**Locust** is an open-source, developer-friendly load-testing tool where test scenarios are written as plain Python code. Rather than configuring complex XML or clunky GUI scripts, you define user behavior using Python classes and tasks.

---

## Core Load Testing Concepts: Beginner Primer

| Metric / Term | Plain-English Definition |
| :--- | :--- |
| **Virtual Users (Users)** | The total number of simulated concurrent clients issuing requests to the system simultaneously. |
| **Spawn Rate** | The rate at which virtual users are started (e.g. 2 users/sec until reaching 10 users). |
| **Wait Time** | The pause duration a virtual user takes between finishing one request and starting the next (e.g. 0.5 to 1.5 seconds). Simulates human think time or client poll intervals. |
| **Requests Per Second (RPS / Throughput)** | The number of HTTP requests processed by the system **each second**. This is a rate of speed, like miles per hour on a speedometer. |
| **Total Requests** | The cumulative count of all HTTP requests processed across the **entire duration** of the test. Distinct from RPS! |
| **Failure Rate (%)** | The percentage of total requests that resulted in an unexpected response (e.g. HTTP 500 or 503): `(Failures / Total Requests) * 100`. |
| **Median Latency (50th percentile / P50)** | The middle response time: 50% of all requests completed faster than this time, and 50% completed slower. |
| **Average Latency (Mean)** | The arithmetic mean of all response times: `Sum of all latencies / Total requests`. |
| **P95 Latency (95th percentile)** | 95% of requests completed within this duration. In cloud engineering, P95 is favored over average latency because it exposes performance degradation experienced by the slowest 5% of users. |
| **P99 Latency (99th percentile)** | 99% of requests completed within this duration. Exposes extreme outliers (tail latency). |

---

## The MicroGuard Test Scenario: `locustfile.py`

MicroGuard's load test scenario is defined in [locustfile.py](../locustfile.py):

```python
from locust import HttpUser, task, between


class MicroGuardUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task
    def process_request(self):
        with self.client.get(
            "/process",
            name="/process",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"Unexpected status code: {response.status_code}"
                )
```

### Code Walkthrough
- **`HttpUser`:** The base class representing a virtual client making HTTP calls.
- **`wait_time = between(0.5, 1.5)`:** After completing a request, each user sleeps for a random interval between 0.5 and 1.5 seconds before sending another.
- **`@task`:** Declares `process_request` as the test workload executed by virtual users.
- **`self.client.get("/process", name="/process", catch_response=True)`:** Sends an HTTP `GET /process` request to the target host. Setting `catch_response=True` tells Locust not to automatically categorize HTTP 4xx/5xx responses as generic failures, allowing custom evaluation.
- **Evaluation Logic:**
  - If the status code is `200 OK`, Locust records `response.success()`.
  - If any other status code arrives (e.g. `503 Service Unavailable` when downstream fails or the breaker is open), Locust records `response.failure(...)` with the exact status code.

---

## Why Locust Runs in Docker on Windows

In `pyproject.toml`, `locust` is listed under the optional development dependencies:
```toml
[dependency-groups]
dev = [
    "locust>=2.46.7",
]
```
However, on this Windows environment, Locust is run **inside a Docker container** rather than directly in the host PowerShell shell.

### The Technical Reason: `gevent` DLL & Security Restrictions
Locust relies heavily on the `gevent` asynchronous concurrency library. `gevent` uses compiled C extensions (native Windows `.pyd` dynamic-link libraries) to implement greenlets and monkey-patching.

On managed Windows workstations (especially enterprise systems or those with Windows Defender Application Control / AppLocker policies enabled), loading un-whitelisted C-extension DLLs triggers security blocks such as:
```text
ImportError: DLL load failed while importing _core_exceptions: An application control policy has blocked this file.
```

### The Solution
By running Locust inside the official Linux container (`locustio/locust`):
1. All `gevent` and Python binaries run natively inside a Linux kernel where no Windows DLL restrictions apply.
2. The host only needs Docker Desktop running.
3. The load test script is mounted directly into the container from the host filesystem.

---

## Docker Compose Service Definition

In [docker-compose.yml](../docker-compose.yml), Locust is configured as follows:

```yaml
  locust:
    image: locustio/locust
    ports:
      - "8089:8089"
    volumes:
      - ./locustfile.py:/mnt/locust/locustfile.py:ro
    command: -f /mnt/locust/locustfile.py --host http://gateway:8000
    depends_on:
      - gateway
```

- **Image:** Uses the official `locustio/locust` image.
- **Volume Mount:** Mounts the host's `./locustfile.py` to `/mnt/locust/locustfile.py:ro` as read-only.
- **Command:** Tells Locust to execute `/mnt/locust/locustfile.py` with the default target host set to `http://gateway:8000` (resolving the Gateway container via Docker's internal network).
- **Port:** Maps host port `8089` to container port `8089`.

---

## Step-by-Step: Running a Load Test

### Step 1: Start Locust Container
To launch Locust alongside the MicroGuard platform, run in Windows PowerShell:
```powershell
docker compose up -d locust
```
(Or if all services were already started with `docker compose up -d`, Locust is already running).

### Step 2: Open the Locust Web Interface
Open your web browser and navigate to:
👉 **`http://localhost:8089`**

### Step 3: Configure and Start the Swarm
On the startup screen:
1. **Number of users:** Enter `10`
2. **Spawn rate:** Enter `2` (users per second)
3. **Host:** Verify that it displays `http://gateway:8000` (pre-filled by Compose)
4. Click **Start swarming**.

```
+-------------------------------------------------------+
|  Start new load test                                  |
|                                                       |
|  Number of users:  [ 10 ]                             |
|  Spawn rate:       [ 2  ]                             |
|  Host:             [ http://gateway:8000 ]            |
|                                                       |
|  [ Start swarming ]                                   |
+-------------------------------------------------------+
```

### Step 4: Monitor the Live Swarm
- Watch the **Statistics** table update in real time.
- Switch to the **Charts** tab to observe:
  - Total Requests per Second (RPS)
  - Response Times (95th percentile and median)
  - Number of Active Users (ramping from 0 to 10)
- Simultaneously view your **Grafana Dashboard** (`http://localhost:3000`) to observe how Prometheus tracks the same traffic.

### Step 5: Stop and Reset the Test
1. Click the red **Stop** button in the top right corner of the Locust UI when your desired test duration is reached (e.g. ~40-60 seconds).
2. To clear the live data before starting another run, click **New test** or click the **Reset stats** icon.

---

## Exporting Results to CSV for Analysis

Once a test has run and you have clicked **Stop**:
1. Click on the **Download Data** tab in the Locust navigation bar.
2. Locate the link labeled **Download request statistics CSV**.
3. Clicking this link downloads a file named `<prefix>_stats.csv`.
4. Move and rename this file into your MicroGuard `results/` directory:
   - For a baseline run: save as `results/normal_load_stats.csv`
   - For a fault-injected run: save as `results/fault_injection_stats.csv`

The directory structure will look like:
```text
microguard/
└── results/
    ├── normal_load_stats.csv
    ├── fault_injection_stats.csv
    └── comparison_report.csv
```

---

## Troubleshooting Guide

### 1. Locust Cannot Reach Gateway (`ConnectionRefusedError` or 100% Failures on Start)
- **Symptom:** In Locust UI, all requests fail immediately with connection errors.
- **Cause:** The **Host** field was set to `http://localhost:8000`. Inside the Locust container, `localhost:8000` points to Locust, not the Gateway!
- **Resolution:** Ensure the Host field is set to:
  ```text
  http://gateway:8000
  ```
  This routes traffic across the Docker bridge network to the Gateway container.

### 2. Locust UI Not Loading (`http://localhost:8089` Unreachable)
- **Diagnosis:** Run `docker compose ps locust`.
- **Resolution:**
  - If exited, inspect logs: `docker compose logs locust`.
  - Check if port 8089 is occupied by another process:
    ```powershell
    Get-NetTCPConnection -LocalPort 8089 -ErrorAction SilentlyContinue
    ```
  - Recreate the container: `docker compose up -d --force-recreate locust`.

---

## Related Documentation

- Architectural request flow: [Architecture Guide](architecture.md)
- Container orchestration: [Docker Guide](docker.md)
- Metric monitoring: [Prometheus Monitoring](prometheus.md)
- Real-time visualization: [Grafana Dashboards](grafana.md)
- Fault injection testing: [Fault Tolerance & Circuit Breakers](fault-tolerance.md)
- Comparison report & data analysis: [Load Test Experiments](experiments.md)
- Main project page: [Root README](../README.md)
