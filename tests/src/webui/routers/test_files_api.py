from __future__ import annotations

import pytest


def test_all_file_handlers_importable() -> None:
    """文件 API 包应导出全部路由 handler。"""
    from src.webui.routers.api.files import (
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

    handlers = (
        files_list,
        files_read,
        files_download,
        files_mkdir,
        files_delete,
        files_rename,
        files_write,
        files_upload,
        files_copy,
        files_move,
        files_search,
        files_drives,
        files_project_root,
    )
    for handler in handlers:
        assert callable(handler)


def test_common_helpers_importable() -> None:
    """路径工具应可从 _common 导入。"""
    from src.webui.routers.api.files._common import safe_resolve

    assert safe_resolve("/") is not None
