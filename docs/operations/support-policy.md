# r2p 源码采用与支持政策

版本：2.1；日期：2026-10-25；状态：当前源码交付适用。

## 1. 支持入口与方式

2026-10-25 通过 GitHub 仓库 API 核验：目标仓库为 public fork，Issues 已开启，Discussions 未开启。
可复现缺陷和建议通过 [r2p Issues](https://github.com/jelven007/r2p/issues/new/choose) 提交；修复通过 [r2p PR](https://github.com/jelven007/r2p/pulls) 关联原问题。
维护者按最小复现、影响范围和严重程度尽力处理；没有工作时限、全天候值守或 SLA 承诺。
本仓库没有启用独立客服、Discord 或 Discussions，不能把上游渠道称为 r2p 支持团队。
账号/仓库写权限已核验，具体人员排班和正式服务合同尚未建立。
当前负责人为 `jelven007`，职责与未建立的备份/私密渠道见[维护者清单](../governance/maintainers.toml)及 [SECURITY.md](../../SECURITY.md)。

## 2. 范围与版本

| 对象 | 本期策略 | 必需说明 |
| --- | --- | --- |
| main 上的 r2p SDK | 问题修复通过 PR，消费方固定已验证 SHA | 平台/解释器证据以支持矩阵为准 |
| 两个历史快照 | 提供不可变检出和恢复，不修改旧标签 | 推荐恢复点见 history.json，原始命名边界不同 |
| 实验 inspect/async/no_std/abi3t | 接受可复现问题，单独评估升级/恢复 | 不从稳定 GIL 路径推导支持结论 |
| Rust/Python 候选包 | 本地构建证据和示例 | 没有公开注册表下载、保修或发行支持期限承诺 |
| 消费方业务服务 | SDK 边界提供协助 | 业务监控、数据、容量和恢复由消费方负责 |

兼容证据见[支持矩阵](../testing/support-matrix.md)，升级规则见[版本政策](../releases/version-policy.md)。
正式包发行时新增生效版本、支持期限、目标矩阵、维护人员和停止支持的迁移通知规则。

## 3. 问题信息与分流

最小信息包括完整源码 SHA、Rust/Python 版本、OS/CPU、features、ABI/GIL、打包工具、完整复现命令、预期/实际及最小代码。
日志只包含必要信息；不要求消费方提供凭证或业务数据。
构建/链接问题交构建角色，语义/并发/崩溃交 SDK 技术角色，文档和使用问题交支持角色。
严重程度按[故障手册](../runbooks/incident-response.md)定级，修复关联回归及受影响支持矩阵。

反馈处理状态为新建 → 待复现 → 已分类 → 已安排 → 修复/答复 → 用户验证 → 关闭；在 Issue 和关联 PR 中记录。
无法复现时写明已测环境、缺失信息和下一步，不将未答复算为解决。
采用和响应指标按[运营计划](operating-plan.md)统计，当前标为“未采集”。
