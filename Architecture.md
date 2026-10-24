# r2p 项目架构入口

r2p 当前是基于 r2p 的 Rust/Python 互操作工程。
运行时核心在 `src/`，FFI、构建配置、过程宏和内省在 `crates/`；Python 产品包、测试、基准、工具和平台资源按职责组织。

| 阅读目标 | 当前文档 |
| --- | --- |
| 理解代码与边界 | [项目分析](docs/governance/project-assessment.md) |
| 组件与调用链路 | [总体技术方案](docs/architecture/system-design.md) |
| API/ABI、错误、线程和支持矩阵 | [接口与兼容性](docs/architecture/interfaces-and-compatibility.md) |
| 文件放置和迁移影响 | [目录规范](docs/development/repository-layout.md) |
| 目录与产品身份决策 | [ADR-0001](docs/architecture/adr/0001-repository-layout.md)、[ADR-0002](docs/architecture/adr/0002-product-and-release-boundaries.md) |

拉取时的原架构说明保留在[上游架构快照](docs/reference/upstream-architecture.md)。
完整研发资料见[文档中心](docs/README.md)。
