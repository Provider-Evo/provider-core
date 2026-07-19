from __future__ import annotations

"""WebUI 文件管理 API 路由处理器。"""

from .meta import files_drives, files_project_root
from .mutate import files_delete, files_mkdir, files_rename, files_write
from .read import files_download, files_list, files_read
from .search import files_search
from .upload import files_upload
from .xfer import files_copy, files_move

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
