# r2p 生产工程与源码交付验证

日期：2026-10-24；记录：VAL-20261024-04。
源码：SDK 验证快照 `f9e8d6461f51b7149b436844339dd9df7abb9e00` 加本次生产工程目录/文档/工作流变更。
状态：本地相关验证通过；远端交付结果单独记录。

## 1. 范围和既有证据

本期调整文档职责、工程入口、目标仓库 URL、根锁政策、Cargo 排除、工作流引用/依赖和外部发行开关。
Rust/Python 核心算法未在本期继续修改。
既有 SDK default/full/no-default、组件、严格 UI、doctest、Python 197 项、stub 16 项、九个示例、MSRV 编译、ABI3/runtime/内省 wheel 和六个 crate 的证据见[内核迁移报告](kernel-migration-validation.md)。
旧目录和 CI 修正结果分别保存在[初始验证](validation-report.md)和[CI 修正验证](ci-fixes-validation.md)，不将旧工具/范围替换为新结论。

## 2. 当前验证

| 检查 | 命令/方法 | 当前结果 |
| --- | --- | --- |
| 主与隔离 workspace | 根、benchmarks/r2p-benches、tools/ffi-check 三个 metadata | 通过，`.tools/production-metadata-*.json` |
| 目录/链接/身份/追踪/两快照 | Python 3.14.9 `tools/check_repository.py` | 24 Cargo 清单、44 工程文档、16 条追踪及两个标签通过 |
| 完整格式/静态入口 | Nox `fmt` | 七会话通过，`.tools/production-fmt-final.log`；75 Markdown 文件无问题 |
| 工作流结构/表达式 | `tools/check_workflows.py --actionlint .tools/actionlint` | 11 工作流通过，0 诊断；临时副本兼容 actionlint 旧语法，源码保持 GitHub `$/` |
| 工作流审计 | zizmor 1.30.1 | 当前源码 offline 检查无发现；首次远端要求恢复 `$/` 引用，已修正 |
| CI 汇总 | 实际 YAML 中汇总脚本注入 | 25 job/24 前置，50 正负场景通过；两种 semver 身份路径和 MSRV/cache 顺序通过 |
| 根 crate 文件内容 | `cargo package -p r2p --list --allow-dirty` | 301 候选文件，SDK/许可齐全，工程文档排除；仅文件清单，不是 package verification |
| Rust/指南文档 | Nox `docs build-guide` | 通过，`.tools/production-docs.log`；最终指南复验通过 |
| 当前 Rust 编译 | `cargo check -p r2p --features full --all-targets --locked` | 通过，`.tools/production-check-final.log` |
| 历史恢复点 | 两标签 SHA、独立 worktree 检出，SDK 快照 full/all-targets/locked 编译 | 通过，`.tools/production-history-check.log`；上游快照保持原名称 |
| 来源完整性 | 四原文、CHANGELOG、两许可证与历史 blob 比较 | 七文件逐字节一致 |
| 最终差异 | `git diff --check`，缓存/制品忽略审阅 | 通过；本地工具和生成制品不提交 |

本机环境：macOS arm64，Rust stable 1.99.1 / MSRV 1.85.1，CPython 3.14.9，uv 0.13.5。
本机工具/输出位于 `.tools/`、`.venv/`、`target/`，不提交。

初次完整格式入口发现 Python 无时区日期测试被 DTZ 规则误判、独立 FFI 工具格式及 31 项句子换行问题。
添加两份日期测试的有意无时区例外，仅调整 FFI 格式和 Markdown 换行，完整入口复验通过。
初次误用 Python 3.9 执行检查脚本缺少 tomllib，改用要求范围内的 Python 3.14.9 后通过。
指南保留 `class/protocols.md` 的两个历史 details 标签警告，构建成功。
首次远端检查发现 FFI 工具仍读取旧 Cargo links 派生变量，已改为 `DEP_R2P_FFI_PYTHON_R2P_CONFIG` 并按实际工具链复验。
no_std UI 的 enum constructor 快照仍保留旧包名列号，按实际诊断修正一列并保持严格检查。
本地 FFI 头文件/签名/布局对照及 32 DLL 名、24 x86 私有导入校验通过，日志 `.tools/production-ffi-check.log`。
本地 no_std 严格 UI 复验 56 通过、13 ignored、7 条件过滤，`.tools/production-ui-nostd.log`；修正后的完整 fmt 七会话再次通过。
首次远端指南外链检查访问合并前 main 的新目录得到 404；流水线现在提供 `R2P_SOURCE_REV`，校验实际测试 SHA 的链接，未忽略失败链接。

## 3. 远端核验

分支、PR、合并和两历史引用结果保存到[交付记录](../../releases/records/2026-10-24-production-baseline.md)。
本地结果不能声称完整 GitHub 平台矩阵通过，远端缺失/失败和原因单列。
完整源码历史保留，Git 标签不匹配 `v*`；外部发布/部署需要对应 `R2P_ENABLE_*` 为 `true`。

## 4. 限制

注册表获取/验证、站点部署/恢复、完整 Python/ABI/平台矩阵和性能基准不属于本期已执行结论。
FFI 对照本地补验只覆盖 CPython 3.14.9/macOS arm64，不能替代其他目标。
历史上游快照使用旧名称，恢复它须配套恢复消费方。
源码交付闭环不等于外部制品发行完成；支持使用本仓库 PR 尽力维护。
目标仓库为 public fork，Issues 关闭；当前令牌修改仓库设置返回 403，未将 Issue 开通写为完成。
