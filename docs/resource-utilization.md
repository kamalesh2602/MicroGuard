# Resource Utilization Measurement Guide

## Overview

This guide details the reproducible resource-utilization measurement workflow implemented for the MicroGuard platform, designed to support empirical comparison between the **Monolithic Baseline** and the **Microservices Pipeline** in alignment with the research paper *Evaluating The Impact Of Cloud-Based Microservices Architecture On Application Performance*.

---

## Measurement Principles & Methodology

1. **Native Docker Statistics Engine:**
   - Resource metrics are collected directly via the Docker daemon using `docker stats --no-stream --format json`.
   - **Non-Invasive Out-of-Band Sampling:** No external profiling agents, sidecars, or invasive bytecode hooks are injected into the benchmarked application containers, avoiding intra-process execution distortion.

2. **Architectural Scope Separation:**
   - **Monolith Baseline:** Exactly one container (`microguard-monolith-1`).
   - **Microservices Deployment:** The combined sum of all three application tier containers:
     - API Gateway (`microguard-gateway-1`)
     - Service A (`microguard-service_a-1`)
     - Service B (`microguard-service_b-1`)
   - **Infrastructure Tiers (Strictly Separated):** Prometheus (`microguard-prometheus-1`), Grafana (`microguard-grafana-1`), and Locust (`microguard-locust-1`) are monitored and recorded, but **never added** to application resource totals.

3. **Measurement Units:**
   - **CPU Usage (`%`):** Expressed as a percentage of a single logical CPU core. For example, `100.0%` represents full saturation of one CPU thread. In multi-container microservice deployments, combined CPU is the arithmetic sum of the three container CPU percentages.
   - **Memory Usage (`MiB`):** Converted to standard Mebibytes ($1\text{ MiB} = 1,048,576\text{ bytes}$) from Docker's raw memory strings (`MiB`, `GiB`, `kB`, `B`). Combined microservices memory is the arithmetic sum of the three container memory footprints.
   - **Sampling Interval (`seconds`):** Default is `1s` to provide fine-grained timeseries resolution during benchmark swarms without placing heavy load on the Docker daemon.

---

## Known Limitations & Considerations

1. **cgroups Memory Accounting:**
   - Docker reports memory from Linux control groups (`cgroups`). This value reflects resident set size (RSS), mapped memory, and internal Python memory arena allocations.
   - Python processes do not immediately return released memory back to the operating system after burst workloads.

2. **Windows WSL2 Virtualization Boundary:**
   - Under Docker Desktop on Windows, containers execute within a lightweight WSL 2 Linux VM. CPU utilization reflects the virtual CPU time allocated by the Hyper-V/WSL2 hypervisor.
   - Background Windows host activity does not directly affect container cgroup metrics, but host CPU throttling can introduce minor variance across runs.

3. **Sampling Resolution & Observer Considerations:**
   - Sampling every 1 second accurately captures load surges and circuit breaker state changes.
   - Metrics collection runs out-of-band against the Docker daemon engine. The observer cost of polling container statistics is borne by the host Docker daemon process and PowerShell caller rather than within the container cgroup limits. However, observer overhead is non-zero on the host machine and depends on hardware capabilities, WSL2 CPU allocation, and the number of active containers.

---

## The Measurement Tools

### 1. `measure_resources.ps1` (PowerShell Script)
The primary collection tool located at the repository root.

**Parameters:**
- `-DurationSeconds <int>`: Total measurement duration in seconds (default: `30`). Set to `0` to run indefinitely until `Ctrl+C` (in standalone mode). When `-RunLocust` is enabled, this configures the Locust load duration (`--run-time`).
- `-IntervalSeconds <int>`: Pause duration between successive `docker stats` queries (default: `1`).
- `-Target <string>`: Architecture or workload label (`monolith`, `microservices`, or `all`). When `-RunLocust` is enabled, must be either `monolith` or `microservices`.
- `-RunLocust`: Switch flag that automatically launches a headless containerized Locust load test synchronized with the resource sampling.
- `-LocustUsers <int>`: Simulated concurrent users (default: `10`).
- `-LocustSpawnRate <int>`: User spawn rate per second (default: `2`).
- `-OutputFile <string>`: Output path for the raw time-series CSV (defaults to `results/resource_usage_<Target>_<Timestamp>.csv`).
- `-SummaryFile <string>`: Output path for the statistical summary CSV (defaults to `results/resource_summary_<Target>_<Timestamp>.csv`).

