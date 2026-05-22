"""
Ollama 客户端模块 - 负责与外部 Ollama 服务器通信
版本: 1.0.0

算法: Track-and-Stop 多臂赌博机最优服务器选择 + 断点续传
- 按模型名称索引可用服务器
- 单模型单服务器直连，多服务器竞争时使用 TAS 选择
- 24 小时自动刷新服务器列表
- 无并发竞速（单请求单服务器）
"""

import asyncio
import hashlib
import inspect
import json
import logging
import math
import os
import signal
import sys
import time
import uuid
from asyncio import Event, Lock, Semaphore
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import *
import script.proxy
# 修复 asyncio 兼容性
asyncio.iscoroutinefunction = inspect.iscoroutinefunction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ollama_client")

# ==================== 导入服务器发现模块 ====================

from script.servers import *


# ==================== 配置类 ====================


class Config:
    """全局配置"""

    # 持久化
    PERSISTENCE_FILE = str(Path("data/ollama_server_stats.json"))

    # 重试配置
    MAX_RETRY_ATTEMPTS = 5
    INITIAL_RETRY_DELAY = 1
    MAX_RETRY_DELAY = 60

    # 超时配置
    HTTP_TIMEOUT = 30
    CHAT_COMPLETION_TIMEOUT = 600
    EMBEDDING_TIMEOUT = 60
    IMAGE_GENERATION_TIMEOUT = 120

    # 空响应重试
    EMPTY_RESPONSE_MAX_RETRIES = 3
    EMPTY_RESPONSE_INITIAL_DELAY = 1.0

    # 并发配置
    MIN_TOKENS_FOR_SELECTION = 10

    # 服务器刷新间隔
    SERVER_REFRESH_INTERVAL = 24 * 60 * 60  # 24 小时

    # Track-and-Stop 算法配置
    TAS_WINDOW_SIZE = 200
    TAS_MIN_SAMPLES = 3
    TAS_EXPLORATION_RATE = 0.1
    TAS_DECAY_FACTOR = 0.995
    TAS_MIN_EXPLORATION = 0.02
    TAS_CONFIDENCE_THRESHOLD = 0.95
    TAS_LATENCY_WEIGHT = 0.4
    TAS_SUCCESS_WEIGHT = 0.4
    TAS_THROUGHPUT_WEIGHT = 0.2
    TAS_COOLDOWN_PERIOD = 30.0
    TAS_STATS_PERSIST_INTERVAL = 60

    # 断点续传
    TAS_CHECKPOINT_DIR = "data/checkpoints"
    TAS_CHECKPOINT_TTL = 3600


class ClientConfig:
    """客户端配置 - 动态模型列表"""

    DEFAULT_MODEL = "llama3.2:latest"

    @staticmethod
    def get_default_model(
        registry: Dict[str, Any],
    ) -> str:
        """从注册表中获取默认模型"""
        if registry:
            # 优先选择有多个服务器支持的模型
            best_model = ""
            best_count = 0
            for name, info in registry.items():
                count = len(info.get("servers", []))
                if count > best_count:
                    best_count = count
                    best_model = name
            if best_model:
                return best_model
        return ClientConfig.DEFAULT_MODEL


# ==================== 数据类 ====================


@dataclass
class ServerPerformanceSample:
    """单次服务器性能采样记录"""

    timestamp: float
    latency: float  # 首 Token 延迟 (秒)
    success: bool
    tokens_generated: int
    total_duration: float  # 总耗时 (秒)
    model: str


