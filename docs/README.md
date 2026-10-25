# r2p 工程文档中心

文档版本：2.0；日期：2026-10-24；技术来源基线：`424149e8a1c42128b05a090941673008fc46c478`。
当前源码交付仓库为 [jelven007/r2p](https://github.com/jelven007/r2p)，固定版本见[交付记录](releases/records/2026-10-24-production-baseline.md)。
产品名称为 `r2p`，统一元数据见 [product.toml](../product.toml)。
适用范围为当前 Rust/Python 互操作 SDK，以及在其基础上建立的生产研发和交付流程。

## 阅读路径

首次接手：项目分析 → 需求 → 总体方案 → 开发指南 → 测试策略 → 运维手册。
参与特定阶段时使用下面的索引。

| 阶段 | 文档 | 回答的问题 |
| --- | --- | --- |
| 分析 | [项目分析与现状](governance/project-assessment.md) | 现有代码是什么、证据在哪里、缺口是什么 |
| 当前复评 | [当前项目复评与下一阶段方案](governance/optimization-reassessment-2026-10-25.md) | 643b3204 上已完成什么、当前缺口和下一阶段投入是什么 |
| 持续优化 | [R-01–R-09 实施记录](governance/optimization-continuation-2026-10-25.md) | 复评后的真实实施、验证与剩余外部条件是什么 |
| 优化原方案 | [2026-10-25 初始优化方案](governance/optimization-plan-2026-10-25.md) | 初始 main 基线的工作包、优先级和验收要求是什么 |
| 优化实施 | [实施记录](governance/optimization-execution-2026-10-25.md)、[测试入口与环境验证](testing/reports/tooling-optimization-2026-10-25.md) | 哪些已实现和验证、哪些仍在执行 |
| 历史优化 | [初次优化评估与建议](governance/optimization-assessment.md) | 上一阶段发现了什么、哪些已经交付 |
| 需求 | [系统需求规格](requirements/system-requirements.md) | 服务谁、实现什么、如何验收 |
| 用户场景 | [采用与升级旅程](requirements/user-journeys.md) | 每条链路的输入、成功条件和失败处理 |
| 需求追踪 | [追踪矩阵 CSV](requirements/traceability.csv) | 需求对应哪段实现、哪个测试、哪个准入条件 |
| 方案 | [总体技术方案](architecture/system-design.md) | 组件如何协作、关键边界及风险是什么 |
| 接口 | [接口与兼容性](architecture/interfaces-and-compatibility.md) | API、ABI、错误、并发和版本如何约束 |
| 决策 | [ADR-0001：目录与工作区](architecture/adr/0001-repository-layout.md) | 为什么采用当前结构 |
| 决策 | [ADR-0002：产品与发布边界](architecture/adr/0002-product-and-release-boundaries.md) | 上游代码与本仓库产品如何区分 |
| 决策 | [ADR-0003：交付与历史](architecture/adr/0003-delivery-and-history.md) | 怎样合并、固定 SHA 和保留两个恢复点 |
| 开发 | [开发指南](development/developer-guide.md) | 环境、命令、编码、变更流程 |
| 目录 | [目录规范与迁移映射](development/repository-layout.md) | 文件放在哪里、移动后有哪些依赖 |
| 配置 | [构建配置注册表](development/configuration-reference.md) | 配置优先级、扩展/嵌入与跨编译条件 |
| 测试 | [测试策略](testing/test-strategy.md) | 分层、用例、矩阵、缺陷及准入 |
| 支持矩阵 | [兼容性证据与状态](testing/support-matrix.md) | 已配置、已编译、已运行和支持等级 |
| 当前验证 | [结构化摘要](testing/evidence-summary.md)、[实际环境与失败等级](testing/reports/evidence-environment-2026-10-25.md) | 各 SHA 实际执行了什么、结果和限制是什么 |
| 持续发行验证 | [跨版本恢复与上传续发](testing/reports/continuous-release-2026-10-25.md) | 各 SHA 版本、原始制品和本地 HTTP 失败恢复如何核验 |
| 工程与资源验证 | [Nox 拆分、保留和取回](testing/reports/nox-resources-2026-10-25.md) | 会话/命令契约和原始制品生命周期如何核验 |
| 性能与成本 | [两种工作量与扩大采样](testing/reports/performance-calibration-2026-10-25.md) | 本地测量说明什么、真实用户负载和连续 CI 成本还缺什么 |
| 上游运行时 | [历史 GC 修复映射与回归](testing/reports/upstream-runtime-2026-10-25.md) | 原始来源、上下文冲突和受控正负例如何复现 |
| 历史验证 | [生产工程基线](testing/reports/production-baseline-validation.md)、[原目录基线](testing/reports/validation-report.md)、[MSRV/汇总修正](testing/reports/ci-fixes-validation.md) | 保留各阶段的原始命令与结果 |
| SDK 内核迁移 | [迁移规则](development/kernel-namespace-migration.md)、[验证报告](testing/reports/kernel-migration-validation.md) | crate、宏、构建变量、Python 模块与打包如何迁移到 r2p |
| 运营 | [运营计划](operations/operating-plan.md) | 采用、反馈、支持、指标如何形成闭环 |
| 支持 | [支持政策](operations/support-policy.md) | 问题入口、维护边界和版本支持 |
| 运维 | [故障操作手册](runbooks/incident-response.md)、[环境与资产](runbooks/environments-and-assets.md) | 构建、监控、告警、故障和恢复 |
| 发布 | [发布与回退](releases/release-and-rollback.md)、[版本政策](releases/version-policy.md)、[两个历史版本](releases/history.json) | 怎样交付、固定版本、停止和恢复 |
| 计划 | [交付计划和风险](governance/delivery-plan.md) | 任务、依赖、责任、完成条件 |
| 治理 | [文档治理](governance/document-management.md) | 状态、审批、更新、证据与唯一来源 |
| 模板 | [变更与发布记录](governance/change-record-template.md) | 如何记录下一次变更和验收 |
| 用户资料 | [r2p 用户指南](guide/src/SUMMARY.md) | 如何使用现有库 |
| 历史参考 | [上游参考说明](reference/README.md) | 哪些资料保留原文、如何判断适用性 |

## 状态约定

所有工程文档遵循同一套状态语言：

- **已实现**：能在当前源码定位对应能力，仍需关注测试覆盖和平台条件。
- **已落地**：代码/流程已纳入本次工程基线；远端交付以交付记录为准。
- **工程规范**：本仓库采用的研发和交付要求；具体执行仍需测试/发行证据。
- **发行准入要求**：外部制品发行前应满足的目标，尚未证明全部满足。
- **待确认**：需要产品或负责人确认的范围、权限、预算或指标。
- **已验证**：有[结构化证据](testing/evidence-summary.md)及引用报告支持，限定 SHA、环境和范围。

当前实际责任人见[维护者清单](governance/maintainers.toml)，由 jelven007 承担已列角色；备份维护者尚未分配。
SLO、支持期限和性能门槛是拟定目标，确定后才构成外部承诺。
上游 PyO3 的发行、包索引、社区和站点保留真实身份；它们不是 r2p 的运营证据。

## 维护原则

产品名称以 [product.toml](../product.toml) 为准；需求编号以[需求规格](requirements/system-requirements.md)为准；路径以[目录规范](development/repository-layout.md)为准；测试执行结果以 `testing/reports/` 报告为准；交付决策以 `releases/records/` 记录为准。
同一变更应在代码、方案、测试和运营/运维说明中同步体现。

文档和 Cargo 路径检查：

```bash
python tools/check_repository.py
uv run --isolated --only-group nox nox -s rumdl
```

第一条需要 Python 3.11+。
检查验证本地目标文件存在；外部网址、Markdown 锚点语义、内容正确性和生产就绪程度需要另外评估。
