# Resource Utilization Measurement Guide

## Overview

This guide details the reproducible resource-utilization measurement workflow implemented for the MicroGuard platform, designed to support empirical comparison between the **Monolithic Baseline** and the **Microservices Pipeline** in alignment with the research paper *Evaluating The Impact Of Cloud-Based Microservices Architecture On Application Performance*.

---

## Measurement Principles & Methodology

1. **Native Docker Statistics Engine:**
   - Resource metrics are collected directly via the Docker daemon using `docker stats --no-stream --format json`.
   - **Zero Added Overhead:** No external profiling agents, sidecars, or heavy APM libraries are injected into the benchmarked containers, preserving workload authenticity.

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
   - **Sampling Interval (`seconds`):** Default is `1s` to provide fine-grained timeseries resolution during benchmark swarms without imposing significant observer effect.

---

## Known Limitations & Considerations

1. **cgroups Memory Accounting:**
   - Docker reports memory from Linux control groups (`cgroups`). This value reflects resident set size (RSS), mapped memory, and internal Python memory arena allocations.
   - Python processes do not immediately return released memory back to the operating system after burst workloads.

2. **Windows WSL2 Virtualization Boundary:**
   - Under Docker Desktop on Windows, containers execute within a lightweight WSL 2 Linux VM. CPU utilization reflects the virtual CPU time allocated by the Hyper-V/WSL2 hypervisor.
   - Background Windows host activity does not directly affect container cgroup metrics, but host CPU throttling can introduce minor variance across runs.

3. **Sampling Resolution Trade-off:**
   - Sampling every 1 second accurately captures load surges and circuit breaker state changes while keeping `docker stats` query overhead below 0.1% CPU.

---

## The Measurement Tools

### 1. `measure_resources.ps1` (PowerShell Script)
The primary collection tool located at the repository root.

**Parameters:**
- `-DurationSeconds <int>`: Total measurement duration in seconds (default: `30`). Set to `0` to run indefinitely until `Ctrl+C`.
- `-IntervalSeconds <int>`: Pause duration between successive `docker stats` queries (default: `1`).
- `-Target <string>`: Tag identifying the benchmark run (`monolith`, `microservices`, or `all`).
- `-RunLocust`: Switch flag that automatically triggers a headless containerized Locust run during the measurement.
- `-LocustUsers <int>`: Simulated concurrent users (default: `10`).
- `-LocustSpawnRate <int>`: User spawn rate per second (default: `2`).
- `-OutputFile <string>`: Output path for the raw time-series CSV.
- `-SummaryFile <string>`: Output path for the statistical summary CSV.

### 2. `analyze_resources.py` (Pandas Analysis Script)
Located at the root of the project to analyze and compare generated CSV files.

**Usage Modes:**
- **Single Run Analysis:**
  ```powershell
  .venv\Scripts\python.exe analyze_resources.py results/resource_usage_monolith_<timestamp>.csv
  ```
- **Comparative Dual Run Analysis:**
  ```powershell
  .venv\Scripts\python.exe analyze_resources.py results/resource_usage_monolith_<timestamp>.csv results/resource_usage_microservices_<timestamp>.csv
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
Run a 30-second benchmark targeting the Monolith with automated resource sampling:
```powershell
powershell -ExecutionPolicy Bypass -File .\measure_resources.ps1 -DurationSeconds 30 -Target "monolith" -RunLocust
```

### Step 3: Measure Microservices Pipeline
Run a 30-second benchmark targeting the Microservices Gateway with identical user load:
```powershell
powershell -ExecutionPolicy Bypass -File .\measure_resources.ps1 -DurationSeconds 30 -Target "microservices" -RunLocust
```

### Step 4: Compare Results
Pass the two generated CSV files to `analyze_resources.py`:
```powershell
.venv\Scripts\python.exe analyze_resources.py results/resource_usage_monolith_<timestamp>.csv results/resource_usage_microservices_<timestamp>.csv
```

---

## Sample Experimental Output

```text
Comparing Monolith [results/resource_usage_monolith.csv] vs Microservices [results/resource_usage_microservices.csv]...

           Metric  Monolith Baseline  Microservices Combined  Delta (%)  Ratio (MS / Mono)
     Mean CPU (%)               0.57                    1.32      130.8               2.31
     Peak CPU (%)               1.19                    1.74       46.2               1.46
Mean Memory (MiB)              46.68                  149.59      220.5               3.20
Peak Memory (MiB)              46.85                  150.24      220.7               3.21

Saved comparison report to: results/resource_comparison_report.csv
```

### Interpretation:
1. **Memory Footprint:** The microservices architecture incurs an approximately **3.2x memory overhead** (~150 MiB vs ~47 MiB) due to hosting 3 isolated Python runtimes, ASGI server instances, and dependency trees.
2. **CPU Utilization:** Inter-service HTTP serialization and network socket handling generate a **2.3x CPU increase** relative to the monolith's in-process asynchronous function dispatch.
