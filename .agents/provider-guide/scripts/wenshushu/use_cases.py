# -*- coding: utf-8 -*-
"""应用服务 / 用例 / DTO 模块。

包含上传请求(UploadRequest)、下载请求(DownloadRequest)、
传输响应(TransferResponse) DTO,以及 UploadUseCase 与 DownloadUseCase。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .domain import FileRecord
from .exceptions import UseCaseError
from .repositories import InMemoryFileRecordRepository

if TYPE_CHECKING:
    from .client import WenShuShuClient


# ===========================================================================
# DTO (数据传输对象)
# ===========================================================================

@dataclass
class UploadRequest:
    """上传请求 DTO。

    Attributes:
        file_path: 文件路径。
        password: 密码(可选)。
        expire_days: 过期天数。
    """

    file_path: str
    password: str = ""
    expire_days: str = "1"


@dataclass
class DownloadRequest:
    """下载请求 DTO。

    Attributes:
        url: 下载链接或令牌。
        password: 密码(可选)。
    """

    url: str
    password: str = ""


@dataclass
class TransferResponse:
    """传输响应 DTO。

    Attributes:
        success: 是否成功。
        message: 消息。
        data: 额外数据。
    """

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


# ===========================================================================
# 用例
# ===========================================================================

class UploadUseCase:
    """上传用例。

    Args:
        client: 文叔叔客户端实例。
        file_repo: 文件记录仓储。
    """

    def __init__(self, client: WenShuShuClient, file_repo: InMemoryFileRecordRepository) -> None:
        self._client = client
        self._file_repo = file_repo

    def execute(self, request: UploadRequest) -> TransferResponse:
        """执行上传用例。

        Args:
            request: 上传请求。

        Returns:
            传输响应。
        """
        file_path = request.file_path
        if not os.path.isfile(file_path):
            raise UseCaseError(f"文件不存在: {file_path}", context={"file_path": file_path})
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        record = FileRecord(name=file_name, size=file_size)
        self._file_repo.save(record)
        try:
            result = self._client.upload(file_path)
            record.mark_uploaded()
            return TransferResponse(success=True, message="上传成功", data=result)
        except Exception as exc:
            record.mark_failed(str(exc))
            raise UseCaseError(f"上传失败: {exc}", context={"file": file_name}) from exc


class DownloadUseCase:
    """下载用例。

    Args:
        client: 文叔叔客户端实例。
    """

    def __init__(self, client: WenShuShuClient) -> None:
        self._client = client

    def execute(self, request: DownloadRequest) -> TransferResponse:
        """执行下载用例。

        Args:
            request: 下载请求。

        Returns:
            传输响应。
        """
        try:
            result = self._client.download(request.url, request.password)
            return TransferResponse(success=True, message="下载成功", data=result)
        except Exception as exc:
            raise UseCaseError(f"下载失败: {exc}", context={"url": request.url}) from exc
