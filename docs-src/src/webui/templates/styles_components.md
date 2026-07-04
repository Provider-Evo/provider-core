# src/webui/templates/styles_components.py

该模块放卡片、按钮、文档卡片、日志框等组件样式。

## 输入对话框样式

### .input-dialog-input

输入对话框中的输入框样式，用于 `showInputDialog` 组件。

**样式特点：**
- 宽度 100%，自适应父容器
- 圆角边框，与全局主题一致
- 聚焦时边框颜色变为主题强调色
- 支持占位符文本
- 平滑的边框颜色过渡动画

## 日志查看器样式

### .log-viewer

日志容器，深色背景 (#0d1117)，圆角 12px，高度 `calc(100vh - 280px)`，自定义滚动条。

### .log-entry

日志条目行，flex 四列布局：时间戳 + 级别 + 模块 + 消息。hover 时半透明高亮。

### .log-level-*

按级别着色：DEBUG 灰、INFO 蓝、WARNING 黄、ERROR 红、CRITICAL 亮红加粗、SUCCESS 绿。

### .log-toolbar

工具栏，包含搜索框、级别过滤下拉、自动滚动/导出/清空按钮。

### .log-conn-status

WebSocket 连接状态指示，`.connected` 时变绿色并带脉冲动画。

### .log-toolbar-advanced

高级过滤面板容器，包含级别、模块、日期范围和字号选择器。默认隐藏，通过"过滤"按钮切换。

### .log-date-label / .log-date-input

日期范围输入框样式，内联 flex 布局，带标签和日期选择器。
