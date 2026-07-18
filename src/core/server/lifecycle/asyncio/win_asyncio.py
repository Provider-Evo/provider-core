"""win_asyncio 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 win_asyncio 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

import sys


def apply_windows_asyncio_patches() -> None:
    """抑制 Windows Proactor 在关停/断连时的无害 asyncio 错误日志。

    - ``_call_connection_lost``：对端已断开时 ``shutdown`` 可能抛 ``WinError 10054``
    - ``Server._attach``：监听 socket 已关闭后仍收到连接会触发 ``AssertionError``
    """
    if sys.platform != "win32":
        return

    _patch_proactor_connection_lost()
    _patch_server_attach()


def _patch_proactor_connection_lost() -> None:
    import asyncio.proactor_events as proactor_events

    base = proactor_events._ProactorBasePipeTransport
    original = base._call_connection_lost
    if getattr(original, "_provider_patched", False):
        return

    def _call_connection_lost(self, exc):  # type: ignore[no-untyped-def]
        try:
            original(self, exc)
        except ConnectionResetError:
            return
        except ConnectionAbortedError:
            return
        except OSError as os_exc:
            if getattr(os_exc, "winerror", None) in (10053, 10054):
                return
            raise

    _call_connection_lost._provider_patched = True  # type: ignore[attr-defined]
    base._call_connection_lost = _call_connection_lost  # type: ignore[method-assign]


def _patch_server_attach() -> None:
    import asyncio.base_events as base_events

    original = base_events.Server._attach
    if getattr(original, "_provider_patched", False):
        return

    def _attach(self, transport):  # type: ignore[no-untyped-def]
        if self._sockets is None:
            transport.close()
            return
        original(self, transport)

    _attach._provider_patched = True  # type: ignore[attr-defined]
    base_events.Server._attach = _attach  # type: ignore[method-assign]
