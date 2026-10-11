import os
from locust import HttpUser, task, between, events

# Target service URL mapping for convenience
SERVICE_TARGETS = {
    "gateway": "http://gateway:8000",
    "microservices": "http://gateway:8000",
    "monolith": "http://monolith:8001",
    "gateway-local": "http://localhost:8000",
    "monolith-local": "http://localhost:8001",
}


@events.init_command_line_parser.add_listener
def init_parser(parser):
    parser.add_argument(
        "--target-service",
        type=str,
        env_var="TARGET_SERVICE",
        default="",
        help="Target service shorthand ('gateway', 'monolith', 'gateway-local', 'monolith-local')",
    )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    target_svc = getattr(environment.parsed_options, "target_service", None)
    if not target_svc:
        target_svc = os.getenv("TARGET_SERVICE", "")

    if target_svc:
        cleaned = target_svc.lower().strip()
        if cleaned in SERVICE_TARGETS:
            environment.host = SERVICE_TARGETS[cleaned]


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