**Locust Benchmark Synchronization Lifecycle:**
When `-RunLocust` is specified, `measure_resources.ps1` enforces strict synchronization with the workload lifecycle:
1. **Dynamic Target Routing:** Maps `-Target monolith` to `http://monolith:8001` and `-Target microservices` to `http://gateway:8000`.
2. **Pre-Sampling Readiness Wait:** Launches a detached headless Locust runner container (`docker compose run -d ...`) with `-v ./results:/mnt/locust/results` and polls `docker inspect` until the container reaches `State.Status == "running"`. Sampling only begins once Locust is actively running, preventing idle pre-test intervals from skewing baseline averages.
3. **Execution Interval Alignment:** The resource sampling loop continues while `State.Running == "true"` and terminates immediately when Locust finishes, ensuring the sampled window precisely covers the active load test.
4. **Exit Code Validation:** The script inspects `State.ExitCode`. If non-zero, it displays the container logs, emits a terminal error, and aborts with a non-zero exit code so that failed tests are never reported as valid benchmarks.
5. **Non-destructive Outputs:** Each run saves to timestamped files, ensuring prior benchmark CSVs are never overwritten.

### 2. `analyze_resources.py` (Pandas Analysis Script)
Located at the root of the project to analyze and compare generated CSV files.

**Usage Modes:**
- **Single Run Analysis:**
  ```powershell
  .venv\Scripts\python.exe analyze_resources.py results/resource_usage_monolith_<timestamp>.csv
  ```
- **Comparative Dual Run Analysis (Positional or Named Flags):**
  ```powershell
  # Using positional arguments
  .venv\Scripts\python.exe analyze_resources.py results/resource_usage_monolith_<timestamp>.csv results/resource_usage_microservices_<timestamp>.csv

  # Using named flags
  .venv\Scripts\python.exe analyze_resources.py --monolith results/resource_usage_monolith_<timestamp>.csv --microservices results/resource_usage_microservices_<timestamp>.csv
  ```

---

## Step-by-Step Benchmark Workflow

To conduct a fair and reproducible comparative evaluation, execute the tests under identical parameters:

### Step 1: Ensure All Containers Are Running
```powershell
docker compose up -d
docker compose ps
```

### Step 2: Measure Monolithic Baseline
Run a 30-second benchmark targeting the Monolith (`http://monolith:8001`) with automated resource sampling:
```powershell
powershell -ExecutionPolicy Bypass -File .\measure_resources.ps1 -DurationSeconds 30 -Target "monolith" -RunLocust
```

### Step 3: Measure Microservices Pipeline
Run a 30-second benchmark targeting the Microservices Gateway (`http://gateway:8000`) with identical user load:
```powershell
powershell -ExecutionPolicy Bypass -File .\measure_resources.ps1 -DurationSeconds 30 -Target "microservices" -RunLocust
```

### Step 4: Compare Results
Pass the two generated CSV files to `analyze_resources.py`:
```powershell
.venv\Scripts\python.exe analyze_resources.py --monolith results/resource_usage_monolith_<timestamp>.csv --microservices results/resource_usage_microservices_<timestamp>.csv
```

---

## Sample Experimental Output

```text
Comparing Monolith [results/resource_usage_monolith_20261011_212300.csv] vs Microservices [results/resource_usage_microservices_20261011_212333.csv]...

           Metric  Monolith Baseline  Microservices Combined  Delta (%)  Ratio (MS / Mono)
     Mean CPU (%)               2.10                   36.42     1636.5              17.36
     Peak CPU (%)               2.96                   73.81     2393.6              24.94
Mean Memory (MiB)              47.29                  151.13      219.6               3.20
Peak Memory (MiB)              47.65                  152.37      219.8               3.20

Saved comparison report to: results/resource_comparison_report.csv
```

### Interpretation:
1. **Memory Footprint:** The microservices architecture incurs an approximately **3.2x memory overhead** (~151 MiB vs ~47 MiB) due to hosting 3 isolated Python runtimes, ASGI server instances, and dependency trees.
2. **CPU Utilization:** Inter-service HTTP serialization, networking, and multi-tier routing generate higher aggregate CPU utilization relative to the monolith's in-process asynchronous function dispatch.

