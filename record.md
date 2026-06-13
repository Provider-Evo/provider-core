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
src/platforms/apiairforce/core/adaptercore.py
src/platforms/apiairforce/core/constants.py
src/platforms/apiairforce/util.py
src/platforms/base.py
src/platforms/caiyuesbk/__init__.py
src/platforms/caiyuesbk/adapter.py
src/platforms/caiyuesbk/client.py
src/platforms/caiyuesbk/core/adaptercore.py
src/platforms/caiyuesbk/core/constants.py
src/platforms/caiyuesbk/util.py
src/platforms/cerebras/__init__.py
src/platforms/cerebras/adapter.py
src/platforms/cerebras/client.py
src/platforms/cerebras/core/adaptercore.py
src/platforms/cerebras/core/constants.py
src/platforms/cerebras/util.py
src/platforms/chatmoe/__init__.py
src/platforms/chatmoe/adapter.py
src/platforms/chatmoe/client.py
src/platforms/chatmoe/core/adaptercore.py
src/platforms/chatmoe/core/constants.py
src/platforms/chatmoe/util.py
src/platforms/chutes/__init__.py
src/platforms/chutes/adapter.py
src/platforms/chutes/client.py
src/platforms/chutes/core/adaptercore.py
src/platforms/chutes/core/constants.py
src/platforms/chutes/util.py
src/platforms/codebuddy/__init__.py
src/platforms/codebuddy/adapter.py
src/platforms/codebuddy/client.py
src/platforms/codebuddy/core/adaptercore.py
src/platforms/codebuddy/core/constants.py
src/platforms/codebuddy/util.py
src/platforms/cursor/__init__.py
src/platforms/cursor/adapter.py
src/platforms/cursor/client.py
src/platforms/cursor/core/adaptercore.py
src/platforms/cursor/util.py
src/platforms/deepseek/__init__.py
src/platforms/deepseek/adapter.py
src/platforms/deepseek/core/__init__.py
src/platforms/deepseek/core/adaptercore.py
src/platforms/deepseek/core/client.py
src/platforms/deepseek/core/constants.py
src/platforms/deepseek/core/headers.py
src/platforms/deepseek/core/hif.py
src/platforms/deepseek/core/modelcache.py
src/platforms/deepseek/core/pow.py
src/platforms/deepseek/core/sessionapi.py
src/platforms/deepseek/core/streamparser.py
src/platforms/deepseek/core/userapi.py
src/platforms/deepseek/util.py
src/platforms/edge_tts/__init__.py
src/platforms/edge_tts/adapter.py
src/platforms/edge_tts/client.py
src/platforms/edge_tts/util.py
src/platforms/edgetts/core/adaptercore.py
src/platforms/edgetts/core/client.py
src/platforms/edgetts/core/constants.py
src/platforms/edgetts/core/drm.py
src/platforms/edgetts/core/tts.py
src/platforms/edgetts/core/websocket.py
src/platforms/edgetts/util.py
src/platforms/gtts/__init__.py
src/platforms/gtts/adapter.py
src/platforms/gtts/client.py
src/platforms/gtts/core/adaptercore.py
src/platforms/gtts/util.py
src/platforms/n1n/__init__.py
src/platforms/n1n/adapter.py
src/platforms/n1n/client.py
src/platforms/n1n/core/adaptercore.py
src/platforms/n1n/core/constants.py
src/platforms/n1n/util.py
src/platforms/nvidia/__init__.py
src/platforms/nvidia/adapter.py
src/platforms/nvidia/client.py
src/platforms/nvidia/core/adaptercore.py
src/platforms/nvidia/core/constants.py
src/platforms/nvidia/util.py
src/platforms/noobkeys/__init__.py
src/platforms/noobkeys/adapter.py
src/platforms/noobkeys/core/__init__.py
src/platforms/noobkeys/core/adaptercore.py
src/platforms/noobkeys/core/client.py
src/platforms/noobkeys/core/constants.py
src/platforms/noobkeys/core/headers.py
src/platforms/noobkeys/core/payloads.py
src/platforms/noobkeys/core/sse.py
src/platforms/noobkeys/util.py
src/platforms/ollama/__init__.py
src/platforms/ollama/adapter.py
src/platforms/ollama/client.py
src/platforms/ollama/core/__init__.py
src/platforms/ollama/core/adaptercore.py
src/platforms/ollama/core/client.py
src/platforms/ollama/core/constants.py
src/platforms/ollama/util.py
src/platforms/openai_fm/__init__.py
src/platforms/openai_fm/adapter.py
src/platforms/openai_fm/client.py
src/platforms/openai_fm/util.py
src/platforms/openaifm/core/adaptercore.py
src/platforms/openaifm/core/client.py
src/platforms/openaifm/core/constants.py
src/platforms/openaifm/core/headers.py
src/platforms/openaifm/core/tts.py
src/platforms/openaifm/util.py
src/platforms/openrouter/__init__.py
src/platforms/openrouter/adapter.py
src/platforms/openrouter/client.py
src/platforms/openrouter/core/adaptercore.py
src/platforms/openrouter/util.py
src/platforms/perplexity/__init__.py
src/platforms/perplexity/adapter.py
src/platforms/perplexity/client.py
src/platforms/perplexity/core/adaptercore.py
src/platforms/perplexity/core/constants.py
src/platforms/perplexity/util.py
src/platforms/qwen/__init__.py
src/platforms/qwen/adapter.py
src/platforms/qwen/core/__init__.py
src/platforms/qwen/core/adaptercore.py
src/platforms/qwen/core/client.py
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
tests/src/core/fncall/test_nous_protocol.py
tests/src/core/fncall/test_original_protocol.py
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
tests/src/platforms/noobkeys/__init__.py
tests/src/platforms/noobkeys/test_noobkeys_mvp.py
tests/src/platforms/ollama/test_ollama_embedding.py
tests/src/platforms/ollama/test_ollama_mvp.py
tests/src/platforms/ollama/test_ollama_servers.py
tests/src/platforms/qwen/test_qwen37max_protocols.py
tests/src/routes/test_anthropic.py
tests/src/routes/test_health.py
tests/src/routes/test_models.py
tests/src/routes/test_openai.py
tests/src/test_logger.py
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
docs-src/src/platforms/noobkeys/INDEX.md
docs-src/src/platforms/ollama/INDEX.md
docs-src/src/platforms/openaifm/INDEX.md
docs-src/src/platforms/openrouter/INDEX.md
docs-src/src/platforms/perplexity/INDEX.md
docs-src/src/platforms/qwen/INDEX.md
docs-src/agents.md
docs-src/src/agents.md
docs-src/src/platforms/agents.md
docs-src/src/platforms/guide.md
docs-src/src/platforms/deepseek/core/deepseek.md
docs-src/src/platforms/ollama/core/ollama.md
docs-src/src/platforms/qwen/core/qwen.md
docs-src/platforms/deepseek/core/deepseek.md
docs-src/platforms/ollama/core/ollama.md
docs-src/platforms/qwen/core/qwen.md
docs-src/platforms/guide.md

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

