# core 静态资源

WebUI 核心功能的前端资源，提供基础模块和工具。

## 目录结构

```
core/
├── api.js           # API 调用模块
├── lazy.js          # 懒加载模块
├── motion.js        # 动画效果模块
├── router.js        # 路由模块
├── state.js         # 状态管理模块
├── tabbar.css       # 标签栏样式
└── tabbar.js        # 标签栏 JavaScript 实现
```

## 核心功能

### api.js

API 调用模块，封装与后端的 HTTP 通信。

### lazy.js

懒加载模块，实现资源的按需加载。

终端（`terminal`）、文件（`files`）、聊天（`chat`）等标签页的 xterm、highlight.js 等依赖已改为 **本地 vendor**（`/static/vendor/...`），不再依赖 jsdelivr / cdnjs。

若浏览器 Network 仍显示 **「已屏蔽：Devtools」**（`(blocked:devtools)`），这是 Chrome 开发者工具里启用了 **请求屏蔽（Request blocking）** 规则，与业务代码无关。打开 DevTools → **网络** → **请求屏蔽**，删除或停用相关规则后刷新页面。

### motion.js

动画效果模块，提供 UI 动画支持。

### router.js

路由模块，实现前端路由管理。

### state.js

状态管理模块，管理应用状态。

### tabbar.js

标签栏 JavaScript 实现，管理标签页切换。

### tabbar.css

标签栏样式定义，包括：
- 标签页布局（水平/竖向/压缩）
- 标签页标题、关闭按钮样式
- 状态点样式（圆形，绿点表示已连接，红点表示断开，黄点表示连接中）
- 压缩模式下仅显示状态点，展开模式下状态点在左侧

## 依赖关系

- 被其他静态资源模块依赖
- 提供 WebUI 的基础功能

## 注意事项

- 此目录为 WebUI 核心模块
- 修改时需要考虑模块间的依赖关系
- 遵循项目的前端编码规范
- 标签页结构为：状态点 + 标题 + 关闭按钮（无图标）