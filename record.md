/x/project/provider-self
.gitignore
AGENTS.md
README.md
config.toml
main.py
requirements.txt
src/__init__.py
src/core/__init__.py
src/core/autoupdate.py
src/core/candidate.py
src/core/config/__init__.py
src/core/config/base.py
src/core/config/manager.py
src/core/config/resolver.py
src/core/config/sections.py
src/core/dispatch/__init__.py
src/core/dispatch/candidate.py
src/core/dispatch/gateway.py
src/core/dispatch/registry.py
src/core/dispatch/runtime_view.py
src/core/dispatch/selector.py
src/core/errors/__init__.py
src/core/errors/base.py
src/core/errors/business.py
src/core/errors/platform.py
src/core/files.py
src/core/fncall/__init__.py
src/core/fncall/base.py
src/core/fncall/parsers/__init__.py
src/core/fncall/parsers/stream.py
src/core/fncall/parsers/xml_parser.py
src/core/fncall/prompt/__init__.py
src/core/fncall/prompt/history.py
src/core/fncall/prompt/inject.py
src/core/fncall/prompt/templates.py
src/core/fncall/protocols/__init__.py
src/core/fncall/protocols/antml.py
src/core/fncall/protocols/bracket.py
src/core/fncall/protocols/custom.py
src/core/fncall/protocols/nous.py
src/core/fncall/protocols/original.py
src/core/fncall/protocols/xml.py
src/core/fncall/registry.py
src/core/fncall/shared/__init__.py
src/core/fncall/shared/coercion.py
src/core/fncall/shared/loop_detect.py
src/core/fncall/shared/normalization.py
src/core/fncall/shared/uuid7.py
src/core/fncall/shared/xml_helpers.py
src/core/gateway.py
src/core/http.py
src/core/ids.py
src/core/io_utils.py
src/core/models_cache.py
src/core/process.py
src/core/proxy.py
src/core/registry.py
src/core/retry.py
src/core/runtime_view.py
src/core/scheduler.py
src/core/selector.py
src/core/server/__init__.py
src/core/server/autoupdate.py
src/core/server/http.py
src/core/server/process.py
src/core/server/proxy.py
src/core/server/server.py
src/core/server/watcher.py
src/core/server.py
src/core/tools.py
src/core/utils/__init__.py
src/core/utils/files.py
src/core/utils/ids.py
src/core/utils/io_utils.py
src/core/utils/retry.py
src/core/utils/scheduler.py
src/core/watcher.py
src/logger.py
src/platforms/__init__.py
src/platforms/apiairforce/__init__.py
src/platforms/apiairforce/adapter.py
src/platforms/apiairforce/client.py
src/platforms/apiairforce/util.py
src/platforms/base.py
src/platforms/caiyuesbk/__init__.py
src/platforms/caiyuesbk/adapter.py
src/platforms/caiyuesbk/client.py
src/platforms/caiyuesbk/util.py
src/platforms/cerebras/__init__.py
src/platforms/cerebras/adapter.py
src/platforms/cerebras/client.py
src/platforms/cerebras/util.py
src/platforms/chatmoe/__init__.py
src/platforms/chatmoe/adapter.py
src/platforms/chatmoe/client.py
src/platforms/chatmoe/util.py
src/platforms/chutes/__init__.py
src/platforms/chutes/adapter.py
src/platforms/chutes/client.py
src/platforms/chutes/util.py
src/platforms/codebuddy/__init__.py
src/platforms/codebuddy/adapter.py
src/platforms/codebuddy/client.py
src/platforms/codebuddy/util.py
src/platforms/cursor/__init__.py
src/platforms/cursor/adapter.py
src/platforms/cursor/client.py
src/platforms/cursor/util.py
src/platforms/deepseek/__init__.py
src/platforms/deepseek/adapter.py
src/platforms/deepseek/core/__init__.py
src/platforms/deepseek/core/adapter_impl.py
src/platforms/deepseek/core/client.py
src/platforms/deepseek/core/constants.py
src/platforms/deepseek/core/headers.py
src/platforms/deepseek/core/hif.py
src/platforms/deepseek/core/impl.py
src/platforms/deepseek/core/models_cache.py
src/platforms/deepseek/core/pow.py
src/platforms/deepseek/core/session_api.py
src/platforms/deepseek/core/stream_parser.py
src/platforms/deepseek/core/user_api.py
src/platforms/deepseek/util.py
src/platforms/edge_tts/__init__.py
src/platforms/edge_tts/adapter.py
src/platforms/edge_tts/client.py
src/platforms/edge_tts/util.py
src/platforms/edgetts/core/client.py
src/platforms/edgetts/core/consts.py
src/platforms/edgetts/core/drm.py
src/platforms/edgetts/core/impl.py
src/platforms/edgetts/core/tts.py
src/platforms/edgetts/core/websocket.py
src/platforms/edgetts/util.py
src/platforms/gtts/__init__.py
src/platforms/gtts/adapter.py
src/platforms/gtts/client.py
src/platforms/gtts/util.py
src/platforms/n1n/__init__.py
src/platforms/n1n/adapter.py
src/platforms/n1n/client.py
src/platforms/n1n/util.py
src/platforms/nvidia/__init__.py
src/platforms/nvidia/adapter.py
src/platforms/nvidia/client.py
src/platforms/nvidia/util.py
src/platforms/ollama/__init__.py
src/platforms/ollama/adapter.py
src/platforms/ollama/client.py
src/platforms/ollama/core/__init__.py
src/platforms/ollama/core/adapter_impl.py
src/platforms/ollama/core/client.py
src/platforms/ollama/core/constants.py
src/platforms/ollama/util.py
src/platforms/openai_fm/__init__.py
src/platforms/openai_fm/adapter.py
src/platforms/openai_fm/client.py
src/platforms/openai_fm/util.py
src/platforms/openaifm/core/client.py
src/platforms/openaifm/core/consts.py
src/platforms/openaifm/core/headers.py
src/platforms/openaifm/core/tts.py
src/platforms/openaifm/util.py
src/platforms/openrouter/__init__.py
src/platforms/openrouter/adapter.py
src/platforms/openrouter/client.py
src/platforms/openrouter/util.py
src/platforms/perplexity/__init__.py
src/platforms/perplexity/adapter.py
src/platforms/perplexity/client.py
src/platforms/perplexity/util.py
src/platforms/qwen/__init__.py
src/platforms/qwen/adapter.py
src/platforms/qwen/core/__init__.py
src/platforms/qwen/core/adapter_impl.py
src/platforms/qwen/core/client.py
src/platforms/qwen/core/impl.py
src/platforms/qwen/core/constants.py
src/platforms/qwen/core/shared.py
src/platforms/qwen/util.py
src/routes/__init__.py
src/routes/anthropic.py
src/routes/openai.py
src/routes/static.py
src/webui/__init__.py
src/webui/app.py
src/webui/config_schema.py
src/webui/dependencies.py
src/webui/logs_ws.py
src/webui/routers/__init__.py
src/webui/routers/admin.py
src/webui/routers/autoupdate.py
src/webui/routers/pages.py
src/webui/routes.py
src/webui/schemas/__init__.py
src/webui/schemas/summary.py
src/webui/server.py
src/webui/services/__init__.py
src/webui/services/summaries.py
src/webui/static/css/styles.css
src/webui/static/index.html
src/webui/static/js/actions.js
src/webui/static/js/bootstrap.js
src/webui/static/js/chat.js
src/webui/static/js/dropdown.js
src/webui/static/js/motion.js
src/webui/static/js/render.js
src/webui/static/js/state.js
src/webui/utils/__init__.py
src/webui/utils/export.py
template/template_config.toml
tests/src/core/config/test_base.py
tests/src/core/config/test_manager.py
tests/src/core/config/test_sections.py
tests/src/core/dispatch/test_candidate.py
tests/src/core/dispatch/test_gateway.py
tests/src/core/dispatch/test_registry.py
tests/src/core/dispatch/test_selector.py
tests/src/core/errors/test_errors.py
tests/src/core/fncall/shared/test_shared.py
tests/src/core/fncall/test_base.py
tests/src/core/test_autoupdate.py
tests/src/core/test_tools.py
tests/src/core/test_webui.py
tests/src/core/test_webui_async_tasks.py
tests/src/core/test_webui_local_store.py
tests/src/core/test_webui_routes.py
tests/src/core/test_webui_support.py
tests/src/core/utils/test_files.py
tests/src/core/utils/test_ids.py
tests/src/core/utils/test_io_utils.py
tests/src/core/utils/test_retry.py
tests/src/core/utils/test_scheduler.py
tests/src/platforms/ollama/test_ollama_servers.py
tests/src/platforms/qwen/test_qwen37max_protocols.py
tests/src/routes/test_anthropic.py
tests/src/routes/test_health.py
tests/src/routes/test_models.py
tests/src/routes/test_openai.py
docs-src/INDEX.md
docs-src/src/webui/INDEX.md
docs-src/src/webui/app.md
docs-src/src/webui/config_schema.md
docs-src/src/webui/routers/INDEX.md
docs-src/src/webui/routers/pages.md
docs-src/src/webui/routes.md
docs-src/src/webui/server.md
docs-src/src/webui/services/INDEX.md
docs-src/template/INDEX.md
.agents/provider-guide/SKILL.md
docs-src/tests-guide.md
docs-src/src/platforms/apiairforce/INDEX.md
docs-src/src/platforms/caiyuesbk/INDEX.md
docs-src/src/platforms/cerebras/INDEX.md
docs-src/src/platforms/chatmoe/INDEX.md
docs-src/src/platforms/chutes/INDEX.md
docs-src/src/platforms/codebuddy/INDEX.md
docs-src/src/platforms/cursor/INDEX.md
docs-src/src/platforms/deepseek/INDEX.md
docs-src/src/platforms/edgetts/INDEX.md
docs-src/src/platforms/gtts/INDEX.md
docs-src/src/platforms/n1n/INDEX.md
docs-src/src/platforms/nvidia/INDEX.md
docs-src/src/platforms/ollama/INDEX.md
docs-src/src/platforms/openaifm/INDEX.md
docs-src/src/platforms/openrouter/INDEX.md
docs-src/src/platforms/perplexity/INDEX.md
docs-src/src/platforms/qwen/INDEX.md

