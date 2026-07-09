# terminal 静态资源

WebUI 终端功能的前端资源。

## 目录结构

```
terminal/
├── terminal.css     # 终端样式
└── terminal.js      # 终端 JavaScript 实现
```

## 核心功能

### terminal.js

终端功能的前端实现，包括：
- 终端界面渲染
- 命令输入处理
- 输出结果展示
- 会话管理

### terminal.css

终端界面的样式定义，包括：
- 终端窗口布局
- 文字样式和颜色
- 光标和滚动条样式

## 依赖关系

- 依赖 `src/webui/static/core/` 中的核心模块
- 依赖 `src/webui/static/ui/` 中的 UI 组件

## 注意事项

- 此文件为 WebUI 前端资源
- 修改时需要考虑浏览器兼容性
- 遵循项目的前端编码规范