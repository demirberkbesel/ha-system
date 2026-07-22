import pytest
import requests
import time
import os

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="module")
def api():
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    pytest.fail("Backend not reachable")


class TestIntegration:
    def test_health(self, api):
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_create_and_get_item(self, api):
        r = requests.post(f"{BASE_URL}/items", json={"name": "integration-test"}, timeout=5)
        assert r.status_code == 201
        item = r.json()
        assert "id" in item
        assert item["name"] == "integration-test"

        r = requests.get(f"{BASE_URL}/items/{item['id']}", timeout=5)
        assert r.status_code == 200
        assert r.json()["name"] == "integration-test"

    def test_list_items(self, api):
        r = requests.get(f"{BASE_URL}/items", timeout=5)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_delete_item(self, api):
        r = requests.post(f"{BASE_URL}/items", json={"name": "delete-me"}, timeout=5)
        assert r.status_code == 201
        item_id = r.json()["id"]

        r = requests.delete(f"{BASE_URL}/items/{item_id}", timeout=5)
        assert r.status_code == 200

        r = requests.get(f"{BASE_URL}/items/{item_id}", timeout=5)
        assert r.status_code == 404

    def test_create_item_empty_name(self, api):
        r = requests.post(f"{BASE_URL}/items", json={}, timeout=5)
        assert r.status_code == 400

    def test_get_nonexistent_item(self, api):
        r = requests.get(f"{BASE_URL}/items/00000000-0000-0000-0000-000000000000", timeout=5)
        assert r.status_code == 404

    def test_delete_nonexistent_item(self, api):
        r = requests.delete(f"{BASE_URL}/items/00000000-0000-0000-0000-000000000000", timeout=5)
        assert r.status_code == 404
