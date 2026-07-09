from __future__ import annotations

import aiohttp.web

from .._common import (
    DRIVES_SENTINEL,
    MAX_PREVIEW_SIZE,
    MAX_UPLOAD_SIZE,
    PROJECT_ROOT,
    SEARCH_SKIP_DIRS,
    entry_info_from_scandir,
    get_drives,
    is_binary_file,
    is_write_forbidden,
    safe_resolve,
    unique_dest,
)

"""WebUI 文件管理 API — 驱动器与项目根。"""

# ---------------------------------------------------------------------------
# GET /v1/webui/files/drives
# ---------------------------------------------------------------------------

async def files_drives(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：files_drives。

Return a list of available filesystem roots.

Windows: drive letters (``["C:\\", "D:\\"]``).
Linux/Mac: ``["/"]``."""
    return aiohttp.web.json_response({"drives": get_drives()})


# ---------------------------------------------------------------------------
# GET /v1/webui/files/project-root
# ---------------------------------------------------------------------------

async def files_project_root(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：files_project_root。

Return the project root path so the frontend can offer a shortcut."""
    return aiohttp.web.json_response({"path": str(PROJECT_ROOT)})
