"""自动更新 → echotools AutoUpdater 重导出 + 单例。"""
from echotools.lifecycle.updater import (
    AutoUpdater,
    get_updater,
    set_updater,
)

__all__ = ["AutoUpdater", "get_updater", "set_updater"]
