import asyncio, json
import main

def test_ramps_json_served():
    r = asyncio.run(main.ramps_us_json())
    assert r.media_type == "application/json"
    assert "max-age" in r.headers.get("cache-control", "")
    assert len(json.load(open(r.path))["items"]) > 0
    assert any(getattr(x, "path", None) == "/ramps_us.json" for x in main.app.routes)

def test_privacy_page_served():
    r = asyncio.run(main.privacy_page())
    assert r.media_type == "text/html"
    assert "Privacy Policy" in open(r.path).read()
