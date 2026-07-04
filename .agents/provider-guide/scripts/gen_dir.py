from __future__ import annotations

"""增强版目录结构分析工具。"""

import argparse
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from common import PROJECT_ROOT, print_output
from src.core.io_utils import atomic_write_text, ensure_directory
from src.core.scriptgen import SCRIPTGEN_ROOT, make_log_text_path


class DirectoryAnalyzer:
    """目录分析器。"""

    def __init__(
        self,
        root_path: Path,
        *,
        show_hidden: bool,
        max_depth: Optional[int],
        exclude_file_path: Optional[Path],
    ) -> None:
        self.root_path = root_path
        self.show_hidden = show_hidden
        self.max_depth = max_depth
        self.exclude_file_path = exclude_file_path.resolve() if exclude_file_path else None
        self.file_count = 0
        self.dir_count = 0
        self.total_size = 0
        self.largest_files: List[tuple[str, int]] = []
        self.file_types: Dict[str, int] = {}

    def should_show(self, path: Path) -> bool:
        """判断是否显示该路径。"""
        if ".pyc" in str(path):
            return False
        if not self.show_hidden and path.name.startswith("."):
            return False
        if self.exclude_file_path and path.resolve() == self.exclude_file_path:
            return False
        return True

    @staticmethod
    def format_size(size_bytes: float) -> str:
        """格式化文件大小。"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        index = 0
        current_size = float(size_bytes)
        while current_size >= 1024 and index < len(size_names) - 1:
            current_size /= 1024.0
            index += 1
        return "{:.1f} {}".format(current_size, size_names[index])

    @staticmethod
    def get_file_type(file_path: Path) -> str:
        """获取文件类型。"""
        return file_path.suffix.lower() or "无扩展名"

    @staticmethod
    def get_file_size(file_path: Path) -> int:
        """安全获取文件大小。"""
        try:
            return file_path.stat().st_size
        except OSError:
            return 0

    def analyze_file(self, file_path: Path) -> None:
        """分析单个文件。"""
        if self.exclude_file_path and file_path.resolve() == self.exclude_file_path:
            return
        size = self.get_file_size(file_path)
        self.file_count += 1
        self.total_size += size
        file_type = self.get_file_type(file_path)
        self.file_types[file_type] = self.file_types.get(file_type, 0) + 1
        if len(self.largest_files) < 10 or size > self.largest_files[-1][1]:
            self.largest_files.append((str(file_path.relative_to(self.root_path)), size))
            self.largest_files.sort(key=lambda item: item[1], reverse=True)
            self.largest_files = self.largest_files[:10]

    def build_tree_lines(
        self,
        path: Optional[Path] = None,
        prefix: str = "",
        depth: int = 0,
        is_last: bool = True,
    ) -> List[str]:
        """递归构建目录树。"""
        current_path = path or self.root_path
        if self.max_depth is not None and self.max_depth >= 0 and depth > self.max_depth:
            return []
        if depth > 0 and not self.should_show(current_path):
            return []

        lines: List[str] = []
        name = current_path.name if current_path.name else str(current_path)
        if depth > 0:
            connector = "└── " if is_last else "├── "
            size_info = ""
            if current_path.is_file():
                size_info = " ({})".format(self.format_size(self.get_file_size(current_path)))
            lines.append(prefix + connector + name + size_info)
        else:
            lines.append(name)

        if current_path.is_file():
            self.analyze_file(current_path)
            return lines

        self.dir_count += 1
        next_prefix = prefix + ("    " if is_last and depth > 0 else "│   " if depth > 0 else "")
        try:
            items = [item for item in current_path.iterdir() if self.should_show(item)]
            items.sort(key=lambda item: (item.is_file(), item.name.lower()))
        except PermissionError:
            lines.append(next_prefix + "└── [权限不足]")
            return lines
        except OSError as exc:
            lines.append(next_prefix + "└── [错误: {}]".format(exc))
            return lines

        for index, item in enumerate(items):
            lines.extend(
                self.build_tree_lines(
                    item,
                    next_prefix,
                    depth + 1,
                    index == len(items) - 1,
                )
            )
        return lines

    def analyze_deep(self) -> float:
        """深入分析目录。"""
        start_time = time.time()
        self.file_count = 0
        self.dir_count = 0
        self.total_size = 0
        self.largest_files = []
        self.file_types = {}
        for root, dirs, files in os.walk(self.root_path):
            current_root = Path(root)
            if not self.show_hidden:
                dirs[:] = [directory for directory in dirs if not directory.startswith(".")]
            for file_name in files:
                if not self.show_hidden and file_name.startswith("."):
                    continue
                file_path = current_root / file_name
                if self.exclude_file_path and file_path.resolve() == self.exclude_file_path:
                    continue
                self.analyze_file(file_path)
            self.dir_count += len(dirs)
        return time.time() - start_time

    def build_statistics_lines(self) -> List[str]:
        """构建统计信息文本。"""
        lines = [
            "",
            "=" * 60,
            "详细统计信息",
            "=" * 60,
            "目录数量: {}".format(self.dir_count),
            "文件数量: {}".format(self.file_count),
            "总大小: {}".format(self.format_size(self.total_size)),
            "",
            "文件类型统计:",
        ]
        for file_type, count in sorted(self.file_types.items(), key=lambda item: item[1], reverse=True)[:10]:
            percentage = (count / self.file_count * 100) if self.file_count else 0
            lines.append("  {}: {} 个 ({:.1f}%)".format(file_type, count, percentage))
        if self.largest_files:
            lines.append("")
            lines.append("最大的文件:")
            for index, (file_path, size) in enumerate(self.largest_files, start=1):
                lines.append("  {:>2}. {} ({})".format(index, file_path, self.format_size(size)))
        return lines


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(description="增强版目录结构分析工具")
    parser.add_argument("path", nargs="?", default=".", help="要分析的目录路径")
    parser.add_argument("-a", "--all", action="store_true", help="显示隐藏文件和目录")
    parser.add_argument("-d", "--depth", type=int, help="限制显示深度")
    parser.add_argument("-s", "--stats", action="store_true", help="显示详细统计信息")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细模式")
    parser.add_argument("--exclude-file", type=str, default="", help="指定要额外排除的文件")
    parser.add_argument("--output", default="", help="输出文件路径")
    args = parser.parse_args()

    root = (PROJECT_ROOT / args.path).resolve() if not Path(args.path).is_absolute() else Path(args.path)
    if not root.exists() or not root.is_dir():
        raise ValueError("指定路径不是目录: {}".format(root))

    exclude_path = None
    if args.exclude_file:
        candidate = root / args.exclude_file
        if candidate.exists():
            exclude_path = candidate.resolve()
    else:
        exclude_path = Path(__file__).resolve()

    analyzer = DirectoryAnalyzer(
        root,
        show_hidden=args.all,
        max_depth=args.depth,
        exclude_file_path=exclude_path,
    )
    tree_lines = analyzer.build_tree_lines()
    if args.stats or args.verbose:
        elapsed = analyzer.analyze_deep()
        tree_lines.append("")
        tree_lines.append("深入分析完成，耗时: {:.2f} 秒".format(elapsed))
        tree_lines.extend(analyzer.build_statistics_lines())

    output = Path(args.output) if args.output else make_log_text_path("dir", SCRIPTGEN_ROOT)
    ensure_directory(output.parent)
    atomic_write_text(output, "\n".join(tree_lines).rstrip() + "\n")
    print_output(output)


if __name__ == "__main__":
    main()
