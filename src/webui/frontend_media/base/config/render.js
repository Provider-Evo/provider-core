// ========================= Config Render: entry point =========================
// 本文件已拆分为 render/ 子目录下的多个模块（见下方列表），本文件仅作为薄入口保留，
// 不再包含任何函数定义。实际加载顺序由 index.html / lazy.js 中的 <script> 标签控制，
// 必须保证以下文件按顺序先于本文件加载完成：
//   render/render_primitives.js  (基础控件渲染，无依赖)
//   render/render_state.js       (target/mode 存取与共享状态变量)
//   render/render_schema.js      (schema 拉取与字段渲染，依赖 primitives + state)
//   render/render_main.js        (tabs/mode/target 切换主流程，依赖 state + schema)
//   render/render_bind.js        (面板事件绑定与 DOM 同步，依赖 state + main)
//   render/render_widgets.js     (模型/音频设备动态控件枚举，依赖 state)
//   render/render_data.js        (_renderConfigData 主渲染与运行时应用，依赖以上全部)
//   render/render_embedded.js    (插件内嵌配置面板，依赖 schema + primitives)
//
// 所有原全局函数名与 window.xxx 挂载均保持不变，逐一分布在上述子模块中。
