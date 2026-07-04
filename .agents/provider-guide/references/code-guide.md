# Provider-V2 代码指南

## 作用

本文件是当前项目级代码规范，不取代迁移保留的 `references/rules/CODE_GUIDE.txt`，而是把该通用规范与 Provider-V2 的真实结构、运行模式和风险点结合起来。

## 代码总原则

1. 所有 Python 文件保留 `from __future__ import annotations`。
2. 所有公开函数、类、方法都要有中文 docstring。
3. 所有新增逻辑必须带类型标注。
4. 禁止新增 emoji、占位实现、静默吞错逻辑。
5. 能进入 `src/core/` 复用的逻辑，不要散落在平台、脚本或路由里重复实现。
6. 优先修复会导致导入失败、启动失败、测试失败、打包失败的问题。

## 项目结构规则

### 入口与运行
- `main.py` 负责 runner/worker 双进程架构。
- 只能从项目根目录执行 `python main.py`。
- 不要把本项目当成有 `pyproject.toml` 的标准可安装包处理。

### 核心目录职责
- `src/core/`：跨平台复用逻辑、配置、注册表、路由支撑、摘要聚合、端口与 I/O 工具。
- `src/routes/`：OpenAI、Anthropic、静态与管理路由。
- `src/platforms/`：平台适配器目录，每个平台保持统一顶层结构。
- `src/webui/`：WebUI 管理台主实现（根路径 `/` 直接服务）。

## 运行时规则

### 启动流程
- 启动前必须检测端口占用。
- 是否自动强杀占用进程，由 `server.STARTUP_FORCE_KILL_PORT` 决定。
- 端口自动释放逻辑统一放在 `src/core/process.py`。

### 日志规则
- IDLE 环境必须输出纯文本，不能出现 ANSI 颜色串。
- 非 IDLE 环境是否保留颜色要谨慎，不影响 IDLE 纯文本要求。
- 不允许为了省事直接删掉日志上下文。

### 外部依赖处理
- 对第三方 API、远端平台、真实账号依赖造成的失败，不阻断主任务。
- 失败原因必须**追加**到 `RECORD.md` 末尾（已 gitignore，不提交），禁止覆盖文件。

## 持久化规则

1. 所有状态写入必须使用原子写。
2. 尽量避免无变化写盘。
3. 持久化内容应尽量稳定排序或稳定结构。
4. cookie、token、device_id 等能复用时优先复用。
5. 平台持久化若可抽象共用，优先抽到 `src/core/`。

## 脚本与工具规则

- script 逻辑中涉及 UUIDv7 时统一使用 `src.core.ids.uuid7()`。
- script 写文件统一使用 `src.core.io_utils.atomic_write_text()`。
- 目录创建统一使用 `src.core.io_utils.ensure_directory()`。
- 生成型脚本的业务辅助能力优先复用 `src.core.scriptgen`。

## WebUI 规则

- WebUI 主实现放在 `src/webui/`。
- 页面必须能在无外网资源环境下渲染。
- 页面失败要降级，不得因单个接口失败整页白屏。
- 根路径 `/` 直接服务 WebUI 管理台，不再维护独立的在线文档页。

## 变更控制

- 改动前后都要在 `RECORD.md` 末尾**追加**新条目（已 gitignore，不提交），禁止覆盖或重写文件。
- 当任务理解或完成状态发生明显变化时，更新 `PLAN.txt`。
- 如果为了回补历史能力而改变脚本行为，必须记录原逻辑与新逻辑差异。
