# 平台开发规范

本文档是 Provider-V2 平台适配器的**唯一权威规范**。所有新增、修改、审计平台的行为必须遵守本文档。本文档只描述**应当如何**，不记录历史债务或当前偏差（偏差由本地 `RECORD.md` 跟踪，该文件已被 `.gitignore` 过滤，不入库）。

## 一、平台顶层结构

每个平台目录必须保持以下顶层结构：

```text
src/platforms/{platform}/
├── __init__.py
├── adapter.py
├── util.py
├── accounts.py
└── core/
```

即使平台**无需凭证**，`accounts.py` 也必须存在（框架统一从该文件导入 `API_KEYS` 或 `ACCOUNTS`）；此时按场景 A 提供空列表 `API_KEYS = []` 并加注释说明。

### 顶层文件语义

- `__init__.py`：对外导出门面。
- `adapter.py`：仅做门面 re-export。
- `util.py`：稳定导出、懒加载 `Adapter`、导出常量或纯函数门面。
- `accounts.py`：**只放凭证与账号数据**（详见"三"）。
- `core/`：真实实现（文件命名规则详见"二"）。

## 二、core 文件命名

`core/` 下每个文件必须以**职责**命名，强制以下两条规则：

1. **禁止泛化标签**：不得出现 `impl` / `misc` / `helper` / `utils` 等无职责指向的词。PlatformAdapter 接口实现**必须**命名为 **`adaptercore.py`**，其模块 docstring 必须明确职责（初始化 / 候选项 / 聊天补全 / 多模态 / 生命周期），网络请求下沉至 `.client`。
2. **禁止下划线**：文件名必须为单个小写单词，单词组合直接拼接（`adaptercore` / `streamparser` / `modelcache` / `userapi`），不使用 snake_case。

### 标准命名示例

| 职责 | 文件名 |
|---|---|
| PlatformAdapter 接口实现 | `adaptercore.py` |
| HTTP/RPC 客户端 | `client.py` |
| 鉴权 | `auth.py` |
| 会话管理 | `session.py` |
| 平台静态常量 | `constants.py` |
| 协议头/载荷 | `headers.py` / `payloads.py` |
| 流式解析 | `sse.py` / `streamparser.py` |
| 模型缓存 | `modelcache.py` |
| 持久化 | `persistence.py` |
| 部署端点 | `endpoints.py` |
| 对话状态 | `conversation.py` |

## 三、accounts.py 凭证组织

`accounts.py` 的职责是**凭证与账号数据**。Provider 框架通过 `from src.platforms.<name>.accounts import API_KEYS | ACCOUNTS` 加载凭证并构造 `Candidate` 列表。按平台鉴权形态从以下三类模板中选择其一，**不得跨场景混用**。

### 场景 A：纯 API Key

平台只需一组字符串 key，无附加字段。**必须**导出 `API_KEYS`（即使为空列表）。

```python
from __future__ import annotations
from typing import List

API_KEYS: List[str] = [
    "sk-your-api-key-here",
]
```

无凭证平台用空列表 + 注释占位，保持框架导入兼容：

```python
# <平台> 通过浏览器指纹 / 匿名访问鉴权，无需 API Key。
# 保留空列表以兼容 Provider-V2 凭证框架。
API_KEYS: List[str] = []
```

### 场景 B：结构化账号（Account dataclass）

平台需要绑定多个字段（`user_id` / `cookie` / `token` / `context_length` 等）。**必须**导出 `ACCOUNTS` 与 `Account` dataclass。

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class Account:
    api_key: str
    user_id: str = ""
    context_length: Optional[int] = None

ACCOUNTS: List[Account] = [
    Account(api_key="sk-...", user_id="u-..."),
]
```

### 场景 C：无凭证平台（服务器地址 / 注册表）

平台无需登录，凭证字段承载连接地址或注册表条目。**必须**导出 `ACCOUNTS` 与 `Account` dataclass。

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass(frozen=True)
class Account:
    server_url: str
    label: str = "default"
    meta: Dict[str, Any] = field(default_factory=dict)

ACCOUNTS: List[Account] = [
    Account(server_url="http://localhost:11434", label="default"),
]
```

