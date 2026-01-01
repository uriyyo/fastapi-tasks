import threading
from typing import Any

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from fastapi_tasks import Tasks, add_tasks


def test_smoke() -> None:
    app = FastAPI()
    add_tasks(app)

    immediate_test = threading.Event()
    after_response_test = threading.Event()
    after_route_test = threading.Event()

    def task(_event: threading.Event) -> None:
        _event.set()

    @app.get("/")
    def endpoint(tasks: Tasks) -> dict[Any, Any]:
        tasks.schedule(task, immediate_test)
        tasks.after_response.schedule(task, after_response_test)
        tasks.after_route.schedule(task, after_route_test)

        return {}

    with TestClient(app) as client:
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {}

        immediate_test.wait()
        after_response_test.wait()
        after_route_test.wait()

        assert immediate_test.is_set()
        assert after_response_test.is_set()
        assert after_route_test.is_set()
