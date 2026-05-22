"""
Ollama 服务器发现模块 - 扫描并验证可用的 Ollama 服务器
版本: 1.0.0

功能:
- 从 freeollama.oneplus1.top 抓取服务器列表
- 并发验证服务器可用性
- 通过 /api/tags 端点获取每个服务器的模型列表及详细信息
- 通过 /api/show 端点获取模型能力（是否支持视觉等）
- 支持定期刷新（24小时间隔）
- 结果持久化到 JSON 文件
"""

import concurrent.futures
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ollama_servers")

# ==================== 常量 ====================

BASE_URL = "https://freeollama.oneplus1.top/"
PAGE_SIZE = 100
TIMEOUT = 10
MAX_WORKERS = 512
REFRESH_INTERVAL = 24 * 60 * 60  # 24小时

# 持久化路径
DATA_DIR = Path("data")
SERVERS_FILE = DATA_DIR / "ollama_servers.json"
MODELS_REGISTRY_FILE = DATA_DIR / "ollama_models_registry.json"


# ==================== 服务器模型详细信息 ====================


def _is_idle() -> bool:
    """检查是否在 idle 环境中运行"""
    return "idlelib" in sys.modules


def fetch_page(page: int, search_query: str = "") -> Optional[str]:
    """获取指定页面的 HTML 内容

    Args:
        page: 页码
        search_query: 搜索关键词

    Returns:
        HTML 文本或 None
    """
    if search_query:
        url = (
            f"{BASE_URL}?search={search_query}"
            f"&page={page}&page_size={PAGE_SIZE}"
        )
    else:
        url = f"{BASE_URL}?page={page}&page_size={PAGE_SIZE}"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.debug("获取第 %d 页失败: %s", page, exc)
        return None


def parse_total_pages(html: str) -> int:
    """从 HTML 中解析总页数

    Args:
        html: HTML 文本

    Returns:
        总页数
    """
    soup = BeautifulSoup(html, "html.parser")
    pagination = soup.find("ul", class_="pagination")
    if not pagination:
        return 1
    page_links = pagination.find_all("a", class_="page-link")
    max_page = 1
    for link in page_links:
        href = link.get("href", "")
        match = re.search(r"page=(\d+)", href)
        if match:
            num = int(match.group(1))
            if num > max_page:
                max_page = num
    return max_page


def parse_ips_from_html(html: str) -> List[str]:
    """从 HTML 中解析服务器 IP 地址

    Args:
        html: HTML 文本

    Returns:
        IP 地址列表
    """
    soup = BeautifulSoup(html, "html.parser")
    ips: List[str] = []
    for btn in soup.find_all("button", onclick=True):
        onclick = btn.get("onclick", "")
        match = re.search(r"copyToClipboard\('([^']+)'\)", onclick)
        if match:
            ips.append(match.group(1))
    return ips


