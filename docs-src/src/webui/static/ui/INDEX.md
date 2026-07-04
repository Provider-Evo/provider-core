# ui 静态资源

WebUI 用户界面组件的前端资源。

## 目录结构

```
ui/
├── bootstrap.js     # Bootstrap 框架 JavaScript
├── dropdown.js      # 下拉菜单组件
├── input-box.css    # 输入框样式
├── input-box.js     # 输入框组件
├── sortable-list/   # 可排序列表组件
└── styles.css       # 全局样式
```

## 核心功能

### bootstrap.js

Bootstrap 框架的 JavaScript 实现，提供基础 UI 组件支持。

### dropdown.js

下拉菜单组件的实现，包括：
- 菜单显示和隐藏
- 选项选择处理
- 键盘导航支持

### input-box.js

输入框组件的实现，包括：
- 文本输入处理
- 自动完成功能
- 输入验证

### sortable-list/

可排序列表组件，支持拖拽排序功能。

## 依赖关系

- 被其他静态资源模块依赖
- 提供 WebUI 的 UI 组件

## 注意事项

- 此目录为 WebUI UI 组件库
- 修改时需要考虑组件的可复用性
- 遵循项目的前端编码规范