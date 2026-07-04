from __future__ import annotations

"""切分合并文本并生成 upload{n}.txt 片段。"""

import argparse
import re
import sys
from pathlib import Path
from typing import List

from common import PROJECT_ROOT, print_output
from src.core.io_utils import atomic_write_text, ensure_directory
from src.core.scriptgen import SCRIPTGEN_ROOT, SCRIPTGEN_SPLIT_ROOT, split_text

DEFAULT_MAX_CHARS = 119913
_PART_FILE_RE = re.compile(r"^upload\d+\.txt$")
INSTRUCTION_LINES = [
    "由于受到限制，你刚刚生成的内容被截断了 --- 请你稍后回复，我会将你之前回复的内容发给你，然后你再根据之前你生成的内容继续对接，从下一行开始生成",
    "这是你之前生成回复的第 1/2 段 --- 请你稍后回复，我会将你之前回复的内容发给你，然后你再根据之前你生成的内容继续对接，从下一行开始生成",
    "根据之前你生成的内容继续对接，从下一行开始生成",
]


def read_file_content(file_path: Path) -> str:
    """读取文件完整内容。"""
    if not file_path.exists():
        raise FileNotFoundError("文件不存在: {}".format(file_path))
    return file_path.read_text(encoding="utf-8")


def resolve_input(path_text: str) -> Path:
    """解析输入文件路径。"""
    if path_text:
        path = Path(path_text)
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    candidates = sorted(SCRIPTGEN_ROOT.glob("upload_*.txt"))
    if not candidates:
        raise FileNotFoundError("未找到 upload_*.txt，请先运行 gen_merger.py")
    return candidates[-1]


def split_content(content: str, max_chars: int, separator: str) -> List[str]:
    """切分文本内容。"""
    if not content:
        return []
    if separator:
        return split_text(content, max_chars=max_chars, separator=separator)
    return [content[index:index + max_chars] for index in range(0, len(content), max_chars)]


def build_part_text(index: int, total: int, content: str) -> str:
    """构建单个分片的旧格式文本。"""
    content_stripped = content.rstrip("\n")
    header = "--- PART {}/{} START ---".format(index, total)
    if index == total:
        footer = "---PART {}/{} END AND START REPLY NOW---".format(index, total)
    else:
        footer = "--- PART {}/{} END AND YOU SHOULD READ QUIET AND DONT REPLY------".format(index, total)
    return "{}\n{}\n{}\n".format(header, content_stripped, footer)


def format_legacy_parts(parts: List[str]) -> str:
    """按旧脚本风格输出全部分段文本。"""
    total = len(parts)
    return "\n".join(
        build_part_text(index, total, content)
        for index, content in enumerate(parts, start=1)
    )


def clear_existing_parts(output_dir: Path) -> None:
    """删除旧的 upload{n}.txt 分片，保留 instruction.txt。"""
    ensure_directory(output_dir)
    for path in output_dir.iterdir():
        if path.is_file() and _PART_FILE_RE.match(path.name):
            path.unlink()


def write_instruction(output_dir: Path) -> Path:
    """写入 instruction.txt。"""
    ensure_directory(output_dir)
    target = output_dir / "instruction.txt"
    atomic_write_text(target, "\n\n".join(INSTRUCTION_LINES) + "\n")
    return target


def write_parts(parts: List[str], output_dir: Path, *, wrap_legacy: bool) -> List[Path]:
    """写入 upload{n}.txt 文件。"""
    ensure_directory(output_dir)
    clear_existing_parts(output_dir)
    outputs: List[Path] = []
    total = len(parts)
    for index, part in enumerate(parts, start=1):
        target = output_dir / "upload{}.txt".format(index)
        payload = build_part_text(index, total, part) if wrap_legacy else part
        atomic_write_text(target, payload)
        outputs.append(target)
    return outputs


def main() -> None:
    """脚本入口。"""
    parser = argparse.ArgumentParser(description="切分 upload 文本")
    parser.add_argument("input", nargs="?", default="", help="输入文件路径")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help="每段最大字符数，默认保留旧逻辑 119913",
    )
    parser.add_argument(
        "--separator",
        default="",
        help="优先切分分隔符；为空时保持旧逻辑，直接按字符数截断",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="输出目录，默认 logs/scriptgen/spilt",
    )
    parser.add_argument(
        "--stdout-mode",
        choices=["paths", "legacy"],
        default="paths",
        help="标准输出模式：paths 输出文件路径，legacy 输出旧格式分段文本",
    )
    parser.add_argument(
        "--raw-files",
        action="store_true",
        help="写入原始片段内容，不在 upload{n}.txt 中包裹旧 PART 提示",
    )
    args = parser.parse_args()

    input_path = resolve_input(args.input)
    output_dir = Path(args.output_dir) if args.output_dir else SCRIPTGEN_SPLIT_ROOT
    content = read_file_content(input_path)
    if not content:
        print("文件为空，无内容可分割。", file=sys.stderr)
        raise SystemExit(0)

    parts = split_content(content, args.max_chars, args.separator)
    outputs = write_parts(parts, output_dir, wrap_legacy=not args.raw_files)
    instruction_path = write_instruction(output_dir)
    if args.stdout_mode == "legacy":
        sys.stdout.write(format_legacy_parts(parts))
    else:
        for output in outputs:
            print_output(output)
        print_output(instruction_path)
    print(
        "分割完成: 共 {} 个 part, 总字符数 {}".format(
            len(parts),
            sum(len(part) for part in parts),
        ),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
