from __future__ import annotations

"""会话离线输出管理混入。"""

from pathlib import Path

from src.foundation.logger import get_logger

logger = get_logger(__name__)


class SessionOutputMixin:
    """提供离线输出的追加、读取、清空与消费能力。"""

    def append_output(self, session_id: str, chunk: str) -> None:
        """向离线输出缓冲区追加终端输出块，超限时自动裁剪。"""
        output_path = self._output_path(session_id)
        try:
            with open(output_path, "a", encoding="utf-8") as fh:
                fh.write(chunk)

            size = output_path.stat().st_size
            if size > self.max_output_bytes:
                self._trim_output(output_path, size)
        except OSError:
            logger.debug("追加离线输出失败: %s", session_id, exc_info=True)
        except Exception:
            logger.warning("追加离线输出时发生意外错误: %s", session_id, exc_info=True)

    def get_offline_output(self, session_id: str) -> str:
        """读取完整的离线输出缓冲区内容。"""
        output_path = self._output_path(session_id)
        if not output_path.exists():
            return ""
        try:
            return output_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.debug("读取离线输出失败: %s", session_id, exc_info=True)
            return ""
        except Exception:
            logger.warning("读取离线输出时发生意外错误: %s", session_id, exc_info=True)
            return ""

    def clear_offline_output(self, session_id: str) -> None:
        """清空离线输出缓冲区（删除输出文件）。"""
        output_path = self._output_path(session_id)
        try:
            if output_path.exists():
                output_path.unlink()
                logger.debug("离线输出已清空: %s", session_id)
        except OSError:
            logger.debug("清空离线输出失败: %s", session_id, exc_info=True)
        except Exception:
            logger.warning("清空离线输出时发生意外错误: %s", session_id, exc_info=True)

    def consume_offline_output(self, session_id: str) -> str:
        """原子性地读取并清空离线输出缓冲区。"""
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
            logger.warning("消费离线输出时发生意外错误: %s", session_id, exc_info=True)
            return ""

    def _output_path(self, session_id: str) -> Path:
        """返回会话离线输出文件路径。"""
        return self.persist_dir / "{0}.output".format(session_id)

    def _trim_output(self, path: Path, current_size: int) -> None:
        """裁剪输出文件至 max_output_bytes 以内，保留最新内容。"""
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
            logger.warning("裁剪输出文件时发生意外错误: %s", path, exc_info=True)
