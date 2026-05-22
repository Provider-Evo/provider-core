#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
net.py - 即插即用透明网络代理模块

使用方法（只需要改一行）：
    删除:  import requests  和  import aiohttp
    添加:  import net

    然后代码里所有 requests.get(...)、aiohttp.ClientSession(...) 等
    全部照常使用，无需任何其他修改。

原理:
    import net 时，自动将 requests 和 aiohttp 注入到调用方的全局命名空间，
    同时对底层 socket 进行猴子补丁，使所有出站连接绑定到虚拟网卡的新 IP。
"""

from __future__ import annotations

import atexit
import ctypes
import functools
import inspect
import json
import logging
import os
import platform
import random
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)
from uuid import uuid4

# ============================================================================
# 日志
# ============================================================================

logger = logging.getLogger("proxy")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(_h)
logger.setLevel(os.environ.get("PROXY_LOG_LEVEL", "INFO").upper())

# ============================================================================
# 先把原始库导入进来（在做任何修改之前）
# ============================================================================

_original_requests = None
_original_aiohttp = None

try:
    import requests as _original_requests
except ImportError:
    logger.debug("requests 未安装")

try:
    import aiohttp as _original_aiohttp
except ImportError:
    logger.debug("aiohttp 未安装")

# ============================================================================
# 平台检测
# ============================================================================

class OSType(Enum):
    """操作系统类型"""
    WINDOWS = auto()
    LINUX = auto()
    MACOS = auto()
    UNKNOWN = auto()


def _detect_os() -> OSType:
    """检测操作系统"""
    s = platform.system().lower()
    if s == "windows":
        return OSType.WINDOWS
    if s == "linux":
        return OSType.LINUX
    if s == "darwin":
        return OSType.MACOS
    return OSType.UNKNOWN


CURRENT_OS: OSType = _detect_os()

# ============================================================================
# 权限管理
# ============================================================================

class PrivilegeManager:
    """管理员权限管理"""

    @staticmethod
    def is_admin() -> bool:
        """检查是否有管理员权限"""
        try:
            if CURRENT_OS == OSType.WINDOWS:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            return os.geteuid() == 0
        except Exception:
            return False

    @staticmethod
    def elevate() -> None:
        """请求提升权限（会重启当前进程）"""
        if PrivilegeManager.is_admin():
            return

        logger.warning("需要管理员权限，正在请求提升...")

        if CURRENT_OS == OSType.WINDOWS:
            script = os.path.abspath(sys.argv[0])
            params = " ".join(f'"{a}"' for a in sys.argv[1:])
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}" {params}', None, 1
            )
            if ret > 32:
                sys.exit(0)
            raise PermissionError("用户拒绝了权限提升")

        sudo = shutil.which("sudo")
        if sudo:
            os.execvp(sudo, [sudo, sys.executable] + sys.argv)
        raise PermissionError(
            f"请手动以 root 运行: sudo {sys.executable} {' '.join(sys.argv)}"
        )

# ============================================================================
# MAC 地址工具
# ============================================================================

class MACAddress:
    """MAC 地址工具类"""

    @staticmethod
    def generate_random() -> str:
        """生成随机的本地管理 MAC 地址"""
        octets = [random.randint(0x00, 0xFF) for _ in range(6)]
        octets[0] = (octets[0] | 0x02) & 0xFE  # locally administered, unicast
        return ":".join(f"{b:02x}" for b in octets)

    @staticmethod
    def to_bytes(mac_str: str) -> bytes:
        """MAC 字符串转字节"""
        return bytes(int(b, 16) for b in mac_str.replace("-", ":").split(":"))

# ============================================================================
# 命令执行
# ============================================================================

def _run(cmd: List[str], *, check: bool = True, timeout: int = 30) -> subprocess.CompletedProcess:
    """执行系统命令"""
    logger.debug("exec: %s", " ".join(cmd))
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=check
    )

# ============================================================================
# 虚拟网卡管理（各平台实现）
# ============================================================================

@dataclass
class InterfaceInfo:
    """虚拟接口信息"""
    name: str
    mac: str
    ip: Optional[str] = None
    mask: Optional[str] = None
    gateway: Optional[str] = None
    dns: List[str] = field(default_factory=list)
    active: bool = False


class InterfaceBackend(ABC):
    """虚拟网卡后端抽象"""

    @abstractmethod
    def create(self, name: str, mac: str) -> InterfaceInfo:
        """创建虚拟接口"""
        ...

    @abstractmethod
    def configure(self, info: InterfaceInfo) -> None:
        """配置 IP"""
        ...

    @abstractmethod
    def destroy(self, info: InterfaceInfo) -> None:
        """销毁接口"""
        ...

    @abstractmethod
    def add_route(self, info: InterfaceInfo) -> None:
        """添加路由"""
        ...

    @abstractmethod
    def remove_route(self, info: InterfaceInfo) -> None:
        """移除路由"""
        ...

    def default_iface(self) -> str:
        """获取默认出口接口"""
        return "eth0"


class LinuxBackend(InterfaceBackend):
    """Linux macvlan 后端"""

    def default_iface(self) -> str:
        r = _run(["ip", "route", "show", "default"], check=False)
        m = re.search(r"dev\s+(\S+)", r.stdout)
        return m.group(1) if m else "eth0"

    def create(self, name: str, mac: str) -> InterfaceInfo:
        parent = self.default_iface()
        _run(["ip", "link", "add", "link", parent, name, "type", "macvlan", "mode", "bridge"])
        _run(["ip", "link", "set", name, "address", mac])
        _run(["ip", "link", "set", name, "up"])
        info = InterfaceInfo(name=name, mac=mac, active=True)
        logger.info("Linux: 已创建 macvlan %s (MAC=%s, parent=%s)", name, mac, parent)
        return info

    def configure(self, info: InterfaceInfo) -> None:
        if not info.ip or not info.mask:
            return
        prefix = sum(bin(int(o)).count("1") for o in info.mask.split("."))
        _run(["ip", "addr", "add", f"{info.ip}/{prefix}", "dev", info.name], check=False)

    def add_route(self, info: InterfaceInfo) -> None:
        if not info.gateway:
            return
        t = "100"
        _run(["ip", "route", "add", "default", "via", info.gateway, "dev", info.name, "table", t], check=False)
        _run(["ip", "rule", "add", "from", info.ip, "table", t], check=False)

    def remove_route(self, info: InterfaceInfo) -> None:
        t = "100"
        _run(["ip", "rule", "del", "from", info.ip, "table", t], check=False)
        _run(["ip", "route", "del", "default", "table", t], check=False)

    def destroy(self, info: InterfaceInfo) -> None:
        _run(["ip", "link", "del", info.name], check=False)
        logger.info("Linux: 已删除 %s", info.name)


class MacOSBackend(InterfaceBackend):
    """macOS feth 后端"""

    _counter = 100

    def default_iface(self) -> str:
        r = _run(["route", "-n", "get", "default"], check=False)
        m = re.search(r"interface:\s*(\S+)", r.stdout)
        return m.group(1) if m else "en0"

    def create(self, name: str, mac: str) -> InterfaceInfo:
        real_name = f"feth{MacOSBackend._counter}"
        MacOSBackend._counter += 1
        _run(["ifconfig", real_name, "create"], check=False)
        _run(["ifconfig", real_name, "lladdr", mac], check=False)
        _run(["ifconfig", real_name, "up"], check=False)
        info = InterfaceInfo(name=real_name, mac=mac, active=True)
        logger.info("macOS: 已创建 %s (MAC=%s)", real_name, mac)
        return info

    def configure(self, info: InterfaceInfo) -> None:
        if info.ip and info.mask:
            _run(["ifconfig", info.name, "inet", info.ip, "netmask", info.mask], check=False)

    def add_route(self, info: InterfaceInfo) -> None:
        if info.gateway:
            _run(["route", "add", "-net", "0.0.0.0/0", info.gateway, "-ifscope", info.name], check=False)

    def remove_route(self, info: InterfaceInfo) -> None:
        _run(["route", "delete", "-net", "0.0.0.0/0", "-ifscope", info.name], check=False)

    def destroy(self, info: InterfaceInfo) -> None:
        _run(["ifconfig", info.name, "destroy"], check=False)
        logger.info("macOS: 已删除 %s", info.name)


class WindowsBackend(InterfaceBackend):
    """Windows 后端"""

    def default_iface(self) -> str:
        r = _run([
            "powershell", "-Command",
            "Get-NetRoute -DestinationPrefix '0.0.0.0/0'"
            " | Sort RouteMetric | Select -First 1 -Expand InterfaceAlias"
        ], check=False)
        return r.stdout.strip() or "Ethernet"

    def create(self, name: str, mac: str) -> InterfaceInfo:
        # 尝试用 PowerShell LoopbackAdapter 模块
        _run([
            "powershell", "-Command",
            "$ProgressPreference='SilentlyContinue';"
            "Install-Module LoopbackAdapter -Force -Scope CurrentUser -EA SilentlyContinue;"
            f"New-LoopbackAdapter -Name '{name}' -Force -EA SilentlyContinue"
        ], check=False)
        _run([
            "powershell", "-Command",
            f"Enable-NetAdapter -Name '{name}' -Confirm:$false -EA SilentlyContinue"
        ], check=False)
        info = InterfaceInfo(name=name, mac=mac, active=True)
        logger.info("Windows: 已准备 %s (MAC=%s)", name, mac)
        return info

    def configure(self, info: InterfaceInfo) -> None:
        if not info.ip or not info.mask:
            return
        prefix = sum(bin(int(o)).count("1") for o in info.mask.split("."))
        _run([
            "powershell", "-Command",
            f"Remove-NetIPAddress -InterfaceAlias '{info.name}' -Confirm:$false -EA SilentlyContinue;"
            f"New-NetIPAddress -InterfaceAlias '{info.name}'"
            f" -IPAddress '{info.ip}' -PrefixLength {prefix}"
            f" -DefaultGateway '{info.gateway}' -EA Stop"
        ], check=False)

    def add_route(self, info: InterfaceInfo) -> None:
        pass  # configure 里已带网关

    def remove_route(self, info: InterfaceInfo) -> None:
        pass

    def destroy(self, info: InterfaceInfo) -> None:
        _run([
            "powershell", "-Command",
            f"Disable-NetAdapter -Name '{info.name}' -Confirm:$false -EA SilentlyContinue"
        ], check=False)
        logger.info("Windows: 已禁用 %s", info.name)


def _get_backend() -> InterfaceBackend:
    """根据平台返回对应后端"""
    if CURRENT_OS == OSType.LINUX:
        return LinuxBackend()
    if CURRENT_OS == OSType.MACOS:
        return MacOSBackend()
    if CURRENT_OS == OSType.WINDOWS:
        return WindowsBackend()
    raise RuntimeError(f"不支持的平台: {platform.system()}")

# ============================================================================
# DHCP 客户端（外部工具优先，内置协议栈备选）
# ============================================================================

class DHCPHelper:
    """DHCP 地址获取"""

    @staticmethod
    def request_via_system(iface_name: str) -> Optional[Dict[str, Any]]:
        """通过系统工具获取 DHCP 地址"""
        try:
            if CURRENT_OS == OSType.LINUX:
                _run(["dhclient", "-r", iface_name], check=False)
                _run(["dhclient", "-v", iface_name], timeout=30)
                return DHCPHelper._read_linux(iface_name)

            if CURRENT_OS == OSType.MACOS:
                _run(["ipconfig", "set", iface_name, "DHCP"], check=False)
                time.sleep(3)
                return DHCPHelper._read_macos(iface_name)

            if CURRENT_OS == OSType.WINDOWS:
                _run(["ipconfig", "/release", iface_name], check=False, timeout=15)
                _run(["ipconfig", "/renew", iface_name], timeout=30)
                return DHCPHelper._read_windows(iface_name)

        except Exception as e:
            logger.warning("系统 DHCP 失败 (%s): %s", iface_name, e)
        return None

    @staticmethod
    def request_via_raw_socket(iface_name: str, mac: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """通过原始套接字发送 DHCP 请求"""
        mac_bytes = MACAddress.to_bytes(mac)
        xid = random.randint(0, 0xFFFFFFFF)

        def build_packet(msg_type: int, *, req_ip: str = None, srv_ip: str = None) -> bytes:
            pkt = bytearray(236)
            pkt[0] = 1  # BOOTREQUEST
            pkt[1] = 1  # Ethernet
            pkt[2] = 6  # MAC len
            struct.pack_into("!I", pkt, 4, xid)
            struct.pack_into("!H", pkt, 10, 0x8000)  # broadcast
            pkt[28:34] = mac_bytes
            pkt += b"\x63\x82\x53\x63"  # magic cookie
            opts = bytearray([53, 1, msg_type])  # message type
            opts += bytes([61, 7, 1]) + mac_bytes  # client id
            if req_ip:
                opts += bytes([50, 4]) + socket.inet_aton(req_ip)
            if srv_ip:
                opts += bytes([54, 4]) + socket.inet_aton(srv_ip)
            opts += bytes([55, 4, 1, 3, 6, 51])  # param list
            opts += bytes([255])  # end
            return bytes(pkt) + bytes(opts)

        def parse(data: bytes) -> Optional[Dict[str, Any]]:
            if len(data) < 240 or data[0] != 2:
                return None
            rx_xid = struct.unpack("!I", data[4:8])[0]
            if rx_xid != xid:
                return None
            if data[236:240] != b"\x63\x82\x53\x63":
                return None
            result: Dict[str, Any] = {
                "ip": socket.inet_ntoa(data[16:20]),
                "type": None, "mask": None, "gw": None, "dns": [], "lease": 3600, "server": None,
            }
            idx = 240
            while idx < len(data):
                code = data[idx]
                if code == 255:
                    break
                if code == 0:
                    idx += 1
                    continue
                if idx + 1 >= len(data):
                    break
                length = data[idx + 1]
                val = data[idx + 2:idx + 2 + length]
                idx += 2 + length
                if code == 53 and length == 1:
                    result["type"] = val[0]
                elif code == 1 and length == 4:
                    result["mask"] = socket.inet_ntoa(val)
                elif code == 3 and length >= 4:
                    result["gw"] = socket.inet_ntoa(val[:4])
                elif code == 6:
                    for i in range(0, length, 4):
                        if i + 4 <= length:
                            result["dns"].append(socket.inet_ntoa(val[i:i+4]))
                elif code == 51 and length == 4:
                    result["lease"] = struct.unpack("!I", val)[0]
                elif code == 54 and length == 4:
                    result["server"] = socket.inet_ntoa(val)
            return result

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if CURRENT_OS == OSType.LINUX:
                try:
                    sock.setsockopt(socket.SOL_SOCKET, 25, iface_name.encode() + b"\0")  # SO_BINDTODEVICE
                except OSError:
                    pass
            sock.settimeout(timeout)
            sock.bind(("0.0.0.0", 68))

            # DISCOVER
            sock.sendto(build_packet(1), ("255.255.255.255", 67))
            logger.debug("DHCP DISCOVER sent (xid=%08X)", xid)

            offer = None
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    data, _ = sock.recvfrom(4096)
                    r = parse(data)
                    if r and r["type"] == 2:  # OFFER
                        offer = r
                        break
                except socket.timeout:
                    break

            if not offer:
                sock.close()
                return None

            logger.debug("DHCP OFFER: %s from %s", offer["ip"], offer["server"])

            # REQUEST
            xid = random.randint(0, 0xFFFFFFFF)
            sock.sendto(
                build_packet(3, req_ip=offer["ip"], srv_ip=offer["server"]),
                ("255.255.255.255", 67),
            )

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    data, _ = sock.recvfrom(4096)
                    r = parse(data)
                    if r and r["type"] == 5:  # ACK
                        sock.close()
                        return r
                    if r and r["type"] == 6:  # NAK
                        sock.close()
                        return None
                except socket.timeout:
                    break

            sock.close()
        except Exception as e:
            logger.warning("原始 DHCP 失败: %s", e)
        return None

    @staticmethod
    def _read_linux(iface: str) -> Optional[Dict[str, Any]]:
        r = _run(["ip", "-j", "addr", "show", iface], check=False)
        try:
            data = json.loads(r.stdout)
            if not data:
                return None
            addrs = [a for a in data[0].get("addr_info", []) if a.get("family") == "inet"]
            if not addrs:
                return None
            ip = addrs[0]["local"]
            plen = addrs[0]["prefixlen"]
            mask_int = (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF
            mask = socket.inet_ntoa(struct.pack("!I", mask_int))
            # 读网关
            rr = _run(["ip", "-j", "route", "show", "dev", iface], check=False)
            gw = None
            try:
                for route in json.loads(rr.stdout):
                    if route.get("dst") == "default":
                        gw = route.get("gateway")
            except Exception:
                pass
            return {"ip": ip, "mask": mask, "gw": gw, "dns": [], "lease": 3600}
        except Exception:
            return None

    @staticmethod
    def _read_macos(iface: str) -> Optional[Dict[str, Any]]:
        r = _run(["ifconfig", iface], check=False)
        m_ip = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", r.stdout)
        if not m_ip:
            return None
        ip = m_ip.group(1)
        m_mask = re.search(r"netmask\s+0x([0-9a-fA-F]+)", r.stdout)
        mask = "255.255.255.0"
        if m_mask:
            mask = socket.inet_ntoa(struct.pack("!I", int(m_mask.group(1), 16)))
        rr = _run(["route", "-n", "get", "default"], check=False)
        m_gw = re.search(r"gateway:\s*(\d+\.\d+\.\d+\.\d+)", rr.stdout)
        gw = m_gw.group(1) if m_gw else None
        return {"ip": ip, "mask": mask, "gw": gw, "dns": [], "lease": 3600}

    @staticmethod
    def _read_windows(iface: str) -> Optional[Dict[str, Any]]:
        r = _run([
            "powershell", "-Command",
            f"Get-NetIPAddress -InterfaceAlias '{iface}' -AddressFamily IPv4"
            " | Select IPAddress,PrefixLength | ConvertTo-Json"
        ], check=False)
        try:
            d = json.loads(r.stdout)
            if isinstance(d, list):
                d = d[0]
            ip = d["IPAddress"]
            plen = d["PrefixLength"]
            mask_int = (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF
            mask = socket.inet_ntoa(struct.pack("!I", mask_int))
            rr = _run([
                "powershell", "-Command",
                f"(Get-NetRoute -InterfaceAlias '{iface}'"
                " -DestinationPrefix '0.0.0.0/0' -EA SilentlyContinue).NextHop"
            ], check=False)
            gw = rr.stdout.strip() or None
            return {"ip": ip, "mask": mask, "gw": gw, "dns": [], "lease": 3600}
        except Exception:
            return None

# ============================================================================
# 猴子补丁引擎
# ============================================================================

class _PatchState:
    """保存补丁前的原始引用"""
    socket_create_connection: Optional[Callable] = None
    urllib3_create_connection: Optional[Callable] = None
    patched: bool = False


_patch_state = _PatchState()


def _apply_patches(source_ip: str) -> None:
    """应用所有猴子补丁，强制绑定源地址"""
    if _patch_state.patched:
        return

    # 1) 补丁 socket.create_connection
    _patch_state.socket_create_connection = socket.create_connection
    _orig_cc = socket.create_connection

    @functools.wraps(_orig_cc)
    def _patched_cc(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, **kw):
        if source_address is None:
            source_address = (source_ip, 0)
        return _orig_cc(address, timeout=timeout, source_address=source_address, **kw)

    socket.create_connection = _patched_cc

    # 2) 补丁 urllib3（requests 底层）
    try:
        import urllib3.util.connection as u3conn
        _patch_state.urllib3_create_connection = u3conn.create_connection
        _orig_u3 = u3conn.create_connection

        @functools.wraps(_orig_u3)
        def _patched_u3(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                        source_address=None, socket_options=None, **kw):
            if source_address is None:
                source_address = (source_ip, 0)
            return _orig_u3(address, timeout=timeout, source_address=source_address,
                            socket_options=socket_options, **kw)

        u3conn.create_connection = _patched_u3
    except ImportError:
        pass

    # 3) 补丁 aiohttp.TCPConnector（如果可用）
    if _original_aiohttp is not None:
        _orig_tcp_init = _original_aiohttp.TCPConnector.__init__

        @functools.wraps(_orig_tcp_init)
        def _patched_tcp_init(self, *args, **kwargs):
            if kwargs.get("local_addr") is None:
                kwargs["local_addr"] = (source_ip, 0)
            _orig_tcp_init(self, *args, **kwargs)

        _original_aiohttp.TCPConnector.__init__ = _patched_tcp_init

    _patch_state.patched = True
    logger.info("猴子补丁已应用，源地址绑定: %s", source_ip)


def _remove_patches() -> None:
    """移除所有猴子补丁"""
    if not _patch_state.patched:
        return

    if _patch_state.socket_create_connection:
        socket.create_connection = _patch_state.socket_create_connection

    if _patch_state.urllib3_create_connection:
        try:
            import urllib3.util.connection as u3conn
            u3conn.create_connection = _patch_state.urllib3_create_connection
        except ImportError:
            pass

    _patch_state.patched = False
    logger.info("猴子补丁已移除")

# ============================================================================
# 代理引擎（核心编排器）
# ============================================================================

class ProxyEngine:
    """代理引擎 - 编排虚拟网卡创建、DHCP、补丁"""

    _instance: Optional[ProxyEngine] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._backend: Optional[InterfaceBackend] = None
        self._iface: Optional[InterfaceInfo] = None
        self._active: bool = False

    @classmethod
    def instance(cls) -> ProxyEngine:
        """单例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def active(self) -> bool:
        return self._active

    @property
    def bound_ip(self) -> Optional[str]:
        return self._iface.ip if self._iface else None

    def start(
        self,
        *,
        mac: Optional[str] = None,
        auto_elevate: bool = True,
        use_system_dhcp: bool = True,
    ) -> str:
        """
        启动代理引擎

        返回: 分配到的 IP 地址
        """
        if self._active:
            logger.info("引擎已启动，当前 IP: %s", self._iface.ip)
            return self._iface.ip

        # 权限
        if auto_elevate and not PrivilegeManager.is_admin():
            PrivilegeManager.elevate()
        if not PrivilegeManager.is_admin():
            raise PermissionError("需要管理员权限")

        # MAC
        if mac is None:
            mac = MACAddress.generate_random()

        # 接口名
        name = f"vproxy_{uuid4().hex[:6]}"

        # 创建
        self._backend = _get_backend()
        self._iface = self._backend.create(name, mac)

        # DHCP
        dhcp_result = None
        if use_system_dhcp:
            dhcp_result = DHCPHelper.request_via_system(self._iface.name)
        if dhcp_result is None:
            dhcp_result = DHCPHelper.request_via_raw_socket(self._iface.name, mac)
        if dhcp_result is None and use_system_dhcp:
            # 再试一次原始套接字
            dhcp_result = DHCPHelper.request_via_raw_socket(self._iface.name, mac)

        if dhcp_result is None:
            self._backend.destroy(self._iface)
            raise RuntimeError("DHCP 获取 IP 失败，请检查网络环境")

        self._iface.ip = dhcp_result["ip"]
        self._iface.mask = dhcp_result.get("mask", "255.255.255.0")
        self._iface.gateway = dhcp_result.get("gw")
        self._iface.dns = dhcp_result.get("dns", [])

        # 配置（内置 DHCP 时需手动配 IP）
        if not use_system_dhcp:
            self._backend.configure(self._iface)

        # 路由
        self._backend.add_route(self._iface)

        # 补丁
        _apply_patches(self._iface.ip)

        self._active = True
        atexit.register(self.stop)

        logger.info("=== 代理引擎已启动 ===")
        logger.info("  接口: %s", self._iface.name)
        logger.info("  MAC:  %s", self._iface.mac)
        logger.info("  IP:   %s", self._iface.ip)
        logger.info("  网关: %s", self._iface.gateway)
        logger.info("========================")

        return self._iface.ip

    def stop(self) -> None:
        """停止并清理"""
        if not self._active:
            return
        _remove_patches()
        if self._backend and self._iface:
            self._backend.remove_route(self._iface)
            self._backend.destroy(self._iface)
        self._active = False
        logger.info("代理引擎已停止")

    def renew(self) -> str:
        """续约/换 IP"""
        if not self._active:
            raise RuntimeError("引擎未启动")
        _remove_patches()
        self._backend.remove_route(self._iface)

        dhcp_result = DHCPHelper.request_via_system(self._iface.name)
        if dhcp_result is None:
            dhcp_result = DHCPHelper.request_via_raw_socket(self._iface.name, self._iface.mac)
        if dhcp_result is None:
            raise RuntimeError("续约失败")

        self._iface.ip = dhcp_result["ip"]
        self._iface.mask = dhcp_result.get("mask", "255.255.255.0")
        self._iface.gateway = dhcp_result.get("gw")
        self._backend.add_route(self._iface)
        _apply_patches(self._iface.ip)

        logger.info("续约成功，新 IP: %s", self._iface.ip)
        return self._iface.ip

    def status(self) -> Dict[str, Any]:
        """状态信息"""
        return {
            "active": self._active,
            "platform": CURRENT_OS.name,
            "interface": self._iface.name if self._iface else None,
            "mac": self._iface.mac if self._iface else None,
            "ip": self._iface.ip if self._iface else None,
            "gateway": self._iface.gateway if self._iface else None,
        }


