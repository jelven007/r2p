# r2p — Rust / Python 互操作工程

`r2p` 是基于 PyO3 的 Rust/Python 互操作工程，提供类型转换、安全对象访问、原生扩展和解释器嵌入能力。
SDK 内核、包名和宏属性统一为 `r2p`，产品元数据见 [product.toml](product.toml)。
当前交付仓库为 `jelven007/r2p`，按已验证的固定 Git SHA 消费。
已有本地回归、候选消费和性能样本；结果限定各自源码与环境，见[当前结构化证据](docs/testing/evidence-summary.md)。
固定实施提交 `b04b79e7` 的候选/恢复、GIL/FT、内省和本机 CLI 验收通过，见[本机报告](docs/testing/reports/local-acceptance-2026-10-25.md)。
当前优化分支的最终 SHA 完整远端验收仍待完成，进度见[持续优化记录](docs/governance/optimization-continuation-2026-10-25.md)。

| 项目 | 基线 |
| --- | --- |
| 产品名称 | `r2p` |
| 交付仓库 | <https://github.com/jelven007/r2p> |
| 技术来源基线 | `424149e8a1c42128b05a090941673008fc46c478`，保留 PyO3 祖先历史 |
| 提交时间 / 分析日期 | 2026-10-23 11:42:30 UTC / 2026-10-24 |
| Rust 包名 / 版本声明 | `r2p` / `0.30.0`，声明不等于本仓库已发布版本 |
| Rust 要求 | 1.85+，Edition 2024 |
| Python | 源码声明 CPython 3.9–3.15；本地已测 3.14.9，见[支持矩阵](docs/testing/support-matrix.md) |
| 恢复点 | [两个历史版本](docs/releases/history.json)，完整 Git 历史保留 |
| 许可 | MIT OR Apache-2.0；保留 PyO3 作者和许可 |

## 项目能力

- Python 调用 Rust：`#[pymodule]`、`#[pyfunction]`、`#[pyclass]`、`#[pymethods]` 创建原生扩展。
- Rust 调用 Python：`Python::attach`、对象调用和解释器初始化支持嵌入。
- 语言边界：`Py<T>`、`Bound<'py, T>`、转换 trait、异常处理和引用计数管理。
- 构建与兼容：FFI、解释器探测、`abi3` / `abi3t`、跨平台构建和可选功能。
- 工程能力：Rust / Python 测试、编译诊断测试、性能基准、类型 stub 内省与用户指南。

当前源码没有定义 HTTP 服务、业务数据库或业务页面。
新生产系统的本期范围为 Rust/Python SDK 的研发、验证、源码交付与支持流程。
详见[项目分析](docs/governance/project-assessment.md)和[需求规格](docs/requirements/system-requirements.md)。

## 目录

```text
r2p/
├── product.toml             # 产品身份、实现包与源码来源
├── Cargo.toml, build.rs      # 主 r2p 包和工作区
├── Cargo.lock, uv.lock       # 已跟踪的工程依赖解析
├── src/                     # 核心安全 API、类型、转换与运行时实现
├── crates/                  # FFI、构建配置、过程宏、内省组件
├── python/                  # Python runtime 预留目录，尚无独立运行时功能
├── tests/                   # Rust 集成测试、UI 测试、python/ 跨语言测试
├── benchmarks/              # 隔离工作区中的性能基准
├── examples/                # 扩展、嵌入、打包示例和模板
├── tools/                   # FFI 校验、Maturin 私有适配和一致性检查
├── infrastructure/          # WebAssembly 构建、Netlify 资源
├── assets/                  # 编译示例资源和品牌素材
├── docs/                    # requirements / architecture / development / testing
│                            # operations / runbooks / releases / governance / guide
├── .github/                 # 平台要求的工作流、Actions、问题模板
└── newsfragments/           # 发行说明片段
```

目录迁移、路径依赖和保留标准入口的依据见[目录规范](docs/development/repository-layout.md)。

## 开发入口

安装 Rust 1.85+、Python、uv；Nox 工程工具默认使用 Python 3.14，与 SDK 支持的最低 Python 版本分开管理。
从仓库根目录运行：

```bash
cargo metadata --no-deps --format-version 1
cargo check -p r2p --locked
cargo test -p r2p --lib --locked
python tools/dev.py --target-python <目标解释器路径> -- -s repository-check
python tools/dev.py --target-python <目标解释器路径> -- -s test-rust -- skip-full
python tools/dev.py --target-python <目标解释器路径> -- -s test-py
```

指南构建还需要 mdBook 和 mdbook-tabs。
配置、测试分层、编译诊断测试所需的 `rust-src`、完整验证命令见[开发指南](docs/development/developer-guide.md)和[测试策略](docs/testing/test-strategy.md)。

## 文档入口

完整索引：[docs/README.md](docs/README.md)。

| 工作 | 入口 |
| --- | --- |
| 项目背景与证据 | [项目分析](docs/governance/project-assessment.md) |
| 需求和验收 | [需求规格](docs/requirements/system-requirements.md)、[追踪矩阵](docs/requirements/traceability.csv) |
| 技术方案 | [总体架构](docs/architecture/system-design.md)、[接口与兼容性](docs/architecture/interfaces-and-compatibility.md) |
| 开发与目录 | [开发指南](docs/development/developer-guide.md)、[目录规范](docs/development/repository-layout.md) |
| 测试与本次验证 | [测试策略](docs/testing/test-strategy.md)、[支持矩阵](docs/testing/support-matrix.md)、[当前证据](docs/testing/evidence-summary.md)、[环境修正](docs/testing/reports/evidence-environment-2026-10-25.md) |
| 运营 | [运营方案](docs/operations/operating-plan.md)、[支持政策](docs/operations/support-policy.md) |
| 运维与发布 | [故障手册](docs/runbooks/incident-response.md)、[发布与回退](docs/releases/release-and-rollback.md)、[版本政策](docs/releases/version-policy.md) |
| 计划与治理 | [交付计划](docs/governance/delivery-plan.md)、[文档治理](docs/governance/document-management.md) |
| r2p 使用资料 | [SDK 入门](docs/sdk/README.md)、[用户指南](docs/guide/src/SUMMARY.md)、[内核迁移](docs/development/kernel-namespace-migration.md) |

## 来源和贡献

SDK 技术标识已迁移为 `r2p`；上游历史、版权与许可证按来源保留。
官方 PyO3 网站、徽章、包索引页面属于上游资料，不代表 `r2p` 已独立运营这些资源。
源码交付和两个历史快照按[交付记录](docs/releases/records/2026-10-24-production-baseline.md)追溯。
注册表和站点发行尚未启用；问题通过 [Issues](https://github.com/jelven007/r2p/issues/new/choose) 反馈，修复通过 [PR](https://github.com/jelven007/r2p/pulls) 提交，按[支持政策](docs/operations/support-policy.md)尽力维护。

本仓库协作方式见 [Contributing.md](Contributing.md)，行为规范见 [Code-of-Conduct.md](Code-of-Conduct.md)，历史发布说明见 [CHANGELOG.md](CHANGELOG.md)。