2026-06-06 14:25:00

[src/platforms/aitianhu2/core/chat.py] SSE 解析重写：移植上游 _V1DeltaAccumulator（228 行状态机，1:1 还原 main.py:969-1197 JS chunk Yte+Qte+dj），支持短键/长键双向规范化、字段继承、多通道并行、完整 JSONPatch op 集；路由守卫放宽为 o/op/p/path/v/value/c/channel 任一存在即交状态机；根因修复 gpt-5.5 上游使用长键或省略重复字段时 antml 标签被静默丢弃导致工具调用失效
[src/routes/openai.py] _stream_chat 标签检测改用 proto.detect_start(buffer) 兼容 <antml:function_calls > 等变体；不支持该方法的协议回退到严格 trigger_tags 匹配
[template/template_config.toml] 版本 2.2.45 → 2.2.46
[config.toml] 同步版本 2.2.46
[README.md] 版本徽章和路线图更新为 2.2.46：aitianhu2 SSE v1 delta 状态机 + detect_start 兼容 + 路由守卫放宽

2026-06-06 15:10:00

[src/core/fncall/protocols/nous.py] NousProtocol.render_prompt 修复：'{tool_descs}\n\n' 由普通字符串字面量改为 + tool_descs + '\n\n' 拼接，使工具定义（参数名/类型/必填/schema）正确注入 prompt；默认配置 qwen = "nous" 下所有 fncall 请求此前均命中此 bug，模型只能靠报错摸索调用方式
[tests/src/core/fncall/test_nous_protocol.py] 新增 test_render_prompt_interpolates_tool_descs 回归测试：断言 prompt 包含工具名与参数名且不含字面 '{tool_descs}'
[template/template_config.toml] 版本 2.2.46 → 2.2.47
[config.toml] 同步版本 2.2.47
[README.md] 版本徽章和路线图更新为 2.2.47：nous fncall tool_descs 插值 bug 修复
[.agents/provider-guide/SKILL.md] 版本字段 2.2.46 → 2.2.47

2026-06-06 16:00:00

