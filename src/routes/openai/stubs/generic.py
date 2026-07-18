"""generic 模块 — HTTP 入口路由。

职责：
    作为 Provider-Evo 项目标准模块，提供 generic 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from src.routes.shared.handler import make_empty_list, make_not_found, make_not_supported

__all__ = ["make_not_supported", "make_empty_list", "make_not_found"]
