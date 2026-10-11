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