[src/core/fncall/protocols/original.py] OriginalProtocol.render_prompt 补全 loop_warning 章节：该参数此前被静默丢弃，现以 <loop_warning> XML 包装注入 prompt；工具调用死循环安全告警在所有协议中应无条件渲染
[tests/src/core/fncall/test_original_protocol.py] 新增 test_render_prompt_renders_loop_warning / test_render_prompt_omits_empty_loop_warning 回归测试
[tests/src/core/fncall/shared/test_shared.py] 新增 format_tool_descs 嵌套 schema 渲染测试：三层 object 嵌套、array items 含 object、input_examples
[template/template_config.toml] 版本 2.2.47 → 2.2.48
[config.toml] 同步版本 2.2.48
[README.md] 版本徽章和路线图更新为 2.2.48：fncall 全协议审计 + original loop_warning 修复
[.agents/provider-guide/SKILL.md] 版本字段 2.2.47 → 2.2.48

2026-06-06 16:15:00

[_write_report.py] 删除审计子代理生成的在项目根目录的临时报告脚本（206 行），非项目结构一部分


2026-06-06 23:10:00

[src/platforms/apiairforce/core/constants.py] 新建：提取内联 BASE_URL/CHAT_PATH/MODELS_PATH/MODELS/CAPS 至标准 constants.py
[src/platforms/apiairforce/core/adaptercore.py] 新建：从 core/impl.py 重命名，PlatformAdapter 接口标准命名
[src/platforms/apiairforce/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/apiairforce/core/client.py] 更新 import 路径引用 constants
[src/platforms/apiairforce/core/headers.py] 更新 import 路径引用 constants
[src/platforms/apiairforce/core/__init__.py] 更新导出引用 adaptercore
[src/platforms/apiairforce/adapter.py] 门面 re-export 更新
[src/platforms/apiairforce/util.py] 懒加载引用更新
[src/platforms/apiairforce/__init__.py] 导出更新
[src/platforms/caiyuesbk/core/constants.py] 新建：提取内联常量至标准 constants.py
[src/platforms/caiyuesbk/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/caiyuesbk/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/caiyuesbk/core/client.py] 更新 import 路径
[src/platforms/caiyuesbk/core/__init__.py] 更新导出
[src/platforms/caiyuesbk/adapter.py] 门面 re-export 更新
[src/platforms/caiyuesbk/util.py] 懒加载引用更新
[src/platforms/caiyuesbk/__init__.py] 导出更新
[src/platforms/cerebras/core/constants.py] 新建：提取 MODELS/CAPS/FETCH_MODELS_ENABLED/MODEL_FETCH_INTERVAL
[src/platforms/cerebras/core/adaptercore.py] 新建：从 core/impl.py 重命名；Adapter 别名统一
[src/platforms/cerebras/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/cerebras/core/client.py] 更新 import 路径
[src/platforms/cerebras/core/__init__.py] 更新导出
[src/platforms/cerebras/adapter.py] 门面 re-export 更新
[src/platforms/cerebras/util.py] 懒加载引用更新
[src/platforms/cerebras/__init__.py] 导出更新
[src/platforms/chatmoe/core/constants.py] 新建：提取内联常量；client.py 硬编码 URL 改为引用 constants
[src/platforms/chatmoe/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/chatmoe/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/chatmoe/core/client.py] 更新 import 路径
[src/platforms/chatmoe/core/__init__.py] 更新导出
[src/platforms/chatmoe/adapter.py] 门面 re-export 更新
[src/platforms/chatmoe/util.py] 懒加载引用更新
[src/platforms/chatmoe/__init__.py] 导出更新
[src/platforms/chutes/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/chutes/core/constants.py] 新建：提取常量
[src/platforms/chutes/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/chutes/core/client.py] 更新 import 路径
[src/platforms/chutes/core/__init__.py] 更新导出
[src/platforms/chutes/adapter.py] 门面 re-export 更新
[src/platforms/chutes/util.py] 懒加载引用更新
[src/platforms/chutes/__init__.py] 导出更新
[src/platforms/codebuddy/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/codebuddy/core/constants.py] 新建：提取常量
[src/platforms/codebuddy/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/codebuddy/core/headers.py] 更新 import 路径
[src/platforms/codebuddy/adapter.py] 门面 re-export 更新
[src/platforms/codebuddy/util.py] 懒加载引用更新
[src/platforms/codebuddy/__init__.py] 导出更新
[src/platforms/cursor/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/cursor/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/cursor/upload.txt] 删除：非项目文件
[src/platforms/cursor/adapter.py] 门面 re-export 更新
[src/platforms/cursor/util.py] 懒加载引用更新
[src/platforms/cursor/__init__.py] 导出更新
[src/platforms/deepseek/core/adaptercore.py] 新建：从 core/adapter_impl.py 重命名
[src/platforms/deepseek/core/modelcache.py] 新建：从 core/models_cache.py 重命名（禁下划线规则）
[src/platforms/deepseek/core/sessionapi.py] 新建：从 core/session_api.py 重命名
[src/platforms/deepseek/core/streamparser.py] 新建：从 core/stream_parser.py 重命名
[src/platforms/deepseek/core/userapi.py] 新建：从 core/user_api.py 重命名
[src/platforms/deepseek/core/adapter_impl.py] 删除：重命名为 adaptercore.py
[src/platforms/deepseek/core/impl.py] 删除：合并入 adaptercore.py
[src/platforms/deepseek/core/models_cache.py] 删除：重命名为 modelcache.py
[src/platforms/deepseek/core/session_api.py] 删除：重命名为 sessionapi.py
[src/platforms/deepseek/core/stream_parser.py] 删除：重命名为 streamparser.py
[src/platforms/deepseek/core/user_api.py] 删除：重命名为 userapi.py
[src/platforms/deepseek/core/client.py] 更新 import 路径
[src/platforms/deepseek/adapter.py] 门面 re-export 更新
[src/platforms/deepseek/util.py] 懒加载引用更新
[src/platforms/deepseek/__init__.py] 导出更新
[src/platforms/edgetts/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/edgetts/core/constants.py] 新建：从 core/consts.py 重命名（标准命名）
[src/platforms/edgetts/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/edgetts/core/consts.py] 删除：重命名为 constants.py
[src/platforms/edgetts/core/client.py] 更新 import 路径
[src/platforms/edgetts/core/drm.py] 更新 import 路径
[src/platforms/edgetts/core/tts.py] 更新 import 路径
[src/platforms/edgetts/adapter.py] 门面 re-export 更新
[src/platforms/edgetts/util.py] 懒加载引用更新
[src/platforms/edgetts/__init__.py] 导出更新
[src/platforms/gtts/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/gtts/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/gtts/adapter.py] 门面 re-export 更新
[src/platforms/gtts/util.py] 懒加载引用更新
[src/platforms/gtts/__init__.py] 导出更新
[src/platforms/n1n/adapter.py] 从 783 行实现重写为 5 行纯门面 re-export
[src/platforms/n1n/util.py] 引入 __getattr__ 懒加载，移除重复常量定义，改为从 core/constants.py 导入
[src/platforms/n1n/core/adaptercore.py] CAPS/FETCH_MODELS_ENABLED/MODEL_FETCH_INTERVAL 改为从 .constants 导入
[src/platforms/n1n/core/constants.py] 新建：集中平台常量
[src/platforms/n1n/core/impl.py] 删除：合并入 adaptercore.py
[src/platforms/n1n/core/client.py] 更新 import 路径
[src/platforms/n1n/__init__.py] 补齐 Adapter 通用别名
[src/platforms/nvidia/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/nvidia/core/constants.py] 新建：提取常量
[src/platforms/nvidia/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/nvidia/core/client.py] 更新 import 路径
[src/platforms/nvidia/adapter.py] 门面 re-export 更新
[src/platforms/nvidia/util.py] 懒加载引用更新
[src/platforms/nvidia/__init__.py] 导出更新
[src/platforms/ollama/core/adaptercore.py] 新建：从 core/adapter_impl.py 重命名
[src/platforms/ollama/core/adapter_impl.py] 删除：重命名为 adaptercore.py
[src/platforms/ollama/core/impl.py] 删除：合并入 adaptercore.py
[src/platforms/ollama/core/constants.py] 更新常量引用
[src/platforms/ollama/adapter.py] 门面 re-export 更新
[src/platforms/ollama/util.py] 懒加载引用更新
[src/platforms/ollama/__init__.py] 导出更新
[src/platforms/openaifm/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/openaifm/core/constants.py] 新建：从 core/consts.py 重命名（标准命名）
[src/platforms/openaifm/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/openaifm/core/consts.py] 删除：重命名为 constants.py
[src/platforms/openaifm/core/client.py] 更新 import 路径
[src/platforms/openaifm/core/headers.py] 更新 import 路径
[src/platforms/openaifm/core/tts.py] 更新 import 路径
[src/platforms/openaifm/adapter.py] 门面 re-export 更新
[src/platforms/openaifm/util.py] 补齐 MODELS/CAPS 导出
[src/platforms/openaifm/__init__.py] 导出更新
[src/platforms/openrouter/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/openrouter/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/openrouter/adapter.py] 门面 re-export 更新
[src/platforms/openrouter/util.py] 懒加载引用更新
[src/platforms/openrouter/__init__.py] 导出更新
[src/platforms/perplexity/core/adaptercore.py] 新建：从 core/impl.py 重命名
[src/platforms/perplexity/core/constants.py] 新建：提取常量
[src/platforms/perplexity/core/impl.py] 删除：重命名为 adaptercore.py
[src/platforms/perplexity/adapter.py] 门面 re-export 更新
[src/platforms/perplexity/util.py] 懒加载引用更新
[src/platforms/perplexity/__init__.py] 导出更新
[src/platforms/qwen/core/adaptercore.py] 新建：从 core/adapter_impl.py 重命名
[src/platforms/qwen/core/adapter_impl.py] 删除：重命名为 adaptercore.py
[src/platforms/qwen/core/impl.py] 删除：合并入 adaptercore.py
[src/platforms/qwen/core/constants.py] BASE_URL/USER_AGENT 从 shared.py 集中至此
[src/platforms/qwen/core/shared.py] 改为从 .constants 导入并 re-export
[src/platforms/qwen/adapter.py] 门面 re-export 更新
[src/platforms/qwen/util.py] 懒加载引用更新
[src/platforms/qwen/__init__.py] 导出更新
[template/template_config.toml] 版本 2.2.48 → 2.2.49
[README.md] 版本徽章和路线图更新为 2.2.49
[docs-src/agents.md] 更新命名陷阱和导入链引用（adapter_impl → adaptercore, models_cache → modelcache）
[docs-src/src/agents.md] 更新 models_cache WARNING 章节
[docs-src/src/platforms/agents.md] 更新 CRITICAL 章节中的文件名引用
[docs-src/src/platforms/guide.md] 更新命名表和依赖图中的 impl → adaptercore 引用
[docs-src/src/platforms/deepseek/core/deepseek.md] 更新架构图和关键文件表中的文件名引用
[docs-src/src/platforms/ollama/core/ollama.md] 更新架构图和关键文件表中的文件名引用
[docs-src/src/platforms/qwen/core/qwen.md] 更新架构图和关键文件表中的文件名引用
[docs-src/platforms/deepseek/core/deepseek.md] 同步更新（镜像副本）
[docs-src/platforms/ollama/core/ollama.md] 同步更新（镜像副本）
[docs-src/platforms/qwen/core/qwen.md] 同步更新（镜像副本）
[docs-src/platforms/guide.md] 同步更新（镜像副本）
[tests/src/platforms/qwen/test_qwen37max_protocols.py] 修复 import 路径 core.impl → core.adaptercore