2026-06-05 23:30:00

[src/webui/static/js/dropdown.js] CustomDropdown 组件添加搜索筛选功能，选项超过5项时自动显示搜索框，列表最多显示5项其余靠滚动
[src/webui/static/css/styles.css] 添加 .custom-dropdown-search 样式，移除列表固定 max-height 改由 JS 动态控制
[template/template_config.toml] 版本 2.2.24 → 2.2.25
[config.toml] 同步版本 2.2.25
[README.md] 版本徽章 2.2.24 → 2.2.25
[.agents/provider-guide/SKILL.md] 版本字段 2.2.24 → 2.2.25
纯前端 JS/CSS 变更，无需 py_compile
pytest: 495 passed, 33 skipped

2026-06-05 22:35:00

[README.md] 修正 main 与 dev 分支差异描述，重写 classical 分支 README

2026-06-05 21:55:00

[AGENTS.md] 新增 CRITICAL 条目澄清 provider-guide 必须通过 Read 直接读取

2026-06-05 21:40:00

[src/core/server/server.py] 鉴权跳过集合移除 /docs /redoc /openapi.json
[src/routes/static.py] 删除 / 的 JSON 响应避免与 WebUI 页面路由冲突
[src/webui/__init__.py] 移除 render_page render_webui 兼容导出
[src/webui/app.py] 移除 render_page 兼容函数
[src/webui/config_schema.py] 删除 docs_path 字段，webui_path 默认改为 /
[src/webui/routers/__init__.py] 移除 docs_page root_page 导出
[src/webui/routers/pages.py] 保留 webui_page 仅服务 index.html
[src/webui/routes.py] 移除 /docs 与 /webui 页面路由，/ 直接服务 index.html
[src/webui/services/__init__.py] 移除 build_doc_sections 导出
[src/webui/static/index.html] 移除文档侧栏 Tab 与 tab-docs 面板，静态资源路径更新为 /static/
[src/webui/static/js/chat.js] 移除注释中对 docs 页的引用
[tests/src/core/test_webui.py] 移除 docs 相关测试，静态路径更新为 /static/
[docs-src/INDEX.md] 更新 WebUI 索引描述
[docs-src/src/webui/INDEX.md] 移除已删除模块条目
[docs-src/src/webui/routes.md] 更新为当前路由清单
[docs-src/src/webui/routers/INDEX.md] 移除文档处理器描述
[docs-src/src/webui/routers/pages.md] 描述改为仅负责管理台页面
[docs-src/src/webui/services/INDEX.md] 移除文档服务描述
[docs-src/src/webui/server.md] 更新为根路径提供 WebUI 的描述
[docs-src/src/webui/app.md] 删除页面渲染相关说明
[docs-src/src/webui/config_schema.md] 反映当前字段
[template/template_config.toml] 版本 2.2.23 → 2.2.24
[config.toml] 同步版本
[README.md] 版本徽章更新，删除 /docs 与 /webui 端点描述
[.agents/provider-guide/SKILL.md] 删除 /docs 引用

