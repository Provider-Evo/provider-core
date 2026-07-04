# -*- coding: utf-8 -*-
"""命令行解析与主入口模块。

提供 ``_parse_cli_args`` 参数解析函数和 ``main`` 主入口函数,
支持 --test / --demo / upload / download 等子命令。
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import textwrap
import traceback
from typing import Any

from .client import _HAS_CRYPTO_DEPS, WenShuShuClient
from .container import Config
from .demo import _run_demo
from .exceptions import (
    ConfigurationError,
    DomainError,
    ExternalServiceError,
    UseCaseError,
    ValidationError,
)
from .logging_setup import setup_logging
from .testing import _get_all_test_classes, _run_tests

# ---------------------------------------------------------------------------
# 退出码常量
# ---------------------------------------------------------------------------
EXIT_SUCCESS = 0
EXIT_TEST_FAIL = 1
EXIT_CONFIG_ERROR = 2
EXIT_BUSINESS_ERROR = 3
EXIT_UNKNOWN_ERROR = 4

# ---------------------------------------------------------------------------
# 版本（与包 __init__.py 保持一致）
# ---------------------------------------------------------------------------
__version__ = "2.2.48"


def _parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 命令行参数列表,为 None 时使用 sys.argv。

    Returns:
        解析后的命名空间。
    """
    parser = argparse.ArgumentParser(
        prog="use_wenshushu",
        description="文叔叔(wenshushu.cn)文件传输工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            使用示例:
              python use_wenshushu.py upload "file.exe"
              python use_wenshushu.py download "https://www.wenshushu.cn/f/xxx"
              python use_wenshushu.py --test
              python use_wenshushu.py --demo
        """),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--test", action="store_true", help="仅运行内嵌测试")
    parser.add_argument("--demo", action="store_true", help="仅运行功能演示")
    parser.add_argument("--verbose", "-v", action="store_true", help="DEBUG 级别日志")
    parser.add_argument("--dry-run", action="store_true", help="解析参数但不执行")
    parser.add_argument("--config", action="append", metavar="K=V", default=[], help="覆盖配置项(可多次)")
    parser.add_argument("--log-file", metavar="PATH", help="日志输出到文件")
    parser.add_argument("command", nargs="?", choices=["upload", "u", "download", "d"], help="操作命令")
    parser.add_argument("target", nargs="?", help="文件路径(上传)或 URL(下载)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """主入口: 解析 CLI -> 初始化日志 -> 调度测试/演示/上传/下载 -> 返回退出码。

    Args:
        argv: 命令行参数列表。

    Returns:
        退出码。
    """
    args = _parse_cli_args(argv)

    # 构建配置
    config_overrides: dict[str, Any] = {}
    for kv in args.config:
        if "=" in kv:
            k, v = kv.split("=", 1)
            config_overrides[k.strip()] = v.strip()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    config_overrides.setdefault("log_level", "DEBUG" if args.verbose else "INFO")
    if args.log_file:
        config_overrides["log_file"] = args.log_file

    try:
        cfg = Config.from_env().override(**{k: v for k, v in config_overrides.items() if hasattr(Config, k)})
        cfg.validate()
    except ConfigurationError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    setup_logging(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        log_file=cfg.log_file,
    )

    if args.dry_run:
        print("dry_run 模式: 参数解析成功,不执行任何操作")
        print(f"  命令: {args.command}")
        print(f"  目标: {args.target}")
        print(f"  配置: {cfg.to_dict()}")
        return EXIT_SUCCESS

    # 无参数时默认运行测试+演示
    run_test = args.test or (not args.command and not args.demo)
    run_demo = args.demo or (not args.command and not args.test)

    if args.test and not args.command:
        run_demo = False
    if args.demo and not args.command:
        run_test = False

    test_passed = True
    if run_test:
        test_passed = _run_tests()

    if run_demo:
        _run_demo()

    if args.command:
        if not _HAS_CRYPTO_DEPS:
            print("错误: 执行上传/下载功能需要安装依赖:", file=sys.stderr)
            print("  pip install requests base58 pycryptodomex", file=sys.stderr)
            return EXIT_CONFIG_ERROR

        if not args.target:
            print("错误: 请提供文件路径(上传)或 URL(下载)", file=sys.stderr)
            return EXIT_CONFIG_ERROR

        try:
            client = WenShuShuClient(cfg)
            if args.command in ("upload", "u"):
                if not os.path.isfile(args.target):
                    print(f"错误: 文件不存在: {args.target}", file=sys.stderr)
                    return EXIT_CONFIG_ERROR
                client.upload(args.target)
            elif args.command in ("download", "d"):
                client.download(args.target)
            return EXIT_SUCCESS
        except (ValidationError, ConfigurationError) as exc:
            print(f"参数/配置错误: {exc}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
        except (ExternalServiceError, UseCaseError, DomainError) as exc:
            print(f"业务错误: {exc}", file=sys.stderr)
            traceback.print_exc()
            return EXIT_BUSINESS_ERROR
        except Exception as exc:
            print(f"未知错误: {exc}", file=sys.stderr)
            traceback.print_exc()
            return EXIT_UNKNOWN_ERROR

    if run_test and not test_passed:
        return EXIT_TEST_FAIL

    return EXIT_SUCCESS
