# Docker & Container Orchestration Guide

## What is Docker and Why Do We Use It?

**Docker** is a containerization platform that packages an application and all its required dependencies (code, runtime, system libraries, configuration) into a lightweight, standalone execution unit called a **container**.

In cloud and microservices engineering, Docker solves the classic problem: *"It works on my machine, but fails elsewhere."*
- **Environment Parity:** The exact same Python version (`3.12-slim`), virtual environment packages, and system libraries run identically on Windows, Linux, and cloud virtual machines.
- **Service Isolation:** Each microservice runs inside its own isolated process space and network namespace, preventing port conflicts and dependency collisions.
- **Predictable Deployment:** Starting the entire multi-service stack requires a single command rather than running multiple manual terminal commands.

---

## Core Container Concepts: Beginner Primer

### 1. Image vs Container
- **Image (Blueprint):** A read-only template that contains the operating system snapshot, application code, installed packages, and default startup instructions. Think of an image as a class in object-oriented programming or a recipe in a cookbook.
- **Container (Running Instance):** An active, running instance instantiated from an image. You can run multiple containers from a single image. A container has an isolated filesystem, CPU/memory allocation, and virtual network interface.

### 2. Dockerfile vs Docker Compose
- **Dockerfile:** A text file containing a step-by-step recipe to build a single Docker image. In MicroGuard, `Dockerfile` compiles the Python application image.
- **Docker Compose (`docker-compose.yml`):** A multi-container orchestration tool. While a Dockerfile defines *how to build an image*, Docker Compose defines *how multiple containers run together*, specifying services, open ports, environment variables, dependencies, and shared networks.

---

## The Shared Dockerfile Architecture

MicroGuard uses a shared build approach for its three Python services (`gateway`, `service_a`, `service_b`). Instead of creating three separate Dockerfiles, each service builds from the single root [Dockerfile](../Dockerfile):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project --python 3.12

COPY gateway ./gateway
COPY services ./services

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### How This Works in Docker Compose
1. **Dependency Layer Caching:** The image first installs `uv` (a high-performance Python package and project manager) and copies only `pyproject.toml` and `uv.lock`. `uv sync` resolves and installs all locked dependencies into `/app/.venv`. Docker caches this layer, so changing service source code does not trigger reinstallation of packages.
2. **Code Placement:** Both `./gateway` and `./services` directories are copied into `/app`.
3. **Execution Command Override:** In `docker-compose.yml`, each service overrides the default `CMD` with its specific Uvicorn entry point:
   - **`gateway`:** `uvicorn gateway.main:app --host 0.0.0.0 --port 8000`
   - **`service_a`:** `uvicorn services.service_a.main:app --host 0.0.0.0 --port 8001`
   - **`service_b`:** `uvicorn services.service_b.main:app --host 0.0.0.0 --port 8002`

Because all three services share the same dependencies (`fastapi`, `httpx`, `aiobreaker`, `prometheus-fastapi-instrumentator`), sharing the image eliminates redundant build steps and minimizes disk usage.

---

## Inter-Container Networking & Service Discovery

When you execute `docker compose up`, Docker Compose automatically provisions an isolated **user-defined bridge network** (named `microguard_default`).

### Automatic Service Discovery via Embedded DNS
Within this bridge network, Docker runs an embedded DNS resolver. Any container can resolve the network address of any sibling container simply by using the Compose service name as its hostname:
- `gateway` sends HTTP requests to `http://service_a:8001`
- `service_a` sends HTTP requests to `http://service_b:8002`
- `prometheus` scrapes metrics from `http://gateway:8000/metrics`, `http://service_a:8001/metrics`, and `http://service_b:8002/metrics`
- `grafana` queries Prometheus at `http://prometheus:9090`
- `locust` sends load traffic to `http://gateway:8000`

You do **not** use `localhost` or hardcoded IP addresses between containers. Inside a container, `localhost` refers exclusively to *that container itself*, not to other containers or your host computer.

---

## Host Ports vs Container Ports

In `docker-compose.yml`, you will notice two different port specifications:

### Published Ports (`ports: ["HOST:CONTAINER"]`)
When a service defines `ports: ["8000:8000"]`, Docker forwards incoming traffic on host port `8000` into container port `8000`:
- **`gateway` (`8000:8000`):** Accessible on your Windows machine at `http://localhost:8000`.
- **`prometheus` (`9090:9090`):** Accessible at `http://localhost:9090`.
- **`grafana` (`3000:3000`):** Accessible at `http://localhost:3000`.
- **`locust` (`8089:8089`):** Accessible at `http://localhost:8089`.

### Internal-Only Services (No Host Ports)
Notice that `service_a` and `service_b` do **not** declare a `ports:` section in `docker-compose.yml`:
- They listen on container ports `8001` and `8002` respectively.
- They are accessible to other containers on the bridge network via `service_a:8001` and `service_b:8002`.
- They are **not** directly accessible from your Windows host browser (`http://localhost:8001` will fail).
- **Why?** This enforces architectural security and encapsulation: internal microservices are protected from external access, forcing all client traffic through the API Gateway.

---

## Environment Variables & Configuration

Configuration is injected into containers at runtime via the `environment:` section in `docker-compose.yml`:

