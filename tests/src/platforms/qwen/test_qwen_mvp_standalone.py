from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os


class TestMvpEnv:
    def test_get_credentials_from_env(self) -> None:
        with patch.dict(os.environ, {"QWEN_EMAIL": "test@example.com", "QWEN_PASSWORD": "password123"}):
            from src.platforms.qwen.mvp.env import get_credentials
            email, password = get_credentials()
            assert email == "test@example.com"
            assert password == "password123"

    def test_get_credentials_from_accounts(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.platforms.qwen.mvp.env.ACCOUNTS", [MagicMock(username="account@example.com", password="accpass")]):
                from src.platforms.qwen.mvp.env import get_credentials
                email, password = get_credentials()
                assert email == "account@example.com"
                assert password == "accpass"

    def test_get_credentials_no_accounts(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.platforms.qwen.mvp.env.ACCOUNTS", []):
                from src.platforms.qwen.mvp.env import get_credentials
                with pytest.raises(SystemExit):
                    get_credentials()


class TestMvpChat:
    @pytest.mark.asyncio
    async def test_get_qwen_stream_returns_generator(self) -> None:
        from src.platforms.qwen.mvp.chat import get_qwen_stream
        
        # Mock the entire flow
        with patch("src.platforms.qwen.mvp.chat.get_credentials", return_value=("test@example.com", "password")), \
             patch("src.platforms.qwen.mvp.chat.aiohttp.ClientSession") as mock_session_class:
            
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_class.return_value.__aexit__ = AsyncMock(return_value=False)
            
            # Mock login response
            mock_login_response = AsyncMock()
            mock_login_response.status = 200
            mock_login_response.json = AsyncMock(return_value={
                "success": True,
                "data": {"access_token": "test-token"}
            })
            
            # Mock create chat response
            mock_chat_response = AsyncMock()
            mock_chat_response.status = 200
            mock_chat_response.json = AsyncMock(return_value={
                "success": True,
                "data": {"id": "test-chat-id"}
            })
            
            # Mock chat response
            mock_chat_stream = AsyncMock()
            mock_chat_stream.status = 200
            mock_chat_stream.content = AsyncMock()
            
            # Setup post to return different responses based on URL
            async def mock_post(url, **kwargs):
                if "signin" in url:
                    return mock_login_response
                elif "new" in url:
                    return mock_chat_response
                else:
                    return mock_chat_stream
            
            mock_session.post = mock_post
            
            # This should return a generator
            gen = get_qwen_stream("Hello", "qwen3-max")
            assert hasattr(gen, '__aiter__')
