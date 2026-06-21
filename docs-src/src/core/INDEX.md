# src/core 索引

核心目录负责配置、注册表、路由支撑、通用工具、端口处理、运行时摘要聚合与复用逻辑。

> **v2.2.65**：核心逻辑已迁移至 `echotools` 包（`requirements.txt` 中 `echotools>=1.0.1`）。
> `src/core/` 下各模块保留原始 API，内部委托给 `echotools` 对应组件。
> `src/core.o/` 目录保存重构前的原始代码备份，供对照参考。

> **v2.2.192**：16 个单行 shim 文件合并至 `shims.py`，文件数量减少 59%。
> 新增 DSML 工具调用协议支持（`fncall/protocols/dsml.py`，重导出自 `echotools`）。

- `ARCHITECTURE.md`：整体架构概览（含 echotools 组件映射表）
- `shims.py`：统一兼容 shim 模块，整合 16 个旧 shim 文件的重导出
- `errors.py`：错误处理向后兼容 shim（聚合 base/platform/business 子模块）
- `models_cache.py`：ModelsCache 模型列表缓存，复用 echotools.ListCache
- `proxy_selector.py`：ProxySelector/ProxyRecord 重导出
- `terminal_sessions.py`：持久化终端会话元数据及离线输出
- `tools.py`：工具调用统一接口（注入、解析、格式化、循环检测、协议抽象）
- `runtime_view.md`：WebUI 与状态接口共用的运行时摘要聚合模块。
- `proxy.md`：代理系统详解。
- `config/INDEX.md`：配置模块索引。
- `fncall/protocols/dsml.py`：DSML 协议重导出模块（echotools 1.0.32+）
