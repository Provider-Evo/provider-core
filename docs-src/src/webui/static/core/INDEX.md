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

### motion.js

动画效果模块，提供 UI 动画支持。

### router.js

路由模块，实现前端路由管理。

### state.js

状态管理模块，管理应用状态。

### tabbar.js

标签栏 JavaScript 实现，管理标签页切换。

## 依赖关系

- 被其他静态资源模块依赖
- 提供 WebUI 的基础功能

## 注意事项

- 此目录为 WebUI 核心模块
- 修改时需要考虑模块间的依赖关系
- 遵循项目的前端编码规范