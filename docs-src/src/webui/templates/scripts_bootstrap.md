# src/webui/templates/scripts_bootstrap.py

该模块负责页面事件绑定与初始化启动流程。

v2.2.153 起拆分为立即执行（核心初始化）和 5 个按标签页延迟初始化函数，配合 LazyLoader 按需加载各标签页资源。

## 日志面板事件绑定

- 搜索框 `input` 事件 → 更新 `_logSearchQuery` 并调用 `filterLogs()`
- 级别下拉 (CustomDropdown) `onChange` → 更新 `_logLevelFilter` 并持久化到 localStorage
- 模块下拉 (CustomDropdown) `onChange` → 更新 `_logModuleFilter` 并调用 `filterLogs()`
- 自动滚动按钮 `click` → 调用 `toggleAutoScroll()`
- 导出按钮 `click` → 调用 `exportLogs()`
- 清空按钮 `click` → 调用 `clearLogs()`
- 过滤切换按钮 `click` → 调用 `_toggleLogFilters()` 展开/收起高级过滤面板
- 日期起始 `change` → 更新 `_logDateFrom` 并持久化，调用 `filterLogs()`
- 日期截止 `change` → 更新 `_logDateTo` 并持久化，调用 `filterLogs()`
- 清除日期按钮 `click` → 重置日期过滤器并调用 `filterLogs()`

初始化时从 localStorage 恢复：自动滚动状态、级别过滤器（通过 CustomDropdown.setValue）、高级面板展开状态、日期范围。
