# ADR-0001：生产研发目录与工作区

日期：2026-10-24。
状态：本次已实施的工程决策。
适用：FR-008、NFR-006。

## 背景

原仓库将多个 crate、Python 包、跨语言测试、基准、FFI 工具和指南直接放在根层。
目录变更会影响 Cargo 依赖、宏/文档 include、Nox 和 CI。
需要明确责任，也需要控制迁移范围。

## 决策

采用主 Cargo 包兼工作区的结构。
保留根 `Cargo.toml`、`build.rs`、`src/` 和 Rust `tests/`；辅助 crate 移入 `crates/`；Python 包移入 `python/`；Python 测试移入 `tests/python/`；基准和 FFI 校验分别移入 `benchmarks/`、`tools/`；指南与工程资料统一为 `docs/`；构建/部署资源移入 `infrastructure/`。

基准与 FFI 校验保留独立 workspace，避免其依赖改变主库的 MSRV 测试条件。
`.github/`、根配置、许可证和 `newsfragments/` 维持工具约定位置。
示例保留原相对布局及生成模板。

## 选项评估

| 选项 | 优点 | 代价 | 结果 |
| --- | --- | --- | --- |
| 原布局加文档 | 路径变化最少 | 根层职责仍散布 | 未采用 |
| 主根包 + 辅助目录分组 | 标准入口稳定、责任明确、迁移可检查 | 辅助组件路径需要联动 | 采用 |
| 全部 crate 包括核心移入 crates，根虚拟 workspace | 完全统一 crate 布局 | 扩大核心测试、资源和发布路径变更 | 后续有真实需要再评估 |
| 预建多服务应用目录 | 可容纳未来业务 | 当前无业务契约和服务代码支撑 | 不作为本期结构 |

## 后果

目录语义更清晰；主库使用方式保持标准。
维护者需要遵循[目录规范](../../development/repository-layout.md)，新增路径用一致性检查、Cargo metadata 和实际构建验证。
后续同步上游时需将原路径应用到新的映射。

上游 README 归档在 `docs/reference/` 并继续用于 crate README 和 doctest；根 README 服务本仓库导航。
用户指南保留上游使用内容，工程文档单独管理状态。

## 验证

检查主/隔离 workspace、Python 扩展、doctest、指南 include、CI 工作目录、过滤器/缓存、Dependabot 和制品内容。
实际结果见[验证报告](../../testing/validation-report.md)。
本地目录实施不等于远端合并或已上线。
