# MISTAKES.md -- 错误、意外与易混淆点

> **用途**：本文件记录 AI 代理在本项目中工作时常见的错误和易混淆之处。
> 如果你遇到了意外情况，请立即告知开发者并追加到本文件中，
> 以防未来的代理重蹈覆辙。
>
> **活文档**：在工作过程中实时更新本文件。
> **最后更新：** 2026-07-04T23:20:00+08:00

---

## 项目身份

Python aiohttp API 代理网关（provider-v2.1-beta），将 OpenAI/Anthropic 格式请求转发到多个 AI 平台（Qwen、DeepSeek、Ollama、AItianhu2）。核心技术栈：aiohttp + tomllib + aiohttp.web 原生服务器（非 ASGI/uvicorn）。

## 必须避免的严重错误

### [CRITICAL] 项目没有 pyproject.toml，不可作为 pip 包安装
**你会假设：** 标准 Python 项目有 pyproject.toml 或 setup.py，可以 `pip install -e .`
**实际情况：** `pyproject.toml` 已存在（`provider-guide` 元数据 + 依赖 SSOT），但日常仍从项目根执行 `python main.py`；`requirements.txt` 由 pyproject 核心依赖同步生成，可选 extras 见 `[project.optional-dependencies]`
**犯错后果：** 忽略 optional 依赖会导致 DeepSeek PoW（wasmtime）、SSH 终端（paramiko）等功能不可用
**正确做法：** 核心依赖 `pip install -r requirements.txt`；按需 `pip install -e ".[deepseek,ssh,async-perf]"`

### [CRITICAL] 删除 config.toml 会静默改变运行时行为
**你会假设：** 删除与默认值相同的配置条目是安全的
**实际情况：** 两个关键字段代码默认值与 config.toml 相反：
- `gateway.concurrent_enabled`: 代码默认 True，config.toml 为 false
- `proxy.proxy_enabled`: 代码默认 False，config.toml 为 true
**犯错后果：** 删除 config.toml 会意外启用并发、禁用代理
**正确做法：** 修改 config.toml 时注意这两个字段的代码默认值与文件值相反

### [CRITICAL] Runner-Worker 架构中 subprocess.Popen 必须传递 env 参数
**你会假设：** 子进程会继承父进程的环境变量
**实际情况：** `subprocess.Popen` 默认不传 `env` 参数时，子进程不会获得 `WORKER_PROCESS=1`，导致 Worker 误以为自己是 Runner 又 fork 新进程
**犯错后果：** 无限嵌套启动，Worker 立即退出
**正确做法：** `_run_runner()` 中 `subprocess.Popen(..., env=env)` 必须传递 env

### [CRITICAL] 平台黑名单优先于 per-platform enabled 设置
**你会假设：** `[platforms.deepseek].enabled = true` 意味着平台已启用
**实际情况：** `platform_list = ["deepseek"]` 在黑名单中，enabled 被静默覆盖
**犯错后果：** 修改代码后认为平台已激活，实际请求不会路由到它
**正确做法：** 从 platform_list 移除平台名才能真正启用

### [CRITICAL] 禁止使用标准 Claude tool call 格式
**你会假设：** Anthropic 使用 `Tool call (name, input)` 格式
**实际情况：** 本项目使用自定义 XML 格式：`<function_calls>` + `<invoke name="...">` + `<parameter>` 标签
**犯错后果：** 生成的 tool call 无法被解析，导致请求失败
**正确做法：** 严格使用 config.toml 中 `<function_calls>` 定义的 XML 格式

### [CRITICAL] uvicorn 不在项目中，README 文档有误
**你会假设：** README 技术栈表中列出的 uvicorn 是实际使用的服务器
**实际情况：** 服务器是纯 aiohttp.web，无任何 ASGI 组件
**犯错后果：** 尝试 `uvicorn main:app` 启动服务器会失败
**正确做法：** 使用 `python main.py` 启动

### [CRITICAL] SSL 验证全局禁用
**你会假设：** HTTPS 请求会验证证书
**实际情况：** `main.py` 中 `TCPConnector` 设置 `ssl.CERT_NONE`
**犯错后果：** 在生产环境中不会检测证书过期或中间人攻击
**正确做法：** 不要依赖 SSL 证书验证作为安全边界

## 易混淆之处