2026-05-31 00:00:00

[src/webui/static/js/chat.js] 新增 assistantAdded 标记修复 SSE 流结束后助手消息未添加到会话历史
[src/webui/static/css/styles.css] z-index 从 1000 提升至 9999，新增 .native-scroll-hidden 隐藏原生滚动条，全局 textarea/button/input 重置样式
[src/webui/static/index.html] textarea 添加 native-scroll-hidden class，viewport 添加固定高度，发送按钮新增箭头图标
[src/webui/static/js/motion.js] 禁用 animateTabIn 避免 CSS 动画冲突，排除 chatSendBtn 不受动画影响
[src/webui/static/js/bootstrap.js] 添加 loadModelsList() 调用修复模型选择框加载问题
[src/webui/routes.py] 静态文件路由添加 show_index=False 和 append_version=True 实现热重载
[src/webui/routers/pages.py] HTML 页面响应添加 Cache-Control 禁止浏览器缓存
[src/core/config/sections.py] ServerCfg 默认版本更新
[template/template_config.toml] 版本 2.2.20 → 2.2.23
[config.toml] 同步版本
[README.md] 版本徽章更新

2026-05-31 00:00:00

[src/webui/static/js/motion.js] 新增 MotionKit 动画框架，appearIn/floatScale/card-hover-lift/fadeInUp/toast-enter 等动效
[src/webui/static/css/styles.css] 新增统一设计系统 CSS，card-hover-lift/badge-loading/toast-enter/fadeInUp/loading-shimmer
[src/webui/static/index.html] 统一所有元素样式 rounded-xl + card-hover-lift
[src/webui/static/js/bootstrap.js] 集成 MotionKit 初始化
[src/webui/static/js/render.js] 动态卡片改用 rounded-xl + card-hover-lift
[src/webui/static/js/state.js] Toast 添加进入退出动画
[src/core/config/sections.py] ServerCfg 默认版本 2.2.21
[template/template_config.toml] 版本 2.2.20 → 2.2.21

