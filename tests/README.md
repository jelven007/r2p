# 测试目录

| 位置 | 用途 |
| --- | --- |
| 根 `tests/*.rs` | Cargo 自动发现的主库集成测试 |
| `ui/` | 非法声明、宏和借用约束的编译诊断；`ui/base/` 为依赖基座 |
| `python/` | 跨语言测试扩展、pytest、属性测试、内省 stub |

主库单元测试随实现位于 `src/`，组件测试随 crate 维护，消费方测试随 `examples/` 维护。
不要将根 Rust 测试再移一层而破坏 Cargo 默认发现。

从根执行 `uv run --isolated --only-group nox nox -s test-rust test-py`。
UI 严格测试需要匹配 Rust 工具链和 rust-src；ignore/skip 模式需明确报告。

入口：[测试策略](../docs/testing/test-strategy.md)、[实际验证](../docs/testing/reports/production-baseline-validation.md)、[开发命令](../docs/development/developer-guide.md)。