py_compile: all platform files compiled successfully
pytest: 531 passed, 16 skipped, 3 warnings

2026-06-07 00:08:00

[src/core/fncall/prompt/templates.py] 新增 _HISTORY_CLARIFY_EN/ZH 双语常量，用于在 conversation_history 开头注入澄清文本
[src/core/fncall/prompt/history.py] 新增 _TOOL_CALL_MARKER_RE 正则；is_webui=True 时若 assistant content 已含工具调用标记则跳过重复渲染
[src/core/fncall/protocols/antml.py] render_prompt 在 conversation_history 内前置历史澄清文本
[src/core/fncall/protocols/bracket.py] render_prompt 在 conversation_history 内前置历史澄清文本
[src/core/fncall/protocols/nous.py] render_prompt 在 conversation_history 内前置历史澄清文本
[src/core/fncall/protocols/original.py] render_prompt 在历史段落前置澄清文本
[src/core/fncall/protocols/xml.py] render_prompt 在 conversation_history 内前置历史澄清文本
[template/template_config.toml] 版本 2.2.49 → 2.2.50
[config.toml] 版本跟随模板 2.2.49 → 2.2.50
[README.md] 版本徽章和路线图更新为 2.2.50
[.agents/provider-guide/SKILL.md] 版本字段 2.2.49 → 2.2.50