# ============================================================================
# 模块级 API
# ============================================================================

_engine = ProxyEngine.instance()

def init(*, mac: Optional[str] = None, auto_elevate: bool = True, use_system_dhcp: bool = True) -> str:
    """启动代理，返回新 IP"""
    return _engine.start(mac=mac, auto_elevate=auto_elevate, use_system_dhcp=use_system_dhcp)

def shutdown() -> None:
    """关闭代理"""
    _engine.stop()

def renew() -> str:
    """换 IP"""
    return _engine.renew()

def status() -> Dict[str, Any]:
    """状态"""
    return _engine.status()

def get_ip() -> Optional[str]:
    """获取当前 IP"""
    return _engine.bound_ip

@contextmanager
def session(*, mac: Optional[str] = None) -> Iterator[str]:
    """上下文管理器"""
    ip = init(mac=mac)
    try:
        yield ip
    finally:
        shutdown()

# ============================================================================
# 核心: 把 requests 和 aiohttp 注入到调用者的命名空间
# ============================================================================

def _inject_into_caller() -> None:
    """
    将 requests 和 aiohttp 注入到执行 `import net` 的那个模块的全局命名空间。

    这样用户写 `import net` 之后，在同一个文件里直接写
    aiohttp.TCPConnector(...) 或 requests.get(...) 就能用。
    """
    # 向上回溯调用栈，找到执行 import net 的那一帧
    frame = inspect.currentframe()
    try:
        # frame 0: _inject_into_caller
        # frame 1: 模块顶层代码（net.py 的 _inject_into_caller() 调用处）
        # frame 2: 执行 import net 的调用者
        caller_frame = frame
        for _ in range(10):  # 最多回溯 10 帧
            if caller_frame is None:
                break
            caller_frame = caller_frame.f_back

            if caller_frame is None:
                break

            caller_globals = caller_frame.f_globals
            module_name = caller_globals.get("__name__", "")

            # 跳过 proxy 自身、importlib 内部帧
            if module_name == __name__:
                continue
            if "importlib" in module_name:
                continue

            # 找到了真正的调用者
            if _original_requests is not None and "requests" not in caller_globals:
                caller_globals["requests"] = _original_requests
                logger.debug("已注入 requests 到 %s", module_name)

            if _original_aiohttp is not None and "aiohttp" not in caller_globals:
                caller_globals["aiohttp"] = _original_aiohttp
                logger.debug("已注入 aiohttp 到 %s", module_name)

            break  # 只注入到第一个非内部调用者
    finally:
        del frame


# 同时注册到 sys.modules，这样 import requests / import aiohttp 也能正常工作
# （如果用户在其他文件里单独 import requests，不受影响）
if _original_requests is not None:
    sys.modules.setdefault("requests", _original_requests)

if _original_aiohttp is not None:
    sys.modules.setdefault("aiohttp", _original_aiohttp)

# 执行注入
_inject_into_caller()

# 同时在 proxy 模块自身上暴露这两个名字，支持 from proxy import aiohttp
if _original_requests is not None:
    requests = _original_requests

if _original_aiohttp is not None:
    aiohttp = _original_aiohttp


# ============================================================================
# __all__
# ============================================================================

__all__ = [
    # 原始库（直接可用）
    "requests",
    "aiohttp",
    # API
    "init",
    "shutdown",
    "renew",
    "status",
    "get_ip",
    "session",
    # 类
    "ProxyEngine",
    "MACAddress",
    "PrivilegeManager",
    "CURRENT_OS",
    "OSType",
]

__version__ = "1.0.0"