2026-05-31 00:00:00

[src/webui/static/css/styles.css] 新增 .tool-btn 和 .voice-gif 样式
[src/webui/static/index.html] 聊天输入框左侧新增文件按钮和语音按钮

2026-05-31 00:00:00

[src/core/config/__init__.py] 新增 write_config() 修复配置保存 500 错误
[src/webui/static/css/styles.css] 硬编码颜色替换为 CSS 变量支持 dark mode
[src/webui/static/js/actions.js] 新增 WebSocket 自动重连逻辑
[src/webui/static/js/chat.js] 新增 SSE 流式响应超时处理
[template/template_config.toml] 版本 2.2.16 → 2.2.17

2026-05-31 00:00:00

[main.py] Python 3.14+ 使用 uvloop.install() 替代已弃用的 asyncio.set_event_loop_policy()
[template/template_config.toml] 版本 2.2.15 → 2.2.16

2026-05-31 00:00:00

[src/core/server/http.py] clean_fncall/safe_flush 新增 platform_id 参数
[src/core/dispatch/gateway.py] yield _meta.platform 让路由层感知实际执行平台
[src/routes/openai.py] 协议感知 tag detection 传递 platform_id
[template/template_config.toml] 版本 2.2.14 → 2.2.15

2026-05-31 00:00:00

[src/core/server/proxy.py] 添加缺失的 TCPConnector 导入
[tests/src/core/fncall/test_base.py] 添加 setup/teardown 保存恢复协议注册表状态
[tests/src/core/test_tools.py] 明确传递 protocol 参数修复协议不匹配
[tests/src/platforms/qwen/test_qwen37max_protocols.py] 新增 22 个测试覆盖 4 协议
[template/template_config.toml] 版本 2.2.13 → 2.2.14

2026-05-31 00:00:00

[src/webui/static/index.html] 新增 WebUI 主页面 HTML shell
[src/webui/static/css/styles.css] 从 layout.py 提取的内联 CSS
[src/webui/static/js/state.js] 新增状态管理与本地存储
[src/webui/static/js/render.js] 新增 DOM 渲染函数
[src/webui/static/js/actions.js] 新增 API 调用与 WebSocket
[src/webui/static/js/chat.js] 新增聊天 SSE 流式与批量测试
[src/webui/static/js/bootstrap.js] 新增事件绑定与初始化
[src/webui/routers/pages.py] 改用 FileResponse 服务静态文件
[src/webui/routes.py] 添加静态路由
[template/template_config.toml] 版本 2.2.12 → 2.2.13

