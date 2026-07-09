# inject 模块

函数调用注入模块，提供函数调用注入到提示词的功能。

## 核心功能

### inject_fncall

```python
def inject_fncall(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    protocol: ToolProtocol,
    lang: str = "en",
    user_system_prompt: str = "",
    loop_detection_threshold: int = 3,
    dump_prompt: bool = True,
) -> List[Dict[str, Any]]:
```

将函数调用注入到消息列表中。

**参数：**
- `messages`: 消息列表
- `tools`: 工具定义列表
- `protocol`: 工具协议
- `lang`: 语言（"en" 或 "zh"）
- `user_system_prompt`: 用户系统提示词
- `loop_detection_threshold`: 循环检测阈值
- `dump_prompt`: 是否转储提示词

**返回：**
- 注入后的消息列表

## 依赖关系

- 依赖 `echotools.fncall.prompt.inject` 提供基础注入功能
- 依赖 `echotools.protocol.base.ToolProtocol` 协议接口
- 依赖 `src.core.config` 获取配置

## 注意事项

- 提示词转储功能可选，需要配置 `fncall.print_prompt` 或 `fncall.record_prompt`
- 转储目录为 `logs/prompts`
- 循环检测阈值默认为 3