### 可选扩展

允许额外导出 `from_config()` / `_load_accounts_from_config()` 支持 `config.toml` 动态注入**账号列表**（仅承载账号枚举，不承载端点 / 模型 / 能力等平台常量）。

### 禁区

`accounts.py` **禁止**承载以下字段，它们属于 `core/constants.py`：

- `BASE_URL` / 部署端点
- `USER_AGENT` / 浏览器指纹
- `BUILD_HASH` / `ACCOUNT_ID` 等平台固定标识
- 超时、模型清单、能力矩阵

## 四、BASE_URL 与平台常量

`BASE_URL` / `USER_AGENT` / `BUILD_HASH` / `MODELS` / `CAPS` 等平台级常量**只在平台代码内维护**，统一放在 `core/constants.py`。

### 强制规则

1. **禁止进入 `config.toml`**：`config.toml` 是 Provider 通用配置，只承载跨平台共享的开关与映射（`[server]` / `[gateway]` / `[fncall]` / `[proxy]` / `[platforms]` 黑/白名单）。**禁止**出现 `[platforms.<name>]` 等平台特定子段；平台特定常量由平台代码自己负责。
2. **禁止进入 `accounts.py`**：`accounts.py` 只放凭证，见"三"。
3. **默认值内置**：`core/constants.py` 中以 `BASE_URL = "https://..."` 直接赋值；切换端点时修改该常量即可。
4. **尾部斜杠**：`BASE_URL` 字面量不得以 `/` 结尾，避免拼接时出现 `//`。

### 示例

```python
# src/platforms/<name>/core/constants.py
from __future__ import annotations

BASE_URL = "https://example.com"
USER_AGENT = "..."
MODELS = ["model-a", "model-b"]
CAPS = {"chat": True, "vision": False, "image_gen": False, "upload": True}
```

### native_tools 能力

当平台的 upstream API 原生支持 OpenAI 格式的 `tools` / `tool_choice` 参数时，在 `CAPS` 中声明 `"native_tools": True`。网关将跳过 `inject_fncall` 协议注入，直接把 `tools` 和 `tool_choice` 透传到上游请求体中。

**适用场景**：平台使用标准 OpenAI-compatible chat/completions 接口，原生理解 `tools` 字段。

**不适用场景**：平台需要自定义 XML / 特殊格式注入工具定义（此时仅声明 `"tools": True`，网关通过 `inject_fncall` 完成协议转换）。

```python
# 原生工具平台示例
CAPS = {"chat": True, "vision": True, "tools": True, "native_tools": True}
```

**网关行为**：
- `native_tools=True` 时：消息不经过 `inject_fncall`，`tools` / `tool_choice` 作为 `**kw` 透传至 `adapter.complete()` -> `client` -> `build_payload()`。
- `native_tools=False`（默认）时：行为不变，仍通过 `inject_fncall` 注入。
- 流式响应中，native 平台返回的 `tool_calls` delta 由 client 层累积，流结束后以完整 `{"tool_calls": [...]}` dict 产出。
- `Candidate` dataclass 新增 `native_tools: bool = False` 字段；`ALL_CAPABILITIES` tuple 新增 `"native_tools"` 条目。

## 五、Adapter 与 util 规则

1. `adapter.py` 只做门面导出。
2. `util.py` 必须承担懒加载职责。
3. `Adapter` 通用别名必须存在，减少注册与导入歧义。
4. 如保留平台特定类名（如 `QwenAdapter`），必须同时支持 `Adapter` 别名。
5. `init()` 必须快速返回，耗时逻辑交给后台任务。
6. `close()` 必须清理后台任务、持久化状态、连接或缓存资源。

## 六、版本与文档同步

### 基准与跟踪关系