2026-05-31 00:00:00

[tests/src/core/dispatch/test_candidate.py] 新增 13 tests
[tests/src/core/dispatch/test_gateway.py] 新增
[tests/src/core/dispatch/test_registry.py] 新增
[tests/src/core/dispatch/test_selector.py] 新增 22 tests
[tests/src/core/errors/test_errors.py] 新增 57 tests
[tests/src/core/config/test_sections.py] 新增
[tests/src/core/config/test_base.py] 新增
[tests/src/core/config/test_manager.py] 新增
[tests/src/core/utils/test_files.py] 新增
[tests/src/core/utils/test_ids.py] 新增
[tests/src/core/utils/test_io_utils.py] 新增
[tests/src/core/utils/test_retry.py] 新增
[tests/src/core/utils/test_scheduler.py] 新增
[tests/src/core/fncall/test_base.py] 新增
[tests/src/core/fncall/shared/test_shared.py] 新增
[tests/src/routes/test_health.py] 新增
[tests/src/routes/test_models.py] 新增
[tests/src/routes/test_openai.py] 新增
[tests/src/routes/test_anthropic.py] 新增
[template/template_config.toml] 版本 2.2.11 → 2.2.12

2026-05-31 00:00:00

[src/core/config/sections.py] 新增 AutoupdateCfg 数据类
[src/core/autoupdate.py] 新增自动更新模块 AutoUpdater
[main.py] 新增 _autoupdate_task 后台任务
[template/template_config.toml] 新增 [autoupdate] 配置段，版本 2.2.10 → 2.2.11

2026-05-30 00:00:00

[src/core/gateway.py] 修复 _single 缺少工具定义注入、_race 缺少 fncall_lang 参数、FncallStreamParser 未传入平台协议
[src/core/tools.py] FncallStreamParser.__init__ 新增可选 protocol 参数
[template/template_config.toml] 版本 2.2.9 → 2.2.10

2026-05-30 00:00:00

[src/routes/openai.py] 修复 create_embeddings 缺少 registry 赋值导致 NameError
[template/template_config.toml] 版本 2.2.8 → 2.2.9

2026-05-30 00:00:00

[src/logger.py] 新增 set_color(enabled) 控制日志颜色
[src/core/config/sections.py] DebugCfg 新增 color 字段，ServerCfg.STARTUP_FORCE_KILL_PORT 改为 snake_case
[src/core/config/manager.py] 加载时自动应用 debug.color
[src/platforms/edgetts/accounts.py] 修复导入路径
[src/platforms/edgetts/core/client.py] 修复导入路径
[src/platforms/edgetts/core/impl.py] 修复导入路径
[src/platforms/edgetts/util.py] 修复导入不存在的模块
[src/platforms/openaifm/core/client.py] 移除不存在的导入
[src/platforms/openaifm/core/headers.py] 新建 build_headers()
[src/platforms/openaifm/core/tts.py] 新建 build_tts_form_data()
[template/template_config.toml] 版本 2.2.7 → 2.2.8

2026-05-30 00:00:00

[src/core/config/sections.py] FncallCfg 新增 fncall_mapping 字段
[src/core/fncall/registry.py] get_protocol 新增 platform_id 参数
[src/core/gateway.py] 延迟协议注入至候选项选定后
[template/template_config.toml] 版本 2.2.7 → 2.2.8

2026-05-30 00:00:00

[src/core/fncall/protocols/nous.py] 新增 Nous Research XML 风格工具调用协议
[template/template_config.toml] 版本 2.2.6 → 2.2.7

2026-05-30 00:00:00

[src/core/fncall/protocols/antml.py] 修复 _ANTML_INSTRUCTION 缺少语法示例，延迟 schema index 构建
[template/template_config.toml] 版本 2.2.4 → 2.2.5

2026-05-30 00:00:00

[src/core/fncall/parsers/stream.py] 修复 _is_call_closed 误触发，_end_tags 预计算
[src/core/gateway.py] 正确传递协议实例给 inject_fncall

2026-05-30 00:00:00

[src/core/fncall/] 新建包 23 个文件，5 种协议模式
[src/core/tools.py] 改为薄适配层从 fncall 重新导出
[src/core/http.py] clean_fncall/safe_flush 改为协议感知
[src/core/config/sections.py] FncallCfg 新增 protocol/custom_prompt 字段
[template/template_config.toml] fncall 段落重构

