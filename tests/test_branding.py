import os

os.environ["VMI_WARM_DEMO"] = "0"
os.environ["VMI_OFFLINE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from vmi.api.server import app  # noqa: E402


def test_product_is_named_visense_in_the_api_and_landing_page():
    assert app.title == "ViSense"
    page = TestClient(app).get("/").text
    assert "<title>ViSense</title>" in page and "<h1>ViSense</h1>" in page
    assert "Visual Match Intelligence" not in page
