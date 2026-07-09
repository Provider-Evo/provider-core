"""共享 pytest fixtures。"""
from __future__ import annotations

import pytest


@pytest.fixture
async def aiohttp_client_session():
    import aiohttp

    async with aiohttp.ClientSession() as session:
        yield session