2026-05-24 00:00:00

[src/core/config/sections.py] ServerCfg 新增 version 字段修复 AttributeError
[src/core/server.py] create_app 新增 setup_webui 调用
[src/routes/static.py] 版本号从硬编码改为从配置模板读取
[src/routes/health.py] 版本号从硬编码改为从配置模板读取

2026-05-24 00:00:00

[.gitignore] 从 blanket *.toml 改为精确 config.toml，新增 template 排除
[template/template_config.toml] 新增配置模板文件
[docs-src/template/INDEX.md] 同步更新模板文档

2026-05-24 00:00:00

[src/platforms/deepseek/core/client.py] 修复 accounts 导入路径
[src/platforms/deepseek/util.py] 修复 accounts 导入路径
[src/platforms/ollama/core/client.py] 修复 accounts 导入路径
[src/platforms/qwen/core/client.py] 修复 accounts 导入路径

2026-06-06 06:45:00

[.gitignore] record.md 改为 RECORD.md（大小写修正）
[config.toml] 平台黑名单新增 aitianhu2
[docs-src/tests-guide.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/apiairforce/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/caiyuesbk/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/cerebras/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/chatmoe/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/chutes/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/codebuddy/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/cursor/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/deepseek/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/edgetts/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/gtts/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/n1n/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/nvidia/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/ollama/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/openaifm/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/openrouter/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/perplexity/INDEX.md] record.md 引用统一改为 RECORD.md
[docs-src/src/platforms/qwen/INDEX.md] record.md 引用统一改为 RECORD.md

2026-06-06 07:40:00

[src/platforms/qwen/core/client.py] 修复 enabled_platforms=[] 时仍能使用代理：持久化加载和 _get_proxy_kwarg 增加 enabled_platforms_set 守卫
[template/template_config.toml] 版本 2.2.25 → 2.2.26
[config.toml] 同步版本 2.2.26
[README.md] 版本徽章和路线图更新为 2.2.26
[.agents/provider-guide/SKILL.md] 版本字段 2.2.26

2026-06-06 07:50:00

[src/webui/static/js/chat.js] 消息编辑对话框按钮统一为「确定」+「取消」，用户消息原「发送」和助手消息原「保存」均改为「确定」
[template/template_config.toml] 版本 2.2.26 → 2.2.27
[config.toml] 同步版本 2.2.27
[README.md] 版本徽章和路线图更新为 2.2.27
[.agents/provider-guide/SKILL.md] 版本字段 2.2.27

2026-06-06 07:55:00

[src/webui/static/js/chat.js] 助手消息编辑按钮添加 inline style 覆盖，使用 CSS 变量适配浅色背景，解决白色按钮不可见问题
[template/template_config.toml] 版本 2.2.27 → 2.2.28
[config.toml] 同步版本 2.2.28
[README.md] 版本徽章和路线图更新为 2.2.28
[.agents/provider-guide/SKILL.md] 版本字段 2.2.28

2026-06-06 08:00:00

[src/routes/anthropic.py] 流式路径从 _meta chunk 捕获 platform_id，用 get_protocol 做协议感知标签检测替代硬编码 _FNCALL_OPEN_TAG；_safe_flush 传入 platform_id；非流式路径同样捕获 platform_id 传给 _clean_fncall
[template/template_config.toml] 版本 2.2.28 → 2.2.29
[config.toml] 同步版本 2.2.29
[README.md] 版本徽章和路线图更新为 2.2.29
[.agents/provider-guide/SKILL.md] 版本字段 2.2.29

2026-06-06 08:10:00

[src/webui/static/index.html] Tailwind backgroundColor 配置添加 accent 颜色定义，修复 bg-accent 类无效导致聊天发送按钮背景透明不可见
[template/template_config.toml] 版本 2.2.29 → 2.2.30
[config.toml] 同步版本 2.2.30
[README.md] 版本徽章和路线图更新为 2.2.30
[.agents/provider-guide/SKILL.md] 版本字段 2.2.30

2026-06-06 08:15:00

[src/webui/routers/autoupdate.py] autoupdate_check 函数添加 from pathlib import Path，修复 Path 未导入导致的 NameError
[template/template_config.toml] 版本 2.2.30 → 2.2.31
[config.toml] 同步版本 2.2.31
[README.md] 版本徽章和路线图更新为 2.2.31
[.agents/provider-guide/SKILL.md] 版本字段 2.2.31

