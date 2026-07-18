"""base 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 base 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from typing import Any, Dict, Optional

__all__ = ["ProviderError"]

_ERROR_TYPE_MAP: Dict[type, str] = {}


def _error_type_name(cls: type) -> str:
    """Derive a snake_case error type name from the class name."""
    name = cls.__name__
    result = [name[0].lower()]
    for ch in name[1:]:
        if ch.isupper():
            result.append("_")
            result.append(ch.lower())
        else:
            result.append(ch)
    return "".join(result)


class ProviderError(Exception):
    """类 ProviderError。"""
    """Base gateway exception. Root of the Provider-V2 error hierarchy."""

    def __init__(
        self,
        message: str,
        original: Optional[Exception] = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.original = original
        self.status_code = status_code

    @property
    def error_type(self) -> str:
        """中文说明：error_type。

Return the snake_case error type name."""
        cls = type(self)
        if cls not in _ERROR_TYPE_MAP:
            _ERROR_TYPE_MAP[cls] = _error_type_name(cls)
        return _ERROR_TYPE_MAP[cls]

    def to_dict(self) -> Dict[str, Any]:
        """中文说明：to_dict。

Serialize error to a JSON-compatible dictionary.

Returns:
    ``{"error": {"type": ..., "message": ..., "status_code": ...}}``"""
        return {
            "error": {
                "type": self.error_type,
                "message": str(self),
                "status_code": self.status_code,
            }
        }