### [WARNING] 平台代理切换机制
**机制：** 每个平台适配器有 `set_proxy_enabled(bool)` 和 `is_proxy_enabled()` 方法，可独立控制是否走代理
**配置级控制：** 只有 `[platforms_proxy].enabled_platforms` 列表中的平台才能使用代理切换（如 `["qwen"]`）
**proxy_urls 匹配：** `config.toml` 中 `proxy_urls` 支持正则表达式，列表中有值时按正则匹配决定是否走代理；为空时所有非 IP URL 都走代理
**Qwen 智能选择：** Qwen 平台的 ProxySelector 根据历史成功率、延迟等指标自动选择代理或直连，无需手动干预
**持久化：** Qwen 代理状态保存在 `persist/qwen/usage.json` 的 `proxy` 字段中，重启后可恢复
**默认状态：** 无持久化数据时代理关闭（`_proxy_override = None`）
**DeepSeek：** 支持手动切换 `adapter.set_proxy_enabled(True/False)`，状态不持久化
**AItianhu2：** 禁止使用代理，`is_proxy_enabled()` 始终返回 False，`set_proxy_enabled()` 无操作
**Ollama：** 不支持代理切换（本地服务不需要代理）
**实现原理：** 通过 `_proxy_override` 变量控制，`_proxy_override is not None` 时在请求中显式传入 `proxy` kwarg 覆盖全局 patch 行为

### [WARNING] python main.py 启动的是 Runner-Worker 双进程架构
**混淆之处：** `python main.py` 不直接启动服务器，而是生成 Runner 进程，Runner 再 fork Worker 子进程（设置 `WORKER_PROCESS=1` 环境变量）
**澄清：** 实际运行两个 Python 进程。Runner 监控 Worker 退出：
- exit code 42 → 热重载重启（冷却 1 秒，快速重启上限 10 次/5 秒）
- 非零退出码 → 错误重启（等待 10 秒，最多 `server.max_restarts` 次，默认 3 次）
- 非零退出码触发重启前，会先终止旧进程以释放端口占用
**影响：** 日志输出经过管道线程，Ctrl+C 先终止 Runner 再 kill Worker
**管道读取：** Runner 使用 `readline()` 按行读取 Worker 输出（非 `read(4096)`），避免日志缓冲卡住
**颜色传递：** Worker 进程设置 `CLICOLOR_FORCE=1` 环境变量，确保通过管道输出时保留 ANSI 颜色代码

### [WARNING] 日志颜色检测自动回退纯文本
**机制：** `_supports_color()` 检测 `NO_COLOR` → 禁用；`FORCE_COLOR`/`CLICOLOR_FORCE` → 启用；`TERM` 环境变量（msys/cygwin/xterm）→ 启用；Windows Terminal (WT_SESSION) → 启用；回退到 `sys.stdout.isatty()`
**影响：** Git Bash、Windows Terminal 等现代终端正常显示颜色；管道重定向或不支持颜色的终端自动回退纯文本格式
**正确做法：** 需要强制颜色时设置 `FORCE_COLOR=1` 或 `CLICOLOR_FORCE=1`；需要禁用时设置 `NO_COLOR=1`

### [WARNING] system-reminder 块保留在对话历史中
**行为：** `<system-reminder>...</system-reminder>` 块不再从 tool result 或消息内容中剥离，完整保留并传递给模型
**原因：** 这些块对 Claude Code 等长时 agent 很重要，包含工具执行上下文和状态信息

### [WARNING] proxy_list_type 已从配置中移除
**行为：** `config.toml` 的 `[proxy]` 段不再有 `proxy_list_type` 字段，`ProxyCfg` 数据类也不包含此字段
**新逻辑：** `proxy_urls` 支持正则表达式匹配，列表为空时所有非 IP URL 都走代理，有值时按正则匹配

### [WARNING] .env 文件被完全忽略
**混淆之处：** 项目根目录有 `.env` 文件
**澄清：** 无任何代码读取 `.env`，无 `python-dotenv` 依赖，`DATABASE_URL` 是死配置
**影响：** 修改 `.env` 不影响任何运行时行为

### [WARNING] config.toml 被 .gitignore 排除
**混淆之处：** `*.toml` 在 `.gitignore` 中
**澄清：** config.toml 永远不会被提交到 git，是用户本地文件
**影响：** 克隆仓库后需要手动创建 config.toml

