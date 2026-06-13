# 代理系统

## 概览

代理系统支持多级控制：

1. **全局代理** — 通过 `config.toml` 或环境变量配置
2. **平台级代理切换** — 每个平台可独立启用/关闭代理
3. **Qwen WAF 自动切换** — 检测到 WAF 自动启用 24 小时

## 全局代理

### 配置方式

**config.toml：**
```toml
[proxy]
proxy_server = "http://110.42.196.178:40000"
proxy_enabled = true
proxy_list_type = "whitelist"
proxy_urls = []  # URL 匹配模式
```

**环境变量（自动检测）：**
```bash
set HTTP_PROXY=http://127.0.0.1:10808
set HTTPS_PROXY=http://127.0.0.1:10808
set ALL_PROXY=socks5://127.0.0.1:10808
```

环境变量优先级高于 config.toml。

### 支持的代理协议

| 协议 | 格式 | 说明 |
|------|------|------|
| HTTP | `http://host:port` | 标准 HTTP 代理 |
| HTTPS | `https://host:port` | HTTPS 代理 |
| SOCKS5 | `socks5://host:port` | SOCKS5 代理 |
| SOCKS5H | `socks5h://host:port` | SOCKS5 远程 DNS |
| SOCKS4 | `socks4://host:port` | SOCKS4 代理 |

### 实现机制

代理通过 **monkey-patching** 实现：
- `src/core/proxy.py` 在导入时 patch `aiohttp.ClientSession` 和 `requests.Session`
- `_should_proxy_url(url)` 判断 URL 是否走代理（whitelist/blacklist）
- HTTP/HTTPS 代理使用 aiohttp 原生 `proxy` 参数
- SOCKS 代理需要 `aiohttp-socks` 库，使用 `SocksConnector`

## 平台级代理切换

### 配置

```toml
[platforms_proxy]
# 只有在此列表中的平台，set_proxy_enabled() 才有效
enabled_platforms = ["qwen"]
```

### API

```python
# 在适配器上调用
adapter.set_proxy_enabled(True)    # 强制使用代理
adapter.set_proxy_enabled(False)   # 强制不使用代理
adapter.is_proxy_allowed()         # 是否被允许使用代理切换
adapter.is_proxy_enabled()         # 当前是否启用
```

### 工作原理

- `_proxy_override: Optional[bool]` 控制行为
- `None` → 使用全局代理行为（由 patch 决定）
- `True` → 强制传入代理 URL
- `False` → 强制传入 `None`（不走代理）
- 在 `session.post()` 时通过 `proxy` kwarg 覆盖全局 patch

### 限制

**不在 `enabled_platforms` 列表中的平台，无论如何调用 `set_proxy_enabled()` 都无效。**

## Qwen WAF 自动切换

### 触发条件

`_do_request` 中检测到响应 `Content-Type` 包含 `text/html` → 抛出 `WAFBlockedError`

### 自动行为

1. `complete()` 重试循环捕获 `WAFBlockedError`
2. 检查平台是否在 `enabled_platforms` 中
3. 调用 `set_proxy_enabled(True, auto=True)`
4. 保存持久化到 `persist/qwen/usage.json`
5. 重试请求（此时使用代理）

### 24 小时过期

- `_proxy_auto_enabled_at` 记录启用时间戳
- 每次 `_get_proxy_kwarg()` 时检查是否超过 86400 秒
- 过期后自动关闭代理
- 再次遇到 WAF 时再次启用

### 持久化格式

```json
{
  "proxy": {
    "enabled": true,
    "auto_enabled_at": 1718000000.0
  }
}
```

## 依赖

- `aiohttp-socks>=0.8.0` — SOCKS 代理支持（可选）
- `requests` — 自动 patch `requests.Session`