@dataclass
class ServerStats:
    """服务器统计数据 - Track-and-Stop 算法核心状态

    使用 Beta 分布建模成功率: Beta(alpha, beta)
    使用滑动窗口维护近期性能指标
    """

    # Beta 分布参数 (成功率先验)
    alpha: float = 1.0  # 成功次数 + 1 (Laplace 平滑)
    beta_param: float = 1.0  # 失败次数 + 1

    # 性能统计
    total_requests: int = 0
    total_successes: int = 0
    total_failures: int = 0

    # 滑动窗口
    recent_samples: deque = field(
        default_factory=lambda: deque(maxlen=Config.TAS_WINDOW_SIZE)
    )

    # 延迟统计 (指数移动平均)
    ema_latency: float = 1.0
    ema_throughput: float = 10.0

    # 冷却状态
    last_failure_time: float = 0.0
    consecutive_failures: int = 0

    # 探索计数
    exploration_count: int = 0
    exploitation_count: int = 0

    def record_success(
        self,
        latency: float,
        tokens: int,
        duration: float,
        model: str,
    ) -> None:
        """记录成功请求"""
        self.total_requests += 1
        self.total_successes += 1
        self.consecutive_failures = 0
        self.alpha += 1.0
        ema_alpha = 0.2
        self.ema_latency = (
            ema_alpha * latency + (1 - ema_alpha) * self.ema_latency
        )
        if duration > 0 and tokens > 0:
            throughput = tokens / duration
            self.ema_throughput = (
                ema_alpha * throughput
                + (1 - ema_alpha) * self.ema_throughput
            )
        self.recent_samples.append(
            ServerPerformanceSample(
                timestamp=time.time(),
                latency=latency,
                success=True,
                tokens_generated=tokens,
                total_duration=duration,
                model=model,
            )
        )

    def record_failure(self, model: str) -> None:
        """记录失败请求"""
        self.total_requests += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        self.beta_param += 1.0
        self.recent_samples.append(
            ServerPerformanceSample(
                timestamp=time.time(),
                latency=float("inf"),
                success=False,
                tokens_generated=0,
                total_duration=0.0,
                model=model,
            )
        )

    @property
    def success_rate(self) -> float:
        """后验成功率均值: E[Beta(a,b)] = a/(a+b)"""
        return self.alpha / (self.alpha + self.beta_param)

    @property
    def success_rate_variance(self) -> float:
        """后验成功率方差"""
        total = self.alpha + self.beta_param
        return (self.alpha * self.beta_param) / (
            total * total * (total + 1)
        )

    @property
    def is_cooling_down(self) -> bool:
        """是否在冷却期"""
        if self.consecutive_failures == 0:
            return False
        cooldown = Config.TAS_COOLDOWN_PERIOD * min(
            self.consecutive_failures, 10
        )
        return time.time() - self.last_failure_time < cooldown

    @property
    def window_success_rate(self) -> float:
        """滑动窗口内成功率"""
        if not self.recent_samples:
            return 0.5
        successes = sum(
            1 for s in self.recent_samples if s.success
        )
        return successes / len(self.recent_samples)

    @property
    def window_avg_latency(self) -> float:
        """滑动窗口内平均延迟"""
        successful = [
            s.latency
            for s in self.recent_samples
            if s.success
        ]
        if not successful:
            return self.ema_latency
        return sum(successful) / len(successful)

    def thompson_sample(self) -> float:
        """Thompson Sampling: 从 Beta 分布中采样"""
        import random

        try:
            x = random.gammavariate(self.alpha, 1.0)
            y = random.gammavariate(self.beta_param, 1.0)
            if x + y == 0:
                return 0.5
            return x / (x + y)
        except (ValueError, ZeroDivisionError):
            return 0.5

    def compute_composite_score(self) -> float:
        """计算综合质量评分"""
        sr = self.success_rate
        lat = self.ema_latency
        norm_latency = 1.0 / (1.0 + math.exp(lat - 2.0))
        thr = self.ema_throughput
        norm_throughput = 1.0 / (
            1.0 + math.exp(-(thr - 5.0) / 5.0)
        )
        score = (
            Config.TAS_SUCCESS_WEIGHT * sr
            + Config.TAS_LATENCY_WEIGHT * norm_latency
            + Config.TAS_THROUGHPUT_WEIGHT * norm_throughput
        )
        return score

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "alpha": self.alpha,
            "beta_param": self.beta_param,
            "total_requests": self.total_requests,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "ema_latency": self.ema_latency,
            "ema_throughput": self.ema_throughput,
            "last_failure_time": self.last_failure_time,
            "consecutive_failures": self.consecutive_failures,
            "exploration_count": self.exploration_count,
            "exploitation_count": self.exploitation_count,
            "success_rate": self.success_rate,
            "composite_score": self.compute_composite_score(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServerStats":
        """从字典反序列化"""
        stats = cls()
        stats.alpha = data.get("alpha", 1.0)
        stats.beta_param = data.get("beta_param", 1.0)
        stats.total_requests = data.get("total_requests", 0)
        stats.total_successes = data.get("total_successes", 0)
        stats.total_failures = data.get("total_failures", 0)
        stats.ema_latency = data.get("ema_latency", 1.0)
        stats.ema_throughput = data.get("ema_throughput", 10.0)
        stats.last_failure_time = data.get(
            "last_failure_time", 0.0
        )
        stats.consecutive_failures = data.get(
            "consecutive_failures", 0
        )
        stats.exploration_count = data.get(
            "exploration_count", 0
        )
        stats.exploitation_count = data.get(
            "exploitation_count", 0
        )
        return stats


@dataclass
class OllamaServer:
    """Ollama 服务器数据类"""

    ip: str
    base_url: str
    models: List[str] = field(default_factory=list)
    verified_at: float = 0.0
    is_available: bool = True
    stats: ServerStats = field(default_factory=ServerStats)


@dataclass
class StreamCheckpoint:
    """流式请求断点记录 - 用于断点续传"""

    checkpoint_id: str
    message: str
    model: str
    server_ip: str
    accumulated_content: str
    tokens_received: int
    last_chunk_time: float
    created_at: float

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "message": self.message,
            "model": self.model,
            "server_ip": self.server_ip,
            "accumulated_content": self.accumulated_content,
            "tokens_received": self.tokens_received,
            "last_chunk_time": self.last_chunk_time,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StreamCheckpoint":
        """反序列化"""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            message=data["message"],
            model=data["model"],
            server_ip=data.get("server_ip", ""),
            accumulated_content=data.get(
                "accumulated_content", ""
            ),
            tokens_received=data.get("tokens_received", 0),
            last_chunk_time=data.get("last_chunk_time", 0.0),
            created_at=data.get("created_at", 0.0),
        )

    @property
    def is_expired(self) -> bool:
        """检查断点是否过期"""
        return (
            time.time() - self.created_at
            > Config.TAS_CHECKPOINT_TTL
        )


@dataclass
class EmbeddingResult:
    """嵌入向量结果"""

    embedding: List[float]
    model: str


@dataclass
class TokenCountResult:
    """Token 计数结果"""

    input_tokens: int
    output_tokens: int = 0


@dataclass
class ExtractedFile:
    """提取的文件数据类"""

    source: str  # base64, url, local
    path_or_url: str
    mime_type: Optional[str] = None
    original_data: Optional[str] = None


# ==================== 工具类 ====================


