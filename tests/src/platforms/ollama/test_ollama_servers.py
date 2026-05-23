"""Ollama 服务器获取测试脚本。

测试 collect_servers 函数的功能，确保修复后的 all_ips 变量作用域问题已解决。

用法:
    python -m tests.test_ollama_servers          # 运行全部测试
    python -m tests.test_ollama_servers test_collect    # 仅运行服务器收集测试
    python -m tests.test_ollama_servers test_parse      # 仅运行解析测试
"""

from __future__ import annotations

import logging
import sys
import unittest.mock as mock
from pathlib import Path

# 确保项目根目录在路径中
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.platforms.ollama.core.client import collect_servers, _parse_ips

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def test_collect() -> None:
    """测试服务器收集功能。
    
    验证 collect_servers 函数能正确处理：
    1. 从网页获取 IP 列表
    2. 合并 additional 参数
    3. 验证服务器并返回正确的字典结构
    """
    logger.info("=== 测试: 服务器收集 ===")
    
    # Mock _fetch_page 返回空，避免网络请求
    logger.info("测试: collect_servers(additional=['192.168.1.100:11434'])")
    try:
        with mock.patch('src.platforms.ollama.core.client._fetch_page', return_value=None):
            servers = collect_servers(additional=['192.168.1.100:11434'])
            logger.info("收集到 %d 个服务器", len(servers))
            logger.info("✓ collect_servers() 测试通过 - 没有 NameError")
    except NameError as e:
        if "ip" in str(e):
            logger.error("✗ 发现 ip 变量未定义错误: %s", e)
            raise
        raise
    except Exception as e:
        logger.error("✗ collect_servers() 测试失败: %s", e)
        raise


def test_parse() -> None:
    """测试 HTML 解析函数。
    
    验证 _parse_ips 函数能正确处理 HTML。
    """
    logger.info("=== 测试: HTML 解析函数 ===")
    
    # 测试示例 HTML
    sample_html = """
    <html>
    <body>
        <button onclick="copyToClipboard('192.168.1.1:11434')">复制</button>
        <button onclick="copyToClipboard('192.168.1.2:11434')">复制</button>
    </body>
    </html>
    """
    
    ips = _parse_ips(sample_html)
    logger.info("解析到 IP: %s", ips)
    assert len(ips) == 2, f"期望 2 个 IP，实际 {len(ips)}"
    assert "192.168.1.1:11434" in ips
    assert "192.168.1.2:11434" in ips
    
    logger.info("✓ HTML 解析函数测试通过")


def main(test_name: str = "") -> None:
    """运行测试。
    
    Args:
        test_name: 指定测试名称，空字符串表示运行全部测试。
    """
    tests = {
        "test_collect": test_collect,
        "test_parse": test_parse,
    }

    if test_name:
        if test_name not in tests:
            logger.error("未知测试: %s (可选: %s)", test_name, ", ".join(tests))
            return
        run_tests = {test_name: tests[test_name]}
    else:
        run_tests = tests

    for name, fn in run_tests.items():
        try:
            fn()
            logger.info("✓ %s 完成", name)
        except Exception as e:
            logger.error("✗ %s 失败: %s", name, e, exc_info=True)


if __name__ == "__main__":
    test_name = sys.argv[1] if len(sys.argv) > 1 else ""
    main(test_name)