| 文件 | `.gitignore` 状态 | 角色 |
|---|---|---|
| `template/template_config.toml` | **未过滤** | 版本号**唯一基准**，入 git |
| `config.toml` | 过滤 | 运行时配置，本地**跟随**模板版本 |
| `README.md` | 未过滤 | 徽章与路线图同步基准版本 |
| `.agents/provider-guide/SKILL.md` | 过滤 | frontmatter 版本字段本地同步，作为 agent 自检参考 |

### 同步规则

1. **版本变更**：只改 `template/template_config.toml` 的 `server.version`（+0.0.1，不得大幅跳号），然后同步到 `config.toml` / `README.md` 徽章与路线图 / `SKILL.md` frontmatter。
2. **禁止硬编码版本**：源码中不得出现形如 `"version": "2.2.x"` 的字面量，统一读 `get_config().server.version`。
3. **`.gitignore` 过滤语义**：`README.md` 路线图与 `RECORD.md` 改动描述**只记录未被过滤的变更**。若某平台源码（如 `src/platforms/aitianhu2/`）或文件（如 `accounts.py` / `RECORD.md` / `config.toml`）被过滤，其变更**不得**出现在 `README.md` 路线图、版本徽章说明或 `RECORD.md` 描述中。
4. **过滤清单变更**：修改根 `.gitignore` 时，同步审视 `README.md` 已记录条目是否需要回滚。

## 七、逐平台合规矩阵

矩阵仅描述**当前是否达标**，不展开历史原因或迁移路径。

| 平台 | 顶层结构 | Adapter 通用门面 | 达标 |
|---|---|---|---|
| aitianhu2 | ✓ | ✓ | ✓ |
| apiairforce | ✓ | ✓ | ✓ |
| caiyuesbk | ✓ | ✓ | ✓ |
| cerebras | ✓ | ✓ | ✓ |
| chatmoe | ✓ | ✓ | ✓ |
| chutes | ✓ | ✓ | ✓ |
| codebuddy | ✓ | ✓ | ✓ |
| cursor | ✓ | ✓ | ✓ |
| deepseek | ✓ | ✓ | ✓ |
| edgetts | ✓ | ✓ | ✓ |
| gtts | ✓ | ✓ | ✓ |
| n1n | ✓ | ✓ | ✓ |
| nvidia | ✓ | ✓ | ✓ |
| ollama | ✓ | ✓ | ✓ |
| openaifm | ✓ | ✓ | ✓ |
| openrouter | ✓ | ✓ | ✓ |
| perplexity | ✓ | ✓ | ✓ |
| qwen | ✓ | ✓ | ✓ |

## 八、修改平台时的检查单

修改任一平台前后，至少检查：

1. `python -c` 导入平台包是否成功。
2. `Adapter` 是否可实例化或能给出明确跳过原因。
3. `name` / `supported_models` / `default_capabilities` 是否可访问。
4. 若涉及持久化：读写是否原子、是否减少无意义写盘。
5. 若涉及网络或后台任务：`close()` 是否真正释放资源。
6. 若涉及代理：是否遵循平台代理允许列表与平台本身能力限制。
7. 若修改 `accounts.py`：文件内只允许凭证字段；按场景 A / B / C 选择对应模板，不跨场景混用；不允许 `BASE_URL` / `USER_AGENT` / 超时 / 模型清单。
8. 若新增或重命名 `core/` 文件：遵守"二"（禁 `impl` 标签、禁下划线、`adaptercore` 为 PlatformAdapter 标准命名）。
9. 若修改 `BASE_URL` 等平台常量：只改 `core/constants.py`；不得同步修改 `config.toml` / `template/template_config.toml` / `accounts.py`。
10. 若改动涉及被 `.gitignore` 过滤的路径（如 `src/platforms/aitianhu2/`、`accounts.py`、`config.toml`、`.agents/`）：改动**不得**写入 `README.md` 路线图或 `RECORD.md` 改动描述（详见"六"）。
