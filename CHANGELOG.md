# 变更日志

本文件记录 **provider-core** 仓库的版本变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

**范围**：仅收录本仓库会 `git commit` 的变更。未入库内容（编排仓、`config/` 本地配置等）**改记入 `RECORD.md`**，见 `docs-src/provider-guide-references/agents-project-conventions.md`「RECORD.md 编写」。

**版本号（可提交）真源**：`pyproject.toml`、`template/template_config.toml` 的 `version` / `server.version` 字段。运行时从本地 `config/main_config.toml` 读取 `server.version`；该目录不提交，发版时在本地同步 bump，但不记入 CHANGELOG。

更完整的里程碑与发版说明见官方文档：[发版历史](https://provider-evo.github.io/docs/release/)。

## [2.2.312] - 2026-07-22

### 修复

- 聊天测试模型选择器：刷新后恢复 `chat_model.json` / localStorage 中保存的模型；`refreshAll` 不再重置为默认模型

## [2.2.311] - 2026-07-22

### 修复

- 调度注册表：`opencode` / `opencodezen` 别名正确解析到 `zen` 适配器，修复流式请求「无适配器: opencode」

## [2.2.310] - 2026-07-22

### 修复

- 终端拆分：关闭一侧窗格后正确恢复为普通单标签；阻止已销毁窗格的 WebSocket 状态回写重新激活双点 UI
- 拆分标签：任意窗格状态点 hover 均可显示 × 以关闭该侧

## [2.2.309] - 2026-07-22

### 修复

- WebUI 拆分标签：× 仅在当前标签且当前窗格状态点 hover 时显示；压缩模式恢复 `display:none` 默认隐藏
- 终端拆分布局刷新后持久化恢复（`terminals.json` 的 `splitLayouts`）

## [2.2.308] - 2026-07-22

### 修复

- `/v1/turns` 真正实现双模式：`input` 返回 Entropy `output` 块；`messages` 兼容层返回 OpenAI `choices`（修复 WebUI 非流式无响应）
- `thinking.interleaved_history` 在原生 `input` 路径贯通（含 Entropy thinking 内容块剥离/保留）
- 流式 `messages` 兼容层使用 `entropy` 思考配置解析历史开关

## [2.2.307] - 2026-07-22

### 增强

- Entropy `thinking.interleaved_history` / 顶层 `interleaved_history`：开则历史保留 assistant 思考+回复，关则仅传可见回复（含 Entropy `type:thinking` 内容块）
- 历史策略下沉 `echotools>=2.3.22` 的 `apply_thinking_history_policy`

## [2.2.306] - 2026-07-22

### 增强

- Entropy 主体 API：`POST /v1/turns`、`GET /v1/models`；OAI/ANT 迁至 `/v1/openai/*`、`/v1/anthropic/*`（旧路径硬删除）
- 思考模式统一为 `off` / `on` / `auto`；新增 `thinking.interleaved_history` 控制是否把历史思考传给模型
- 内核 always-entml；依赖 `echotools>=2.3.19`

## [2.2.302] - 2026-07-21

### 增强

- 工具调用参数规范化：依赖 `echotools>=2.3.7` 的 `normalize_tool_calls`，修复模型输出 Python 字面量无法 JSON 解析的问题

## [2.2.301] - 2026-07-21

### 修复

- 文件选项卡布局自适应浏览器高度（对齐终端选项卡）
- 文件搜索忽略目录改为大小写不敏感精确匹配，不再误跳 `Log`/`config` 等项目目录
- 鉴权：`auth.enabled` 时所有端点需 API Key / Virtual Key / WebUI Token（会话 Cookie 或 Bearer），移除无密钥直通
- 终端自定义背景刷新丢失：`terminals.json` 合并写入，避免连接列表覆盖背景设置
- 插件热重载 `ensure_candidates` 调用 Registry 包装器；client import 顺序修复

## [2.2.300] - 2026-07-21

### 修复

- WebUI 懒加载补全 `term_ctxitems.js`、`kbd_nav.js`、`preview_host.js`；终端脚本加载顺序调整
- 插件市场默认显示已安装项；`isCompatible` 与 `2.2.x` 上限语义修正
- 12+ 插件 `config_schema.json` 同步（含 Coplan-Util）；`load_plugin_api_keys` 支持 WebUI 写入 config.toml
- achecker 全量合规（目录子项 / 函数长度 / 嵌套深度）

## [2.2.299] - 2026-07-20

### 修复

- `AppConfig` 补充 `adapter_proxy` / `platforms_proxy` 配置段，修复 `/v1/webui/summary` 500
- WebUI 懒加载补全 `ops.js`、`search.js`、`term_search.js`；`motion_kit.js` 加载顺序修正
- Provider-Webui-Util enhance 静态资源路径与 `static/` 目录对齐
- 依赖 `echotools>=2.3.6`

## [2.2.298] - 2026-07-20

### 变更

- 注释套话清理与并发/兼容注释补强；`strip_comment_boilerplate.py --verify` 门禁（编排仓脚本，本仓 `src/` / `plugins/` 受益）
- Coplan-Util 内置策略路径修复；插件 overlay 同步至 `plugins/`
- README 精简；新增本文件与 `LICENSE`

## [2.2.297] - 2026-07

### 新增

- 单插件热重载（on_unload → 清缓存 → on_load）、`fast_restart`；provider-sdk 0.3.2
- TabBar 与生命周期重构；CI lint 门禁

### 变更

- 移除 legacy `src/platforms` 双轨代码

## [2.2.270] - 2026-06

### 新增

- 插件生态落地：容错加载、29 个插件脚手架、WebUI 插件面板与插件市场
- opencode / zen 合并为 zen 适配器

---

历史细项（v2.2.0 起逐版记录）曾集中写在旧版 README 路线图章节，已迁出以避免与本文档重复维护。查阅旧记录可使用 git 历史中的 `README.md`（`git log -p -- README.md`）。
