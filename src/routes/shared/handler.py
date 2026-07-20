
from typing import Callable

import aiohttp.web

from src.routes.openai.chat.helpers import _err, _json, _not_supported

__all__ = ["make_not_supported", "make_empty_list", "make_not_found"]


def make_not_supported(
    feature: str,
) -> Callable[[aiohttp.web.Request], aiohttp.web.Response]:
    async def handler(_request: aiohttp.web.Request) -> aiohttp.web.Response:
        return _not_supported(feature)

    return handler


def make_empty_list(
    _object: str = "list",
) -> Callable[[aiohttp.web.Request], aiohttp.web.Response]:
    async def handler(_request: aiohttp.web.Request) -> aiohttp.web.Response:
        return _json({"object": _object, "data": [], "has_more": False})

    return handler


def make_not_found(
    resource: str,
) -> Callable[[aiohttp.web.Request], aiohttp.web.Response]:
    async def handler(_request: aiohttp.web.Request) -> aiohttp.web.Response:
        return _err(404, "{} not found".format(resource), "not_found")

    return handler