def get_model_details(
    base_url: str, model_name: str
) -> Optional[Dict[str, Any]]:
    """通过 /api/show 端点获取模型详细信息

    Args:
        base_url: 服务器基础 URL
        model_name: 模型名称

    Returns:
        模型详细信息字典或 None
    """
    try:
        resp = requests.post(
            f"{base_url}/api/show",
            json={"name": model_name},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def detect_model_capabilities(
    model_detail: Optional[Dict[str, Any]],
) -> Dict[str, bool]:
    """从模型详情中检测模型能力

    通过 /api/show 返回的 model_info 和 template 字段判断模型能力。
    不依赖模型名称进行硬编码判断。

    Args:
        model_detail: /api/show 返回的模型详情

    Returns:
        能力字典，包含 vision, embedding, tools 等布尔值
    """
    capabilities: Dict[str, bool] = {
        "chat": True,
        "vision": False,
        "embedding": False,
        "tools": False,
        "code": False,
    }

    if not model_detail:
        return capabilities

    # 检查 model_info 中的 projector 相关字段（视觉模型特征）
    model_info = model_detail.get("model_info", {})
    if model_info:
        for key in model_info:
            key_lower = key.lower()
            # 视觉模型通常有 vision 或 projector 相关的张量
            if "vision" in key_lower or "projector" in key_lower:
                capabilities["vision"] = True
                break
            # 多模态编码器
            if "mmproj" in key_lower or "clip" in key_lower:
                capabilities["vision"] = True
                break

    # 检查 template 中是否有 tools 支持标记
    template = model_detail.get("template", "")
    if template:
        template_lower = template.lower()
        if "tools" in template_lower or ".Tools" in template:
            capabilities["tools"] = True

    # 检查 modelfile 中的参数
    details = model_detail.get("details", {})
    if details:
        families = details.get("families", [])
        if families:
            for family in families:
                family_lower = family.lower()
                if "clip" in family_lower or "vision" in family_lower:
                    capabilities["vision"] = True

    # 检查 parameters 字段
    parameters = model_detail.get("parameters", "")
    if parameters and "embedding" in parameters.lower():
        capabilities["embedding"] = True

    return capabilities


def verify_and_get_models(
    ip: str,
) -> Optional[Dict[str, Any]]:
    """验证服务器可用性并获取模型列表及详细信息

    Args:
        ip: 服务器 IP 地址（含端口）

    Returns:
        包含模型列表和能力信息的字典，或 None
    """
    base = f"http://{ip}"

    # 验证 Ollama 服务是否运行
    try:
        resp = requests.get(base, timeout=TIMEOUT)
        if "ollama is running" not in resp.text.lower():
            return None
    except Exception:
        return None

    # 通过 /api/tags 获取模型列表
    try:
        resp = requests.get(f"{base}/api/tags", timeout=TIMEOUT)
        data = resp.json()
        raw_models = data.get("models", [])
        if not raw_models:
            return None
    except Exception:
        return None

    models_info: List[Dict[str, Any]] = []
    for model_entry in raw_models:
        model_name = model_entry.get("name", "")
        if not model_name:
            continue

        # 基础模型信息（来自 /api/tags）
        model_data: Dict[str, Any] = {
            "name": model_name,
            "size": model_entry.get("size", 0),
            "digest": model_entry.get("digest", ""),
            "modified_at": model_entry.get("modified_at", ""),
            "details": model_entry.get("details", {}),
        }

        # 获取详细能力信息（来自 /api/show）
        detail = get_model_details(base, model_name)
        caps = detect_model_capabilities(detail)
        model_data["capabilities"] = caps

        # 从 details 中提取参数规模等信息
        details = model_entry.get("details", {})
        if details:
            model_data["family"] = details.get("family", "")
            model_data["parameter_size"] = details.get(
                "parameter_size", ""
            )
            model_data["quantization_level"] = details.get(
                "quantization_level", ""
            )
            model_data["families"] = details.get("families", [])

        models_info.append(model_data)

    return {
        "ip": ip,
        "base_url": base,
        "models": models_info,
        "model_names": [m["name"] for m in models_info],
        "verified_at": time.time(),
    }


def collect_all_servers(search_query: str = "") -> Dict[str, Any]:
    """收集所有可用的 Ollama 服务器及其模型信息

    Args:
        search_query: 可选的搜索关键词

    Returns:
        以 IP 为键的服务器信息字典
    """
    idle = _is_idle()

    first_html = fetch_page(1, search_query)
    if not first_html:
        logger.error("获取第 1 页失败")
        return {}

    total_pages = parse_total_pages(first_html)
    if idle:
        print(f"实时检测进度：已处理第 1 页，共 {total_pages} 页")

    all_ips: List[str] = parse_ips_from_html(first_html)

    page_bar = None
    if not idle:
        try:
            from tqdm import tqdm

            page_bar = tqdm(total=total_pages, desc="获取页面", unit="页")
            page_bar.update(1)
        except ImportError:
            page_bar = None

    def fetch_and_parse(page: int) -> List[str]:
        """获取并解析指定页面的 IP 列表"""
        html = fetch_page(page, search_query)
        if html:
            return parse_ips_from_html(html)
        return []

    remaining_pages = list(range(2, total_pages + 1))
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=20
    ) as executor:
        futures = {
            executor.submit(fetch_and_parse, p): p
            for p in remaining_pages
        }
        for future in concurrent.futures.as_completed(futures):
            page_num = futures[future]
            try:
                ips = future.result()
                all_ips.extend(ips)
            except Exception as exc:
                logger.warning("获取第 %d 页异常: %s", page_num, exc)
            if idle:
                print(
                    f"实时检测进度：已处理第 {page_num} 页，"
                    f"共 {total_pages} 页"
                )
            elif page_bar:
                page_bar.update(1)

    if page_bar:
        page_bar.close()

    all_ips = list(set(all_ips))
    result: Dict[str, Any] = {}

    if idle:
        print(f"\n开始验证 {len(all_ips)} 个服务...")

    verify_bar = None
    if not idle:
        try:
            from tqdm import tqdm

            verify_bar = tqdm(
                total=len(all_ips), desc="验证服务", unit="个"
            )
        except ImportError:
            verify_bar = None

    verified_count = 0
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:
        futures = {
            executor.submit(verify_and_get_models, ip): ip
            for ip in all_ips
        }
        for future in concurrent.futures.as_completed(futures):
            ip = futures[future]
            verified_count += 1
            try:
                server_info = future.result()
                if server_info is not None:
                    result[ip] = server_info
            except Exception as exc:
                logger.debug("验证服务器 %s 异常: %s", ip, exc)
            if idle:
                print(
                    f"实时检测进度：已验证 "
                    f"{verified_count}/{len(all_ips)} 个服务"
                )
            elif verify_bar:
                verify_bar.update(1)

    if verify_bar:
        verify_bar.close()

    return result


