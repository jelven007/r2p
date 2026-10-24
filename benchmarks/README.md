# 性能基准

`r2p-benches/` 是独立 Cargo workspace，避免基准依赖影响主库 MSRV 解析。
现有基准覆盖附着、函数调用、容器、转换、错误和类。

从根运行 `uv run --isolated --only-group nox nox -s bench`；Python 基准位于 `tests/python/` 的 Nox bench 会话。

比较必须固定硬件、OS、Rust/Python、GIL/ABI、features、依赖、release 优化和负载，至少保存三次样本、中位数和波动。
拟定 5% 退化阈值触发分析，不能将一次样本作为验收结论。

要求见[测试策略](../docs/testing/test-strategy.md)和[需求规格](../docs/requirements/system-requirements.md)。
