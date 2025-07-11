import pytest
from fastapi.testclient import TestClient
from src.main_fastapi import app

@pytest.fixture
def client():
    """Create a test client for FastAPI app."""
    return TestClient(app)

@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "google_api_key": "test_key",
        "google_cse_id": "test_cse_id",
        "log_level": "INFO"
    }