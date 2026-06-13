"""CDN URL 构建工具（纯函数，无 I/O）。"""

from __future__ import annotations

from .endpoints import VIDEO_CDN_BASE


def build_cdn_video_url(
    user_id: str,
    video_type: str,
    message_id: str,
    task_id: str,
    token: str,
) -> str:
    """构建视频 CDN 下载 URL。

    Args:
        user_id: 用户 ID。
        video_type: 视频类型（如 ``i2v``）。
        message_id: 消息 ID。
        task_id: 任务 ID。
        token: Bearer 令牌（用于 ``key`` 查询参数）。

    Returns:
        完整的 CDN 视频 URL。

    Examples:
        >>> build_cdn_video_url("u", "i2v", "m", "t", "k")
        'https://cdn.qwenlm.ai/output/u/i2v/m/t.mp4?key=k'
    """
    return "{}/{}/{}/{}/{}.mp4?key={}".format(
        VIDEO_CDN_BASE,
        user_id,
        video_type,
        message_id,
        task_id,
        token,
    )
