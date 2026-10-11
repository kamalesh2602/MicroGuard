# Grafana Dashboards & Visualization Guide

## What is Grafana and How Does It Differ From Prometheus?

While **Prometheus** acts as the metric collector and time-series database, **Grafana** is a specialized visualization, dashboarding, and analytics platform.

| Capability | Prometheus | Grafana |
| :--- | :--- | :--- |
| **Primary Role** | Metrics scraping, storage, and PromQL query evaluation | Data visualization, dashboard design, and user interaction |
| **Data Storage** | Stores raw time-series metrics on disk | Stores dashboard definitions, alerts, and user settings (not metric data) |
| **Interface** | Basic debugging UI with simple raw graphs | Rich, interactive, customizable production-grade dashboards |
| **Visual Types** | Basic lines and raw tables | Time series, Stat panels, Gauges, Heatmaps, Bar charts, Logs |

In MicroGuard, Prometheus collects telemetry from our three FastAPI services, and Grafana queries Prometheus to provide a unified, real-time command center.

---

## Connecting Grafana to Prometheus

Inside Docker Compose, Grafana runs as its own containerized service. When configuring the Prometheus connection in Grafana, you must use the **internal Docker network address**:

👉 **`http://prometheus:9090`**

> [!IMPORTANT]
> Do **not** use `http://localhost:9090` when configuring Prometheus inside Grafana!
> Inside the Grafana container, `localhost` points to the Grafana container itself. Using `http://prometheus:9090` allows Docker's internal DNS to route requests to the Prometheus container on port 9090.

---

## Accessing Grafana & Configuring the Data Source

### 1. Opening Grafana
1. Open your web browser and navigate to:
   👉 **`http://localhost:3000`**
2. Log in with the default credentials:
   - **Username:** `admin`
   - **Password:** `admin`
3. (Optional) Grafana will prompt you to change your password. You can set a new password or click **Skip**.

### 2. Verifying or Adding the Prometheus Data Source
If you are setting up or verifying the data source:
1. In the left navigation menu, click **Connections** (gear icon or plug icon) → **Data sources**.
2. Click **Add data source** and select **Prometheus**.
3. In the **Prometheus server URL** field, enter:
   ```text
   http://prometheus:9090
   ```
4. Scroll to the bottom and click **Save & test**.
5. You should see a green success banner: *"Successfully queried the Prometheus API."*

---

## The MicroGuard Monitoring Dashboard

MicroGuard includes a pre-configured dashboard titled **"MicroGuard Monitoring"** (Dashboard UID: `ad8bqjr`), organized into three dedicated monitoring panels:

```
+-----------------------------------+-----------------------------------+
|     Request Rate by Service       |       HTTP 5xx Error Rate         |
|     (Time Series - Lines)         |      (Time Series - Lines)        |
+-----------------------------------+-----------------------------------+
|                       Circuit Breaker State                           |
|                       (Stat Panel - Badge)                            |
+-----------------------------------------------------------------------+
```

---

## Panel Explanations & Actual PromQL Queries

### Panel 1: Request Rate by Service
- **Panel Title:** `Request Rate by Service`
- **Visualization Type:** `Time series`
- **PromQL Expression:**
  ```promql
  sum by (job) (
    rate(http_requests_total{handler!="/metrics"}[1m])
  )
  ```
- **What It Means:** Displays the incoming request volume (Requests Per Second, RPS) arriving at each microservice.
- **How to Read It:**
  - In normal operation, you will see lines for `gateway`, `service_a`, and `service_b` moving in sync (e.g., ~9-10 req/s during load testing).
  - When the circuit breaker opens, `gateway` and `service_a` traffic remain high, but `service_b` request rate drops to zero because Service A stops forwarding calls to Service B.

---

### Panel 2: HTTP 5xx Error Rate
- **Panel Title:** `HTTP 5xx Error Rate`
- **Visualization Type:** `Time series`
- **PromQL Expression:**
  ```promql
  sum by (job) (
    rate(http_requests_total{status=~"5..", handler!="/metrics"}[1m])
  )
  ```
- **What It Means:** Measures the rate of server-side error responses (`500 Internal Server Error` and `503 Service Unavailable`) per second across all services.
- **How to Read It:**
  - During normal operation, this graph remains flat at `0`.
  - During fault injection, errors immediately spike across all services as Service B throws 500s and upstream services return 503s.

---

### Panel 3: Circuit Breaker State
- **Panel Title:** `Circuit Breaker State`
- **Visualization Type:** `Stat`
- **Calculation / Reducer:** `Last *` or `lastNotNull`
- **PromQL Expression:**
  ```promql
  microguard_circuit_breaker_state
  ```
