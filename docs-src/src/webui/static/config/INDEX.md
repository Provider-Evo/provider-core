# config 静态资源

WebUI 配置管理功能的前端资源。

## 目录结构

```
config/
├── actions.js       # 配置操作 JavaScript 实现
└── render.js        # 配置渲染 JavaScript 实现
```

## 核心功能

### actions.js

配置操作的前端实现，包括：
- 配置项的增删改查
- 配置保存和加载
- 配置验证逻辑

### render.js

配置渲染的前端实现，包括：
- 配置界面渲染
- 配置项展示
- 配置状态显示

## 依赖关系

- 依赖 `src/webui/static/core/` 中的核心模块
- 依赖 `src/webui/static/ui/` 中的 UI 组件

## 注意事项

- 此文件为 WebUI 前端资源
- 修改时需要考虑浏览器兼容性
- 遵循项目的前端编码规范