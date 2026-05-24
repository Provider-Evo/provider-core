2026-05-24 | 配置管理改进

### 变更文件

- .gitignore
- template/template_config.toml
- docs-src/template/INDEX.md

### 变更说明

**配置管理改进：精确 .gitignore 规则 + 新增配置模板文件**

- `.gitignore`：从 blanket `*.toml` + `!template/config.toml` 改为精确 `config.toml`，只忽略根目录配置文件，不再误伤所有 `.toml` 文件
- `template/template_config.toml`：新增 Provider-V2 配置模板文件，作为用户分发基准，包含 server、auth、gateway、proxy、platforms、fncall、debug 等全部配置段
- `docs-src/template/INDEX.md`：同步更新模板文档

### 验证结果

- 无 Python 源码变更，无需 pytest/py_compile

---

2026-05-24 | v2.2.2

### 变更文件

- src/platforms/deepseek/core/client.py
- src/platforms/deepseek/util.py
- src/platforms/ollama/core/client.py
- src/platforms/qwen/core/client.py

### 变更说明

**Bug 修复：平台 accounts 模块导入路径错误**

- 修复 4 个平台文件中 `accounts` 模块的错误导入路径
- 从 `core.accounts` 改为顶层 `accounts`（遵循平台开发规范 §三 依赖流动）
- 影响平台：qwen、ollama、deepseek
- 修复后平台注册不再报 `No module named 'src.platforms.xxx.core.accounts'` 错误

### 验证结果

- 代码修复已应用，待运行时验证

---

.gitignore
main.py
requirements.txt
src/__init__.py
src/core/__init__.py
src/core/config.py
src/core/http.py
src/core/scheduler.py
src/core/server.py
src/logger.py
src/platforms/__init__.py
src/platforms/deepseek/TODO.txt
src/platforms/deepseek/__init__.py
src/platforms/deepseek/adapter.py
src/platforms/deepseek/core/__init__.py
src/platforms/deepseek/core/adapter_impl.py
src/platforms/deepseek/core/client.py
src/platforms/deepseek/core/constants.py
src/platforms/deepseek/core/headers.py
src/platforms/deepseek/core/hif.py
src/platforms/deepseek/core/models_cache.py
src/platforms/deepseek/core/pow.py
src/platforms/deepseek/core/session_api.py
src/platforms/deepseek/core/stream_parser.py
src/platforms/deepseek/core/user_api.py
src/platforms/deepseek/util.py
src/platforms/ollama/__init__.py
src/platforms/ollama/adapter.py
src/platforms/ollama/client.py
src/platforms/ollama/core/__init__.py
src/platforms/ollama/core/adapter_impl.py
src/platforms/ollama/core/client.py
src/platforms/ollama/core/constants.py
src/platforms/ollama/util.py
src/platforms/qwen/__init__.py
src/platforms/qwen/adapter.py
src/platforms/qwen/core/__init__.py
src/platforms/qwen/core/adapter_impl.py
src/platforms/qwen/core/client.py
src/platforms/qwen/core/constants.py
src/platforms/qwen/util.py
src/routes/__init__.py
src/routes/chat.py
src/routes/function_call.py
src/routes/health.py
src/routes/models.py

## 变更说明

### .gitignore

- 修改内容：
  - 由 `.scripts/gen_gitignore.py` 自动重新生成
  - 大幅简化，采用分类结构（Directories / Extensions / File names）
  - 新增忽略 `.agents`、`.claude`、`.codebuddy`、`.zed`、`data`、`node_modules`、`persist` 等目录
  - 新增忽略 `.dll`、`.dylib`、`.json`、`.pyc`、`.pyd`、`.pyo`、`.so`、`.srt`、`.toml`、`.wasm`、`.zip` 等扩展名
  - 排除 `!template/config.toml` 保留模板文件追踪
  - 移除 `logs/`、`.scripts/`、`*.log` 等原有条目
  - 新增 `src/platforms/aitianhu2/` 排除和 `!template/` 保留
- 改动影响：
  - 运行时产生的 JSON/TOML/WASM/日志等文件不再污染 `git status`
  - `config.toml` 被忽略，仅保留模板文件

### README.md

- 修改内容：
  - 全面重写，从 68 行扩展到 221+ 行
  - 新增分支说明（main/dev 分支定位）
  - 新增项目背景、痛点分析、核心功能对比表
  - 新增技术栈表格，版本号要求
  - 新增效果展示（服务启动日志、API 调用示例、Swagger UI）
  - 重写安装指南（pip/虚拟环境/Docker/系统特定说明）
  - 重写使用说明（OpenAI/Anthropic 调用示例、工具调用、流式响应、Thinking 模式）
  - 新增请求参数说明表
  - 重写项目结构图，新增核心目录说明
  - 更新配置说明章节开头
