from __future__ import annotations

"""Ollama 服务器在线发现与验证。"""

import concurrent.futures
import re
import time
from typing import Any, Dict, List, Optional

import requests

from src.logger import get_logger
from .constants import (
    BASE_URL,
    MAX_WORKERS,
    PAGE_SIZE,
    TIMEOUT,
)
from .detect import detect_capabilities

logger = get_logger(__name__)


def _fetch_page(page: int) -> Optional[str]:
    """获取指定页面的 HTML 内容。

    Args:
        page: 页码。

    Returns:
        HTML 字符串或 None。
    """
    try:
        r = requests.get(
            "{}?page={}&page_size={}".format(BASE_URL, page, PAGE_SIZE),
            timeout=TIMEOUT,
            verify=False,
        )
        if r.ok:
            return r.text
        return None
    except Exception:
        return None


def _parse_pages(html: str) -> int:
    """从 HTML 中解析总页数。

    Args:
        html: 首页 HTML 内容。

    Returns:
        总页数。
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        pag = soup.find("ul", class_="pagination")
        if not pag:
            return 1
        mx = 1
        for a in pag.find_all("a", class_="page-link"):
            m = re.search(r"page=(\d+)", a.get("href", ""))
            if m:
                mx = max(mx, int(m.group(1)))
        return mx
    except Exception:
        return 1


def _parse_ips(html: str) -> List[str]:
    """从 HTML 中提取服务器 IP 列表。

    Args:
        html: 页面 HTML 内容。

    Returns:
        IP 地址列表。
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        ips: List[str] = []
        for btn in soup.find_all("button", onclick=True):
            m = re.search(
                r"copyToClipboard\('([^']+)'\)",
                btn.get("onclick", ""),
            )
            if m:
                ips.append(m.group(1))
        return ips
    except Exception:
        return []


def _show_model(base: str, name: str) -> Optional[Dict[str, Any]]:
    """查询模型详情。

    Args:
        base: 服务器基础 URL。
        name: 模型名称。

    Returns:
        模型详情字典或 None。
    """
    try:
        r = requests.post(
            "{}/api/show".format(base),
            json={"name": name},
            timeout=TIMEOUT,
            verify=False,
        )
        if r.ok:
            return r.json()
        return None
    except Exception:
        return None


def _verify_server(ip: str) -> Optional[Dict[str, Any]]:
    """验证单个服务器并获取模型列表。

    Args:
        ip: 服务器 IP（含端口）。

    Returns:
        服务器信息字典或 None。
    """
    base = "http://{}".format(ip)
    try:
        r = requests.get(base, timeout=TIMEOUT)
        if "ollama" not in r.text.lower():
            return None
    except Exception:
        return None

    try:
        r = requests.get("{}/api/tags".format(base), timeout=TIMEOUT)
        models = r.json().get("models", [])
        if not models:
            return None
    except Exception:
        return None

    infos: List[Dict[str, Any]] = []
    for m in models:
        name = m.get("name", "")
        if not name:
            continue
        detail = _show_model(base, name)
        _det = m.get("details") or {}
        infos.append({
            "name": name,
            "size": m.get("size", 0),
            "capabilities": detect_capabilities(detail),
            "family": _det.get("family") or "",
            "parameter_size": _det.get("parameter_size") or "",
        })

    return {
        "ip": ip,
        "base_url": base,
        "models": infos,
        "model_names": [m["name"] for m in infos],
        "verified_at": time.time(),
    }


def collect_servers(
    additional: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """收集所有可用的 Ollama 服务器。

    从在线列表抓取 + 附加服务器列表合并后并发验证。

    Args:
        additional: 附加服务器 IP 列表。

    Returns:
        服务器字典 {ip: server_info}。
    """
    all_ips: List[str] = []
    html = _fetch_page(1)
    if html:
        pages = _parse_pages(html)
        all_ips.extend(_parse_ips(html))

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
            futs = {
                ex.submit(_fetch_page, p): p
                for p in range(2, pages + 1)
            }
            for f in concurrent.futures.as_completed(futs):
                r = f.result()
                if r:
                    all_ips.extend(_parse_ips(r))

    all_ips = list(set(all_ips))

    if additional:
        for s in additional:
            if s and s not in all_ips:
                all_ips.append(s)

    result: Dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_verify_server, ip): ip for ip in all_ips}
        for f in concurrent.futures.as_completed(futs):
            try:
                info = f.result()
                if info:
                    result[info["ip"]] = info
            except Exception as e:
                logger.debug("验证服务器 %s 失败: %s", futs[f], e)

    return result
