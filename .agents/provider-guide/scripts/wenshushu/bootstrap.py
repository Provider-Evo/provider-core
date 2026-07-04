# -*- coding: utf-8 -*-
"""应用引导 / 装配模块。

提供 ``create_container`` 函数,用于创建并配置依赖注入容器,
将所有组件(Config、仓储、客户端、用例、EventBus)组装在一起。
"""
from __future__ import annotations

from .client import WenShuShuClient
from .container import Config, Container
from .fp import EventBus
from .repositories import (
    InMemoryFileRecordRepository,
    InMemoryTransferTaskRepository,
)
from .use_cases import DownloadUseCase, UploadUseCase


def create_container(config: Config | None = None) -> Container:
    """创建并配置依赖注入容器。

    Args:
        config: 配置对象。

    Returns:
        已配置的容器。

    >>> c = create_container()
    >>> isinstance(c.resolve(Config), Config)
    True
    """
    cfg = config or Config.from_env()
    container = Container()
    container.instance(Config, cfg)
    container.singleton(
        InMemoryFileRecordRepository,
        lambda c: InMemoryFileRecordRepository(),
    )
    container.singleton(
        InMemoryTransferTaskRepository,
        lambda c: InMemoryTransferTaskRepository(),
    )
    container.singleton(
        WenShuShuClient,
        lambda c: WenShuShuClient(c.resolve(Config)),
    )
    container.singleton(
        UploadUseCase,
        lambda c: UploadUseCase(
            c.resolve(WenShuShuClient),
            c.resolve(InMemoryFileRecordRepository),
        ),
    )
    container.singleton(
        DownloadUseCase,
        lambda c: DownloadUseCase(c.resolve(WenShuShuClient)),
    )
    container.singleton(EventBus, lambda c: EventBus())
    return container.build()
