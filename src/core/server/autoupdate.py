from __future__ import annotations

"""自动更新模块——检测远端提交并执行 git pull。"""

import asyncio
import os
from pathlib import Path
from typing import Optional, Tuple

from src.logger import get_logger

__all__ = ["AutoUpdater", "get_updater", "set_updater"]

logger = get_logger(__name__)


class AutoUpdater:
    """自动更新器：定期检查远端提交，有新提交时执行 pull 并触发重启。"""

    def __init__(self, root: Path, branch: str, interval: int) -> None:
        self._root = root
        self._branch = branch
        self._interval = interval
        self._running = False

    async def run(self) -> None:
        """启动自动更新循环。"""
        self._running = True
        logger.info("自动更新监视已启动 (branch=%s, interval=%ds)", self._branch, self._interval)

        # 启动时立即检查一次
        await self._check_and_update()

        while self._running:
            await asyncio.sleep(self._interval)
            try:
                await self._check_and_update()
            except Exception as e:
                logger.warning("自动更新检查异常: %s", e)

    def stop(self) -> None:
        """停止自动更新循环。"""
        self._running = False
        logger.info("自动更新监视已停止")

    async def _check_and_update(self) -> None:
        """执行一次检查，如有新提交则 pull 并重启。"""
        if not self._is_git_repo():
            logger.debug("当前目录不是 git 仓库，跳过自动更新")
            self._running = False  # 永久停止
            return

        is_behind, local_hash, remote_hash = await self._is_behind_remote()
        if not is_behind:
            logger.debug("当前已是最新提交 (local=%s)", local_hash[:8] if local_hash else "unknown")
            return

        logger.info(
            "检测到新提交: local=%s -> remote=%s，正在拉取更新...",
            local_hash[:8] if local_hash else "unknown",
            remote_hash[:8] if remote_hash else "unknown",
        )

        success = await self._pull()
        if not success:
            logger.error("git pull 失败，跳过本次更新")
            return

        logger.info("更新拉取成功，准备重启 Worker 进程...")
        self._trigger_restart()

    # -- Git 操作 --

    def _is_git_repo(self) -> bool:
        """检查当前目录是否为 git 仓库。"""
        return (self._root / ".git").is_dir()

    async def _run_git(self, *args: str, timeout: int = 30) -> Tuple[bool, str, str]:
        """执行 git 命令，返回 (success, stdout, stderr)。"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                *args,
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()
            return proc.returncode == 0, out, err
        except asyncio.TimeoutError:
            return False, "", f"git {' '.join(args)} 超时 ({timeout}s)"
        except FileNotFoundError:
            return False, "", "git 命令未找到，请确认 git 已安装"
        except Exception as e:
            return False, "", str(e)

    async def _is_behind_remote(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """检查本地是否落后于远端。

        Returns:
            (is_behind, local_hash, remote_hash)
        """
        # 先 fetch 获取最新远端信息
        ok, out, err = await self._run_git("fetch", "origin", self._branch)
        if not ok:
            logger.warning("git fetch 失败: %s", err)
            return False, None, None

        # 获取本地 HEAD commit
        ok, local_hash, err = await self._run_git("rev-parse", "HEAD")
        if not ok:
            logger.warning("获取本地 HEAD 失败: %s", err)
            return False, None, None

        # 获取远端分支 commit
        ok, remote_hash, err = await self._run_git("rev-parse", f"origin/{self._branch}")
        if not ok:
            logger.warning("获取远端 commit 失败: %s", err)
            return False, local_hash, None

        if local_hash == remote_hash:
            return False, local_hash, remote_hash

        # 检查本地是否是远端的祖先（即是否落后）
        ok, _, _ = await self._run_git(
            "merge-base", "--is-ancestor", local_hash, remote_hash,
        )
        if ok:
            # local_hash 是 origin/branch 的祖先 -> 有新提交
            return True, local_hash, remote_hash

        # 分叉或其他情况，只要 hash 不同就认为需要更新
        return True, local_hash, remote_hash

    async def _pull(self) -> bool:
        """执行 git pull。

        使用 --ff-only 确保只进行 fast-forward 合并，避免合并冲突。
        如果无法 fast-forward，先尝试 stash 本地修改再 pull。
        """
        # 检查工作树状态
        ok, out, err = await self._run_git("status", "--porcelain")
        if ok and out:
            logger.warning("工作树有未提交的修改，正在暂存...")
            stash_ok, _, stash_err = await self._run_git(
                "stash", "push", "-m", "autoupdate: stash before pull",
            )
            if not stash_ok:
                logger.error("git stash 失败: %s", stash_err)
                return False

        # 先尝试 fast-forward only
        ok, out, err = await self._run_git("pull", "--ff-only", "origin", self._branch)
        if not ok:
            logger.warning("git pull --ff-only 失败: %s，尝试普通 pull", err)
            ok, out, err = await self._run_git("pull", "origin", self._branch)
            if not ok:
                logger.error("git pull 失败: %s", err)
                return False

        logger.info("git pull 成功: %s", out)
        return True

    def _trigger_restart(self) -> None:
        """触发进程重启（与 FileWatcher._trigger_restart 相同的模式）。"""
        os._exit(42)


# -- 全局单例（供 WebUI 访问） --
_updater: Optional[AutoUpdater] = None


def get_updater() -> Optional[AutoUpdater]:
    """获取当前自动更新器实例。"""
    return _updater


def set_updater(updater: AutoUpdater) -> None:
    """设置全局自动更新器实例。"""
    global _updater
    _updater = updater
