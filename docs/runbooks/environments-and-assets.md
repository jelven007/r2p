# r2p 环境与工程资产

版本：2.0；日期：2026-10-24；状态：当前源码资产盘点，不包含秘密值。
关联：NFR-004/007，操作见[故障手册](incident-response.md)。

| 资产/环境 | 当前状态 | 来源与责任角色 | 维护/恢复规则 |
| --- | --- | --- | --- |
| GitHub `jelven007/r2p` | public，默认 main，当前账号有推送权限 | product.toml / 仓库维护角色 | 普通合并、保留祖先、核验远端 SHA |
| 分支保护 | 本次核验 main 无保护规则 | GitHub / 仓库维护角色 | 是否启用按团队协作需要另配置，不声称已强制审阅 |
| 两个 Git 历史快照 | 本地创建，远端状态由交付记录核验 | releases/history.json / 发行角色 | 不可变，独立检出回归，主分支通过 revert PR 恢复 |
| 根 Cargo.lock / uv.lock | 已跟踪 | Cargo/uv / 构建角色 | 记录解析变化；MSRV 在隔离副本准备依赖 |
| 本地 macOS arm64 验证 | stable 1.99.1 / 1.85.1，CPython 3.14.9 | testing/reports / 测试角色 | .tools、target、.nox 是本机缓存，不作为正式制品存储 |
| GitHub Actions | 工作流源码存在 | .github/workflows / 构建角色 | 运行和平台结果分别记录；临时失败与源码失败区分 |
| CodSpeed | 基准可运行，目标仓库未接入上传服务，首次上传 401 | benchmarks 工作流 / 性能角色 | simulation 继续执行；注册及认证核验后设 R2P_ENABLE_CODSPEED=true |
| crates.io / PyPI | 未启用独立发行 | 仓库变量/平台环境 / 发行角色 | 对应启用变量为 true 且 G1–G6 通过才发布 |
| Netlify / gh-pages 文档站点 | 构建资源存在，部署默认关闭 | infrastructure/netlify / 运维角色 | 域名、站点和旧制品恢复在启用时验收 |
| 支持反馈 | fork 仓库 Issues 关闭，复现/修复通过 PR | operations/support-policy / 支持角色 | 当前授权无法改设置，记录版本/环境/复现，不承诺时限 |
| 上游参考与许可证 | 四份归档及双许可证保留 | docs/reference / 技术角色 | 保存原文来源；品牌素材按上游身份说明 |

生产注册表/站点启用时补充资产标识、实际负责人、权限环境、工具链、制品存储、保留期、告警和演练证据。
凭证由环境或平台 OIDC 管理；本表不记录令牌、私钥或完整环境变量。
SDK 没有业务数据库、常驻服务实例或业务数据备份任务。

源码恢复使用[版本政策](../releases/version-policy.md)中的固定 SHA 和快照。
正式制品恢复必须保存旧制品及 SHA-256，并在干净环境验证导入和消费方关键场景。
