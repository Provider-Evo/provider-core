from __future__ import annotations

"""账号格式双向转换脚本。"""

import argparse
import ast
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import PROJECT_ROOT, print_output
from src.core.io_utils import atomic_write_text

DEFAULT_PLATFORM = "qwen"


def format_service_name(raw: str) -> str:
    """将原始名称格式化为首字母大写服务名。"""
    if not raw:
        return "Service"
    result: List[str] = []
    first_letter_found = False
    for char in raw:
        if char.isalpha():
            if not first_letter_found:
                result.append(char.upper())
                first_letter_found = True
            else:
                result.append(char.lower())
        else:
            result.append(char)
    return "".join(result)


def find_accounts_file(name: str) -> Optional[Path]:
    """查找 accounts.py 文件路径。"""
    candidate = PROJECT_ROOT / "src" / "platforms" / name / "accounts.py"
    if candidate.is_file():
        return candidate
    return None


def parse_accounts_file(accounts_file: Path) -> Tuple[str, List[Any]]:
    """用 AST 静态解析 accounts.py。"""
    source = accounts_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(accounts_file))
    accounts_node: Optional[ast.List] = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        else:
            targets = [node.target]
            value = node.value
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "ACCOUNTS" and isinstance(value, ast.List):
                accounts_node = value
                break
        if accounts_node is not None:
            break
    if accounts_node is None:
        raise ValueError("未在文件中找到 ACCOUNTS = [...] 赋值")
    if not accounts_node.elts:
        raise ValueError("ACCOUNTS 列表为空，无法检测格式")

    first_elt = accounts_node.elts[0]
    if isinstance(first_elt, ast.Dict):
        accounts_data: List[Dict[str, str]] = []
        for elt in accounts_node.elts:
            if not isinstance(elt, ast.Dict):
                continue
            item: Dict[str, str] = {}
            for key, value in zip(elt.keys, elt.values):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                    item[str(key.value)] = str(value.value)
            if item:
                accounts_data.append(item)
        return "old", accounts_data

    if isinstance(first_elt, ast.Call):
        accounts_data_new: List[Dict[str, str]] = []
        for elt in accounts_node.elts:
            if not isinstance(elt, ast.Call):
                continue
            keyword_map: Dict[str, str] = {}
            for keyword in elt.keywords:
                if keyword.arg and isinstance(keyword.value, ast.Constant):
                    keyword_map[keyword.arg] = str(keyword.value.value)
            for index, argument in enumerate(elt.args):
                if not isinstance(argument, ast.Constant):
                    continue
                if index == 0 and "username" not in keyword_map and "email" not in keyword_map:
                    keyword_map["username"] = str(argument.value)
                elif index == 1 and "password" not in keyword_map:
                    keyword_map["password"] = str(argument.value)
            if keyword_map:
                accounts_data_new.append(keyword_map)
        return "new", accounts_data_new

    raise ValueError("无法识别 ACCOUNTS 中元素格式")


def old_to_new(accounts: List[Dict[str, str]], service_name: str) -> str:
    """将旧格式转换为新格式。"""
    lines: List[str] = [
        '"""{} 凭证管理。"""'.format(service_name),
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "from typing import List, Optional",
        "",
        "",
        "@dataclass",
        "class Account:",
        '    """{} 登录账号。"""'.format(service_name),
        "",
        "    username: str",
        "    password: str",
        '    token: str = ""',
        '    user_id: str = ""',
        '    password_hash: str = ""',
        "    token_expires: float = 0.0",
        "    memory_disabled: bool = False",
        "    context_length: Optional[int] = None",
        "",
        "",
        "ACCOUNTS: List[Account] = [",
    ]
    for account_dict in accounts:
        for identity, password in account_dict.items():
            lines.append('    Account(username="{}", password="{}"),'.format(identity, password))
    lines.extend(["]", ""])
    return "\n".join(lines)


def new_to_old(accounts: List[Dict[str, str]]) -> str:
    """将新格式转换为旧格式。"""
    lines: List[str] = ["ACCOUNTS = ["]
    for keyword_map in accounts:
        identity = keyword_map.get("username") or keyword_map.get("email", "")
        password = keyword_map.get("password", "")
        if identity:
            lines.append('    {{"{}": "{}"}},'.format(identity, password))
    lines.extend(["]", ""])
    return "\n".join(lines)


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(description="accounts.py 双向转换工具")
    parser.add_argument("platform", nargs="?", default=DEFAULT_PLATFORM, help="目标平台名")
    parser.add_argument(
        "--mode",
        choices=["validate", "convert"],
        default="validate",
        help="默认仅校验；只有 convert 才会写回文件",
    )
    parser.add_argument(
        "--direction",
        choices=["auto", "old-to-new", "new-to-old"],
        default="auto",
        help="convert 模式下的转换方向，默认自动检测",
    )
    args = parser.parse_args()

    accounts_file = find_accounts_file(args.platform)
    if accounts_file is None:
        print("错误: 找不到 accounts.py 文件", file=sys.stderr)
        raise SystemExit(1)

    current_format, accounts_data = parse_accounts_file(accounts_file)
    if args.mode == "validate":
        print("{}:{}".format(accounts_file, current_format))
        return

    service_name = format_service_name(args.platform)
    direction = args.direction
    if direction == "auto":
        direction = "old-to-new" if current_format == "old" else "new-to-old"

    if direction == "old-to-new":
        content = old_to_new(accounts_data, service_name)
    else:
        content = new_to_old(accounts_data)

    atomic_write_text(accounts_file, content)
    print_output(accounts_file)


if __name__ == "__main__":
    main()
