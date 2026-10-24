# CI 分层与门禁验证

日期：2026-10-25；范围：O-04/O-05；状态：本地验证通过，远端执行和保护分别跟踪。

## 检查选择

`tools/ci_policy.py` 根据事件、标签及真实 Git diff 生成 required/optional/not-applicable 集合，每项保留理由。
工程治理/运营等文档只要求 resolve 和 engineering；SDK README、Contributing、指南/include 仍要求 Rust 格式、doctest、文档构建和消费方验证。
核心源码、宏、FFI、Cargo/锁和工具变更保留核心 PR 矩阵。
未知路径、空差异、周期/手动/merge_group、完整矩阵标签以及矩阵定义修改按更广范围执行。
标签增删会重算选择；FFI 选择也来自同一模型，移除 reusable build 的独立路径过滤。

PR 10 个组合和完整 45 个组合抽取到 `tools/engineering/ci_matrix.py`，保留原平台/解释器/MSRV 组合。
每周一 03:23 UTC 执行完整矩阵；实际结果须另行登记，不将 schedule 配置等同于运行通过。
前瞻 nightly/beta 保持独立容错语义，不代表稳定支持。

汇总重新计算计划，拒绝必需项失败/取消/跳过、缺少 job、未知 job、空理由及被修改的矩阵或标签。
不适用项只能有明确选择理由并实际 skipped。
保留原 24 前置任务的 50 个可执行正负场景，并增加所有必需项意外跳过、任务/矩阵遗漏和计划篡改回归。
当前 24 项工具 unittest 全部通过，包含以上子场景。

## 去重和实际验证

benches/main 并发组使用分支而非 SHA，连续提交可取消旧任务。
基准只在性能相关变更或显式全量事件运行；站点按 SDK 文档/源码影响选择。
缓存预热保留手动恢复入口，取消重复的每次 main push 构建，正常 CI 与周期矩阵继续保存缓存。
release 站点任务不取消；没有 site 制品时部署工作流明确不适用。
MSRV build 改为在已准备的隔离副本中实际运行 docs/test-rust/test-py，并上传真实锁及配置。

本地 actionlint 对 11 个工作流通过；受影响六个工作流 zizmor 通过。
`nox -s docs build-guide` 两会话成功，约 29 秒；指南保留已有 HTML 标签提示，构建退出成功。
消费方真实执行见[消费报告](consumer-optimization-2026-10-25.md)。
原始本地日志为 `target/optimization/ci-contracts-final.log`、`sdk-docs.log`、`sdk-doctest.log`。
工程文档检查 ≤5 分钟仍是试行目标；20 次样本的 P50/P95 未采集。

## 远端规则

2026-10-25 GitHub API 确认当前身份 `jelven007`、仓库元数据权限 admin/maintain/push 为 true，但保护接口 GET 和 PUT 均返回 `403 Resource not accessible by integration`。
后续 main 查询仍为 `protected=false`，提交为 `3a24917eb2766aa8ded8c04fefde1c1d4b133c00`。
实际 token 的 administration 权限不能由仓库元数据权限推定。
可应用的[保护配置](../../governance/main-protection.json)要求稳定 `conclusion`、最新 base、禁止强推/删除及解决 review 对话。
当前只有已核实的一名维护者，不设虚构的第二审阅人要求。
远端强制尚未生效，不能宣称 O-05 远端验收完成。