### [WARNING] .scripts/ 是隐藏构建工具目录
**混淆之处：** 以点开头的目录通常隐藏，包含 12 个 Python 脚本
**澄清：** 这些是代码生成/打包工具，与运行时无关。且被 `.gitignore` 排除
**影响：** git clone 后此目录不存在

### [WARNING] .htaccess 与项目无关
**混淆之处：** 根目录有 Apache 配置文件
**澄清：** 项目使用 aiohttp，不依赖 Apache。这是残留文件
**影响：** 忽略即可

### [WARNING] persist/ 和 logs/ 在源码树中
**混淆之处：** 运行时缓存（JSON、WASM）和日志文件直接在项目根目录下
**澄清：** 150+ 个 .log 文件和多个 .json 状态文件污染源码树
**影响：** `git status` 输出被大量运行时文件淹没

## 结构性意外

| 预期 | 实际 | 影响 |
|------|------|------|
| 标准 src/ 布局，包名是项目名 | 包名就是 src | 导入路径为 `from src.core...` |
| 测试在 tests/ 目录 | 测试是各平台下的 test.py | 无 pytest 发现，需手动运行 |
| 有 Dockerfile/CI 配置 | 完全缺失 | 仅 `pip install + python main.py` |
| uvicorn ASGI 服务器 | aiohttp.web 原生 | 不可用 ASGI 部署方式 |

## 命名陷阱

| 名称 | 你以为的含义 | 实际含义或行为 |
|------|-------------|----------------|
| `main.py` | 直接启动服务器 | Runner-Worker 双进程架构的入口 |
| `.scripts/*.py` | 应用模块 | 10+ 个独立工具脚本，各有 `main()` |
| `src/platforms/*/test.py` | pytest 单元测试 | 需要真实凭证的集成测试脚本 |
| `src/core/models_cache.py` vs `deepseek/core/modelcache.py` | 同一类 | 两个独立的 ModelsCache 实现 |
| `src/platforms/*/accounts.py` | 相同 schema | 四个完全不同的 Account 数据类/配置 |

## 依赖与导入陷阱

- `src/core/__init__.py` 声明 `__all__` 但不导入，`from src.core import config` 会失败
- `src/__init__.py` 和 `src/platforms/__init__.py` 的 `__all__` 为空
- 三个平台各有 `adapter.py` -> `util.py` -> `core/adaptercore.py` 的间接导入链
- `src/platforms/*/util.py` 通过 `__getattr__` 延迟导入 `core/` 中的类

## 构建、测试与运行意外

| 命令 | 预期行为 | 实际行为 |
|------|---------|---------|
| `pytest` | 运行测试 | 无测试发现（无 test_*.py 在 tests/ 目录） |
| `python -m src` | 启动应用 | 无 `__main__.py`，ModuleNotFoundError |
| `uvicorn main:app` | 启动 ASGI 服务器 | 无 ASGI app，不存在 |
| `python main.py` | 启动单进程服务器 | 启动 Runner + Worker 双进程 |

## 反模式（明确禁止）

| 禁止做法 | 应采取的做法 | 原因 |
|----------|-------------|------|
| 使用 `print()` 调试 | 使用 `logging.getLogger(__name__)` | 项目使用 loguru 日志系统 |
| 修改 `adapter.py` 文件 | 修改 `core/adaptercore.py` | adapter.py 仅重导出 |
| 从 `src.core` 直接导入 | 使用完整路径 `from src.core.xxx import` | `__init__.py` 无导入语句 |
| 假设 `.env` 生效 | 修改 `config.toml` | 项目不读取 `.env` |

## 配置陷阱

- `config.toml` 查找策略：CONFIG_PATH 环境变量 -> 源码父目录 -> cwd -> 向上 5 级
- 无 `tomllib`（Python < 3.11）且无 `tomli` 时，静默回退到默认配置
- 配置热重载通过 2 秒轮询检测文件 mtime 实现，非 inotify

## 最近发现的意外日志

<!-- 当你遇到意外时，在此追加：
### {ISO 日期} -- {标题}
**上下文：** {你正在执行的任务}
**意外：** {发生了什么}
**解决方案：** {正确的行为或做法}
-->


## 镜像说明

本文件是历史 AGENTS/agents 文档通过目录镜像方式放入 docs-src 的副本，不是 docs-src 专属规则。
