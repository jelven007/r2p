# r2p 发行入口

产品名称为 `r2p`，元数据见 [product.toml](product.toml)。
本仓库的包名、作者与上游链接仍延续 r2p。
本次目录/文档整理未执行发行或部署；独立注册表、站点及权限需按[产品身份决策](docs/architecture/adr/0002-product-and-release-boundaries.md)明确。

当前执行规范：

- [发行、部署与回退](docs/maintenance/release-and-rollback.md)：身份、质量门禁、制品、发布后核验和恢复。
- [运维手册](docs/maintenance/runbook.md)：故障定级、排查、停止、恢复和复盘。
- [测试策略](docs/testing/test-strategy.md)与[验证报告](docs/testing/validation-report.md)：必需证据和本次实际结果。
- [变更与发布记录模板](docs/governance/change-record-template.md)：版本、SHA、依赖、制品哈希、批准和恢复记录。

既有 GitHub 发布工作流会响应标签或手动事件；启用前核对目标、授权、环境和包选择。
拉取时的流程原文保留在[上游发行快照](docs/reference/upstream-releasing.md)，供上游协作参考。
