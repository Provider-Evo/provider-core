# 变更日志

本文件记录 **provider-core** 仓库的版本变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

**范围**：仅收录本仓库会 `git commit` 的变更。编排工作区其他目录、以及 `config/` 本地运行时配置（gitignore，不提交）**不得**写入本文。

**版本号（可提交）真源**：`pyproject.toml`、`template/template_config.toml` 的 `version` / `server.version` 字段。运行时从本地 `config/main_config.toml` 读取 `server.version`；该目录不提交，发版时在本地同步 bump，但不记入 CHANGELOG。

更完整的里程碑与发版说明见官方文档：[发版历史](https://provider-evo.github.io/docs/release/)。

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
