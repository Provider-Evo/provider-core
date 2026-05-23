# tests 索引

## 运行方式

- `pytest tests -q`
- `pytest tests/src/core -q`
- `pytest tests/src/platforms/<platform> -q`

## 目录说明

- `conftest.py`：统一注入项目根目录。
- `helpers/`：平台契约测试辅助函数。
- `src/core/`：核心复用逻辑测试。
- `src/platforms/`：平台 MVP 测试与特定平台测试。

## 跳过规则

- 第三方依赖缺失、远程 API 不可用、账号密钥失效时允许跳过。
- 跳过应使用 pytest.skip，并给出明确原因。
