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