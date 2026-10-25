# 证据与运营治理验证

日期：2026-10-25；范围：O-09；状态：结构化治理本地验证通过，外部采用样本和私密渠道未完成。

`docs/testing/evidence.json` 登记十个已完成基线 build 的独立环境、工作流汇总、本轮 full/MSRV/docs 三条本地记录及 native/abi3/embedding 三条消费记录，共 17 条。
远端数据来自真实完成的 [CI 40112259362](https://github.com/jelven007/r2p/actions/runs/40112259362)，保留源码 `839ddb30dc3c936049a26f946b6206af25a99ba9`。
本地记录明确标注 worktree-changes，并保留基线 SHA、具体 Rust/Python、GIL、特性、命令、结果、锁摘要、时间和报告。
无法从任务名称确定的 patch 版本要求查原始日志，不编造版本或逐项 skip 结果。
生成摘要可检查漂移，配置/编译/运行/汇总等级分离，同 ID 的历史记录不可覆盖。
当前 PR 未完成矩阵不写入已验证支持行。

需求 CSV 分列实现与验收状态，关联证据 ID/具体报告，并将 owner 关联到已核实当前 GitHub 账号 `jelven007`。
待采集性能、外部恢复和运营数据明确写 pending/process-only 与 not-collected。
Issues/Discussions 入口按实际状态同步，原始发行/测试报告保持历史语义。
[当前仓库状态](../../governance/repository-state.json)记录权限限制、发行开关和采用样本边界。

CODEOWNERS 及[维护者清单](../../governance/maintainers.toml)落实当前一名维护者职责，不虚构备份人员或 SLA。
GitHub 私密报告 GET 返回 disabled，启用 PUT 返回 403；SECURITY.md 如实描述当前没有私密渠道。
main 保护同样因权限受限未生效，见[CI 验证](ci-policy-optimization-2026-10-25.md)。
这些未完成项仍约束首次外部发行。
现有 Dependabot 的 Cargo/Actions 周期为每周、uv/Netlify npm 为季度；告警由当前维护者按影响处理，没有将配置本身视作漏洞审计结果。

新 r2p 发行片段采用独立 `r2p-towncrier.toml`、`r2p-newsfragments/` 与 `R2P_CHANGELOG.md`，预览成功且链接指向 r2p 的 #2。
既有 PyO3 CHANGELOG、片段及其 towncrier 来源完整保留。
Nox check-changelog 已切换为新目录。
两个内部消费者已安装/运行；外部首次采用、升级、反馈、响应时间和连续 20 次工程文档 CI 成本样本尚未采集。

29 项工具 unittest、Ruff、86 份 Markdown 检查、仓库路径/追踪和 towncrier 草稿预览成功。
新增证据负向测试阻断缺失来源、重复 ID、无理由跳过、配置冒充成功及生成摘要漂移。
原始本地日志为 `target/optimization/o09-contracts.log`、`rumdl-o09.log` 和 `r2p-changelog-preview.*`。

远端第二次 CI 的 engineering 中 Ruff、rumdl 和 24 项工具测试已成功，typos 将故意错误输入 `skip-ful` 当作拼写问题阻断。
已仅为该完整输入添加精确 regex 例外，保留原始错误参数回归和报告；未关闭拼写检查。
此失败保持原结果，最终候选的远端验证另外记录。