- 改动影响：
  - 文档更加完善，适合新用户快速上手
  - 提供了多种平台调用的完整示例代码

### main.py

- 修改内容：
  - 重写 Runner-Worker 架构的 Worker 启动逻辑
  - 引入新的配置模块 `src.core.config.manager` 替代旧的 `src.core.config`
  - 新增文件监视器 `FileWatcher` 集成
  - 服务器创建改为使用新的 `src.core.server` 模块
  - 移除旧的 `uvloop` 平台特定处理
  - 新增日志颜色检测和终端兼容性改进
- 改动影响：
  - 启动流程与新核心架构对齐
  - 支持配置热重载和文件监视自动重启

### requirements.txt

- 修改内容：
  - 更新依赖版本要求
  - 新增 `tomlkit`、`watchdog`、`aiohttp-socks` 等新依赖
- 改动影响：
  - 支持新配置管理器的 TOML 编辑和文件监控功能

### src/__init__.py

- 修改内容：
  - 更新 `__all__` 导出列表
- 改动影响：
  - 适配新模块结构

### src/core/__init__.py

- 修改内容：
  - 从直接导入各模块改为从新子模块导入
  - 新增 `candidate`、`errors`、`files`、`gateway`、`models_cache`、`proxy`、`registry`、`retry`、`selector`、`tools`、`watcher` 等导出
  - 移除旧的 `config`、`scheduler` 导出
- 改动影响：
  - 适配核心模块重构后的新文件结构

### src/core/config.py（删除）

- 修改内容：
  - 整个文件被删除，功能迁移到 `src/core/config/` 目录
- 改动影响：
  - 旧配置系统被新的多文件配置架构替代

### src/core/http.py

- 修改内容：
  - 精简 HTTP 工具函数
  - 移除旧的 `clean_fncall` 实现（迁移到 `src.core.tools`）
  - 保留 `get_json`、`safe_flush` 等基础工具
- 改动影响：
  - HTTP 层职责更清晰，fncall 处理独立到 tools 模块

### src/core/scheduler.py（删除）

- 修改内容：
  - 整个文件被删除
- 改动影响：
  - 调度功能被新的 `gateway`、`selector`、`retry` 模块替代

### src/core/server.py

- 修改内容：
  - 重写服务器创建逻辑
  - 集成新的路由注册系统
  - 新增 `REGISTRY_KEY`、`SESSION_KEY` 等 AppKey 定义
  - 适配新的 aiohttp.web 路由注册方式
- 改动影响：
  - 服务器启动与新路由系统（OpenAI/Anthropic/Static）对齐

### src/logger.py

- 修改内容：
  - 重写日志系统
  - 新增颜色检测逻辑（`NO_COLOR`、`FORCE_COLOR`、`CLICOLOR_FORCE`、`TERM`、`WT_SESSION`）
  - 新增纯文本回退机制
  - 改进日志格式和输出
  - 从 loguru 改为 Python 标准 logging
- 改动影响：
  - 减少外部依赖，日志输出更稳定
  - 支持更多终端环境的颜色显示

### src/platforms/__init__.py

- 修改内容：
  - 更新 `__all__` 导出列表
  - 新增 `base` 模块导出
- 改动影响：
  - 适配新平台适配器基类

### src/platforms/deepseek/TODO.txt（删除）

- 修改内容：
  - 删除 TODO 文件
- 改动影响：
  - 清理开发过程中的临时记录

### src/platforms/deepseek/__init__.py

- 修改内容：
  - 更新导出列表
  - 适配新的 `adapter_impl` 结构
- 改动影响：
  - 与其他平台导出风格保持一致

### src/platforms/deepseek/adapter.py

- 修改内容：
  - 简化为重导出模块
  - 实际实现迁移到 `core/adapter_impl.py`
- 改动影响：
  - 与其他平台架构对齐（adapter.py 仅重导出）

### src/platforms/deepseek/core/__init__.py

- 修改内容：
  - 更新内部模块导出
- 改动影响：
  - 适配新模块拆分

### src/platforms/deepseek/core/adapter_impl.py

- 修改内容：
  - 实现新的 `PlatformAdapter` 基类接口
  - 重写 `init`、`candidates`、`ensure_candidates`、`complete`、`close` 方法
  - 适配新的 `Candidate` 数据结构
  - 集成新的流式解析和工具调用处理
