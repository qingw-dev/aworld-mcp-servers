import pytest
from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    """Test basic health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

def test_import_main_modules():
    """Test that main modules can be imported."""
    try:
        import src.main
        import src.config
        import src.gaia.agent
        import src.rag.services.search_orchestrator
    except ImportError as e:
        pytest.fail(f"Failed to import module: {e}")