py_compile: all changed files compiled successfully
pytest: 531 passed, 16 skipped, 3 warnings

2026-06-07 00:15:00

[src/core/fncall/prompt/templates.py] 澄清文本措辞修正："当前任务"→"用户发送的最新消息"，消除 LLM 将历史任务与当前指令混淆的歧义

py_compile: templates.py compiled successfully
pytest: 148 passed (fncall tests)

2026-06-07 00:22:00

[src/webui/static/js/chat.js] 修复助手消息重试按钮导致用户消息重复的 bug：统一助手/用户重试路径，均从用户消息开始删除 DOM 和历史，由 sendChatMessage 统一重新添加
[template/template_config.toml] 版本 2.2.50 → 2.2.51
[config.toml] 版本跟随模板 2.2.50 → 2.2.51
[README.md] 版本徽章和路线图更新为 2.2.51
[.agents/provider-guide/SKILL.md] 版本字段 2.2.50 → 2.2.51

pytest: 531 passed, 16 skipped, 3 warnings

2026-06-07 01:00:00

[src/platforms/ollama/core/adaptercore.py] 新增 create_embedding() 方法，委托给 OllamaClient，附带未初始化状态守卫
[src/platforms/ollama/core/client.py] 新增 create_embedding() 方法调用 /api/embed；修复 _verify_server() 处理完整 URL 格式的 bug（http://或https://前缀不再重复添加）；增强 detect_capabilities() embedding 模型名称关键词检测（bge/nomic/text2vec/e5-/gte-/sentence/embed）
[src/platforms/ollama/core/constants.py] 新增 EMBED_PATH="/api/embed" 常量；CAPS 添加 "embedding": True 能力声明
[main.py] Runner 根据 config.toml debug.color 决定 CLICOLOR_FORCE/NO_COLOR 环境变量
[src/logger.py] set_color() 支持 handler 重建：更新 _color_override 后移除旧 console handler 并重新添加，使颜色变更立即生效
[template/template_config.toml] 版本 2.2.51 → 2.2.52
[config.toml] 版本跟随模板 2.2.51 → 2.2.52、proxy_enabled=true
[README.md] 版本徽章更新为 2.2.52；路线图新增 v2.2.52 已完成条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.51 → 2.2.52
[docs-src/src/platforms/ollama/core/ollama.md] 更新文档：新增 embedding 支持说明、服务器地址处理、能力检测详情、向量嵌入请求流程
[tests/src/platforms/ollama/test_ollama_embedding.py] 新增：detect_capabilities embedding 检测、_verify_server URL 格式、常量验证、adapter embedding 方法测试
[tests/src/test_logger.py] 新增：set_color() handler 重建测试