- 改动影响：
  - 与新核心架构完全对齐

### src/platforms/deepseek/core/client.py

- 修改内容：
  - 大幅重写（+529 行）
  - 新增完整的 HTTP 客户端实现
  - 支持流式和非流式请求
  - 集成代理切换逻辑
  - 新增错误处理和重试机制
- 改动影响：
  - 客户端功能更完善，与新 gateway 架构兼容

### src/platforms/deepseek/core/constants.py

- 修改内容：
  - 更新 API 端点、模型列表等常量
  - 新增配置相关常量
- 改动影响：
  - 适配平台 API 变更

### src/platforms/deepseek/core/headers.py

- 修改内容：
  - 微调请求头构建逻辑
- 改动影响：
  - 小改动，不影响核心功能

### src/platforms/deepseek/core/hif.py

- 修改内容：
  - 更新 HIF（Human Interface Format）处理逻辑
- 改动影响：
  - 适配新消息格式

### src/platforms/deepseek/core/models_cache.py

- 修改内容：
  - 简化模型缓存逻辑
  - 使用新的 `src.core.models_cache` 通用实现
- 改动影响：
  - 减少平台特定缓存代码

### src/platforms/deepseek/core/pow.py

- 修改内容：
  - 微调 PoW（Proof of Work）计算逻辑
- 改动影响：
  - 保持与 DeepSeek 平台 PoW 验证兼容

### src/platforms/deepseek/core/session_api.py

- 修改内容：
  - 更新会话管理逻辑
- 改动影响：
  - 适配新认证流程

### src/platforms/deepseek/core/stream_parser.py

- 修改内容：
  - 重写流式响应解析器
  - 支持新的 SSE 格式
  - 改进 chunk 处理逻辑
- 改动影响：
  - 流式输出更稳定

### src/platforms/deepseek/core/user_api.py

- 修改内容：
  - 更新用户 API 调用
- 改动影响：
  - 适配平台用户接口变更

### src/platforms/deepseek/util.py

- 修改内容：
  - 新增/更新工具函数
  - 集成新的配置获取方式
- 改动影响：
  - 工具函数与新架构对齐

### src/platforms/ollama/__init__.py

- 修改内容：
  - 更新导出列表
- 改动影响：
  - 适配新模块结构

### src/platforms/ollama/adapter.py

- 修改内容：
  - 简化为重导出模块
- 改动影响：
  - 与其他平台架构对齐

### src/platforms/ollama/client.py

- 修改内容：
  - 更新 Ollama HTTP 客户端
- 改动影响：
  - 适配 Ollama API

### src/platforms/ollama/core/__init__.py

- 修改内容：
  - 更新内部导出
- 改动影响：
  - 适配新模块

### src/platforms/ollama/core/adapter_impl.py

- 修改内容：
  - 实现新的 `PlatformAdapter` 基类接口
  - 适配 `Candidate` 数据结构
  - 重写核心方法
- 改动影响：
  - 与新架构对齐

### src/platforms/ollama/core/client.py

- 修改内容：
  - 大幅重写（+852 行）
  - 新增完整 Ollama API 客户端实现
  - 支持聊天补全、嵌入等接口
- 改动影响：
  - Ollama 平台功能更完整

### src/platforms/ollama/core/constants.py

- 修改内容：
  - 更新模型列表和 API 常量
- 改动影响：
  - 适配 Ollama 更新

### src/platforms/ollama/util.py

- 修改内容：
  - 更新工具函数
- 改动影响：
  - 与新架构对齐

### src/platforms/qwen/__init__.py

- 修改内容：
  - 更新导出列表
- 改动影响：
  - 适配新模块结构

### src/platforms/qwen/adapter.py

- 修改内容：
  - 简化为重导出模块
- 改动影响：
  - 与其他平台架构对齐

### src/platforms/qwen/core/__init__.py

- 修改内容：
  - 微调内部导出
- 改动影响：
  - 适配新模块

### src/platforms/qwen/core/adapter_impl.py

- 修改内容：
  - 实现新的 `PlatformAdapter` 基类接口（+514 行）
  - 适配 `Candidate` 数据结构
  - 集成代理切换、模型缓存、账号池等
- 改动影响：
  - Qwen 平台完整适配新架构

### src/platforms/qwen/core/client.py

- 修改内容：
  - 大幅重写（+2193 行）
  - 新增完整 DashScope API 客户端
  - 支持聊天、视觉、工具调用等
- 改动影响：
  - Qwen 平台功能大幅增强

