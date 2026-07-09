# chutes 平台文档

## 目录职责

- `adapter.py`：平台门面导出。
- `accounts.py`：平台部署配置。
- `util.py`：稳定导出与懒加载门面。
- `core/`：平台具体实现。

## 测试入口

- 对应 MVP 测试位于 `tests/src/platforms/chutes/test_chutes_mvp.py`。

## 维护提示

- 修改前先对照 `docs-src/src/platforms/guide.md`。
- 如果平台依赖第三方 API，失败原因应记录到 `RECORD.md`。
