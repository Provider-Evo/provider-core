"""Tests for src/routes/models.py."""
import json
import pytest
from unittest.mock import MagicMock

from src.routes.models import setup_routes, _list_models, _get_model, _MODELS


class TestListModels:
    @pytest.mark.asyncio
    async def test_returns_model_list(self):
        request = MagicMock()
        response = await _list_models(request)

        assert response.status == 200
        body = json.loads(response.text)
        assert body["object"] == "list"
        assert "data" in body
        assert len(body["data"]) == len(_MODELS)

    @pytest.mark.asyncio
    async def test_models_have_required_fields(self):
        request = MagicMock()
        response = await _list_models(request)

        body = json.loads(response.text)
        for model in body["data"]:
            assert "id" in model
            assert "object" in model
            assert "created" in model
            assert "owned_by" in model


class TestGetModel:
    @pytest.mark.asyncio
    async def test_returns_existing_model(self):
        request = MagicMock()
        request.match_info = {"model": "qwen-turbo"}

        response = await _get_model(request)
        assert response.status == 200

        body = json.loads(response.text)
        assert body["id"] == "qwen-turbo"
        assert body["owned_by"] == "qwen"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_model(self):
        request = MagicMock()
        request.match_info = {"model": "nonexistent-model"}

        response = await _get_model(request)
        assert response.status == 404

        body = json.loads(response.text)
        assert "error" in body
        assert "nonexistent-model" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_returns_deepseek_model(self):
        request = MagicMock()
        request.match_info = {"model": "deepseek-chat"}

        response = await _get_model(request)
        assert response.status == 200

        body = json.loads(response.text)
        assert body["id"] == "deepseek-chat"
        assert body["owned_by"] == "deepseek"


class TestModelsRoutes:
    def test_setup_routes_adds_endpoints(self):
        app = MagicMock()
        app.router = MagicMock()

        setup_routes(app)

        # Should add two routes
        assert app.router.add_get.call_count == 2

        # Check /v1/models
        calls = app.router.add_get.call_args_list
        assert calls[0][0][0] == "/v1/models"
        assert calls[0][0][1] == _list_models

        # Check /v1/models/{model}
        assert calls[1][0][0] == "/v1/models/{model}"
        assert calls[1][0][1] == _get_model
