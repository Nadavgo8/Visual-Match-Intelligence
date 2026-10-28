import os
import re

os.environ["VMI_WARM_DEMO"] = "0"
os.environ["VMI_OFFLINE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from vmi.api.server import app  # noqa: E402


def test_product_is_named_visense_in_the_api_and_landing_page():
    assert app.title == "ViSense"
    page = TestClient(app).get("/").text
    assert "<title>ViSense</title>" in page
    heading = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S).group(1)
    assert re.sub(r"<[^>]+>", "", heading) == "ViSense"
    assert "visual match intelligence" not in page.lower()


def test_landing_page_joins_both_surfaces_through_one_labelled_room_code():
    page = TestClient(app).get("/").text
    assert re.search(r'<label for="room">', page) and 'id="room"' in page
    assert re.search(r'<a id="tv"[^>]*href="/tv\?room=', page)
    assert re.search(r'<a id="app"[^>]*href="/app\?room=', page)
    assert "document.getElementById(\"tv\").href = `/tv?room=${v}`" in page
    assert "document.getElementById(\"app\").href = `/app?room=${v}`" in page