2026-06-06 08:25:00

[src/core/fncall/prompt/history.py] _format_conversation_history 新增 protocol 参数，使用 protocol.format_assistant_tool_calls() 渲染历史工具调用，确保格式与协议指令一致，修复 LLM 工具调用死循环
[src/core/fncall/prompt/inject.py] inject_fncall 将 protocol 传递给 _format_conversation_history
[template/template_config.toml] 版本 2.2.31 → 2.2.32
[config.toml] 同步版本 2.2.32
[README.md] 版本徽章和路线图更新为 2.2.32
[.agents/provider-guide/SKILL.md] 版本字段 2.2.32

2026-06-06 08:30:00

[src/core/fncall/prompt/history.py] 检测 role=tool 消息判断 agent CLI，跳过渲染 assistant tool_calls 块避免双重渲染，仅 WebUI 无 tool 角色消息时才渲染
[template/template_config.toml] 版本 2.2.32 → 2.2.33
[config.toml] 同步版本 2.2.33
[README.md] 版本徽章和路线图更新为 2.2.33
[.agents/provider-guide/SKILL.md] 版本字段 2.2.33

2026-06-06 08:35:00

[src/core/fncall/prompt/history.py] 非 WebUI 检测条件扩大：检查 role=tool 或 assistant 带 tool_calls，仅纯文本消息（WebUI）才渲染工具调用历史
[tests/src/core/test_tools.py] 更新 test_format_history_user_assistant 断言匹配新行为
[template/template_config.toml] 版本 2.2.33 → 2.2.34
[config.toml] 同步版本 2.2.34
[README.md] 版本徽章和路线图更新为 2.2.34
[.agents/provider-guide/SKILL.md] 版本字段 2.2.34

2026-06-06 09:45:00

[template/template_config.toml] 版本 2.2.34 → 2.2.35
[config.toml] 同步版本 2.2.35
[README.md] 版本徽章和路线图更新为 2.2.35：aitianhu2 平台对齐上游（动态 carids + 48h 刷新、system_hints 透传、Authorization 头补全、认证加固、22h 软刷新）

2026-06-06 10:05:00

[template/template_config.toml] 版本 2.2.35 → 2.2.36
[config.toml] 同步版本 2.2.36
[README.md] 版本徽章和路线图更新为 2.2.36：aitianhu2 流式对话 client_prepare_state + x-conduit-token 透传

2026-06-06 10:10:00

[template/template_config.toml] 版本 2.2.36 → 2.2.37
[config.toml] 同步版本 2.2.37
[README.md] 版本徽章和路线图更新为 2.2.37：aitianhu2 401 重认证强制刷新 carids + 落地页正则未匹配日志

2026-06-06 10:35:00

[src/core/server/server.py] _auth_middleware 放行 /login 与 /static/；接受 pv2_session Cookie 作为 Bearer 等价凭证；浏览器访问无凭证时 302 到 /login，API 客户端仍返回 JSON 401
[src/webui/routers/__init__.py] 新增 login_page / logout_page 导出
[src/webui/routers/pages.py] 新增 login_page（GET/POST）与 logout_page 处理器；登录页内联 CSS，light/dark 自适应；POST 校验 [auth].keys 命中则下发 pv2_session HttpOnly Cookie（30 天有效期）
[src/webui/routes.py] 注册 /login（* 方法）与 /logout（GET）路由
[docs-src/src/webui/routers/pages.md] 补充 login_page / logout_page 处理器的职责说明
[template/template_config.toml] 版本 2.2.37 → 2.2.38
[config.toml] 同步版本 2.2.38
[README.md] 版本徽章和路线图更新为 2.2.38：WebUI 登录页 + Cookie 鉴权 + 静态资源放行

2026-06-06 10:45:00

[src/core/server/server.py] _auth_middleware 的 skip 集合移除 /，管理面板现需鉴权：未登录浏览器访问 / 自动 302 到 /login，登录后由 pv2_session Cookie 驱动回到 /
[template/template_config.toml] 版本 2.2.38 → 2.2.39
[config.toml] 同步版本 2.2.39
[README.md] 版本徽章和路线图更新为 2.2.39：管理面板强制鉴权

2026-06-06 10:55:00