| Service | Variable | Value | Purpose |
| :--- | :--- | :--- | :--- |
| `gateway` | `SERVICE_A_URL` | `http://service_a:8001` | Tells the Gateway where to reach Service A |
| `service_a` | `SERVICE_B_URL` | `http://service_b:8002` | Tells Service A where to reach Service B |
| `service_b` | `FAULT_DELAY_SECONDS` | `"0"` | Artificial response latency in seconds |
| `service_b` | `FAULT_ERROR_RATE` | `"0"` | Probability of throwing HTTP 500 (`0` to `1.0`) |

---

## Grafana Named Volume (`grafana_data`)

At the bottom of `docker-compose.yml`, you will find:
```yaml
volumes:
  grafana_data:
```
And under the `grafana` service:
```yaml
volumes:
  - grafana_data:/var/lib/grafana
```

### Why Does This Exist?
Containers have an **ephemeral filesystem**. By default, when a container is removed (`docker compose down`), any files written inside the container (such as Grafana's internal SQLite database containing your created dashboards, users, and saved data sources) are deleted permanently.

A **Docker Named Volume** creates a persistent storage location managed by Docker on your host drive outside the container lifecycle. When Grafana restarts or the container is recreated, Docker re-mounts the `grafana_data` volume to `/var/lib/grafana`, preserving all your dashboards intact.

---

## Starting, Stopping, Restarting, Recreating, and Rebuilding

Understanding container lifecycle commands in Windows PowerShell:

| Action | PowerShell Command | What It Does |
| :--- | :--- | :--- |
| **Start / Up** | `docker compose up -d` | Creates and starts all containers in detached (background) mode. |
| **Stop** | `docker compose stop` | Pauses running containers without destroying them. State in memory is halted. |
| **Resume** | `docker compose start` | Resumes stopped containers without recreating them. |
| **Tear Down** | `docker compose down` | Stops and removes active containers, networks, and internal storage. Volumes are preserved. |
| **Tear Down with Volumes** | `docker compose down -v` | Stops containers and **destroys named volumes** (Warning: deletes saved Grafana dashboards). |
| **Restart Single Service** | `docker compose restart service_b` | Restarts a specific container process. |
| **Recreate Service** | `docker compose up -d service_b` | Re-reads `docker-compose.yml` (e.g. after changing env vars) and recreates only `service_b`. |
| **Rebuild Images** | `docker compose up -d --build` | Re-runs the `Dockerfile` build instructions to update code changes, then recreates containers. |

---

## Useful Windows PowerShell Commands

### Inspecting Running Services
```powershell
# List all running compose services with status and exposed ports
docker compose ps

# View resource usage (CPU %, Memory %, Network I/O)
docker stats
```

### Viewing Logs
```powershell
# Stream logs from all services in real time
docker compose logs -f

# Stream logs from only the API Gateway
docker compose logs -f gateway

# Stream logs from Service A to inspect circuit breaker logs
docker compose logs -f service_a

# View the last 50 log lines of Service B
docker compose logs --tail=50 service_b
```

### Container Health and Execution
```powershell
# Test Gateway connectivity from host PowerShell
curl.exe -s http://localhost:8000/health

# Execute an interactive shell inside a running container (Linux container)
docker compose exec gateway sh
```

---

## Troubleshooting Guide

### 1. Port Conflict (`Bind for 0.0.0.0:XXXX failed: port is already allocated`)
- **Symptom:** Docker fails to start a container because port `8000`, `9090`, `3000`, or `8089` is already in use by another application.
- **Diagnosis in PowerShell:**
  ```powershell
  Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Format-Table OwningProcess, LocalAddress, LocalPort, State
  ```
- **Resolution:** Terminate the conflicting process using its PID (`Stop-Process -Id <PID>`) or check if an older Docker container is still running (`docker ps`).

### 2. Service Crashes on Startup (`CrashLoopBackOff` or Exited Code 1)
- **Symptom:** `docker compose ps` shows a container with `State: Exited (1)`.
- **Diagnosis:** Run `docker compose logs <service-name>` to read the Python traceback.
- **Common Cause:** Missing dependency in `uv.lock` or syntax error in Python files. Rebuild with `docker compose up -d --build`.

### 3. Inter-Service Connection Refused (`httpx.ConnectError: [Errno 111]`)
- **Symptom:** The Gateway logs show connection errors when calling Service A.
- **Diagnosis:**
  1. Verify Service A is running: `docker compose ps service_a`.
  2. Verify the environment variable `SERVICE_A_URL` points to `http://service_a:8001`, not `http://localhost:8001`.
  3. Ensure both services are in the same network: `docker network inspect microguard_default`.

---

## Related Documentation

- Architectural overview: [Architecture Guide](architecture.md)
- Metric scraping details: [Prometheus Monitoring](prometheus.md)
- Visualizing dashboards: [Grafana Dashboards](grafana.md)
- Load testing: [Locust Load Testing](locust.md)
- Fault injection: [Fault Tolerance & Circuit Breakers](fault-tolerance.md)
- Load testing analysis: [Load Test Experiments](experiments.md)
- Main project page: [Root README](../README.md)
