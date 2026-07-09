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

## 重启覆盖层样式

### .restart-overlay

全屏固定覆盖层，z-index 10001。默认隐藏，显示时带 0.95 不透明度和 4px 背景模糊。使用 flex 居中布局。

### .restart-bg-rings

背景同心圆环容器。包含三个 `.restart-ring`，使用 `restartRing` 关键帧动画（scale 0.8->1.3，opacity 0->0.15->0），交错 0.6s 触发，产生扩散脉冲效果。

### .restart-card

居中卡片，使用 CSS 变量主题色（`--panel`、`--border`），圆角 16px，带阴影。包含图标、标题、描述、进度条、元信息和操作按钮。

### .restart-icon-wrap / .restart-spinner / .restart-pulse

图标容器 72x72px。spinner 使用 `restartSpin` 旋转动画（1s 线性无限）。pulse 在 spinner 背后使用 `restartPulse` 缩放动画（1->2.2，opacity 0.3->0）。

### .restart-progress-bar

进度条，宽度 220px，高度 6px，使用 `--accent` 色，transition 0.2s。

### .restart-btn / .restart-btn-primary

操作按钮，匹配全局按钮风格。primary 使用 `--accent` 背景白字。
