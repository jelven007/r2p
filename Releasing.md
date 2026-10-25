# r2p 发行入口

产品名称为 `r2p`，元数据见 [product.toml](product.toml)。
SDK 包名为 `r2p` / `r2p-*`，作者和许可证保留 PyO3 原始来源。
本期交付固定 Git SHA 的源码到 `jelven007/r2p`；注册表和站点发布默认关闭。

当前执行规范：

- [发行、部署与回退](docs/releases/release-and-rollback.md)：源码/制品门禁、核验和恢复。
- [版本政策](docs/releases/version-policy.md)、[两个历史版本](docs/releases/history.json)、[本期交付记录](docs/releases/records/2026-10-24-production-baseline.md)。
- [运维手册](docs/runbooks/incident-response.md)：故障定级、排查、停止、恢复和复盘。
- [测试策略](docs/testing/test-strategy.md)与[当前验证](docs/testing/reports/production-baseline-validation.md)：必需证据和本次实际结果。
- [变更与发布记录模板](docs/governance/change-record-template.md)：版本、SHA、依赖、制品哈希、批准和恢复记录。
- [候选制品验收](docs/testing/reports/candidate-acceptance-2026-10-25.md)：本机六包注册表消费、扩展/CLI wheel、拒绝和保留制品恢复。

外部发行工作流要求对应 `R2P_ENABLE_*` 仓库变量为 `true`，启用前核对目标、授权、环境和包选择。
发布 gate 要求同 SHA 的完整成功 CI 与候选 manifest；Rust 使用原始已验收 `.crate`，CLI wheel 要求七个原生平台运行和完整集合复验。
当前只有本机候选与恢复通过，同 SHA 远端 CI 和七平台 wheel 仍待执行。
`history/*` 标签用于恢复，不触发 `v*` 注册表发布。
拉取时的流程原文保留在[上游发行快照](docs/reference/upstream-releasing.md)，供上游协作参考。
