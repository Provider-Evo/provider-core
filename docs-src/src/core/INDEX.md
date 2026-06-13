# src/core 索引

核心目录负责配置、注册表、路由支撑、通用工具、端口处理、运行时摘要聚合与复用逻辑。

> **v2.2.65**：核心逻辑已迁移至 `echotools` 包（`requirements.txt` 中 `echotools>=1.0.1`）。
> `src/core/` 下各模块保留原始 API，内部委托给 `echotools` 对应组件。
> `src/core.o/` 目录保存重构前的原始代码备份，供对照参考。

- `ARCHITECTURE.md`：整体架构概览（含 echotools 组件映射表）
- `runtime_view.md`：WebUI 与状态接口共用的运行时摘要聚合模块。
- `proxy.md`：代理系统详解。
- `config/INDEX.md`：配置模块索引。
