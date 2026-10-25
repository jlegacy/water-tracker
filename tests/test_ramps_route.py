from fastapi.testclient import TestClient
import main

def test_ramps_json_served():
    r = TestClient(main.app).get("/ramps_us.json")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "max-age" in r.headers.get("cache-control", "")
    assert len(r.json()["items"]) > 0