py_compile: all changed files compiled successfully
pytest: 554 passed, 16 skipped, 3 warnings

2026-06-07 02:00:00

[src/core/server/proxy.py] 新增 _LOCAL_HOSTS 正则，localhost 和 *.localhost 跳过代理直连。修复启用全局代理后本地 Ollama 服务器无法被发现的问题
[src/logger.py] _setup_handlers() 中尽早通过 tomllib 读取 config.toml 的 debug.color，确保首行日志就尊重 color=false 设置
[src/platforms/ollama/core/constants.py] 新增 DYNAMIC_DISCOVERY 常量，控制动态服务器发现开关
[src/platforms/ollama/core/client.py] DYNAMIC_DISCOVERY 为 False 时跳过网络服务器发现和定时刷新，仅使用持久化缓存
[template/template_config.toml] 版本 2.2.52 → 2.2.53
[config.toml] 版本跟随模板 2.2.52 → 2.2.53
[README.md] 版本徽章更新为 2.2.53；路线图新增 v2.2.53 三项改动说明
[.agents/provider-guide/SKILL.md] 版本字段 2.2.52 → 2.2.53

2026-06-07 03:00:00

[src/platforms/ollama/core/constants.py] DYNAMIC_DISCOVERY 从 True 改为 False，关闭 Ollama 动态服务器发现，仅使用持久化缓存
[template/template_config.toml] 版本 2.2.53 → 2.2.54
[config.toml] 版本跟随模板 2.2.53 → 2.2.54
[README.md] 版本徽章更新为 2.2.54；路线图新增 v2.2.54 条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.53 → 2.2.54

2026-06-07 04:00:00

[src/platforms/ollama/core/client.py] candidates() 添加运行时模型名关键词检测（bge/nomic/text2vec/e5-/gte-/sentence/embed），覆盖缓存中过期的 embedding=false；collect_servers() 添加 skip_network 参数跳过网络抓取仅验证 additional 列表；_do_refresh() 传递 skip_network 参数；background_setup() DYNAMIC_DISCOVERY=False 时仍验证 ACCOUNTS 本地服务器
[template/template_config.toml] 版本 2.2.54 → 2.2.55
[config.toml] 版本跟随模板 2.2.54 → 2.2.55
[README.md] 版本徽章更新为 2.2.55；路线图新增 v2.2.55 条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.54 → 2.2.55

py_compile: src/platforms/ollama/core/client.py compiled successfully
pytest: (pending)

2026-06-07 05:00:00

[src/platforms/ollama/core/client.py] background_setup() 在 DYNAMIC_DISCOVERY=False 时直接 return，不再调用 _do_refresh(force=True) 覆盖持久化缓存（此前 force=True + skip_network=True 会将缓存清空为 0 服务器）
[src/platforms/ollama/core/constants.py] DYNAMIC_DISCOVERY 临时恢复为 True 以重建被清空的缓存
[src/platforms/ollama/core/client.py] collect_servers() 的 skip_network 参数保留供未来使用
[template/template_config.toml] 版本 2.2.55 → 2.2.56
[config.toml] 版本跟随模板 2.2.55 → 2.2.56
[README.md] 版本徽章更新为 2.2.56；路线图新增 v2.2.56 条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.55 → 2.2.56

