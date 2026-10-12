# MicroGuard Live Demo Steps

## 1. Start everything

Start all Docker Compose containers in detached mode:
```powershell
docker compose up -d
```

Verify that all 7 containers are running:
```powershell
docker compose ps
```

---

## 2. Show the application

Send an HTTP request to the microservices API Gateway:
- URL: `http://localhost:8000/process`
```powershell
curl.exe -s http://localhost:8000/process
```

Check the API Gateway health endpoint:
- URL: `http://localhost:8000/health`
```powershell
curl.exe -s http://localhost:8000/health
```

Send an identical request to the standalone Monolith baseline:
- URL: `http://localhost:8001/process`
```powershell
curl.exe -s http://localhost:8001/process
```

Check the Monolith baseline health endpoint:
- URL: `http://localhost:8001/health`
```powershell
curl.exe -s http://localhost:8001/health
```

---

## 3. Show monitoring

### Prometheus
- Prometheus UI: `http://localhost:9090`
- Scrape targets page: `http://localhost:9090/targets`
- PromQL graph editor: `http://localhost:9090/graph`

Query the circuit breaker state (0 = Closed, 1 = Open, 2 = Half-Open):
```text
microguard_circuit_breaker_state
```

Query per-service request rates in requests per second:
```text
sum by (job) (rate(http_requests_total{handler!="/metrics"}[1m]))
```

Query HTTP 5xx error rates across all services:
```text
sum by (job) (rate(http_requests_total{status=~"5..", handler!="/metrics"}[1m]))
```

### Grafana
- Grafana UI: `http://localhost:3000`
- Default login: Username `admin` | Password `admin`
- Existing dashboard to open: **MicroGuard Monitoring** (UID: `ad8bqjr`)

### Locust
- Locust web interface: `http://localhost:8089`

Run short test against the Microservices Gateway:
- Host: `http://gateway:8000`
- Number of users: `10`
- Spawn rate: `2`
- Click **Start swarming**, observe traffic for 15–30 seconds, then click **Stop**.

Run short test against the Monolith Baseline:
- Host: `http://monolith:8001`
- Number of users: `10`
- Spawn rate: `2`
- Click **Start swarming**, observe traffic for 15–30 seconds, then click **Stop**.

---

## 4. Show fault tolerance

Enable 100% failure rate on Service B and recreate the container:
```powershell
$env:FAULT_ERROR_RATE = "1.0"; docker compose up -d service_b
```

Send 5 requests to trip Service A's circuit breaker after 3 failures:
```powershell
1..5 | ForEach-Object { curl.exe -s http://localhost:8000/process }
```

Query Prometheus via PromQL to verify the breaker state has changed to Open (1):
```text
microguard_circuit_breaker_state
```

Optionally query Prometheus circuit breaker state directly from PowerShell:
```powershell
curl.exe -s "http://localhost:9090/api/v1/query?query=microguard_circuit_breaker_state"
```

Restore healthy configuration on Service B and recreate the container:
```powershell
$env:FAULT_ERROR_RATE = "0"; docker compose up -d service_b
```

Wait 10 seconds for the circuit breaker cooldown period to expire:
```powershell
Start-Sleep -Seconds 10
```

Send a probe request to trigger trial recovery and reset the breaker to Closed (0):
```powershell
curl.exe -s http://localhost:8000/process
```

Emergency recovery command if you need to abort or reset during demo:
```powershell
$env:FAULT_ERROR_RATE = "0"; Remove-Item Env:\FAULT_ERROR_RATE -ErrorAction SilentlyContinue; docker compose up -d --force-recreate service_b
```

---

## 5. Show benchmark results

Run an automated 30-second synchronized resource benchmark on the Monolith:
```powershell
powershell -ExecutionPolicy Bypass -File .\measure_resources.ps1 -DurationSeconds 30 -Target "monolith" -RunLocust
```

Run an automated 30-second synchronized resource benchmark on the Microservices:
```powershell
powershell -ExecutionPolicy Bypass -File .\measure_resources.ps1 -DurationSeconds 30 -Target "microservices" -RunLocust
```

List the newest generated resource timeseries CSV files:
```powershell
Get-ChildItem results/resource_usage_*.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 4 Name
```

Compare resource utilization using existing benchmark CSV files:
```powershell
.venv\Scripts\python.exe analyze_resources.py --monolith results/resource_usage_monolith_20261011_213219.csv --microservices results/resource_usage_microservices_20261011_213256.csv
```

List the newest generated Locust statistics CSV files:
```powershell
Get-ChildItem results/*_stats.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 4 Name
```

Compare architecture throughput and latency using existing Locust stats files:
```powershell
.venv\Scripts\python.exe analyze_results.py --monolith results/monolith_20261011_213219_stats.csv --microservices results/microservices_20261011_213256_stats.csv
```

Compare normal vs fault injection Locust load test runs:
```powershell
.venv\Scripts\python.exe analyze_results.py
```

---

## 6. Stop everything

Safely stop all containers while preserving Grafana dashboard volume data:
```powershell
docker compose down
```
