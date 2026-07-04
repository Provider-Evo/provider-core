from __future__ import annotations

"""按当前平台规范生成平台脚手架。"""

import argparse
from pathlib import Path

from common import PROJECT_ROOT, print_output
from src.core.io_utils import atomic_write_text, ensure_directory

TEMPLATE_FILES = {
    "__init__.py": "from __future__ import annotations\n\nfrom .adapter import Adapter\n\n__all__ = ['Adapter']\n",
    "adapter.py": "from __future__ import annotations\n\nfrom .util import Adapter\n\n__all__ = ['Adapter']\n",
    "util.py": "from __future__ import annotations\n\nfrom typing import Any\n\n__all__ = ['Adapter']\n\n\ndef __getattr__(name: str) -> Any:\n    if name == 'Adapter':\n        from .core.impl import Adapter as _Adapter  # noqa: PLC0415\n\n        return _Adapter\n    raise AttributeError('module has no attribute {!r}'.format(name))\n",
    "accounts.py": "from __future__ import annotations\n\nfrom dataclasses import dataclass\nfrom typing import List\n\n\n@dataclass\nclass Account:\n    username: str\n    password: str\n\n\nACCOUNTS: List[Account] = []\n",
    "core/__init__.py": "from __future__ import annotations\n\nfrom .impl import Adapter\n\n__all__ = ['Adapter']\n",
    "core/impl.py": "from __future__ import annotations\n\nfrom typing import Any, AsyncGenerator, Dict, List, Union\n\nimport aiohttp\n\nfrom src.platforms.base import PlatformAdapter\n\n\nclass Adapter(PlatformAdapter):\n    @property\n    def name(self) -> str:\n        return 'service'\n\n    async def init(self, session: aiohttp.ClientSession) -> None:\n        del session\n        return None\n\n    async def candidates(self) -> List[Any]:\n        return []\n\n    async def ensure_candidates(self, count: int) -> int:\n        del count\n        return 0\n\n    async def complete(\n        self,\n        candidate: Any,\n        messages: List[Dict[str, Any]],\n        model: str,\n        stream: bool,\n        **kw: Any\n    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:\n        del candidate, messages, model, stream, kw\n        if False:\n            yield {}\n        return\n\n    async def close(self) -> None:\n        return None\n",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="生成平台脚手架")
    parser.add_argument("name", help="平台目录名")
    args = parser.parse_args()

    platform_root = PROJECT_ROOT / "src" / "platforms" / args.name
    if platform_root.exists():
        raise FileExistsError("平台目录已存在: {}".format(platform_root))
    for relative_path, content in TEMPLATE_FILES.items():
        target = platform_root / relative_path
        ensure_directory(target.parent)
        atomic_write_text(target, content.replace("service", args.name))
    print_output(platform_root)


if __name__ == "__main__":
    main()
