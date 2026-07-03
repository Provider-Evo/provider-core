from __future__ import annotations

"""Terminal session persistence store.

持久化终端会话元数据及离线输出到磁盘，使 shell 进程能在服务器
重启后存活，客户端可重连至已有会话。

存储结构
--------
::

    persist/terminal/
        {session_id}.json      -- 会话元数据（JSON 格式）
        {session_id}.output    -- 滚动离线输出日志（纯文本）

元数据 JSON 结构
----------------
::

    {
        "session_id": "abc123",
        "pid": 12345,
        "cwd": "/home/user/project",
        "shell": "/bin/bash",
        "cols": 220,
        "rows": 50,
        "kind": "local",
        "ssh_config": null,
        "name": "my-session",
        "status": "alive",
        "created_at": 1700000000.0,
        "updated_at": 1700000100.0,
        "_env_keys": ["PATH", "HOME"]
    }

注意事项
--------
- ``env`` 字段的值不会被持久化，只记录键名（``_env_keys``），
  避免将敏感环境变量（如 API Key）写入磁盘。
- 离线输出文件超出 ``max_output_bytes`` 时，自动裁剪最旧内容，
  保留最新的 ``max_output_bytes`` 字节。
- ``cleanup_stale`` 方法清理状态为 ``"destroyed"`` 且超过保留
  期限的会话，建议在服务启动时或定期任务中调用。

使用示例
--------
.. code-block:: python

    from pathlib import Path
    from core.terminal_sessions import get_terminal_store

    store = get_terminal_store()

    # 保存会话
    store.save("sess-001", pid=9876, cwd="/tmp", shell="/bin/zsh")

    # 追加离线输出
    store.append_output("sess-001", "hello world\\n")

    # 读取离线输出
    output = store.get_offline_output("sess-001")

    # 标记会话为已销毁
    store.save("sess-001", status="destroyed")

    # 清理超过 1 小时的已销毁会话
    count = store.cleanup_stale(max_age_seconds=3600)
    print(f"已清理 {count} 个过期会话")
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger import get_logger

__all__ = ["TerminalSessionStore", "get_terminal_store"]

logger = get_logger(__name__)

# 每个会话离线输出文件的默认最大字节数（5 MB）。
_DEFAULT_MAX_OUTPUT_BYTES: int = 5 * 1024 * 1024

# 已销毁会话的默认保留时长（秒），用于支持撤销关闭操作（5 分钟）。
_DEFAULT_DESTROYED_RETENTION: int = 300

# 模块级单例，首次调用 get_terminal_store() 时初始化。
_store: Optional["TerminalSessionStore"] = None


class TerminalSessionStore:
    """持久化终端会话元数据及离线输出。

    所有文件 I/O 操作均捕获异常并记录日志，不向调用方抛出存储层错误，
    确保终端功能在持久化失败时仍可降级运行。

    Parameters
    ----------
    persist_dir:
        会话文件存储目录，不存在时自动递归创建。
    max_output_bytes:
        每个会话离线输出文件的最大字节数，默认 5 MB。
        超出时自动裁剪最旧内容，保留最新部分。
    """

    def __init__(
        self,
        persist_dir: Path,
        max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self.persist_dir = persist_dir
        self.max_output_bytes = max_output_bytes
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("TerminalSessionStore 初始化: persist_dir=%s", persist_dir)

    # ------------------------------------------------------------------
    # 元数据 CRUD
    # ------------------------------------------------------------------

    def save(
        self,
        session_id: str,
        pid: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        shell: Optional[str] = None,
        cols: int = 80,
        rows: int = 24,
        kind: str = "local",
        ssh_config: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        status: str = "alive",
    ) -> None:
        """保存或更新会话元数据。

        若会话已存在，则合并更新字段并保留 ``created_at``；
        若会话不存在，则创建新记录并同时设置 ``created_at``。

        Parameters
        ----------
        session_id:
            会话唯一标识，用作文件名的主键。
        pid:
            Shell 进程 ID，进程退出后可置为 ``None``。
        cwd:
            当前工作目录路径字符串。
        env:
            环境变量字典。**值不会被持久化**，只记录键名以供调试。
        shell:
            Shell 可执行文件路径，例如 ``"/bin/bash"``。
        cols:
            终端列数，默认 80。
        rows:
            终端行数，默认 24。
        kind:
            会话类型，``"local"`` 表示本地 shell，``"ssh"`` 表示远程。
        ssh_config:
            SSH 连接配置字典，仅 ``kind="ssh"`` 时有效。
            例如 ``{"host": "192.168.1.1", "port": 22, "user": "root"}``。
        name:
            会话显示名称，供 UI 展示使用。
        status:
            会话状态：

            - ``"alive"``：进程运行中。
            - ``"destroyed"``：进程已退出，等待清理。
        """
        meta_path = self._meta_path(session_id)
        data: Dict[str, Any] = {}

        # 读取已有元数据（若存在），合并更新
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.debug(
                    "读取已有会话元数据失败，将覆盖: %s",
                    meta_path,
                    exc_info=True,
                )
                data = {}
            except Exception:
                logger.warning(
                    "读取会话元数据时发生意外错误，将覆盖: %s",
                    meta_path,
                    exc_info=True,
                )
                data = {}

        now = time.time()
        data.update(
            {
                "session_id": session_id,
                "pid": pid,
                "cwd": cwd,
                "shell": shell,
                "cols": cols,
                "rows": rows,
                "kind": kind,
                "ssh_config": ssh_config,
                "name": name,
                "status": status,
                "updated_at": now,
            }
        )

        # 首次保存时设置创建时间戳
        if "created_at" not in data:
            data["created_at"] = now

        # 仅记录 env 的键名，不持久化值（防止泄露 API Key 等敏感信息）
        if env:
            data["_env_keys"] = sorted(env.keys())

        try:
            meta_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("会话元数据已保存: %s (status=%s)", session_id, status)
        except OSError:
            logger.debug("保存会话元数据失败: %s", session_id, exc_info=True)
        except Exception:
            logger.warning(
                "保存会话元数据时发生意外错误: %s",
                session_id,
                exc_info=True,
            )

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """加载会话元数据。

        Parameters
        ----------
        session_id:
            会话唯一标识。

        Returns
        -------
        Optional[Dict[str, Any]]
            会话元数据字典；会话不存在或读取失败时返回 ``None``。
        """
        meta_path = self._meta_path(session_id)
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.debug(
                "加载会话元数据失败: %s",
                session_id,
                exc_info=True,
            )
            return None
        except Exception:
            logger.warning(
                "加载会话元数据时发生意外错误: %s",
                session_id,
                exc_info=True,
            )
            return None

    def delete(self, session_id: str) -> None:
        """删除会话元数据及离线输出文件。

        两个文件均尝试删除；若任一文件不存在则静默忽略。

        Parameters
        ----------
        session_id:
            会话唯一标识。
        """
        for path in (
            self._meta_path(session_id),
            self._output_path(session_id),
        ):
            try:
                if path.exists():
                    path.unlink()
                    logger.debug("已删除文件: %s", path)
            except OSError:
                logger.debug("删除文件失败: %s", path, exc_info=True)
            except Exception:
                logger.warning(
                    "删除文件时发生意外错误: %s",
                    path,
                    exc_info=True,
                )

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有已持久化的会话元数据。

        Returns
        -------
        List[Dict[str, Any]]
            所有会话元数据字典的列表，按会话文件名字典序排列。
            读取失败的文件会被跳过并记录警告日志。
        """
        results: List[Dict[str, Any]] = []
        for meta_path in sorted(self.persist_dir.glob("*.json")):
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                results.append(data)
            except (OSError, json.JSONDecodeError):
                logger.debug("跳过无法读取的元数据文件: %s", meta_path, exc_info=True)
            except Exception:
                logger.warning(
                    "读取元数据文件时发生意外错误，已跳过: %s",
                    meta_path,
                    exc_info=True,
                )
        return results

    # ------------------------------------------------------------------
    # 离线输出管理
    # ------------------------------------------------------------------

    def append_output(self, session_id: str, chunk: str) -> None:
        """向离线输出缓冲区追加终端输出块。

        追加完成后检查文件大小，若超过 ``max_output_bytes`` 则
        自动调用 :meth:`_trim_output` 裁剪最旧内容。

        Parameters
        ----------
        session_id:
            会话唯一标识。
        chunk:
            待追加的终端输出字符串（可包含 ANSI 转义序列）。
        """
        output_path = self._output_path(session_id)
        try:
            with open(output_path, "a", encoding="utf-8") as fh:
                fh.write(chunk)

            # 检查文件大小，必要时裁剪
            size = output_path.stat().st_size
            if size > self.max_output_bytes:
                self._trim_output(output_path, size)
        except OSError:
            logger.debug("追加离线输出失败: %s", session_id, exc_info=True)
        except Exception:
            logger.warning(
                "追加离线输出时发生意外错误: %s",
                session_id,
                exc_info=True,
            )

    def get_offline_output(self, session_id: str) -> str:
        """读取完整的离线输出缓冲区内容。

        Parameters
        ----------
        session_id:
            会话唯一标识。

        Returns
        -------
        str
            离线输出内容；缓冲区文件不存在时返回空字符串。
            读取时使用 ``errors="replace"`` 容错非 UTF-8 字节。
        """
        output_path = self._output_path(session_id)
        if not output_path.exists():
            return ""
        try:
            return output_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.debug("读取离线输出失败: %s", session_id, exc_info=True)
            return ""
        except Exception:
            logger.warning(
                "读取离线输出时发生意外错误: %s",
                session_id,
                exc_info=True,
            )
            return ""

    def clear_offline_output(self, session_id: str) -> None:
        """清空离线输出缓冲区（删除输出文件）。

        Parameters
        ----------
        session_id:
            会话唯一标识。
        """
        output_path = self._output_path(session_id)
        try:
            if output_path.exists():
                output_path.unlink()
                logger.debug("离线输出已清空: %s", session_id)
        except OSError:
            logger.debug("清空离线输出失败: %s", session_id, exc_info=True)
        except Exception:
            logger.warning(
                "清空离线输出时发生意外错误: %s",
                session_id,
                exc_info=True,
            )

    def consume_offline_output(self, session_id: str) -> str:
        """原子性地读取并清空离线输出缓冲区。

        读取完整内容后立即删除输出文件，避免并发客户端重复消费。
        适用于服务器重启后恢复会话时的一次性读取场景。

        Parameters
        ----------
        session_id:
            会话唯一标识。

        Returns
        -------
        str
            离线输出内容；缓冲区文件不存在时返回空字符串。
        """
        output_path = self._output_path(session_id)
        if not output_path.exists():
            return ""
        try:
            content = output_path.read_text(encoding="utf-8", errors="replace")
            output_path.unlink()
            logger.debug("离线输出已消费: %s (%d bytes)", session_id, len(content))
            return content
        except OSError:
            logger.debug("消费离线输出失败: %s", session_id, exc_info=True)
            return ""
        except Exception:
            logger.warning(
                "消费离线输出时发生意外错误: %s",
                session_id,
                exc_info=True,
            )
            return ""

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def cleanup_stale(self, max_age_seconds: int = 86400) -> int:
        """清除已销毁且超过保留期限的会话。

        遍历所有会话元数据，筛选出 ``status == "destroyed"`` 且
        ``updated_at`` 距今超过 ``max_age_seconds`` 的会话，
        调用 :meth:`delete` 逐一删除。

        Parameters
        ----------
        max_age_seconds:
            已销毁会话的最大保留时长（秒），默认 86400（24 小时）。

        Returns
        -------
        int
            本次清理的会话数量。
        """
        count = 0
        now = time.time()
        for meta in self.list_all():
            if meta.get("status") != "destroyed":
                continue
            updated = meta.get("updated_at", 0)
            if now - updated > max_age_seconds:
                sid = meta.get("session_id", "")
                self.delete(sid)
                count += 1
                logger.info("已清理过期会话: %s (age=%.0fs)", sid, now - updated)
        return count

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _meta_path(self, session_id: str) -> Path:
        """返回会话元数据文件路径。

        Parameters
        ----------
        session_id:
            会话唯一标识。

        Returns
        -------
        Path
            ``{persist_dir}/{session_id}.json``
        """
        return self.persist_dir / f"{session_id}.json"

    def _output_path(self, session_id: str) -> Path:
        """返回会话离线输出文件路径。

        Parameters
        ----------
        session_id:
            会话唯一标识。

        Returns
        -------
        Path
            ``{persist_dir}/{session_id}.output``
        """
        return self.persist_dir / f"{session_id}.output"

    def _trim_output(self, path: Path, current_size: int) -> None:
        """裁剪输出文件至 ``max_output_bytes`` 以内，保留最新内容。

        以二进制模式读取文件末尾 ``max_output_bytes`` 字节，
        覆盖写回，丢弃最旧的内容。

        Parameters
        ----------
        path:
            输出文件路径。
        current_size:
            当前文件字节数（来自 ``stat().st_size``）。
        """
        try:
            with open(path, "rb") as fh:
                fh.seek(max(0, current_size - self.max_output_bytes))
                tail = fh.read()
            with open(path, "wb") as fh:
                fh.write(tail)
            logger.debug(
                "输出文件已裁剪: %s (%d -> %d bytes)",
                path,
                current_size,
                len(tail),
            )
        except OSError:
            logger.debug("裁剪输出文件失败: %s", path, exc_info=True)
        except Exception:
            logger.warning(
                "裁剪输出文件时发生意外错误: %s",
                path,
                exc_info=True,
            )


# ------------------------------------------------------------------
# 模块级单例（首次使用时惰性初始化）
# ------------------------------------------------------------------


def get_terminal_store(persist_dir: Optional[Path] = None) -> TerminalSessionStore:
    """获取或创建模块级 TerminalSessionStore 单例。

    采用惰性初始化策略：首次调用时根据 ``persist_dir`` 参数创建
    实例并缓存；后续调用始终返回同一实例，忽略 ``persist_dir`` 参数。

    若需要使用不同的 ``persist_dir``，请直接实例化
    :class:`TerminalSessionStore`。

    Parameters
    ----------
    persist_dir:
        持久化目录路径。为 ``None`` 时使用默认路径：
        ``<project_root>/persist/terminal/``，其中
        ``<project_root>`` 为本文件向上三级的目录。

    Returns
    -------
    TerminalSessionStore
        模块级单例对象。
    """
    global _store
    if _store is not None:
        return _store

    if persist_dir is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        persist_dir = project_root / "persist" / "terminal"

    _store = TerminalSessionStore(persist_dir)
    logger.debug("全局 TerminalSessionStore 单例已创建: %s", persist_dir)
    return _store
