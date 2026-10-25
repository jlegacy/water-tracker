import asyncio, json
import main

def test_ramps_json_served():
    r = asyncio.run(main.ramps_us_json())
    assert r.media_type == "application/json"
    assert "max-age" in r.headers.get("cache-control", "")
    assert len(json.load(open(r.path))["items"]) > 0
    assert any(getattr(x, "path", None) == "/ramps_us.json" for x in main.app.routes)
