# registry 模块

协议注册和获取模块，提供函数调用协议的注册和查询功能。

## 核心功能

### get_protocol

```python
def get_protocol(
    protocol_id: str = "",
    *,
    default_protocol: str = "",
    custom_prompt_en: str = "",
    custom_prompt_zh: str = "",
    platform_id: str = "",
    mapping: Optional[Dict[str, str]] = None,
) -> ToolProtocol:
```

获取协议，自动从项目配置读取默认协议和平台映射。

**优先级：**
1. `protocol_id`（API 请求显式指定）
2. `fncall_mapping`（管理员配置）
3. `default_protocol`（全局默认）

**参数：**
- `protocol_id`: 协议 ID
- `default_protocol`: 默认协议
- `custom_prompt_en`: 自定义英文提示词
- `custom_prompt_zh`: 自定义中文提示词
- `platform_id`: 平台 ID
- `mapping`: 平台到协议的映射

### list_protocols

```python
def list_protocols() -> list:
```

返回所有已注册的协议 ID 列表。

## 依赖关系

- 依赖 `echotools.fncall.registry` 提供基础注册功能
- 依赖 `echotools.protocol.base` 提供协议接口
- 依赖 `src.core.config` 获取项目配置

## 注意事项

- 协议优先级按上述顺序生效
- 自定义协议使用 `custom_prompt_en` 和 `custom_prompt_zh` 参数
- 平台映射配置在 `config.toml` 的 `[fncall]` 部分