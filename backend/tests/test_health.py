from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db"] == "ok"
    assert body["postgis"]


def test_unknown_route(client: TestClient) -> None:
    response = client.get("/v1/nope")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found"}
    assert "Traceback" not in response.text