[src/core/server/server.py] _auth_middleware 的 skip 集合进一步移除 /health 与 /v1/models：两路由现需 pv2_session Cookie 或 Bearer/X-API-Key 任一有效才放行；浏览器无凭证 302 到 /login，API 客户端 JSON 401
[template/template_config.toml] 版本 2.2.39 → 2.2.40
[config.toml] 同步版本 2.2.40
[README.md] 版本徽章和路线图更新为 2.2.40：/health 与 /v1/models 强制鉴权


2026-06-06 11:15:00

[src/core/config/sections.py] GatewayCfg 新增 group_list_type (whitelist/blacklist) + group_list + is_platform_enabled helper，控制并发竞速平台黑白名单；PlatformsProxyCfg 新增 group_list_type + is_platform_enabled helper，控制 enabled_platforms 的白名单/黑名单语义
[src/core/dispatch/gateway.py] 候选集按 [gateway].group_list_type + group_list 过滤；concurrent_enabled=false 时仅退化为 n=1，名单仍过滤候选集
[src/core/dispatch/runtime_view.py] 摘要导出 gateway.group_list_type + group_count 与 platforms_proxy.group_list_type
[src/platforms/base.py] is_proxy_allowed 文档更新：决策现经 platforms_proxy.is_platform_enabled
[src/platforms/deepseek/core/adapter_impl.py] is_proxy_allowed 改用 platforms_proxy.is_platform_enabled(self.name)
[src/platforms/deepseek/core/impl.py] 同上
[src/platforms/qwen/core/adapter_impl.py] 同上
[src/platforms/qwen/core/impl.py] 同上
[src/platforms/qwen/core/client.py] 三处 enabled_platforms_set 直查改为 is_platform_enabled("qwen")
[template/template_config.toml] 版本 2.2.40 → 2.2.41；[gateway] 新增 group_list_type/group_list；[platforms_proxy] 新增 group_list_type
[config.toml] 同步版本 2.2.41 与新字段
[README.md] 版本徽章和路线图更新为 2.2.41：gateway + platforms_proxy 黑白名单
2026-06-06 11:30:00

[src/core/config/sections.py] GatewayCfg 文档 + is_platform_enabled 文档更新：group_list 语义修正为"竞速名单"，不再切断路由
[src/core/dispatch/gateway.py] group_list 不再过滤候选集；改为构建 racing_pool，竞速池 ≥ 2 才启用 n>1，否则退化到全候选集单发
[template/template_config.toml] 版本 2.2.41 → 2.2.42；gateway 注释同步新语义
[config.toml] 同步版本 2.2.42
[README.md] 版本徽章和路线图更新为 2.2.42：gateway.group_list 竞速名单语义修正

2026-06-06 13:05:00

[template/template_config.toml] 版本 2.2.42 → 2.2.43
[config.toml] 同步版本 2.2.43
[README.md] 版本徽章和路线图更新为 2.2.43：aitianhu2 多账号重构 + 动态 account_id + CRITICAL bug 修复（aitianhu2 平台源码被 .gitignore 过滤，详见 src/platforms/aitianhu2/）

2026-06-06 13:30:00

[src/core/fncall/protocols/antml.py] _BLOCK_RE 放宽为 <antml:function_calls\b[^>]*> 以容忍带空格/属性/换行的变体；detect_start 改用前缀匹配 <antml:function_calls 并手动查找闭合 >；解决模型输出变体标签时 tool_calls 漏解析落入 content 的问题
[src/routes/openai.py] 非流式 chat_completions 新增兜底：若网关未产出 tool_calls 块（请求未带 tools 或流式解析器漏掉），对整段 content 再跑一次 get_protocol(platform_id=).parse() 提取 tool_calls
[template/template_config.toml] 版本 2.2.43 → 2.2.44
[config.toml] 同步版本 2.2.44
[README.md] 版本徽章和路线图更新为 2.2.44：antml fncall 变体兼容 + 非流式 tool_calls 兜底 + aitianhu2 429 冷却与 fallback sentinel token（aitianhu2 平台源码被 .gitignore 过滤）

2026-06-06 14:10:00

[src/core/fncall/prompt/inject.py] _maybe_dump_prompt 把 record_prompt 视作 print_prompt 别名：任一为 true 即落盘 prompt 到 logs/prompts/<uuid7>.txt
[src/core/fncall/protocols/antml.py] AntmlProtocol.render_prompt 同步接受 record_prompt/print_prompt 任一为 true 触发 dump
[template/template_config.toml] 版本 2.2.44 → 2.2.45
[config.toml] 同步版本 2.2.45
[README.md] 版本徽章和路线图更新为 2.2.45：fncall record_prompt 字段激活
