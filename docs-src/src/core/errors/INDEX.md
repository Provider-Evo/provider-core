# errors 模块

错误处理模块，定义了 Provider-V2 的完整错误层次结构。

## 目录结构

```
errors/
├── __init__.py      # 错误类重导出 + classify_http_error
├── base.py          # 基础错误类 ProviderError
├── business.py      # 业务级异常
└── platform.py      # 平台级异常
```

## 核心类

### ProviderError (base.py)

所有错误的基类，提供：
- `message`: 错误消息
- `original`: 原始异常（可选）
- `status_code`: HTTP 状态码（默认 500）
- `error_type`: snake_case 错误类型名（自动生成）
- `to_dict()`: 序列化为 JSON 兼容字典

### 业务级异常 (business.py)

网关自身的业务逻辑错误：

| 异常类 | 状态码 | 说明 |
|--------|--------|------|
| `NoCandidateError` | 503 | 无可用候选项 |
| `NetworkError` | 502 | 网络连接失败、超时 |
| `ConfigError` | 500 | 配置文件格式错误 |
| `ValidationError` | 400 | 请求体格式或参数不合法 |
| `RequestTimeoutError` | 504 | 平台响应超时 |
| `NotSupportedError` | 501 | 功能不支持 |

### 平台级异常 (platform.py)

平台侧返回的错误：

| 异常类 | 状态码 | 说明 |
|--------|--------|------|
| `PlatformError` | 500 | 平台通用错误基类 |
| `AuthError` | 401 | 认证失败 |
| `LoginError` | 401 | 登录失败 |
| `TokenExpiredError` | 401 | Token 过期 |
| `UploadError` | 502 | 文件上传失败 |
| `PoWError` | 500 | PoW 计算失败 |
| `EmbeddingError` | 500 | 嵌入向量生成失败 |
| `RateLimitError` | 429 | 速率限制 |
| `ModelNotFoundError` | 404 | 模型不存在 |
| `ContextLengthError` | 400 | 上下文长度超限 |
| `StreamError` | 500 | 流式响应错误 |
| `ServerError` | 5xx | 上游服务器错误 |
| `ImageError` | 500 | 图像处理错误 |
| `AudioError` | 500 | 音频处理错误 |
| `VideoError` | 500 | 视频处理错误 |
| `RerankError` | 500 | 重排序错误 |
| `ModerationError` | 500 | 内容审核错误 |
| `FileError` | 500 | 文件操作错误 |
| `BatchError` | 500 | 批处理错误 |
| `QuotaExceededError` | 402 | 配额耗尽 |

## 关键函数

### classify_http_error

```python
def classify_http_error(
    status_code: int,
    message: str,
    original: Optional[Exception] = None,
) -> ProviderError:
```

将 HTTP 状态码分类为对应的类型化错误实例。支持：
- 400: 根据消息内容区分 `ContextLengthError` 和 `ValidationError`
- 401: `AuthError`
- 402: `QuotaExceededError`
- 404: `ModelNotFoundError`
- 408/504: `RequestTimeoutError`
- 429: `RateLimitError`
- 5xx: `ServerError`
- 其他: `PlatformError`

## 依赖关系

- 被所有平台适配器使用
- 被路由处理器使用进行错误响应
- 被调度器使用进行候选项过滤

## 注意事项

- 所有错误类都继承自 `ProviderError`，可通过 `isinstance` 检查
- `to_dict()` 方法用于生成标准错误响应格式
- `error_type` 属性自动从类名生成 snake_case 名称