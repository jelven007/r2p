# r2p 工程文档中心

文档基线：2026-10-24；源码基线：`424149e8a1c42128b05a090941673008fc46c478`。
产品名称为 `r2p`，统一元数据见 [product.toml](../product.toml)。
适用范围为当前 Rust/Python 互操作 SDK，以及在其基础上建立的生产研发和交付流程。

## 阅读路径

首次接手：项目分析 → 需求 → 总体方案 → 开发指南 → 测试策略 → 运维手册。
参与特定阶段时使用下面的索引。

| 阶段 | 文档 | 回答的问题 |
| --- | --- | --- |
| 分析 | [项目分析与现状](governance/project-assessment.md) | 现有代码是什么、证据在哪里、缺口是什么 |
| 优化 | [全面优化评估与建议](governance/optimization-assessment.md) | 下一步优先改什么、收益与完成条件是什么 |
| 需求 | [系统需求规格](requirements/system-requirements.md) | 服务谁、实现什么、如何验收 |
| 需求追踪 | [追踪矩阵 CSV](requirements/traceability.csv) | 需求对应哪段实现、哪个测试、哪个准入条件 |
| 方案 | [总体技术方案](architecture/system-design.md) | 组件如何协作、关键边界及风险是什么 |
| 接口 | [接口与兼容性](architecture/interfaces-and-compatibility.md) | API、ABI、错误、并发和版本如何约束 |
| 决策 | [ADR-0001：目录与工作区](architecture/adr/0001-repository-layout.md) | 为什么采用当前结构 |
| 决策 | [ADR-0002：产品与发布边界](architecture/adr/0002-product-and-release-boundaries.md) | 上游代码与本仓库产品如何区分 |
| 开发 | [开发指南](development/developer-guide.md) | 环境、命令、编码、变更流程 |
| 目录 | [目录规范与迁移映射](development/repository-layout.md) | 文件放在哪里、移动后有哪些依赖 |
| 测试 | [测试策略](testing/test-strategy.md) | 分层、用例、矩阵、缺陷及准入 |
| 验证 | [本次验证报告](testing/validation-report.md) | 本次实际执行了什么、结果和限制是什么 |
| CI 修正 | [MSRV 与汇总验证](testing/ci-fixes-validation.md) | 工具链和门禁修正了什么、有哪些运行证据 |
| SDK 内核迁移 | [迁移规则](development/kernel-namespace-migration.md)、[验证报告](testing/kernel-migration-validation.md) | crate、宏、构建变量、Python 模块与打包如何迁移到 r2p |
| 运营 | [运营计划](operations/operating-plan.md) | 采用、反馈、支持、指标如何形成闭环 |
| 运维 | [运维操作手册](maintenance/runbook.md) | 构建、监控、告警、故障和恢复 |
| 发布 | [发布与回退](maintenance/release-and-rollback.md) | 怎样交付、验证、停止、恢复 |
| 计划 | [交付计划和风险](governance/delivery-plan.md) | 任务、依赖、责任、完成条件 |
| 治理 | [文档治理](governance/document-management.md) | 状态、审批、更新、证据与唯一来源 |
| 模板 | [变更与发布记录](governance/change-record-template.md) | 如何记录下一次变更和验收 |
| 用户资料 | [r2p 用户指南](guide/src/SUMMARY.md) | 如何使用现有库 |
| 历史参考 | [上游参考说明](reference/README.md) | 哪些资料保留原文、如何判断适用性 |

## 状态约定

所有工程文档遵循同一套状态语言：

- **已实现**：能在当前源码定位对应能力，仍需关注测试覆盖和平台条件。
- **本次已落地**：本地已有目录、配置、脚本或文档变更；不代表已提交、远端合并或部署。
- **拟定要求**：生产开发和验收的目标，尚未证明全部满足。
- **待确认**：需要产品或负责人确认的范围、权限、预算或指标。
- **已验证**：有[验证报告](testing/validation-report.md)中的命令和结果支持；不得用静态检查替代运行验证。

文档里的责任人为角色，实际人员尚未分配。
SLO、支持期限和性能门槛是拟定目标，确定后才构成外部承诺。
官方 r2p 的发行、包索引、社区和站点是参考来源。

## 维护原则

产品名称以 [product.toml](../product.toml) 为准；需求编号以[需求规格](requirements/system-requirements.md)为准；路径以[目录规范](development/repository-layout.md)为准；测试执行结果以[验证报告](testing/validation-report.md)为准；发布决策以发布记录为准。
同一变更应在代码、方案、测试和运营/运维说明中同步体现。

文档和 Cargo 路径检查：

```bash
python tools/check_repository.py
uv run --isolated --only-group nox nox -s rumdl
```

第一条需要 Python 3.11+。
检查验证本地目标文件存在；外部网址、Markdown 锚点语义、内容正确性和生产就绪程度需要另外评估。
