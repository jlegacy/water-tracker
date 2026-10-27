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
    body = open(r.path).read()
    assert "Privacy Policy" in body
    assert "October 27, 2026" in body
    assert "50 miles" in body
    assert "IndexedDB" in body
    assert "Delete my trails" in body
    assert "does not currently send push notifications" in body
    assert "PLACEHOLDER" in body  # contact / legal name still need owner input
    assert "display-only" in body
    assert "Premium" in body
