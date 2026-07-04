/d/Project/provider-self
src/logger.py
template/template_config.toml
config/main_config.toml
README.md
.agents/provider-guide/SKILL.md
src/webui/static/terminal/terminal.js
src/webui/app.py
src/webui/routers/admin.py
src/webui/routers/files.py
src/webui/static/core/state.js
src/webui/static/index.html
src/webui/static/ui/bootstrap.js
src/paths.py
main.py
src/platforms/apiairforce/core/sse.py
src/platforms/caiyuesbk/core/sse.py
src/webui/static/ui/styles.css

2026-07-04 22:30:00
[src/logger.py] 日志文件命名分隔符从下划线改为连字符
[template/template_config.toml] 版本号更新至 2.2.239
[config/main_config.toml] 版本号同步更新至 2.2.239
[README.md] 版本徽章和路线图版本号更新至 2.2.239
[.agents/provider-guide/SKILL.md] 版本字段更新至 2.2.239

2026-07-04 22:35:00
[src/webui/static/core/state.js] 日志面板虚拟滚动，优化大量日志条目时的渲染性能

2026-07-04 23:00:00
[src/webui/static/terminal/terminal.js] 修复终端输出不实时显示，添加 xterm.refresh() 强制刷新视口
[template/template_config.toml] 版本号更新至 2.2.240
[config/main_config.toml] 版本号同步更新至 2.2.240
[README.md] 版本徽章和路线图版本号更新至 2.2.240
[.agents/provider-guide/SKILL.md] 版本字段更新至 2.2.240

2026-07-04 23:30:00
[src/paths.py] 新增集中路径管理模块，提供 project_root/config_dir/persist_dir
[src/webui/routers/admin.py] 重构路径硬编码为 src.paths 调用，提取 _validate_filename 校验函数
[src/webui/routers/files.py] 重构路径硬编码为 src.paths.project_root 导入
[src/webui/app.py] 添加 asyncio 导入
[src/webui/static/core/state.js] 新增日志正则表达式搜索切换功能
[src/webui/static/index.html] 添加正则搜索按钮
[src/webui/static/ui/bootstrap.js] 绑定正则搜索按钮事件

2026-07-04 23:45:00
[src/core/config/manager.py] 重构路径硬编码为 src.paths.config_dir 调用
[src/core/models_cache.py] 重构路径硬编码为 src.paths.persist_dir 调用
[src/webui/services/stats.py] 重构路径硬编码为 src.paths.persist_json_dir 调用
[template/template_config.toml] 版本号更新至 2.2.242
[config/main_config.toml] 版本号同步更新至 2.2.242
[README.md] 版本徽章和路线图版本号更新至 2.2.242

2026-07-04 23:50:00
[main.py] WebUIWorker 不再占用独立端口，通过共享内存与 MainWorker 通信

2026-07-04 23:55:00
[src/platforms/apiairforce/core/sse.py] 重构为使用共享 SSE 解析模块
[src/platforms/caiyuesbk/core/sse.py] 重构为使用共享 SSE 解析模块
[src/webui/static/ui/styles.css] 更新 WebUI 样式
