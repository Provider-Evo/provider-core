# RECORD.md

> 本文件被 .gitignore 排除，不参与版本控制。仅供本地记录变更和阻塞项。

## 2026-07-04

### 日志文件命名分隔符修改 (v2.2.239)

**变更内容**：将日志文件命名中的 `_` 分隔符改为 `-`，使文件名更清晰易读。

**修改文件**：
- `src/logger.py`：第 401 行，日志文件名模式从 `{log_name}_{time:YYYYMMDD_HHmmss}.log` 改为 `{log_name}-{time:YYYYMMDD-HHmmss}.log`
- 版本号同步更新至 2.2.239（template/template_config.toml, config/main_config.toml, README.md, .agents/provider-guide/SKILL.md）

**影响**：
- 新生成的日志文件将使用连字符（-）作为分隔符，例如 `provider-v2-20260704-204009.log`
- 旧的日志文件不受影响，保持原有命名格式

### 日志面板虚拟滚动 (v2.2.239)

**变更内容**：为日志面板添加虚拟滚动，优化大量日志条目时的渲染性能。

**修改文件**：
- `src/webui/static/core/state.js`：新增虚拟滚动状态和渲染逻辑，重构 addLogEntry 和 filterLogs

**影响**：
- 日志条目通过虚拟滚动只渲染可视区域内的条目，减少 DOM 节点数量
- 滚动时按需创建/销毁日志条目 DOM 元素

### 终端实时性修复 (v2.2.240)

**变更内容**：修复终端输出不实时显示的问题，需要按回车才能看到新内容。

**修改文件**：
- `src/webui/static/terminal/terminal.js`：在 xterm.js 写入输出后强制刷新视口

**影响**：
- 终端输出现在会实时显示，无需用户手动按回车或滚动
- 提升终端交互体验，避免用户误以为程序卡住