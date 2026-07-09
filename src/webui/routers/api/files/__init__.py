from __future__ import annotations

"""WebUI 文件管理 API 路由包。"""

from .handlers import (
    files_copy,
    files_delete,
    files_download,
    files_drives,
    files_list,
    files_mkdir,
    files_move,
    files_project_root,
    files_read,
    files_rename,
    files_search,
    files_upload,
    files_write,
)

__all__ = [
    "files_copy",
    "files_delete",
    "files_download",
    "files_drives",
    "files_list",
    "files_mkdir",
    "files_move",
    "files_project_root",
    "files_read",
    "files_rename",
    "files_search",
    "files_upload",
    "files_write",
]
