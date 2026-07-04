from __future__ import annotations

"""文件内容合并工具。"""

import argparse
import mimetypes
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence

from common import PROJECT_ROOT, print_output
from src.core.io_utils import atomic_write_text, ensure_directory
from src.core.scriptgen import SCRIPTGEN_ROOT, make_log_text_path

_DEFAULT_TEXT_EXTENSIONS = {
    ".txt",
    ".py",
    ".js",
    ".html",
    ".css",
    ".json",
    ".xml",
    ".csv",
    ".md",
    ".rst",
    ".yml",
    ".yaml",
    ".ini",
    ".cfg",
    ".conf",
    ".log",
    ".sh",
    ".bat",
    ".sql",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".php",
    ".rb",
    ".go",
    ".rs",
    ".swift",
    ".kt",
    ".ts",
    ".jsx",
    ".tsx",
    ".toml",
}
_DEFAULT_EXCLUDES = {
    "upload.txt",
    "output.txt",
    "merged.txt",
    ".gitignore",
    ".DS_Store",
    "Thumbs.db",
    "spilt_script.py",
}


def is_text_file(file_path: Path) -> bool:
    """判断文件是否为文本文件。"""
    if file_path.suffix.lower() in _DEFAULT_TEXT_EXTENSIONS:
        return True
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return bool(mime_type and mime_type.startswith("text/"))


def read_file_content(file_path: Path, encoding: str = "utf-8") -> Optional[str]:
    """读取文件内容，自动尝试多种编码。"""
    encodings_to_try = [encoding, "utf-8", "gbk", "gb2312", "latin1"]
    for current_encoding in encodings_to_try:
        try:
            return file_path.read_text(encoding=current_encoding)
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


def should_exclude_file(file_path: Path, exclude_patterns: Sequence[str]) -> bool:
    """判断是否应该排除该文件。"""
    filename = file_path.name
    if filename in _DEFAULT_EXCLUDES:
        return True
    return any(pattern in filename for pattern in exclude_patterns)


def generate_file_header(file_path: Path, root_path: Path) -> str:
    """生成文件头部。"""
    return "# {}\n".format(file_path.relative_to(root_path).as_posix())


def walk_directory(
    root: Path,
    *,
    max_depth: Optional[int],
    exclude_dirs: Sequence[str],
) -> Iterator[Path]:
    """遍历目录，支持深度限制和目录排除。"""
    root = root.resolve()
    root_depth = len(root.parts)

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue

        parts = file_path.relative_to(root).parts
        file_depth = len(parts)

        if max_depth is not None and file_depth > max_depth:
            continue

        if any(part in exclude_dirs for part in parts[:-1]):
            continue

        yield file_path


def sort_files(files: List[Path], sort_mode: str) -> List[Path]:
    """按指定方式排序。"""
    if sort_mode == "name":
        return sorted(files, key=lambda f: f.name)
    elif sort_mode == "size":
        return sorted(files, key=lambda f: f.stat().st_size)
    elif sort_mode == "ext":
        return sorted(files, key=lambda f: (f.suffix.lower(), f.name))
    else:  # path
        return sorted(files)


def merge_files_to_document(
    root_path: Path,
    output_file: Path,
    *,
    include_hidden: bool,
    exclude_patterns: Sequence[str],
    only_text_files: bool,
    exclude_self: bool,
    script_path: Optional[Path],
    max_depth: Optional[int],
    exclude_dirs: Sequence[str],
    extensions: Sequence[str],
    add_header: bool,
    add_separator: bool,
    encoding: str,
    verbose: bool,
) -> Dict[str, int]:
    """将目录下文件合并到单个文档。"""
    root = root_path.resolve()
    stats = {
        "total_files": 0,
        "processed_files": 0,
        "skipped_files": 0,
        "excluded_files": 0,
        "encoding_errors": 0,
        "total_size": 0,
    }
    lines: List[str] = [
        "文件内容合并文档",
        "源目录: {}".format(root),
        "=" * 60,
        "",
    ]

    all_files = list(walk_directory(root, max_depth=max_depth, exclude_dirs=exclude_dirs))
    all_files = sort_files(all_files, "path")

    for file_path in all_files:
        if file_path.resolve() == output_file.resolve():
            continue
        if exclude_self and script_path and file_path.resolve() == script_path.resolve():
            stats["excluded_files"] += 1
            continue
        if not include_hidden and any(part.startswith(".") for part in file_path.relative_to(root).parts):
            stats["excluded_files"] += 1
            continue
        if should_exclude_file(file_path, exclude_patterns):
            stats["excluded_files"] += 1
            continue
        if extensions and file_path.suffix.lower() not in extensions:
            stats["skipped_files"] += 1
            continue
        if only_text_files and not is_text_file(file_path):
            stats["skipped_files"] += 1
            continue

        stats["total_files"] += 1
        content = read_file_content(file_path, encoding=encoding)
        if content is None:
            stats["encoding_errors"] += 1
            continue

        if add_header:
            lines.append(generate_file_header(file_path, root))
        lines.append(content.rstrip())
        lines.append("")
        if add_separator:
            lines.append("-" * 50)
            lines.append("")
        stats["processed_files"] += 1
        stats["total_size"] += len(content.encode("utf-8", errors="ignore"))

        if verbose:
            print("  [OK] {}".format(file_path.relative_to(root)))

    atomic_write_text(output_file, "\n".join(lines).rstrip() + "\n")
    return stats


