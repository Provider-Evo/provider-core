# src/core/dispatch/runtime_view.py

该模块提供运行时视图聚合工具，用于收集平台状态、模型列表和配置摘要。

## 概述

提供一组辅助函数，用于构建 WebUI 和状态接口所需的只读汇总数据。

## 导出接口

- `collect_platform_status`：收集平台状态摘要
- `collect_model_entries`：收集模型列表
- `build_config_summary`：构建安全配置摘要
- `build_runtime_summary`：构建完整的运行时摘要

## 核心功能

### 1. 平台状态收集

`collect_platform_status` 函数：
- 遍历所有注册的平台适配器
- 收集每个平台的候选项数量、可用数量、模型数量
- 捕获异常并返回错误信息

### 2. 模型列表收集

`collect_model_entries` 函数：
- 委托给 `Registry.all_models()`
- 返回所有模型的字典列表

### 3. 配置摘要构建

`build_config_summary` 函数：
- 读取全局配置
- 返回安全的配置摘要（不含敏感信息）
- 覆盖服务器、认证、网关、代理、平台等配置

### 4. 运行时摘要构建

`build_runtime_summary` 函数：
- 组合平台状态、模型列表、配置摘要
- 添加平台能力和数量统计
- 返回完整的 WebUI 摘要载荷

## 函数签名

```python
async def collect_platform_status(registry: Any) -> Dict[str, Dict[str, Any]]
async def collect_model_entries(registry: Any) -> List[Dict[str, Any]]
def build_config_summary() -> Dict[str, Any]
async def build_runtime_summary(registry: Any) -> Dict[str, Any]
```

## 依赖关系

- **上游依赖**：`src/core/config`
- **被依赖**：`src/webui/routers/summary.py`, `src/routes/` 下的摘要接口
- **标准库**：`time`, `typing`

## 约束和注意事项

1. **只读操作**：所有函数均为只读，不修改任何状态
2. **异常处理**：平台状态收集时捕获异常，返回错误信息
3. **配置安全**：配置摘要不含密钥等敏感信息
4. **异步操作**：平台状态和模型收集需要异步调用

## 交互

- 与 `Registry` 配合获取平台和模型信息
- 与 `get_config` 配合读取配置
- 为 WebUI 和 API 提供汇总数据