2026-06-07 06:00:00

[src/platforms/ollama/core/constants.py] DYNAMIC_DISCOVERY 从 True 改回 False；缓存已重建完成（480 台服务器），关闭动态发现，使用持久化缓存工作
[template/template_config.toml] 版本 2.2.56 → 2.2.57
[config.toml] 版本跟随模板 2.2.56 → 2.2.57
[README.md] 版本徽章更新为 2.2.57；路线图新增 v2.2.57 条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.56 → 2.2.57

2026-06-07 08:00:00

[src/routes/openai.py] create_embeddings() 改用 get_candidates(model=, capability="embedding") 双重过滤，优先选择有请求模型的服务器；找不到时回退到仅 capability 过滤。此前只按 embedding 能力选择，导致请求路由到没有该模型的服务器返回 404 "model not found"
[template/template_config.toml] 版本 2.2.57 → 2.2.58
[config.toml] 版本跟随模板 2.2.57 → 2.2.58
[README.md] 版本徽章更新为 2.2.58；路线图新增 v2.2.58 条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.57 → 2.2.58

2026-06-07 09:00:00

[src/core/dispatch/gateway.py] dispatch() 无 tools 时统一处理 system 消息：将所有 role=system 消息内容折叠到第一条 user 消息中，确保所有平台（包括不原生支持 system role 的平台如 Qwen）都能收到系统指令。有 tools 时由 inject_fncall 处理（现有逻辑不变）
[template/template_config.toml] 版本 2.2.58 → 2.2.59
[config.toml] 版本跟随模板 2.2.58 → 2.2.59
[README.md] 版本徽章更新为 2.2.59；路线图新增 v2.2.59 条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.58 → 2.2.59

2026-06-07 10:00:00

[src/core/fncall/prompt/history.py] _format_conversation_history() 修复：role="tool" 消息现在仅在 is_webui=True 时渲染（此前始终渲染），非 WebUI 客户端（API/CLI）不再在 prompt 中注入工具调用历史；非 WebUI 时 assistant 消息若只有 tool_calls 无文本内容则跳过整个空 <assistant> 块
[template/template_config.toml] 版本 2.2.59 → 2.2.60
[config.toml] 版本跟随模板 2.2.59 → 2.2.60
[README.md] 版本徽章更新为 2.2.60；路线图新增 v2.2.60 条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.59 → 2.2.60

2026-06-07 11:00:00

[src/core/fncall/prompt/history.py] _format_conversation_history() 修正：移除 is_webui 检测逻辑，始终渲染 assistant tool_calls 和 tool results，所有协议所有客户端统一处理；跳过无内容的空 assistant 块（此前版本错误地添加了 is_webui 条件，现回退并统一渲染）
[tests/src/core/test_tools.py] 修正测试断言：tool_calls 和 tool results 现在始终渲染，移除 "Non-WebUI → NOT rendered" 相关断言
[README.md] 修正 v2.2.60 路线图描述，准确反映 is_webui 移除而非添加

2026-06-13 08:00:00

[src/core/dispatch/selector.py] TAS 候选项自动调优重构：替换 CandidateStats+Beta 分布为 TASRecord（5 个核心变量：error_time/last_call/ema_speed/ema_latency/n_fails），新增 TASWeights 自适应权重（5 维，乘法更新+归一化），持久化到 persist/gateway/ JSON 文件，评分公式改为 5 维自适应 sigmoid 归一化，连续失败次数 n_fails 纳入评分维度（越多惩罚越重，上限 10）
[src/core/dispatch/candidate.py] make_id() 改为确定性 SHA-256 哈希（传入 resource_id 时），重启后 ID 不变
[src/core/dispatch/gateway.py] _single()/_rec() 新增 generation_dur（排除 TTFT 的纯生成时长）和 completion_tokens（上游实际 token 数）传递
[src/core/dispatch/registry.py] Selector 初始化传入 persist_dir 路径
[src/platforms/apiairforce/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/caiyuesbk/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/cerebras/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/chatmoe/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/chutes/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/codebuddy/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/cursor/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/deepseek/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/edgetts/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/gtts/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/n1n/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/nvidia/core/client.py] make_id() 补充 resource_id 参数（2 处）
[src/platforms/ollama/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/openaifm/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/openrouter/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/perplexity/core/client.py] make_id() 补充 resource_id 参数
[src/platforms/qwen/core/client.py] make_id() 补充 resource_id 参数
[tests/src/core/dispatch/test_selector.py] 重写测试：TASRecord/TASWeights 替代 CandidateStats，新增 n_fails 评分测试、持久化测试、5 维权重归一化测试
[tests/src/core/dispatch/test_candidate.py] 新增 make_id 确定性哈希测试（deterministic/different_resource_ids/fallback）
[config.toml] 版本 2.2.60 → 2.2.61
[template/template_config.toml] 版本 2.2.60 → 2.2.61
[README.md] 版本徽章更新为 2.2.61；路线图新增 v2.2.61 条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.60 → 2.2.61
验证: py_compile 全部通过; pytest 560 passed, 16 skipped, 3 warnings