def print_statistics(stats: Dict[str, int]) -> None:
    """打印统计信息。"""
    print("统计信息:")
    print("  总文件数: {}".format(stats["total_files"]))
    print("  已处理文件: {}".format(stats["processed_files"]))
    print("  跳过文件: {}".format(stats["skipped_files"]))
    print("  排除文件: {}".format(stats["excluded_files"]))
    print("  编码错误: {}".format(stats["encoding_errors"]))
    print("  总字符数: {:,}".format(stats["total_size"]))


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(description="将目录下所有 UTF-8 文件内容合并到一个文档中")
    parser.add_argument("path", nargs="?", default=".", help="要处理的目录路径")
    parser.add_argument("--files", nargs="*", default=[], help="要合并的具体文件路径列表（替代目录遍历）")
    parser.add_argument("-o", "--output", default="", help="输出文件路径")
    parser.add_argument("-a", "--all", action="store_true", help="包含隐藏文件和目录")
    parser.add_argument("-e", "--exclude", nargs="*", default=[], help="排除文件模式")
    parser.add_argument("-b", "--binary", action="store_true", help="包含二进制文件")
    parser.add_argument("--no-exclude-self", action="store_true", help="不排除脚本自身")
    parser.add_argument("--max-depth", type=int, default=None, help="最大递归深度")
    parser.add_argument("--exclude-dir", nargs="*", default=[], help="排除的目录名称")
    parser.add_argument("--extension", nargs="*", default=[], help="只合并这些扩展名的文件")
    parser.add_argument("--no-header", action="store_true", help="禁用文件头标记")
    parser.add_argument("--no-separator", action="store_true", help="禁用文件间分隔符")
    parser.add_argument("--sort", choices=["path", "name", "size", "ext"], default="path", help="排序方式")
    parser.add_argument("--dry-run", action="store_true", help="预览模式：只列出文件，不实际合并")
    parser.add_argument("--encoding", default="utf-8", help="主编码")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    # 文件列表模式：直接处理 --files 参数指定的文件
    if args.files:
        file_paths = [Path(f).resolve() for f in args.files if Path(f).exists()]
        if not file_paths:
            raise ValueError("--files 参数中的文件都不存在")
        output = Path(args.output) if args.output else make_log_text_path("upload", SCRIPTGEN_ROOT)
        ensure_directory(output.parent)
        
        if args.dry_run:
            print("预览模式 - 将要处理的文件:")
            for fp in file_paths:
                print("  {}".format(fp))
            return
        
        # 合并指定的文件列表
        lines: List[str] = [
            "文件内容合并文档",
            "源文件: {} 个".format(len(file_paths)),
            "=" * 60,
            "",
        ]
        stats = {"total_files": 0, "processed_files": 0, "skipped_files": 0, "excluded_files": 0, "encoding_errors": 0, "total_size": 0}
        
        for file_path in file_paths:
            stats["total_files"] += 1
            content = read_file_content(file_path, encoding=args.encoding)
            if content is None:
                stats["encoding_errors"] += 1
                continue
            if not args.no_header:
                lines.append("# {}".format(file_path))
            lines.append(content.rstrip())
            lines.append("")
            if not args.no_separator:
                lines.append("-" * 50)
                lines.append("")
            stats["processed_files"] += 1
            stats["total_size"] += len(content.encode("utf-8", errors="ignore"))
            if args.verbose:
                print("  [OK] {}".format(file_path))
        
        atomic_write_text(output, "\n".join(lines).rstrip() + "\n")
        print_statistics(stats)
        print_output(output)
        return

    # 目录模式：原有逻辑
    root = (PROJECT_ROOT / args.path).resolve() if not Path(args.path).is_absolute() else Path(args.path)
    if not root.exists() or not root.is_dir():
        raise ValueError("指定路径不是目录: {}".format(root))

    output = Path(args.output) if args.output else make_log_text_path("upload", SCRIPTGEN_ROOT)
    ensure_directory(output.parent)
    script_path = Path(__file__).resolve() if not args.no_exclude_self else None

    if args.dry_run:
        print("预览模式 - 将要处理的文件:")
        for file_path in walk_directory(root, max_depth=args.max_depth, exclude_dirs=args.exclude_dir):
            if file_path.resolve() == output.resolve():
                continue
            if script_path and file_path.resolve() == script_path.resolve():
                continue
            if not args.all and any(part.startswith(".") for part in file_path.relative_to(root).parts):
                continue
            if should_exclude_file(file_path, args.exclude):
                continue
            if args.extension and file_path.suffix.lower() not in args.extension:
                continue
            if not args.binary and not is_text_file(file_path):
                continue
            print("  {}".format(file_path.relative_to(root)))
        return

    stats = merge_files_to_document(
        root,
        output,
        include_hidden=args.all,
        exclude_patterns=args.exclude,
        only_text_files=not args.binary,
        exclude_self=not args.no_exclude_self,
        script_path=script_path,
        max_depth=args.max_depth,
        exclude_dirs=args.exclude_dir,
        extensions=args.extension,
        add_header=not args.no_header,
        add_separator=not args.no_separator,
        encoding=args.encoding,
        verbose=args.verbose,
    )
    print_statistics(stats)
    print_output(output)


if __name__ == "__main__":
    main()
