from __future__ import annotations

"""WebUI 脚本聚合。"""

from src.webui.templates.scripts_actions import WEBUI_SCRIPTS_ACTIONS
from src.webui.templates.scripts_bootstrap import WEBUI_SCRIPTS_BOOTSTRAP
from src.webui.templates.scripts_render import WEBUI_SCRIPTS_RENDER
from src.webui.templates.scripts_state import WEBUI_SCRIPTS_STATE

__all__ = ["WEBUI_SCRIPTS"]

WEBUI_SCRIPTS = "\n".join(
    [
        WEBUI_SCRIPTS_STATE.strip("\n"),
        WEBUI_SCRIPTS_RENDER.strip("\n"),
        WEBUI_SCRIPTS_ACTIONS.strip("\n"),
        WEBUI_SCRIPTS_BOOTSTRAP.strip("\n"),
    ]
) + "\n"
