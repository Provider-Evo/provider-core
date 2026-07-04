# sortable-list 静态资源

WebUI 可排序列表组件的前端资源。

## 目录结构

```
sortable-list/
├── sortable-list.css    # 可排序列表样式
└── sortable-list.js     # 可排序列表 JavaScript 实现
```

## 核心功能

### sortable-list.js

可排序列表组件的实现，包括：
- 拖拽排序功能
- 排序动画效果
- 排序状态管理

### sortable-list.css

可排序列表组件的样式定义，包括：
- 列表项布局
- 拖拽状态样式
- 排序动画样式

## 依赖关系

- 依赖 `src/webui/static/core/` 中的核心模块
- 被其他 UI 组件使用

## 注意事项

- 此文件为 WebUI 前端组件
- 修改时需要考虑浏览器兼容性
- 遵循项目的前端编码规范