def build_models_registry(
    servers: Dict[str, Any],
) -> Dict[str, Any]:
    """构建模型注册表 - 按模型名称索引，记录哪些服务器提供该模型

    Args:
        servers: 以 IP 为键的服务器信息字典

    Returns:
        以模型名称为键的注册表字典，包含:
        - servers: 提供该模型的服务器列表
        - capabilities: 模型能力（取多个服务器的并集）
        - details: 模型详情
    """
    registry: Dict[str, Any] = {}

    for ip, server_info in servers.items():
        base_url = server_info.get("base_url", f"http://{ip}")
        models = server_info.get("models", [])

        for model in models:
            model_name = model.get("name", "")
            if not model_name:
                continue

            if model_name not in registry:
                registry[model_name] = {
                    "servers": [],
                    "capabilities": model.get(
                        "capabilities",
                        {"chat": True, "vision": False},
                    ),
                    "family": model.get("family", ""),
                    "parameter_size": model.get("parameter_size", ""),
                    "quantization_level": model.get(
                        "quantization_level", ""
                    ),
                    "families": model.get("families", []),
                }

            registry[model_name]["servers"].append(
                {
                    "ip": ip,
                    "base_url": base_url,
                    "verified_at": server_info.get(
                        "verified_at", time.time()
                    ),
                }
            )

            # 合并能力（取并集）
            caps = model.get("capabilities", {})
            existing_caps = registry[model_name]["capabilities"]
            for key, value in caps.items():
                if value:
                    existing_caps[key] = True

    return registry


def save_servers_data(
    servers: Dict[str, Any],
    registry: Dict[str, Any],
) -> None:
    """持久化服务器数据和模型注册表

    Args:
        servers: 服务器信息字典
        registry: 模型注册表
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    servers_data = {
        "servers": servers,
        "last_refresh": time.time(),
        "server_count": len(servers),
        "total_models": sum(
            len(s.get("model_names", []))
            for s in servers.values()
        ),
    }

    registry_data = {
        "models": registry,
        "last_refresh": time.time(),
        "unique_model_count": len(registry),
    }

    # 原子写入
    temp_servers = str(SERVERS_FILE) + ".tmp"
    with open(temp_servers, "w", encoding="utf-8") as f:
        json.dump(servers_data, f, ensure_ascii=False, indent=2)
    os.replace(temp_servers, str(SERVERS_FILE))

    temp_registry = str(MODELS_REGISTRY_FILE) + ".tmp"
    with open(temp_registry, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, ensure_ascii=False, indent=2)
    os.replace(temp_registry, str(MODELS_REGISTRY_FILE))

    logger.info(
        "数据已保存: %d 个服务器, %d 个独立模型",
        len(servers),
        len(registry),
    )


def load_servers_data() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """加载持久化的服务器数据和模型注册表

    Returns:
        (servers, registry) 元组
    """
    servers: Dict[str, Any] = {}
    registry: Dict[str, Any] = {}

    if SERVERS_FILE.exists():
        try:
            with open(SERVERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                servers = data.get("servers", {})
                last_refresh = data.get("last_refresh", 0)
                logger.info(
                    "从磁盘加载 %d 个服务器 (上次刷新: %s)",
                    len(servers),
                    time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(last_refresh),
                    ),
                )
        except Exception as exc:
            logger.warning("加载服务器数据失败: %s", exc)

    if MODELS_REGISTRY_FILE.exists():
        try:
            with open(
                MODELS_REGISTRY_FILE, "r", encoding="utf-8"
            ) as f:
                data = json.load(f)
                registry = data.get("models", {})
                logger.info(
                    "从磁盘加载 %d 个模型注册表",
                    len(registry),
                )
        except Exception as exc:
            logger.warning("加载模型注册表失败: %s", exc)

    return servers, registry


def needs_refresh() -> bool:
    """检查是否需要刷新服务器列表

    Returns:
        True 表示需要刷新
    """
    if not SERVERS_FILE.exists():
        return True

    try:
        with open(SERVERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            last_refresh = data.get("last_refresh", 0)
            elapsed = time.time() - last_refresh
            return elapsed >= REFRESH_INTERVAL
    except Exception:
        return True


def refresh_servers(
    force: bool = False,
    search_query: str = "",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """刷新服务器列表（同步方法）

    Args:
        force: 是否强制刷新
        search_query: 搜索关键词

    Returns:
        (servers, registry) 元组
    """
    if not force and not needs_refresh():
        logger.info("服务器列表未过期，使用缓存数据")
        return load_servers_data()

    logger.info("开始刷新 Ollama 服务器列表...")
    start_time = time.time()

    servers = collect_all_servers(search_query)
    registry = build_models_registry(servers)
    save_servers_data(servers, registry)

    elapsed = time.time() - start_time
    logger.info(
        "服务器刷新完成: %d 个服务器, %d 个独立模型, 耗时 %.1f 秒",
        len(servers),
        len(registry),
        elapsed,
    )

    return servers, registry


if __name__ == "__main__":
    servers_result = collect_all_servers()
    registry_result = build_models_registry(servers_result)
    save_servers_data(servers_result, registry_result)

    print(
        f"\n共发现 {len(servers_result)} 个可用 Ollama 服务，"
        f"{len(registry_result)} 个独立模型"
    )

    # 打印模型统计
    for model_name, info in sorted(registry_result.items()):
        server_count = len(info.get("servers", []))
        caps = info.get("capabilities", {})
        caps_str = ", ".join(
            k for k, v in caps.items() if v
        )
        print(
            f"  {model_name}: {server_count} 个服务器 "
            f"[{caps_str}]"
        )