- **What It Means:** Renders a large, prominent status indicator showing the instantaneous state of Service A's circuit breaker protecting Service B.
- **Why It is a Gauge:** The state of a circuit breaker is not a cumulative counter; it is a current condition that shifts dynamically between Closed (0), Open (1), and Half-Open (2).

---

## How to Create or Edit Panels & Configure Value Mappings

If you wish to create a panel from scratch or customize an existing one:

### 1. Creating a Panel
1. Inside the dashboard, click **Add** (top right) → **Visualization**.
2. Select the **prometheus** data source.
3. Under the **Query** tab, switch to **Code** mode and enter the PromQL query.
4. On the right sidebar, choose the visualization type:
   - For throughput or error trends: Choose **Time series**.
   - For current status badges: Choose **Stat**.

### 2. Configuring Circuit Breaker Value Mappings
The numeric gauge values (`0`, `1`, `2`) are difficult for a human operator to interpret during an incident. Grafana allows you to map numbers to human-readable labels and colors:

1. In the right-hand panel settings sidebar, scroll down to the **Value mappings** section.
2. Click **Add value mappings** → **Add a new mapping**.
3. Choose condition: **Value**.
4. Configure the three mappings:
   - **Value:** `0` → **Display text:** `Closed` → **Color:** `Green`
   - **Value:** `1` → **Display text:** `Open` → **Color:** `Red`
   - **Value:** `2` → **Display text:** `Half-Open` → **Color:** `Yellow` / `Orange`
5. Click **Apply**.
6. Under **Stat styles**, set:
   - **Color mode:** `Background` or `Value`
   - **Graph mode:** `Area` or `None`
   - **Text mode:** `Auto` or `Value and name`
7. Click **Save** in the top right corner.

Now, whenever the breaker trips, the panel boldly flashes **Open** in red. When recovered, it displays **Closed** in green.

---

## Generating Traffic to Populate Dashboards

If no requests have been sent to the application, the graphs will appear flat or show "No data". To generate traffic:

### Option A: Run Locust (Recommended)
Follow the [Locust Guide](locust.md) to swarm the Gateway with 10 users. Graphs will immediately show throughput curves of ~9-10 req/s.

### Option B: Quick PowerShell Traffic Loop
Run this loop in Windows PowerShell to send 50 requests over 10 seconds:
```powershell
1..50 | ForEach-Object {
    curl.exe -s http://localhost:8000/process | Out-Null
    Start-Sleep -Milliseconds 200
}
```

---

## Grafana Persistence with Docker Named Volumes

In `docker-compose.yml`, Grafana is configured with a persistent volume:
```yaml
services:
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  grafana_data:
```

### Why This Matters
- Grafana stores all dashboard JSON files, user logins, data source connections, and preferences in an internal SQLite database at `/var/lib/grafana/grafana.db`.
- Because this path is mounted to the named volume `grafana_data`, your dashboards are **safe** across container reboots, updates, or `docker compose down`.
- If you run `docker compose down -v` (with the `-v` flag), Docker will delete all named volumes, wiping your custom Grafana dashboards and resetting Grafana to factory defaults.

---

## Troubleshooting Guide

### 1. Graphs Show "No Data"
- **Cause 1 (Time Range):** Check the time range selector in the top-right corner of Grafana. If it is set to `Last 6 hours` and you only ran a 30-second test, the data spike will appear as a tiny line. Set the range to **Last 5 minutes** or **Last 15 minutes**.
- **Cause 2 (No Traffic):** Prometheus rate calculations (`rate(...[1m])`) require at least two scrapes with active traffic. Send requests via Locust or curl.
- **Cause 3 (Data Source Disconnected):** Verify that the Prometheus container is reachable from Grafana by testing the data source under **Connections → Data sources**.

### 2. Panel Displays Raw Numbers Instead of "Closed" or "Open"
- **Cause:** Value mappings are missing or not enabled for the field.
- **Resolution:** Re-open the panel editor, ensure the three mappings (`0 = Closed`, `1 = Open`, `2 = Half-Open`) are defined under **Value mappings**, and click **Save**.

### 3. Error: `dial tcp: lookup prometheus on 127.0.0.11:53: no such host`
- **Cause:** The Prometheus container is not running or the service name in the data source URL is misspelled.
- **Resolution:** Ensure the URL is `http://prometheus:9090` and verify with `docker compose ps` that the Prometheus container is active.

---

## Related Documentation

- Architectural structure: [Architecture Guide](architecture.md)
- Container volume details: [Docker Guide](docker.md)
- Prometheus queries and metrics: [Prometheus Monitoring](prometheus.md)
- Load testing setup: [Locust Load Testing](locust.md)
- Circuit breaker theory: [Fault Tolerance & Circuit Breakers](fault-tolerance.md)
- Load testing results: [Load Test Experiments](experiments.md)
- Main project page: [Root README](../README.md)
