# 旧 .scripts/AGENTS 迁移说明

原 `.scripts/AGENTS.md` 的用途是提醒维护者：

- `.scripts/` 是隐藏目录。
- 目录下的脚本是开发与打包工具，不是应用运行入口。
- 不要误以为包含 `main()` 的脚本都可以当作服务入口运行。

当前该说明已迁移到 skill 参考资料中，`.scripts/` 目录本身只保留 `warp.py`。