### src/platforms/qwen/core/constants.py

- 修改内容：
  - 更新 API 端点和模型常量
- 改动影响：
  - 适配 DashScope API

### src/platforms/qwen/util.py

- 修改内容：
  - 更新工具函数
- 改动影响：
  - 与新架构对齐

### src/routes/__init__.py

- 修改内容：
  - 更新路由模块导出
  - 移除旧的 `chat`、`function_call`、`health`、`models` 导出
  - 新增 `anthropic`、`openai`、`static` 导出
- 改动影响：
  - 适配新路由架构

### src/routes/chat.py（删除）

- 修改内容：
  - 整个文件被删除，功能迁移到 `src/routes/openai.py`
- 改动影响：
  - 路由职责重新划分

### src/routes/function_call.py（删除）

- 修改内容：
  - 整个文件被删除，功能迁移到 `src/core/tools.py`
- 改动影响：
  - 工具调用处理集中到核心模块

### src/routes/health.py（删除）

- 修改内容：
  - 整个文件被删除，功能迁移到 `src/routes/static.py`
- 改动影响：
  - 静态路由集中管理

### src/routes/models.py（删除）

- 修改内容：
  - 整个文件被删除，功能迁移到 `src/routes/static.py` 和 `src/routes/openai.py`
- 改动影响：
  - 模型列表路由重新组织

### src/core/candidate.py（新增）

- 修改内容：
  - 定义 `Candidate` 数据类，包含全部能力布尔字段及元数据
  - 定义 `ALL_CAPABILITIES` 元组（32 种能力）
  - 提供 `make_id()` 生成全局唯一候选项 ID
  - `Candidate` 包含 `has_capability()`、`to_model_dict()` 方法
- 改动影响：
  - 统一的候选项数据模型，支持细粒度能力描述

### src/core/config/（新增目录）

- 修改内容：
  - 新配置系统，包含 `__init__.py`、`base.py`、`sections.py`、`manager.py`、`resolver.py`
  - `sections.py`：定义所有配置段数据类（ServerCfg、GatewayCfg、ProxyCfg 等）
  - `manager.py`：配置管理器，支持模板合并、版本检查、watchdog 热重载
  - `resolver.py`：共享模型名称解析器
  - `base.py`：配置基类
  - 使用 `tomlkit` 保留注释，使用 `watchdog` 实时监控
  - 支持 `AppConfig.from_dict()` 从字典构造配置
- 改动影响：
  - 配置系统从单文件重构为模块化架构
  - 新增配置文件实时监控和热重载能力
  - 新增模板合并和版本管理机制

### src/core/errors.py（新增）

- 修改内容：
  - 定义完整的异常层次结构
  - 根基类 `ProviderError`，包含 `original` 和 `status_code`
  - 平台级异常：`PlatformError`、`AuthError`、`RateLimitError`、`ServerError` 等
  - 业务异常：`NoCandidateError`、`ModelNotFoundError`、`ContextLengthError` 等
  - 新增 `classify_http_error()` 根据 HTTP 状态码自动分类异常
- 改动影响：
  - 统一的异常体系，便于错误处理和调试

### src/core/files.py（新增）

- 修改内容：
  - `FileUtil` 工具类，静态方法集合
  - MIME 类型推断、Data URI 解析、文件保存、MD5 计算等
  - 支持图像、音频、视频、PDF 等文件类型
- 改动影响：
  - 文件处理工具函数集中管理

### src/core/gateway.py（新增）

- 修改内容：
  - 核心请求分发模块 `dispatch()` 函数
  - 支持单候选项执行和多候选项竞速
  - 集成 TAS 候选项选择器
  - 注入 fncall 工具调用
  - 处理 token 估算和 usage 规范化
  - `_single()` 单候选项执行，`_race()` 多候选项竞速
- 改动影响：
  - 核心请求分发逻辑，支持并发竞速模式

### src/core/models_cache.py（新增）

- 修改内容：
  - 通用模型列表缓存管理器 `ModelsCache`
  - 支持从 `persist/{platform}/models.json` 读取缓存
  - 定时刷新远程模型列表
  - 支持覆盖或追加策略
- 改动影响：
  - 统一的模型缓存实现，替代各平台独立实现

### src/core/proxy.py（新增）

- 修改内容：
  - 完整的代理支持模块
  - 支持 HTTP/HTTPS/SOCKS5 代理
  - 自动检测环境变量和配置文件
  - Patch `requests` 和 `aiohttp` 库以使用代理
  - SOCKS 代理使用 `aiohttp-socks`
  - SSL 验证全局禁用
