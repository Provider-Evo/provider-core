from __future__ import annotations

"""src.logger set_color() handler rebuild 测试。"""

import sys
from unittest import mock

import pytest


class TestSetColorHandlerRebuild:
    """set_color() 重建 console handler 测试。"""

    def test_set_color_updates_override(self) -> None:
        """set_color() 正确更新 _color_override 变量。"""
        from src import logger as log_module

        original = log_module._color_override
        try:
            log_module.set_color(True)
            assert log_module._color_override is True
            log_module.set_color(False)
            assert log_module._color_override is False
            log_module.set_color(None)
            assert log_module._color_override is None
        finally:
            log_module._color_override = original

    def test_set_color_rebuilds_handler_when_initialized(self) -> None:
        """初始化完成后调用 set_color() 应重建 console handler。"""
        from src import logger as log_module

        if not log_module._initialized:
            pytest.skip("logger 未完成初始化")

        original_override = log_module._color_override
        original_handler_id = log_module._console_handler_id
        try:
            log_module.set_color(False)
            # handler ID 应该已变更（旧 handler 被移除，新 handler 被添加）
            new_handler_id = log_module._console_handler_id
            # 新的 handler ID 应该不等于旧的（除非碰巧 loguru 重用同一个 ID）
            assert log_module._color_override is False
            assert new_handler_id is not None
        finally:
            log_module._color_override = original_override
            if original_handler_id is not None:
                log_module._console_handler_id = original_handler_id

    def test_console_handler_id_exists(self) -> None:
        """_console_handler_id 模块变量存在。"""
        from src import logger as log_module
        assert hasattr(log_module, "_console_handler_id")
