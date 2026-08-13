"""
test_api.py

Purpose (in simple language):
------------------------------
Automated tests for the Phase 4 FastAPI backend, using FastAPI's own
TestClient (no real network socket needed - it calls the app directly in
memory, which is why these tests are fast and don't depend on a running
uvicorn process).

Run with:
    cd backend/app
    ../venv/bin/python -m pytest ../tests/test_api.py -v
"""

import os
import sys

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import pytest
from fastapi.testclient import TestClient

from main import app
from model_loader import registry_manager


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# --- Root & Health ---

def test_root_endpoint(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["project"] == "KrushiMitra AI"
    assert body["status"] == "running"


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["model_registry_loaded"] is True
    assert isinstance(body["models_loaded"], int)
    assert "timestamp" in body


def test_registry_loading():
    """Confirms the registry manager actually has data loaded (not just an empty stub)."""
    assert registry_manager.is_loaded is True
    assert len(registry_manager.registry_df) > 0
    assert len(registry_manager.canonical_crops) == 5
    assert len(registry_manager.canonical_markets) == 5


# --- Reference data endpoints ---

def test_crops_endpoint(client):
    r = client.get("/crops")
    assert r.status_code == 200
    body = r.json()
    assert "Onion" in body["crops"]
    assert len(body["crops"]) == 5


def test_markets_endpoint_no_filter(client):
    r = client.get("/markets")
    assert r.status_code == 200
    body = r.json()
    assert len(body["markets"]) == 5
    assert body["filtered_by_crop"] is None


def test_markets_endpoint_with_crop_filter(client):
    r = client.get("/markets?crop=Onion")
    assert r.status_code == 200
    body = r.json()
    assert body["filtered_by_crop"] == "Onion"
    assert "Sangli" in body["markets"]


def test_markets_endpoint_invalid_crop(client):
    r = client.get("/markets?crop=Mango")
    assert r.status_code == 404


def test_models_endpoint_schema(client):
    r = client.get("/models")
    assert r.status_code == 200
    body = r.json()
    assert body["total_registered"] > 0
    first = body["models"][0]
    for field in ["crop", "market", "variety_used", "selected_model", "model_type", "mae", "rmse", "development_data"]:
        assert field in first
    # internal file paths must NEVER be exposed
    assert "model_file_path" not in first
    assert "Model_File_Path" not in first


# --- Prediction endpoint: happy paths ---

def test_predict_naive_pair(client):
    r = client.post("/predict", json={"crop": "Onion", "market": "Sangli", "variety": "Local", "forecast_date": "2026-08-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["selected_model"] == "Naive_Previous_Price"
    assert body["estimated_price_range"]["lower"] <= body["predicted_price"] <= body["estimated_price_range"]["upper"]
    assert body["confidence_level"] in {"High", "Medium", "Low"}
    assert body["trend"] in {"Increasing", "Stable", "Decreasing"}


def test_predict_crop_specific_ml_pair(client):
    r = client.post("/predict", json={"crop": "Soybean", "market": "Satara", "forecast_date": "2026-08-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["selected_model"] == "Random_Forest_Crop_Specific"
    assert body["model_scope"] == "crop_specific"
    assert body["estimated_price_range"]["lower"] <= body["predicted_price"] <= body["estimated_price_range"]["upper"]


def test_predict_combined_ml_pair(client):
    r = client.post("/predict", json={"crop": "Wheat", "market": "Satara", "forecast_date": "2026-08-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["selected_model"] == "Random_Forest_Combined"
    assert body["model_scope"] == "combined"
    assert body["estimated_price_range"]["lower"] <= body["predicted_price"] <= body["estimated_price_range"]["upper"]


def test_predict_response_schema_complete(client):
    r = client.post("/predict", json={"crop": "Onion", "market": "Pune", "forecast_date": "2026-08-01"})
    assert r.status_code == 200
    body = r.json()
    required_fields = [
        "crop", "market", "variety_used", "forecast_date", "predicted_price",
        "estimated_price_range", "confidence_score", "confidence_level",
        "selected_model", "model_scope", "trend", "explanation",
    ]
    for field in required_fields:
        assert field in body, f"Missing field in /predict response: {field}"
    assert "lower" in body["estimated_price_range"] and "upper" in body["estimated_price_range"]


# --- Prediction endpoint: error paths ---

def test_predict_invalid_crop(client):
    r = client.post("/predict", json={"crop": "Mango", "market": "Sangli", "forecast_date": "2026-08-01"})
    assert r.status_code == 404
    assert "Unknown crop" in r.json()["detail"]


def test_predict_invalid_market(client):
    r = client.post("/predict", json={"crop": "Onion", "market": "Delhi", "forecast_date": "2026-08-01"})
    assert r.status_code == 404
    assert "Unknown market" in r.json()["detail"]


def test_predict_invalid_variety(client):
    r = client.post("/predict", json={"crop": "Onion", "market": "Sangli", "variety": "Purple", "forecast_date": "2026-08-01"})
    assert r.status_code == 404
    assert "Unknown variety" in r.json()["detail"]


def test_predict_invalid_date_format(client):
    r = client.post("/predict", json={"crop": "Onion", "market": "Sangli", "forecast_date": "01-08-2026"})
    assert r.status_code == 422


def test_predict_missing_field(client):
    r = client.post("/predict", json={"crop": "Onion", "forecast_date": "2026-08-01"})
    assert r.status_code == 422
    assert "market" in r.json()["detail"]


def test_predict_malformed_json(client):
    r = client.post("/predict", data="not valid json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_predict_ineligible_pair(client):
    """Soybean @ Sangli was marked ineligible back in Phase 1 (insufficient records)."""
    r = client.post("/predict", json={"crop": "Soybean", "market": "Sangli", "forecast_date": "2026-08-01"})
    assert r.status_code == 404
    assert "eligible" in r.json()["detail"].lower()


def test_unknown_route_returns_404(client):
    r = client.get("/this-route-does-not-exist")
    assert r.status_code == 404


# --- Model loading behavior ---

def test_model_lazy_loading_and_reuse(client):
    """
    The combined model artifact should be loaded once and then reused -
    predicting for two different pairs that both selected the combined
    model should not increase the cache size beyond one entry for that file.
    """
    cache_size_before = registry_manager.models_loaded_count
    client.post("/predict", json={"crop": "Wheat", "market": "Satara", "forecast_date": "2026-08-01"})
    cache_size_after_first = registry_manager.models_loaded_count
    client.post("/predict", json={"crop": "Tomato", "market": "Satara", "forecast_date": "2026-08-01"})
    cache_size_after_second = registry_manager.models_loaded_count

    # both Wheat@Satara and Tomato@Satara use the SAME combined_random_forest.joblib file
    assert cache_size_after_second == cache_size_after_first, (
        "Expected the shared combined model to be reused from cache, not reloaded as a second entry"
    )
    assert cache_size_after_first >= cache_size_before


if __name__ == "__main__":
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])
