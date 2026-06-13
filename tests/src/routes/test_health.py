"""Tests for src/routes/health.py."""
import pytest
from unittest.mock import MagicMock, patch
import aiohttp.web

from src.routes.health import setup_routes, _health_check


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_ok(self):
        mock_cfg = MagicMock()
        mock_cfg.server.version = "2.2.3"

        with patch("src.routes.health.get_config", return_value=mock_cfg):
            request = MagicMock()
            response = await _health_check(request)

            assert response.status == 200
            import json
            body = json.loads(response.text)
            assert body["status"] == "ok"
            assert body["version"] == "2.2.3"


class TestHealthRoutes:
    def test_setup_routes_adds_health_endpoint(self):
        app = MagicMock()
        app.router = MagicMock()

        setup_routes(app)

        # Verify GET /health was added
        app.router.add_get.assert_called_once()
        call_args = app.router.add_get.call_args
        assert call_args[0][0] == "/health"
        assert call_args[0][1] == _health_check