2026-06-13

[src/core/fncall/prompt/inject.py] inject_fncall() 新增 dump_prompt: bool = True 参数，为 False 时跳过 _maybe_dump_prompt()，避免并发竞速模式下重复写入 prompt 文件
[src/core/dispatch/gateway.py] _race() 在 worker 启动前统一调用一次 inject_fncall(dump_prompt=True) 转储 prompt，worker 内部 _w() 传 dump_prompt=False 抑制重复写入
[template/template_config.toml] 版本 2.2.61 → 2.2.62
[config.toml] 同步版本 2.2.62
[README.md] 版本徽章和路线图更新为 2.2.62
[.agents/provider-guide/SKILL.md] 版本字段 2.2.61 → 2.2.62
验证: py_compile 全部通过; pytest 560 passed, 16 skipped, 3 warnings

2026-06-13 10:23:00

[src/platforms/noobkeys/__init__.py] 新增 noobkeys 平台包：导出 NoobKeysAdapter / Adapter
[src/platforms/noobkeys/adapter.py] 平台门面：从 util 重导出 Adapter 类
[src/platforms/noobkeys/util.py] 懒加载门面：__getattr__ 延迟导入 core.adaptercore，re-export 常量与纯函数
[src/platforms/noobkeys/core/__init__.py] core 子包初始化
[src/platforms/noobkeys/core/adaptercore.py] NoobKeysAdapter 实现：init() 立即返回、后台完成模型拉取；complete() 透传 thinking/search 不进入 HTTP 请求体
[src/platforms/noobkeys/core/client.py] HTTP 客户端：Bearer 鉴权、指数退避重试、按上游错误消息分类处理（鉴权失败/余额不足/限速/5xx）；流式与非流式统一产出 thinking/content/usage
[src/platforms/noobkeys/core/constants.py] 平台常量：BASE_URL、CHAT_PATH、9 个模型、纯文本能力（chat=True 其余 False）、关闭远程模型拉取
[src/platforms/noobkeys/core/headers.py] 请求头构造：Content-Type + Bearer
[src/platforms/noobkeys/core/payloads.py] 请求体构造：model/messages/stream + temperature/top_p/max_tokens/stop
[src/platforms/noobkeys/core/sse.py] SSE 解析：支持 delta.reasoning 与 delta.reasoning_content 两种 reasoning 字段
[docs-src/src/platforms/noobkeys/INDEX.md] 新增 noobkeys 平台文档：能力、模型列表、reasoning 处理、错误分类、维护提示
[tests/src/platforms/noobkeys/__init__.py] 新增 noobkeys 测试包
[tests/src/platforms/noobkeys/test_noobkeys_mvp.py] 新增 noobkeys MVP 契约测试
[template/template_config.toml] 版本 2.2.62 → 2.2.63
[config.toml] 同步版本 2.2.63
[README.md] 版本徽章更新为 2.2.63；platforms 徽章 11+ → 12+；已支持平台表新增 NoobKeys；路线图新增 v2.2.63 条目
[.agents/provider-guide/SKILL.md] 版本字段 2.2.62 → 2.2.63
验证: py_compile 全部通过; pytest 561 passed, 16 skipped, 3 warnings

2026-06-13 16:00:00

[src/logger.py] 新增 _resolve_log_name() 函数，日志文件名和默认 module_name 改为从 config.toml 的 debug.log_name 读取
[config.toml] [debug] 新增 log_name 配置项；修复损坏的重复 [debug] 段落；版本 2.2.63 → 2.2.64
[template/template_config.toml] 同步新增 log_name 配置项；版本 2.2.63 → 2.2.64
[README.md] 版本徽章和路线图更新为 2.2.64
[.agents/provider-guide/SKILL.md] 版本字段 2.2.63 → 2.2.64
验证: py_compile 通过; pytest tests/src/test_logger.py 3 passed