- 改动影响：
  - 从旧代理模块重构，功能更完善

### src/core/registry.py（新增）

- 修改内容：
  - 平台注册表 `Registry` 类
  - 递归发现 `src.platforms` 下所有平台适配器
  - 黑白名单过滤
  - 热重载平台适配器（清理 sys.modules）
  - 提供 `get_candidates`、`ensure_candidates`、`adapter_for` 等方法
  - 集成 TAS 选择器
- 改动影响：
  - 统一的平台注册和管理中心

### src/core/retry.py（新增）

- 修改内容：
  - 重试工具模块
  - `retry_with_backoff`：指数退避重试
  - `retry_on_empty`：空响应重试
  - `retry_on_exception`：指定异常类型重试
- 改动影响：
  - 通用重试逻辑，各平台复用

### src/core/selector.py（新增）

- 修改内容：
  - TAS（Thompson Sampling + 冷却机制）选择器
  - `CandidateStats` 统计类（Beta 分布 + EMA）
  - `Selector` 类实现 TAS 算法
  - 滑动窗口、探索率衰减、冷却时间等超参数
  - 提供 `select()`、`record()`、`get_stats()` 方法
- 改动影响：
  - 智能候选项选择，优化请求延迟和成功率

### src/core/tools.py（新增）

- 修改内容：
  - fncall 模板注入与解析模块（1655 行）
  - 支持 en/zh 双语
  - Schema 感知类型转换（JSON Schema）
  - 流式解析状态机 `FncallStreamParser`
  - Agent 循环检测 `detect_tool_loop`
  - UUIDv7 生成
  - XML 格式 tool call 解析
- 改动影响：
  - 完整的工具调用处理系统，从旧 `function_call.py` 大幅增强

### src/core/watcher.py（新增）

- 修改内容：
  - 文件变更监视器 `FileWatcher`
  - 扫描 `src/` 下所有 `.py` 文件和 `config.toml`
  - 分类变更为核心文件或平台文件
  - 核心文件变更触发进程重启（exit code 42）
  - 平台文件变更触发热重载
- 改动影响：
  - 支持代码和配置热重载

### src/platforms/base.py（新增）

- 修改内容：
  - 平台适配器抽象基类 `PlatformAdapter`
  - 定义必需接口：`name`、`init`、`candidates`、`ensure_candidates`、`complete`、`close`
  - 提供可选能力方法默认实现（embedding、image、audio、video、moderation、rerank 等）
  - 代理切换方法 `set_proxy_enabled`、`is_proxy_enabled`
- 改动影响：
  - 统一的平台适配器规范

### src/platforms/qwen/core/shared.py（新增）

- 修改内容：
  - Qwen 平台共享工具和常量
- 改动影响：
  - 减少 Qwen 平台内部代码重复

### src/routes/anthropic.py（新增）

- 修改内容：
  - Anthropic 兼容路由（1097 行）
  - `POST /v1/messages`、`POST /messages`
  - `GET /anthropic/v1/models`、`GET /anthropic/v1/models/{model_id}`
  - `POST /v1/messages/count_tokens`
  - 支持流式/非流式、thinking 模式、工具调用、多模态内容
  - Anthropic 格式与 OpenAI 格式转换
- 改动影响：
  - 新增 Anthropic API 兼容支持

### src/routes/openai.py（新增）

- 修改内容：
  - OpenAI 兼容路由（2085 行）
  - `POST /v1/chat/completions`、`POST /v1/responses`
  - `POST /v1/embeddings`、图片、音频、视频端点
  - Files、Fine-tuning、Batch、Assistants、Threads、Runs、Vector Stores、Uploads 端点
  - 完整支持流式输出和工具调用
  - 文件上传提取（base64 data URI）
- 改动影响：
  - 从旧 `chat.py` 大幅扩展，实现完整 OpenAI API 兼容

### src/routes/static.py（新增）

- 修改内容：
  - 静态路由模块
  - `GET /`、`GET /health`、`GET /docs`
  - `GET /v1/models`、`GET /v1/models/{model_id}`
  - `GET /v1/status`（含 TAS 统计数据）
  - `GET /v1/capabilities`（能力矩阵查询）
  - `POST /v1/admin/refresh_models`（手动触发模型刷新）
- 改动影响：
  - 集中管理健康检查、模型列表、状态等基础路由

### tests/（新增目录）

- 修改内容：
  - 新增测试目录
  - 当前为空目录结构
- 改动影响：
  - 为后续测试代码提供存放位置
