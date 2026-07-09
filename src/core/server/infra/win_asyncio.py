"""Windows asyncio Proactor 无害错误抑制。"""

from __future__ import annotations

import sys


def apply_windows_asyncio_patches() -> None:
    """抑制 Proactor 在连接被对端强制关闭时的 ConnectionResetError 日志噪音。

    Windows 默认 ProactorEventLoop 在 ``_call_connection_lost`` 中对已断开的套接字
    调用 ``shutdown(SHUT_RDWR)`` 时可能抛出 ``[WinError 10054]``，属于无害竞态。
    """
    if sys.platform != "win32":
        return

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
