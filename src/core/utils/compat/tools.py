from __future__ import annotations

"""工具调用统一接口。

将 ``echotools`` 中分散在多个子模块的工具调用相关符号集中重导出，
外部代码统一从 ``core.tools`` 导入，与底层库的内部结构解耦。

模块职责
--------
此模块是纯重导出层，不包含任何业务逻辑。底层实现变更时，
只需修改此文件的 import 路径，所有调用方无感知。

导出符号说明
------------

注入与解析
~~~~~~~~~~
- :func:`inject_fncall` — 将工具调用注入到消息流中。
- :func:`parse_fncall` — 从模型输出中解析工具调用（通用格式）。
- :func:`parse_fncall_xml` — 从模型输出中解析工具调用（XML 格式）。
- :class:`FncallStreamParser` — 流式解析器，用于增量处理模型输出。

格式化与标准化
~~~~~~~~~~~~~~
- :func:`format_tool_descs` — 将工具描述格式化为模型可识别的字符串。
- :func:`normalize_content` — 标准化消息内容格式。

循环检测
~~~~~~~~
- :func:`detect_tool_loop` — 检测工具调用是否陷入循环。
- :class:`LoopDetectionResult` — 循环检测结果的数据类。

协议抽象
~~~~~~~~
- :class:`ToolProtocol` — 工具协议基类，定义工具调用的序列化规范。
- :func:`get_protocol` — 根据协议名称获取对应的 :class:`ToolProtocol` 实例。

使用示例
--------
.. code-block:: python

    from core.tools import (
        inject_fncall,
        parse_fncall,
        FncallStreamParser,
        format_tool_descs,
        detect_tool_loop,
        LoopDetectionResult,
        ToolProtocol,
        get_protocol,
    )

    # 获取协议实例
    protocol = get_protocol("openai")

    # 格式化工具描述
    tool_desc = format_tool_descs(tools, protocol)

    # 流式解析
    parser = FncallStreamParser(protocol)
    for chunk in stream:
        result = parser.feed(chunk)

    # 循环检测
    detection: LoopDetectionResult = detect_tool_loop(call_history)
    if detection.is_loop:
        raise RuntimeError("工具调用陷入循环")

兼容性说明
----------
此模块保持与原始 ``core/tools.py`` 完全相同的 ``__all__`` 导出列表，
所有原有 ``from core.tools import ...`` 的调用方无需修改。
"""

from echotools.fncall import (
    FncallStreamParser,
    LoopDetectionResult,
    detect_tool_loop,
    format_tool_descs,
    inject_fncall,
    normalize_content,
    parse_fncall,
    parse_fncall_xml,
)
from echotools.fncall.registry import get_protocol
from echotools.protocol.base import ToolProtocol

__all__ = [
    # 注入与解析
    "inject_fncall",
    "parse_fncall",
    "parse_fncall_xml",
    "FncallStreamParser",
    # 格式化与标准化
    "format_tool_descs",
    "normalize_content",
    # 循环检测
    "detect_tool_loop",
    "LoopDetectionResult",
    # 协议抽象
    "ToolProtocol",
    "get_protocol",
]
