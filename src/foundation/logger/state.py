"""logger 模块共享状态。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.foundation.paths import project_root as _project_root

LOG_DIR: Path = _project_root / "logs"

# 标记是否已完成基础 handler 初始化，避免重复添加
initialized: bool = False

# 全局颜色覆盖：None 表示自动检测，True/False 强制开启/关闭
color_override: Optional[bool] = None

# 控制台 handler ID（用于 set_color 时移除并重建）
console_handler_id: Optional[int] = None
