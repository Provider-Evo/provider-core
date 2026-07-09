# tests/src/core/dispatch 索引

调度模块测试目录。

## 文件列表

- `test_selector.py`：Selector 类的单元测试
- `test_gateway.py`：Gateway 类的单元测试
- `test_registry.py`：Registry 类的单元测试
- `test_candidate.py`：Candidate 相关测试

## 测试覆盖

### test_selector.py

测试 `Selector` 类的核心功能：
- 候选者评分逻辑
- 冷却机制（错误触发冷却）
- 失败惩罚
- 过期清理
- 持久化刷新

### test_gateway.py

测试 `Gateway` 类的功能：
- 请求路由
- 候选者选择
- 并发控制

## 运行测试

```bash
# 运行所有调度测试
pytest tests/src/core/dispatch/ -v

# 运行特定测试文件
pytest tests/src/core/dispatch/test_selector.py -v
```