# 参与 r2p 开发

r2p 源自 PyO3，SDK 名称、宏属性、构建配置和 Python 辅助模块已迁移为 r2p。
参与者遵循[行为规范](Code-of-Conduct.md)，保留作者、许可和来源，并对提交内容及验证结果负责。

## 开始工作

1. 阅读[项目分析](docs/governance/project-assessment.md)和[需求规格](docs/requirements/system-requirements.md)，定位需求或缺陷。
2. 按[开发指南](docs/development/developer-guide.md)准备环境；按[目录规范](docs/development/repository-layout.md)放置文件。
3. 对照[总体方案](docs/architecture/system-design.md)和[接口/兼容约束](docs/architecture/interfaces-and-compatibility.md)实现。
4. 按[测试策略](docs/testing/test-strategy.md)运行相关回归，记录失败、跳过和未覆盖项。
5. 同步文档、追踪矩阵及必要发行片段，使用[变更记录模板](docs/governance/change-record-template.md)整理审阅材料。

## 变更要求

公共 API、ABI、解释器/MSRV、宏、线程和 unsafe 修改必须说明兼容影响与不变量。
目录移动同步 Cargo、Nox、CI、mdBook、打包路径；生成模板保留可供消费者使用的版本配置。

新增功能核对 `full` 特性及实际 CI 矩阵。
AI 辅助生成内容仍由贡献者核验源码、正确性和测试，不将未经检查的输出作为已验证证据。
上游贡献规则和 AI 责任原文见[上游贡献快照](docs/reference/upstream-contributing.md)。

从根目录运行 `uv run --isolated --only-group nox nox -s fmt` 和受影响测试；完整命令、工具依赖和限制见开发指南。
PR 描述包含问题、最终行为、需求编号、兼容影响、验证及回退方式。

贡献与复现/修复反馈通过 [r2p PR](https://github.com/jelven007/r2p/pulls) 提交；Issues 当前关闭，启用后使用仓库问题模板。
源码交付与两个历史版本依[发行方案](docs/releases/release-and-rollback.md)和[版本政策](docs/releases/version-policy.md)执行。
