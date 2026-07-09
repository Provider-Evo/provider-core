# src/core/dispatch/registry.py

该模块实现平台注册表，负责管理平台适配器和候选项。

## 概述

`Registry` 类封装 `echotools.plugin.registry.PluginRegistry`，提供平台发现、注册、候选项收集和选择功能。

## 导出接口

- `Registry`：平台注册表类

## 核心功能

### 1. 平台初始化

`init` 方法：
- 读取配置中的白名单/黑名单
- 发现并注册 `src.platforms` 下的平台适配器
- 验证必要方法（`init`, `candidates`, `ensure_candidates`, `complete`, `close`）

### 2. 候选项管理

- `get_candidates`：收集所有可用候选项，支持按模型和能力过滤
- `ensure_candidates`：确保平台提供足够数量的候选项
- `get_capable_candidate`：获取具备指定能力的候选项

### 3. 模型列表

- `all_models`：收集所有模型及其能力信息（/v1/models 格式）；合并适配器 `default_capabilities` 与候选项级能力，并对 whisper/transcribe 模型名补充 `audio_transcription`
- `list_models`：`all_models` 的别名

### 4. 平台重载

- `reload_platform` / `reload_platforms`：从 `plugins/` 热重载 platform 适配器
- `reload_plugins`：全量插件运行时重建（Admin API）
- `reload_plugins_by_ids`：按 manifest `id` 精确重载；`reload_app=False` 时仅 platform adapter，跳过 L3

`reload_platform` 方法支持动态重载指定平台适配器。

## 函数签名

```python
class Registry:
    def __init__(self) -> None
    async def init(self, session: Any) -> None
    async def reload_platform(self, platform_name: str, session: Any) -> bool
    async def get_candidates(self, model: Optional[str] = None, capability: Optional[str] = None) -> List[Candidate]
    async def ensure_candidates(self, model: str, count: int) -> None
    def adapter_for(self, c: Candidate) -> Optional[Any]
    async def get_capable_adapter(self, capability: str) -> Optional[Any]
    async def get_capable_candidate(self, capability: str) -> Optional[Candidate]
    async def all_models(self) -> List[Dict[str, Any]]
    async def list_models(self) -> List[Dict[str, Any]]
    async def close(self) -> None
```

## 依赖关系

- **上游依赖**：`echotools.plugin.registry.PluginRegistry`
- **被依赖**：`src/core/dispatch/gateway.py`, `src/routes/chat.py`
- **内部依赖**：`src/core/dispatch/candidate.py`, `src/core/dispatch/selector.py`

## 约束和注意事项

1. **持久化路径**：选择器数据存储在 `persist/gateway/`
2. **平台发现**：仅发现 `src.platforms` 下的平台
3. **过滤逻辑**：候选项必须 `available=True` 且 `busy=False`
4. **错误处理**：平台 `ensure_candidates` 失败时记录警告但继续

## 交互

- 与 `Selector` 配合进行候选项选择
- 与平台适配器配合获取候选项
- 与 `Gateway` 配合提供请求路由