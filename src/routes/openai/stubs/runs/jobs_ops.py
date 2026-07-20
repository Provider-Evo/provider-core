
import aiohttp.web

from src.foundation.logger import get_logger
from src.routes.openai.chat.helpers import (
    _err,
    _json,
    _not_supported,
)

logger = get_logger(__name__)

# =======================================================================
# Fine-tuning
# =======================================================================


async def create_fine_tuning_job(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建微调任务端点 /v1/fine_tuning/jobs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _not_supported("Fine-tuning")


async def list_fine_tuning_jobs(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """微调任务列表端点 /v1/fine_tuning/jobs。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_fine_tuning_job(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取微调任务详情端点 /v1/fine_tuning/jobs/{job_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Job not found", "job_not_found")


async def cancel_fine_tuning_job(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消微调任务端点 /v1/fine_tuning/jobs/{job_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Job not found", "job_not_found")


async def list_fine_tuning_events(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """微调任务事件列表端点 /v1/fine_tuning/jobs/{job_id}/events。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


# =======================================================================
# Batch
# =======================================================================


async def create_batch(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """创建批处理任务端点 /v1/batches。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _not_supported("Batch")


async def list_batches(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """批处理任务列表端点 /v1/batches。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _json({"object": "list", "data": []})


async def retrieve_batch(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """获取批处理任务详情端点 /v1/batches/{batch_id}。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Batch not found", "batch_not_found")


async def cancel_batch(
    request: aiohttp.web.Request,
) -> aiohttp.web.Response:
    """取消批处理任务端点 /v1/batches/{batch_id}/cancel。

    Args:
        request: 请求对象。

    Returns:
        响应对象。
    """
    return _err(404, "Batch not found", "batch_not_found")
