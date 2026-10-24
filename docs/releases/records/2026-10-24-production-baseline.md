# 2026-10-24 r2p 生产工程源码交付记录

记录：DEL-20261024-01；类型：源码交付；状态：本地准备完成，远端核验结果在本记录追加。
目标：[jelven007/r2p](https://github.com/jelven007/r2p) 的 `main`。
范围：FR-007/008、NFR-003–008、ADR-0001/0002/0003。

## 1. 交付内容

SDK 内核改名为 r2p；生产工程按 crates/python/tests/benchmarks/tools/infrastructure/assets/docs 职责组织。
需求、架构、开发、测试、运营、运维和发行资料更新为 2.0 基线，补充旅程、配置表、支持矩阵、支持政策、环境资产和版本历史。
目标仓库链接、Cargo 打包排除、根锁文件政策、工作流相对引用/依赖及发行开关联动更新。
未更改上游版权、许可证和四份原文归档。

## 2. 来源与两个历史版本

| 标识 | 完整 SHA | 证据 |
| --- | --- | --- |
| `history/upstream-baseline-2026-10-24` | `424149e8a1c42128b05a090941673008fc46c478` | 迁移前源码基线，保留原 PyO3 名称 |
| `history/sdk-kernel-2026-10-24` | `f9e8d6461f51b7149b436844339dd9df7abb9e00` | r2p SDK 迁移与本地回归快照 |

清单唯一来源为[history.json](../history.json)。
目标仓库原 main 与上述上游基线一致；当前账号推送权限已通过 API 核验。
历史保留采用两个不可变恢复标签和完整提交祖先，不截断历史，不强推。

## 3. 验证与交付准入

SDK 回归见[内核迁移验证](../../testing/reports/kernel-migration-validation.md)。
当前目录/文档/工作流/打包/历史检出结果见[生产工程验证](../../testing/reports/production-baseline-validation.md)。
本期按源码 G1–G6 的适用项交付；平台完整矩阵和注册表/站点准入单独记录。

## 4. 远端结果

| 项目 | 状态 |
| --- | --- |
| 功能分支 | `refactor/production-layout-docs`，待本次最终推送 |
| PR/主分支合并 | 待本次最终源码验证后执行 |
| 远端两标签 | 待推送后逐项 SHA 核验 |
| 本地与远端 main | 待合并后核验一致、工作区干净 |
| crates.io/PyPI/Netlify | 未执行，发布开关默认关闭 |

远端结果以目标 GitHub PR、main 和标签查询为准；本记录后续追加实际链接和核验结果。
源码提交无法自包含自己的最终 SHA，使用 Git 提交/PR 标识追溯。

## 5. 恢复与限制

恢复 SDK 验证快照可保持 r2p 名称；恢复上游基线须同步消费方 PyO3 依赖和导入。
先独立检出运行回归，主分支通过 revert PR 恢复。
没有注册表制品、站点部署或商业支持承诺；已测平台和实验边界见[支持矩阵](../../testing/support-matrix.md)。