class RetryManager:
    """重试管理器"""

    @staticmethod
    async def exponential_backoff(attempt: int) -> float:
        """指数退避计算"""
        if attempt <= 0:
            return Config.INITIAL_RETRY_DELAY
        delay = Config.INITIAL_RETRY_DELAY * (2 ** (attempt - 1))
        return min(delay, Config.MAX_RETRY_DELAY)

    @staticmethod
    async def should_retry(
        attempt: int,
        max_attempts: int = Config.MAX_RETRY_ATTEMPTS,
    ) -> bool:
        """判断是否应该重试"""
        return attempt < max_attempts

    @staticmethod
    async def retry_with_backoff(
        func: Callable, *args: Any, **kwargs: Any
    ) -> Any:
        """带退避的重试"""
        attempt = 0
        last_exception: Optional[Exception] = None
        while await RetryManager.should_retry(attempt):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                attempt += 1
                if await RetryManager.should_retry(attempt):
                    delay = (
                        await RetryManager.exponential_backoff(
                            attempt
                        )
                    )
                    logger.warning(
                        "重试 %d/%d: %s, 等待 %s 秒后重试",
                        attempt,
                        Config.MAX_RETRY_ATTEMPTS,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
        raise last_exception

    @staticmethod
    async def retry_on_empty_response(
        func: Callable,
        *args: Any,
        max_retries: int = Config.EMPTY_RESPONSE_MAX_RETRIES,
        initial_delay: float = Config.EMPTY_RESPONSE_INITIAL_DELAY,
        **kwargs: Any,
    ) -> Any:
        """空响应重试"""
        attempt = 0
        last_result: Any = None
        while attempt < max_retries:
            try:
                result = await func(*args, **kwargs)
                if result is None:
                    raise ValueError("Response is None")
                if isinstance(result, str) and not result.strip():
                    raise ValueError(
                        "Response is empty string"
                    )
                if isinstance(result, dict):
                    content = result.get(
                        "text", result.get("content", "")
                    )
                    if (
                        isinstance(content, str)
                        and not content.strip()
                    ):
                        raise ValueError(
                            "Response content is empty"
                        )
                return result
            except ValueError as e:
                last_result = None
                attempt += 1
                if attempt < max_retries:
                    delay = initial_delay * (
                        2 ** (attempt - 1)
                    )
                    logger.warning(
                        "空响应重试 %d/%d: %s, "
                        "等待 %.1f 秒后重试",
                        attempt,
                        max_retries,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "空响应重试次数已耗尽: %s", e
                    )
                    raise
            except Exception:
                raise
        return last_result


class FileUtils:
    """文件工具类"""

    @staticmethod
    def is_url(path: str) -> bool:
        """检查是否为 URL"""
        return path.startswith(("http://", "https://"))

    @staticmethod
    def is_base64_data_uri(data: str) -> bool:
        """检查是否为 Base64 数据 URI"""
        if not data or not isinstance(data, str):
            return False
        return data.startswith("data:") and ";base64," in data

    @staticmethod
    def extract_base64_image(data_uri: str) -> Optional[str]:
        """从 data URI 中提取 base64 数据"""
        if not FileUtils.is_base64_data_uri(data_uri):
            return None
        try:
            parts = data_uri.split(";base64,", 1)
            if len(parts) == 2:
                return parts[1]
        except Exception:
            pass
        return None


# ==================== 断点续传管理器 ====================


class CheckpointManager:
    """断点续传管理器"""

    def __init__(self) -> None:
        self._checkpoints: Dict[str, StreamCheckpoint] = {}
        self._lock = Lock()
        self._checkpoint_dir = Path(Config.TAS_CHECKPOINT_DIR)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

    async def save_checkpoint(
        self, checkpoint: StreamCheckpoint
    ) -> None:
        """保存断点"""
        async with self._lock:
            self._checkpoints[
                checkpoint.checkpoint_id
            ] = checkpoint
            try:
                filepath = (
                    self._checkpoint_dir
                    / f"{checkpoint.checkpoint_id}.json"
                )
                data = checkpoint.to_dict()
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(
                        data, f, ensure_ascii=False, indent=2
                    )
            except Exception as e:
                logger.warning("保存断点到磁盘失败: %s", e)

    async def get_checkpoint(
        self, checkpoint_id: str
    ) -> Optional[StreamCheckpoint]:
        """获取断点"""
        async with self._lock:
            cp = self._checkpoints.get(checkpoint_id)
            if cp and not cp.is_expired:
                return cp
            try:
                filepath = (
                    self._checkpoint_dir
                    / f"{checkpoint_id}.json"
                )
                if filepath.exists():
                    with open(
                        filepath, "r", encoding="utf-8"
                    ) as f:
                        data = json.load(f)
                    cp = StreamCheckpoint.from_dict(data)
                    if not cp.is_expired:
                        self._checkpoints[checkpoint_id] = cp
                        return cp
                    else:
                        filepath.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(
                    "从磁盘加载断点失败: %s", e
                )
            return None

    async def remove_checkpoint(
        self, checkpoint_id: str
    ) -> None:
        """移除断点"""
        async with self._lock:
            self._checkpoints.pop(checkpoint_id, None)
            try:
                filepath = (
                    self._checkpoint_dir
                    / f"{checkpoint_id}.json"
                )
                filepath.unlink(missing_ok=True)
            except Exception as e:
                logger.warning("删除断点文件失败: %s", e)

    async def find_checkpoint_for_message(
        self, message: str, model: str
    ) -> Optional[StreamCheckpoint]:
        """根据消息和模型查找可用断点"""
        msg_hash = hashlib.md5(
            message.encode("utf-8")
        ).hexdigest()
        async with self._lock:
            for cp in self._checkpoints.values():
                if cp.is_expired:
                    continue
                cp_msg_hash = hashlib.md5(
                    cp.message.encode("utf-8")
                ).hexdigest()
                if (
                    cp_msg_hash == msg_hash
                    and cp.model == model
                    and cp.tokens_received > 0
                ):
                    return cp
            return None

    async def cleanup_expired(self) -> int:
        """清理过期断点"""
        async with self._lock:
            expired_ids = [
                cid
                for cid, cp in self._checkpoints.items()
                if cp.is_expired
            ]
            for cid in expired_ids:
                del self._checkpoints[cid]
                try:
                    filepath = (
                        self._checkpoint_dir / f"{cid}.json"
                    )
                    filepath.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                for fp in self._checkpoint_dir.glob("*.json"):
                    try:
                        with open(
                            fp, "r", encoding="utf-8"
                        ) as f:
                            data = json.load(f)
                        created_at = data.get("created_at", 0)
                        if (
                            time.time() - created_at
                            > Config.TAS_CHECKPOINT_TTL
                        ):
                            fp.unlink(missing_ok=True)
                            expired_ids.append(fp.stem)
                    except Exception:
                        fp.unlink(missing_ok=True)
            except Exception:
                pass
            return len(expired_ids)


# ==================== Track-and-Stop 服务器选择器 ====================


class TrackAndStopSelector:
    """Track-and-Stop 最优服务器选择算法

    基于多臂赌博机 (Multi-Armed Bandit) 理论:
    - Track 阶段: 使用 Thompson Sampling 探索各服务器性能
    - Stop 阶段: 当置信度足够高时, 锁定最优服务器进行利用
    """

    def __init__(self, debug: bool = False) -> None:
        self._exploration_rate = Config.TAS_EXPLORATION_RATE
        self._total_selections = 0
        self._debug = debug
        self._lock = Lock()

    def _debug_print(self, message: str) -> None:
        """调试输出"""
        if self._debug:
            logger.debug("[TAS 选择器] %s", message)

    async def select_server(
        self,
        available_servers: List[OllamaServer],
        model: str = "",
    ) -> Optional[OllamaServer]:
        """选择最优服务器"""
        async with self._lock:
            if not available_servers:
                return None

            self._total_selections += 1

            # 过滤冷却中的服务器
            active_servers = [
                s
                for s in available_servers
                if not s.stats.is_cooling_down
            ]
            if not active_servers:
                active_servers = sorted(
                    available_servers,
                    key=lambda s: s.stats.last_failure_time,
                )
                active_servers = active_servers[:1]

            # 只有一个服务器，直接返回
            if len(active_servers) == 1:
                selected = active_servers[0]
                selected.stats.exploitation_count += 1
                return selected

            # 检查停止条件
            should_stop = self._check_stop_condition(
                active_servers
            )

            # epsilon-greedy 探索
            current_epsilon = self._get_current_epsilon()
            import random

            force_explore = random.random() < current_epsilon

            if should_stop and not force_explore:
                # 利用阶段
                selected = max(
                    active_servers,
                    key=lambda s: s.stats.compute_composite_score(),
                )
                selected.stats.exploitation_count += 1
                self._debug_print(
                    f"[利用] 选择 {selected.ip} "
                    f"评分={selected.stats.compute_composite_score():.4f}"
                )
            else:
                # 探索阶段
                selected = self._thompson_sampling_select(
                    active_servers
                )
                selected.stats.exploration_count += 1
                reason = (
                    "强制探索"
                    if force_explore
                    else "Thompson 采样"
                )
                self._debug_print(
                    f"[探索/{reason}] 选择 {selected.ip} "
                    f"总请求={selected.stats.total_requests}"
                )

            # 衰减探索率
            self._exploration_rate = max(
                Config.TAS_MIN_EXPLORATION,
                self._exploration_rate * Config.TAS_DECAY_FACTOR,
            )

            return selected

    def _check_stop_condition(
        self, servers: List[OllamaServer]
    ) -> bool:
        """检查停止条件"""
        min_samples = Config.TAS_MIN_SAMPLES
        for srv in servers:
            if srv.stats.total_requests < min_samples:
                return False

        if len(servers) < 2:
            return (
                servers[0].stats.total_requests >= min_samples
            )

        sorted_servers = sorted(
            servers,
            key=lambda s: s.stats.compute_composite_score(),
            reverse=True,
        )
        best = sorted_servers[0]
        second = sorted_servers[1]

        best_score = best.stats.compute_composite_score()
        second_score = second.stats.compute_composite_score()
        best_std = math.sqrt(
            best.stats.success_rate_variance
        )
        second_std = math.sqrt(
            second.stats.success_rate_variance
        )

        gap = best_score - second_score
        threshold = best_std + second_std
        has_enough_samples = (
            best.stats.total_requests >= min_samples * 2
        )
        is_confident = gap > threshold and has_enough_samples

        return is_confident

    def _thompson_sampling_select(
        self, servers: List[OllamaServer]
    ) -> OllamaServer:
        """Thompson Sampling 选择"""
        best_score = -1.0
        best_server = servers[0]
        import random

        for srv in servers:
            sampled_sr = srv.stats.thompson_sample()
            latency_bonus = random.gauss(0, 0.05)
            throughput_bonus = random.gauss(0, 0.05)

            lat = srv.stats.ema_latency
            norm_latency = 1.0 / (1.0 + math.exp(lat - 2.0))
            thr = srv.stats.ema_throughput
            norm_throughput = 1.0 / (
                1.0 + math.exp(-(thr - 5.0) / 5.0)
            )

            score = (
                Config.TAS_SUCCESS_WEIGHT * sampled_sr
                + Config.TAS_LATENCY_WEIGHT
                * (norm_latency + latency_bonus)
                + Config.TAS_THROUGHPUT_WEIGHT
                * (norm_throughput + throughput_bonus)
            )

            if score > best_score:
                best_score = score
                best_server = srv

        return best_server

    def _get_current_epsilon(self) -> float:
        """获取当前探索率"""
        return self._exploration_rate

    async def get_algorithm_stats(
        self, servers: Dict[str, OllamaServer]
    ) -> Dict[str, Any]:
        """获取算法统计信息"""
        async with self._lock:
            server_stats = {}
            for ip, srv in servers.items():
                server_stats[ip] = {
                    **srv.stats.to_dict(),
                    "is_cooling_down": srv.stats.is_cooling_down,
                    "window_success_rate": srv.stats.window_success_rate,
                    "window_avg_latency": srv.stats.window_avg_latency,
                    "models": srv.models,
                }

            total_explore = sum(
                srv.stats.exploration_count
                for srv in servers.values()
            )
            total_exploit = sum(
                srv.stats.exploitation_count
                for srv in servers.values()
            )
            return {
                "algorithm": (
                    "Track-and-Stop "
                    "(Thompson Sampling + epsilon-greedy)"
                ),
                "total_selections": self._total_selections,
                "current_epsilon": self._exploration_rate,
                "exploration_total": total_explore,
                "exploitation_total": total_exploit,
                "explore_ratio": (
                    total_explore
                    / max(total_explore + total_exploit, 1)
                ),
                "server_stats": server_stats,
            }


# ==================== 服务器池管理器 ====================


class ServerPool:
    """服务器池管理器

    管理所有已发现的 Ollama 服务器，
    维护模型到服务器的映射关系，
    使用 Track-and-Stop 算法进行最优选择。
    """

    def __init__(self, debug: bool = False) -> None:
        self.servers: Dict[str, OllamaServer] = {}
        self.model_to_servers: Dict[str, List[str]] = {}
        self.models_registry: Dict[str, Any] = {}
        self.lock = Lock()
        self.debug = debug
        self.selector = TrackAndStopSelector(debug=debug)
        self.checkpoint_manager = CheckpointManager()
        self._persist_executor: Optional[
            ThreadPoolExecutor
        ] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._stats_persist_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._initialized = False
        self.running = True
        self.shutdown_event = Event()
        self.persistence_file = Config.PERSISTENCE_FILE

    def _debug_print(self, message: str) -> None:
        """调试输出"""
        if self.debug:
            logger.debug("[服务器池] %s", message)

    def _load_stats_from_disk(self) -> None:
        """从磁盘加载 TAS 统计数据"""
        if not os.path.exists(self.persistence_file):
            self._debug_print(
                f"统计文件不存在: {self.persistence_file}"
            )
            return
        try:
            with open(
                self.persistence_file, "r", encoding="utf-8"
            ) as f:
                data = json.load(f)
            stats_data = data.get("server_stats", {})
            for ip, stats_dict in stats_data.items():
                if ip in self.servers:
                    self.servers[ip].stats = (
                        ServerStats.from_dict(stats_dict)
                    )
                else:
                    # 保留历史统计（服务器可能暂时不可用）
                    srv = OllamaServer(
                        ip=ip,
                        base_url=f"http://{ip}",
                        is_available=False,
                        stats=ServerStats.from_dict(stats_dict),
                    )
                    self.servers[ip] = srv
            self._debug_print(
                f"从磁盘加载 {len(stats_data)} 个服务器统计"
            )
        except Exception as e:
            self._debug_print(f"加载统计数据失败: {e}")

    def _save_stats_to_disk(self) -> None:
        """保存 TAS 统计数据到磁盘"""
        try:
            Path(self.persistence_file).parent.mkdir(
                parents=True, exist_ok=True
            )
            data = {
                "server_stats": {
                    ip: srv.stats.to_dict()
                    for ip, srv in self.servers.items()
                },
                "last_updated": time.time(),
            }
            temp_file = f"{self.persistence_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(
                    data, f, indent=2, ensure_ascii=False
                )
            os.replace(temp_file, self.persistence_file)
        except Exception as e:
            self._debug_print(f"保存统计数据失败: {e}")

    async def initialize(self) -> None:
        """初始化服务器池"""
        if self._initialized:
            return

        self._persist_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="persist"
        )

        # 加载或刷新服务器列表
        await self._refresh_server_list()

        # 加载历史统计
        self._load_stats_from_disk()

        # 启动后台任务
        self._refresh_task = asyncio.create_task(
            self._refresh_worker()
        )
        self._stats_persist_task = asyncio.create_task(
            self._stats_persist_worker()
        )
        self._cleanup_task = asyncio.create_task(
            self._cleanup_worker()
        )

        self._initialized = True
        self._debug_print(
            f"服务器池初始化完成: "
            f"{len(self.servers)} 个服务器, "
            f"{len(self.models_registry)} 个模型"
        )

    async def _refresh_server_list(self) -> None:
        """刷新服务器列表（在线程池中执行同步扫描）"""
        loop = asyncio.get_event_loop()
        try:
            servers_data, registry = await loop.run_in_executor(
                self._persist_executor,
                lambda: refresh_servers(force=needs_refresh()),
            )
        except Exception as e:
            logger.error("刷新服务器列表失败: %s", e)
            # 尝试从缓存加载
            try:
                servers_data, registry = (
                    await loop.run_in_executor(
                        self._persist_executor,
                        load_servers_data,
                    )
                )
            except Exception as e2:
                logger.error("加载缓存服务器数据也失败: %s", e2)
                return

        async with self.lock:
            # 更新模型注册表
            self.models_registry = registry

            # 更新服务器映射
            new_model_to_servers: Dict[str, List[str]] = {}

            for ip, server_info in servers_data.items():
                model_names = server_info.get(
                    "model_names", []
                )
                base_url = server_info.get(
                    "base_url", f"http://{ip}"
                )

                if ip in self.servers:
                    # 保留现有统计，更新模型列表和可用性
                    self.servers[ip].models = model_names
                    self.servers[ip].base_url = base_url
                    self.servers[ip].is_available = True
                    self.servers[ip].verified_at = (
                        server_info.get(
                            "verified_at", time.time()
                        )
                    )
                else:
                    self.servers[ip] = OllamaServer(
                        ip=ip,
                        base_url=base_url,
                        models=model_names,
                        verified_at=server_info.get(
                            "verified_at", time.time()
                        ),
                        is_available=True,
                    )

                for model in model_names:
                    if model not in new_model_to_servers:
                        new_model_to_servers[model] = []
                    new_model_to_servers[model].append(ip)

            # 标记不再可用的服务器（但保留统计）
            active_ips = set(servers_data.keys())
            for ip in self.servers:
                if ip not in active_ips:
                    self.servers[ip].is_available = False

            self.model_to_servers = new_model_to_servers

            self._debug_print(
                f"服务器列表已刷新: "
                f"{len(active_ips)} 个活跃, "
                f"{len(self.models_registry)} 个模型"
            )

    async def _refresh_worker(self) -> None:
        """定期刷新服务器列表"""
        while self.running and not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(
                    Config.SERVER_REFRESH_INTERVAL
                )
                if not self.running:
                    break
                logger.info("开始定期刷新服务器列表...")
                await self._refresh_server_list()
                # 持久化统计
                if self._persist_executor:
                    self._persist_executor.submit(
                        self._save_stats_to_disk
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("服务器刷新任务异常: %s", e)
                await asyncio.sleep(60)

    async def _stats_persist_worker(self) -> None:
        """TAS 统计定期持久化"""
        while self.running and not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(
                    Config.TAS_STATS_PERSIST_INTERVAL
                )
                if self._persist_executor and self.running:
                    self._persist_executor.submit(
                        self._save_stats_to_disk
                    )
                cleaned = (
                    await self.checkpoint_manager.cleanup_expired()
                )
                if cleaned > 0:
                    self._debug_print(
                        f"清理了 {cleaned} 个过期断点"
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._debug_print(
                    f"统计持久化任务异常: {e}"
                )
                await asyncio.sleep(10)

    async def _cleanup_worker(self) -> None:
        """清理过期数据"""
        while self.running and not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(60)

    async def get_server_for_model(
        self, model: str
    ) -> Optional[OllamaServer]:
        """根据模型名称获取最优服务器

        - 若只有一个服务器支持该模型，直接返回
        - 若多个服务器支持，使用 TAS 算法选择最优

        Args:
            model: 模型名称

        Returns:
            最优服务器或 None
        """
        async with self.lock:
            server_ips = self.model_to_servers.get(model, [])
            if not server_ips:
                self._debug_print(
                    f"没有服务器支持模型: {model}"
                )
                return None

            available = [
                self.servers[ip]
                for ip in server_ips
                if ip in self.servers
                and self.servers[ip].is_available
            ]

            if not available:
                self._debug_print(
                    f"模型 {model} 的所有服务器不可用"
                )
                return None

        # 单服务器直连
        if len(available) == 1:
            self._debug_print(
                f"模型 {model} 仅有一个服务器: "
                f"{available[0].ip}"
            )
            return available[0]

        # 多服务器 TAS 选择
        selected = await self.selector.select_server(
            available, model
        )
        if selected:
            self._debug_print(
                f"TAS 选择服务器 {selected.ip} 用于模型 "
                f"{model} (评分="
                f"{selected.stats.compute_composite_score():.4f})"
            )
        return selected

    async def record_success(
        self,
        server: OllamaServer,
        model: str,
        latency: float = 0.0,
        tokens: int = 0,
        duration: float = 0.0,
    ) -> None:
        """记录成功请求"""
        async with self.lock:
            server.stats.record_success(
                latency, tokens, duration, model
            )
        if self._persist_executor and self.running:
            self._persist_executor.submit(
                self._save_stats_to_disk
            )

    async def record_failure(
        self,
        server: OllamaServer,
        model: str,
    ) -> None:
        """记录失败请求"""
        async with self.lock:
            server.stats.record_failure(model)
        if self._persist_executor and self.running:
            self._persist_executor.submit(
                self._save_stats_to_disk
            )

    def get_available_models(self) -> List[str]:
        """获取所有可用模型名称"""
        return list(self.model_to_servers.keys())

    def get_model_info(
        self, model: str
    ) -> Optional[Dict[str, Any]]:
        """获取模型详细信息"""
        return self.models_registry.get(model)

    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        async with self.lock:
            active_servers = sum(
                1
                for s in self.servers.values()
                if s.is_available
            )
            total_models = len(self.model_to_servers)

            sorted_servers = sorted(
                [
                    s
                    for s in self.servers.values()
                    if s.is_available
                ],
                key=lambda x: x.stats.compute_composite_score(),
                reverse=True,
            )

            server_list = [
                {
                    "ip": srv.ip,
                    "base_url": srv.base_url,
                    "models": srv.models,
                    "is_available": srv.is_available,
                    "tas_score": round(
                        srv.stats.compute_composite_score(),
                        4,
                    ),
                    "success_rate": round(
                        srv.stats.success_rate, 4
                    ),
                    "ema_latency": round(
                        srv.stats.ema_latency, 3
                    ),
                    "total_requests": srv.stats.total_requests,
                    "consecutive_failures": (
                        srv.stats.consecutive_failures
                    ),
                    "is_cooling_down": (
                        srv.stats.is_cooling_down
                    ),
                }
                for srv in sorted_servers
            ]

            tas_stats = await self.selector.get_algorithm_stats(
                self.servers
            )

            return {
                "active_servers": active_servers,
                "total_servers": len(self.servers),
                "available_models": total_models,
                "model_names": list(
                    self.model_to_servers.keys()
                ),
                "servers": server_list,
                "tas_algorithm": tas_stats,
                "strategy": (
                    "Track-and-Stop "
                    "(Thompson Sampling + epsilon-greedy)"
                ),
            }

    async def force_refresh(self) -> None:
        """强制刷新服务器列表"""
        loop = asyncio.get_event_loop()
        try:
            servers_data, registry = (
                await loop.run_in_executor(
                    self._persist_executor,
                    lambda: refresh_servers(force=True),
                )
            )
            async with self.lock:
                self.models_registry = registry
                new_model_to_servers: Dict[str, List[str]] = {}
                active_ips = set(servers_data.keys())

                for ip, server_info in servers_data.items():
                    model_names = server_info.get(
                        "model_names", []
                    )
                    base_url = server_info.get(
                        "base_url", f"http://{ip}"
                    )

                    if ip in self.servers:
                        self.servers[ip].models = model_names
                        self.servers[ip].base_url = base_url
                        self.servers[ip].is_available = True
                        self.servers[ip].verified_at = (
                            server_info.get(
                                "verified_at", time.time()
                            )
                        )
                    else:
                        self.servers[ip] = OllamaServer(
                            ip=ip,
                            base_url=base_url,
                            models=model_names,
                            verified_at=server_info.get(
                                "verified_at", time.time()
                            ),
                            is_available=True,
                        )

                    for model in model_names:
                        if model not in new_model_to_servers:
                            new_model_to_servers[model] = []
                        new_model_to_servers[model].append(ip)

                for ip in self.servers:
                    if ip not in active_ips:
                        self.servers[ip].is_available = False

                self.model_to_servers = new_model_to_servers

            logger.info(
                "强制刷新完成: %d 服务器, %d 模型",
                len(active_ips),
                len(registry),
            )
        except Exception as e:
            logger.error("强制刷新失败: %s", e)

    async def shutdown(self) -> None:
        """关闭服务器池"""
        self.running = False
        self.shutdown_event.set()
        tasks_to_cancel = []
        if self._refresh_task:
            tasks_to_cancel.append(self._refresh_task)
        if self._stats_persist_task:
            tasks_to_cancel.append(self._stats_persist_task)
        if self._cleanup_task:
            tasks_to_cancel.append(self._cleanup_task)
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self._persist_executor:
            self._persist_executor.shutdown(wait=True)
            self._save_stats_to_disk()
        self._debug_print("服务器池已关闭")


# ==================== 异步 Ollama 客户端 ====================


class AsyncOllamaClient:
    """异步 Ollama 客户端

    核心特性:
    - Track-and-Stop 最优服务器选择
    - 断点续传
    - 动态模型发现
    - 无并发竞速（单请求单服务器）
    """

    def __init__(
        self,
        debug: bool = False,
    ) -> None:
        self.server_pool = ServerPool(debug=debug)
        self.session_lock = Lock()
        self.semaphore = Semaphore(100)
        self.connector: Optional[aiohttp.TCPConnector] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._closing = False
        self._initialized = False
        self.debug = debug
        self._init_lock = Lock()
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        try:
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(
                        self.graceful_shutdown()
                    ),
                )
        except (RuntimeError, NotImplementedError):
            pass

    def _debug_print(self, message: str) -> None:
        """调试输出"""
        if self.debug:
            logger.debug("[客户端] %s", message)

    async def ensure_initialized(self) -> None:
        """确保已初始化"""
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            await self.initialize()

    async def initialize(self) -> None:
        """初始化客户端"""
        if self._initialized:
            return
        try:
            self.connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
                ssl=False,
            )
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=aiohttp.ClientTimeout(
                    total=Config.HTTP_TIMEOUT
                ),
            )
            await self.server_pool.initialize()
            self._initialized = True
            self._debug_print("客户端初始化完成")
        except Exception as e:
            await self._cleanup_resources()
            raise e

    async def _cleanup_resources(self) -> None:
        """清理资源"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
        except Exception as e:
            self._debug_print(f"关闭 session 异常: {e}")
        try:
            if self.connector and not self.connector.closed:
                await self.connector.close()
        except Exception as e:
            self._debug_print(f"关闭 connector 异常: {e}")

    async def graceful_shutdown(self) -> None:
        """优雅关闭"""
        if self._closing:
            return
        self._closing = True
        self._debug_print("开始优雅关闭...")
        try:
            await self.close()
        except Exception as e:
            self._debug_print(f"关闭异常: {e}")
        finally:
            self._debug_print("优雅关闭完成")

    async def close(self) -> None:
        """关闭客户端"""
        if self._closing:
            return
        self._closing = True
        self._debug_print("关闭客户端...")
        try:
            await self.server_pool.shutdown()
        except Exception as e:
            self._debug_print(f"关闭服务器池异常: {e}")
        await self._cleanup_resources()
        await asyncio.sleep(0.1)
        self._initialized = False

    def _build_ollama_messages(
        self,
        prompt: str,
        images: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """构建 Ollama 消息格式

        Ollama /api/chat 接口要求 messages 为列表，
        每条消息包含 role 和 content 字段，
        图像通过 images 字段传递（base64 编码列表）。

        对于函数调用，prompt 已由 ollama_util 构建好
        NousXML fncall 格式，直接作为 user 消息发送。

        Args:
            prompt: 已构建好的提示词文本
            images: base64 编码的图像列表

        Returns:
            Ollama 格式的消息列表
        """
        message: Dict[str, Any] = {
            "role": "user",
            "content": prompt,
        }
        if images:
            message["images"] = images
        return [message]

    async def _send_chat_request_stream(
        self,
        server: OllamaServer,
        model: str,
        prompt: str,
        images: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        cancel_event: Optional[Event] = None,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """向 Ollama 服务器发送流式聊天请求

        使用 /api/chat 端点进行流式通信。

        Args:
            server: 目标服务器
            model: 模型名称
            prompt: 提示词
            images: base64 图像列表
            temperature: 温度
            top_p: Top-P
            max_tokens: 最大 token 数
            stop: 停止序列
            cancel_event: 取消事件

        Yields:
            文本块或元数据字典
        """
        messages = self._build_ollama_messages(prompt, images)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        # 构建 options
        options: Dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if top_p is not None:
            options["top_p"] = top_p
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if stop:
            options["stop"] = stop
        if options:
            payload["options"] = options

        request_url = f"{server.base_url}/api/chat"

        try:
            async with self.session.post(
                request_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(
                    total=Config.CHAT_COMPLETION_TIMEOUT
                ),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Ollama HTTP {response.status}: "
                        f"{error_text}"
                    )

                # Ollama 流式返回 NDJSON (每行一个 JSON)
                buffer = b""
                async for chunk in response.content.iter_any():
                    if (
                        cancel_event
                        and cancel_event.is_set()
                    ):
                        self._debug_print("请求被取消")
                        break
                    if not chunk:
                        continue

                    buffer += chunk
                    lines = buffer.split(b"\n")
                    buffer = lines[-1]  # 保留不完整的行

                    for line in lines[:-1]:
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(
                                line.decode(
                                    "utf-8", errors="replace"
                                )
                            )
                        except json.JSONDecodeError:
                            continue

                        # 检查错误
                        if "error" in data:
                            raise Exception(
                                f"Ollama 错误: "
                                f"{data['error']}"
                            )

                        # 提取消息内容
                        msg = data.get("message", {})
                        content = msg.get("content", "")
                        if content:
                            yield content

                        # 检查是否完成
                        if data.get("done", False):
                            # 提取使用量信息
                            usage_info: Dict[str, Any] = {}
                            if "prompt_eval_count" in data:
                                usage_info[
                                    "prompt_tokens"
                                ] = data["prompt_eval_count"]
                            if "eval_count" in data:
                                usage_info[
                                    "completion_tokens"
                                ] = data["eval_count"]
                            if (
                                "prompt_eval_count" in data
                                and "eval_count" in data
                            ):
                                usage_info["total_tokens"] = (
                                    data["prompt_eval_count"]
                                    + data["eval_count"]
                                )
                            if "total_duration" in data:
                                usage_info[
                                    "total_duration_ns"
                                ] = data["total_duration"]
                            if "eval_duration" in data:
                                usage_info[
                                    "eval_duration_ns"
                                ] = data["eval_duration"]
                            if usage_info:
                                yield {"usage": usage_info}
                            break

                # 处理剩余 buffer
                if buffer.strip():
                    try:
                        data = json.loads(
                            buffer.decode(
                                "utf-8", errors="replace"
                            )
                        )
                        msg = data.get("message", {})
                        content = msg.get("content", "")
                        if content:
                            yield content
                        if data.get("done", False):
                            usage_info = {}
                            if "prompt_eval_count" in data:
                                usage_info[
                                    "prompt_tokens"
                                ] = data["prompt_eval_count"]
                            if "eval_count" in data:
                                usage_info[
                                    "completion_tokens"
                                ] = data["eval_count"]
                            if usage_info:
                                yield {"usage": usage_info}
                    except json.JSONDecodeError:
                        pass

        except aiohttp.ClientError as e:
            raise Exception(
                f"Ollama 连接错误 ({server.ip}): {e}"
            )

    async def _send_chat_request_nonstream(
        self,
        server: OllamaServer,
        model: str,
        prompt: str,
        images: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """向 Ollama 服务器发送非流式聊天请求

        Args:
            server: 目标服务器
            model: 模型名称
            prompt: 提示词
            images: base64 图像列表
            temperature: 温度
            top_p: Top-P
            max_tokens: 最大 token 数
            stop: 停止序列

        Returns:
            包含响应内容和使用量的字典
        """
        messages = self._build_ollama_messages(prompt, images)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        options: Dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if top_p is not None:
            options["top_p"] = top_p
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if stop:
            options["stop"] = stop
        if options:
            payload["options"] = options

        request_url = f"{server.base_url}/api/chat"

        try:
            async with self.session.post(
                request_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(
                    total=Config.CHAT_COMPLETION_TIMEOUT
                ),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Ollama HTTP {response.status}: "
                        f"{error_text}"
                    )

                data = await response.json()

                if "error" in data:
                    raise Exception(
                        f"Ollama 错误: {data['error']}"
                    )

                msg = data.get("message", {})
                content = msg.get("content", "")

                usage_info: Dict[str, Any] = {}
                if "prompt_eval_count" in data:
                    usage_info["prompt_tokens"] = data[
                        "prompt_eval_count"
                    ]
                if "eval_count" in data:
                    usage_info["completion_tokens"] = data[
                        "eval_count"
                    ]
                if (
                    "prompt_eval_count" in data
                    and "eval_count" in data
                ):
                    usage_info["total_tokens"] = (
                        data["prompt_eval_count"]
                        + data["eval_count"]
                    )

                return {
                    "text": content,
                    "usage": usage_info,
                }

        except aiohttp.ClientError as e:
            raise Exception(
                f"Ollama 连接错误 ({server.ip}): {e}"
            )

    async def chat_stream(
        self,
        message: str,
        model: str,
        images: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        max_retries: int = 2,
        enable_checkpoint: bool = True,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """聊天流 (TAS 选择 + 断点续传)

        Args:
            message: 消息内容（已经是 NousXML fncall 格式的 prompt）
            model: 模型名称
            images: base64 图像列表
            temperature: 温度
            top_p: Top-P
            max_tokens: 最大 token 数
            stop: 停止序列
            max_retries: 最大重试次数
            enable_checkpoint: 是否启用断点续传

        Yields:
            文本块或元数据字典
        """
        await self.ensure_initialized()

        # 检查断点
        resume_checkpoint: Optional[StreamCheckpoint] = None
        if enable_checkpoint:
            resume_checkpoint = (
                await self.server_pool.checkpoint_manager.find_checkpoint_for_message(
                    message, model
                )
            )
            if resume_checkpoint:
                self._debug_print(
                    f"找到可用断点: "
                    f"{resume_checkpoint.tokens_received} tokens"
                )
                yield resume_checkpoint.accumulated_content

        checkpoint_id = uuid.uuid4().hex

        async with self.semaphore:
            for attempt in range(max_retries + 1):
                server = (
                    await self.server_pool.get_server_for_model(
                        model
                    )
                )
                if not server:
                    if attempt < max_retries:
                        await asyncio.sleep(2)
                        continue
                    raise Exception(
                        f"没有可用的服务器支持模型: {model}"
                    )

                start_time = time.time()
                first_token_time: Optional[float] = None
                tokens_received = 0
                accumulated_content = ""

                try:
                    async for chunk in (
                        self._send_chat_request_stream(
                            server=server,
                            model=model,
                            prompt=message,
                            images=images,
                            temperature=temperature,
                            top_p=top_p,
                            max_tokens=max_tokens,
                            stop=stop,
                        )
                    ):
                        if isinstance(chunk, dict):
                            yield chunk
                        else:
                            tokens_received += 1
                            accumulated_content += chunk
                            if first_token_time is None:
                                first_token_time = time.time()
                            yield chunk

                            # 定期保存断点
                            if (
                                enable_checkpoint
                                and tokens_received % 50 == 0
                            ):
                                cp = StreamCheckpoint(
                                    checkpoint_id=checkpoint_id,
                                    message=message,
                                    model=model,
                                    server_ip=server.ip,
                                    accumulated_content=accumulated_content,
                                    tokens_received=tokens_received,
                                    last_chunk_time=time.time(),
                                    created_at=time.time(),
                                )
                                await self.server_pool.checkpoint_manager.save_checkpoint(
                                    cp
                                )

                    # 成功完成
                    duration = time.time() - start_time
                    ftl = (
                        first_token_time - start_time
                        if first_token_time
                        else duration
                    )
                    await self.server_pool.record_success(
                        server,
                        model,
                        latency=ftl,
                        tokens=tokens_received,
                        duration=duration,
                    )

                    # 清除断点
                    await self.server_pool.checkpoint_manager.remove_checkpoint(
                        checkpoint_id
                    )
                    if resume_checkpoint:
                        await self.server_pool.checkpoint_manager.remove_checkpoint(
                            resume_checkpoint.checkpoint_id
                        )
                    return

                except Exception as e:
                    duration = time.time() - start_time
                    await self.server_pool.record_failure(
                        server, model
                    )

                    # 保存断点
                    if (
                        enable_checkpoint
                        and tokens_received > 0
                    ):
                        cp = StreamCheckpoint(
                            checkpoint_id=checkpoint_id,
                            message=message,
                            model=model,
                            server_ip=server.ip,
                            accumulated_content=accumulated_content,
                            tokens_received=tokens_received,
                            last_chunk_time=time.time(),
                            created_at=time.time(),
                        )
                        await self.server_pool.checkpoint_manager.save_checkpoint(
                            cp
                        )
                        self._debug_print(
                            f"异常中断, 断点已保存: "
                            f"{tokens_received} tokens"
                        )

                    self._debug_print(
                        f"尝试 {attempt + 1}/"
                        f"{max_retries + 1} 失败: {e}"
                    )
                    if attempt == max_retries:
                        raise
                    await asyncio.sleep(1)

    async def chat_completion(
        self,
        message: str,
        model: str,
        images: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """聊天补全 (非流式, TAS 选择)

        Args:
            message: 消息内容（已经是 NousXML fncall 格式的 prompt）
            model: 模型名称
            images: base64 图像列表
            temperature: 温度
            top_p: Top-P
            max_tokens: 最大 token 数
            stop: 停止序列

        Returns:
            包含文本和使用量的字典
        """
        await self.ensure_initialized()

        async def _do_completion() -> Dict[str, Any]:
            server = (
                await self.server_pool.get_server_for_model(
                    model
                )
            )
            if not server:
                raise Exception(
                    f"没有可用的服务器支持模型: {model}"
                )

            start_time = time.time()
            try:
                result = (
                    await self._send_chat_request_nonstream(
                        server=server,
                        model=model,
                        prompt=message,
                        images=images,
                        temperature=temperature,
                        top_p=top_p,
                        max_tokens=max_tokens,
                        stop=stop,
                    )
                )

                duration = time.time() - start_time
                content = result.get("text", "")
                tokens = len(content) // 3
                await self.server_pool.record_success(
                    server,
                    model,
                    latency=duration,
                    tokens=tokens,
                    duration=duration,
                )
                return result

            except Exception as e:
                duration = time.time() - start_time
                await self.server_pool.record_failure(
                    server, model
                )
                raise

        return await RetryManager.retry_on_empty_response(
            _do_completion
        )

    async def get_embeddings(
        self,
        text: Union[str, List[str]],
        model: str = "nomic-embed-text",
    ) -> List[List[float]]:
        """获取嵌入向量

        使用 Ollama /api/embed 端点。

        Args:
            text: 输入文本或文本列表
            model: 嵌入模型名称

        Returns:
            嵌入向量列表
        """
        await self.ensure_initialized()

        server = await self.server_pool.get_server_for_model(
            model
        )
        if not server:
            raise Exception(
                f"没有可用的服务器支持嵌入模型: {model}"
            )

        if isinstance(text, str):
            texts = [text]
        else:
            texts = text

        payload: Dict[str, Any] = {
            "model": model,
            "input": texts,
        }

        request_url = f"{server.base_url}/api/embed"

        try:
            async with self.session.post(
                request_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(
                    total=Config.EMBEDDING_TIMEOUT
                ),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Ollama 嵌入错误 "
                        f"HTTP {response.status}: "
                        f"{error_text}"
                    )

                data = await response.json()
                if "error" in data:
                    raise Exception(
                        f"Ollama 嵌入错误: {data['error']}"
                    )

                embeddings = data.get("embeddings", [])
                if not embeddings:
                    # 兼容旧版本 /api/embeddings 端点
                    embedding = data.get("embedding", [])
                    if embedding:
                        embeddings = [embedding]

                await self.server_pool.record_success(
                    server, model
                )
                return embeddings

        except Exception as e:
            await self.server_pool.record_failure(
                server, model
            )
            raise

    async def get_server_status(self) -> Dict[str, Any]:
        """获取服务器状态"""
        await self.ensure_initialized()
        return await self.server_pool.get_status()

    async def force_refresh_servers(self) -> None:
        """强制刷新服务器列表"""
        await self.ensure_initialized()
        await self.server_pool.force_refresh()

    def get_available_models(self) -> List[str]:
        """获取所有可用模型名称"""
        return self.server_pool.get_available_models()

    def get_model_info(
        self, model: str
    ) -> Optional[Dict[str, Any]]:
        """获取模型详细信息"""
        return self.server_pool.get_model_info(model)


# ==================== 导出 ====================

__all__ = [
    # 配置
    "Config",
    "ClientConfig",
    # 数据类
    "ServerPerformanceSample",
    "ServerStats",
    "OllamaServer",
    "StreamCheckpoint",
    "EmbeddingResult",
    "TokenCountResult",
    "ExtractedFile",
    # 工具类
    "RetryManager",
    "FileUtils",
    # 管理器
    "CheckpointManager",
    "TrackAndStopSelector",
    "ServerPool",
    # 主客户端
    "AsyncOllamaClient",
]


# ==================== 测试入口 ====================


async def _test_client() -> None:
    """测试客户端"""
    client = AsyncOllamaClient(debug=True)
    try:
        await client.ensure_initialized()

        # 获取状态
        status = await client.get_server_status()
        logger.info(
            "服务器状态: %s",
            json.dumps(status, ensure_ascii=False, indent=2),
        )

        # 获取可用模型
        models = client.get_available_models()
        logger.info("可用模型: %s", models)

        if models:
            test_model = models[0]
            logger.info("使用模型 %s 测试聊天...", test_model)

            # 测试非流式
            result = await client.chat_completion(
                message="你好，请简单介绍一下你自己。",
                model=test_model,
            )
            logger.info("非流式响应: %s", result)

            # 测试流式
            logger.info("测试流式聊天...")
            full = []
            async for chunk in client.chat_stream(
                message="请用一句话描述太阳。",
                model=test_model,
            ):
                if isinstance(chunk, str):
                    full.append(chunk)
                    print(chunk, end="", flush=True)
            print()
            logger.info("流式响应完成: %d 字符", len("".join(full)))

    except Exception as e:
        logger.error("测试失败: %s", e)
        raise
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(_test_client())
