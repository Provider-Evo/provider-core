# DeepSeek 平台说明

## 概览

DeepSeek 平台（DeepSeek 网页版）支持：

- 文本聊天（t2t，含 thinking / search 模式）
- 视觉理解（vision）

## 架构

```
DeepSeekAdapter (adapter_impl.py)
  └── DeepseekClient (client.py)
      ├── 账号管理 (_candidates, _rebuild_candidates)
      ├── HIF 令牌管理 (_hif_managers, 后台刷新)
      ├── PoW 计算 (WasmPow, WASM 下载)
      ├── 流式补全 (_do_stream_request)
      └── 模型缓存 (ModelsCache, 独立副本)
```

## 关键文件

| 文件 | 说明 |
|------|------|
| `client.py` | 核心客户端，HIF 管理、PoW、流式补全 |
| `adapter_impl.py` | 适配器实现 |
| `hif.py` | HIF 令牌管理器（HTTP 身份伪造令牌） |
| `pow.py` | WASM PoW 计算器 |
| `models_cache.py` | DeepSeek 专用的模型缓存（与 src/core/ 中的不同） |
| `session_api.py` | 会话管理 API |
| `user_api.py` | 用户管理 API |

## HIF 系统

DeepSeek 使用 HIF（HTTP Identity Forgery）机制：
- 每个账号有独立的 `HifTokenManager`
- HIF 令牌需要定期刷新
- 后台 Task `_bg_hif_refresh` 负责自动刷新

## PoW 系统

- 使用 WebAssembly 进行 PoW（Proof of Work）计算
- WASM 文件在启动时下载（`download_wasm`）
- 后台每 24 小时检查 WASM 更新

## 代理切换

DeepSeek 支持 **手动代理切换**：

```python
adapter.set_proxy_enabled(True)   # 强制使用代理
adapter.set_proxy_enabled(False)  # 强制不使用代理
adapter.is_proxy_enabled()        # 查询当前状态
```

### 前提条件

DeepSeek 必须在 `config.toml` 的 `[platforms_proxy].enabled_platforms` 中：

```toml
[platforms_proxy]
enabled_platforms = ["qwen", "deepseek"]  # 添加 deepseek 以启用
```

**不在列表中时，`set_proxy_enabled()` 无效。**

### 限制

- **无自动触发** — 不会因 WAF 或其他错误自动切换代理
- **状态不持久化** — 代理状态仅存于内存，重启后恢复默认

## 请求流程

1. 使用账号的 session cookie 和 HIF 令牌
2. 创建会话 (`/api/v0/chat/new_session`)
3. 发送补全请求 (`/api/v0/chat/completion`)
4. SSE 流式解析 (`_parse_sse_stream`)
5. 处理 continue 截断（最多 `MAX_CONTINUE` 次续写）
6. 后台停止会话

## 注意事项

1. **`models_cache.py` 是独立副本** — 与 `src/core/models_cache.py` 不同
2. **无 `test.py` 文件** — 需要手动测试
3. **黑名单默认包含 deepseek** — 需从 `platform_list` 中移除才能启用
4. **HIF 是核心认证机制** — 与常规 token 不同
