# MSRV 特性任务与 CI 汇总修正验证

日期：2026-10-24；状态：本地配置修正与验证完成，远端 CI 待运行。
关联：OPT-02、OPT-03、NFR-003、NFR-005。
基础提交：`424149e8a1c42128b05a090941673008fc46c478`；包含当前未提交目录迁移和 CI 修改。

## 1. 修正内容

| 原问题 | 当前行为 |
| --- | --- |
| `check-feature-powerset` 的 stable/MSRV 两项均使用 stable | job 级 `RUSTUP_TOOLCHAIN` 绑定 `matrix.rust`，安装和后续 Cargo 命令使用同一工具链 |
| Rust 缓存在目标工具链安装前恢复 | 先安装并输出 Rust/Cargo 版本，再恢复缓存，使缓存读取对应的编译器配置 |
| `conclusion` 未汇总四项检查 | 补齐 `semver-checks`、`test-debug-min-version`、`test-introspection-pr`、`pytests-type-checking` |
| `resolve` 仅通过其他任务间接进入结果链路 | 显式纳入汇总，当前 25 个 job 中的 24 个前置任务全部覆盖 |

改动位于[ci.yml](../../.github/workflows/ci.yml)。
保留 stable 与 MSRV 的矩阵、MSRV 项的 `minimal-versions` 参数、原测试会话与事件条件。
汇总继续允许成功和条件跳过，失败与取消返回非零状态。

## 2. 本机验证结果

| 检查 | 方法 | 结果与证据 |
| --- | --- | --- |
| YAML 与依赖图 | 解析全部 job，检查依赖存在、无重复、无环，汇总集合覆盖所有其他 job | 25 个 job、24 个汇总依赖，通过；`.tools/ci-fixes-validation.log` |
| stable 工具链 | 从实际 YAML 提取安装步骤，设置矩阵值后执行 | 使用 Rust 1.99.1，通过 |
| MSRV 工具链 | 同上，MSRV 取根 Cargo 清单中的 `1.85` | 使用 Rust 1.85.1，通过 |
| 成功与跳过 | 执行实际 YAML 中的 Bash/jq 汇总脚本，分别注入全部成功和条件跳过 | 2 个正向场景通过 |
| 失败与取消 | 对 24 个前置任务逐个注入 failure/cancelled，其他任务设为成功 | 48 个负向场景均被阻断 |
| 原遗漏回归 | 对四个遗漏任务分别注入 failure/cancelled，对比基础提交与当前汇总 | 8 个原配置放行场景，新配置全部阻断 |
| MSRV 特性编译 | 隔离副本使用 Rust 1.85.1、CPython 3.14.9、兼容依赖解析，执行 full/all-targets 检查 | 通过；`.tools/msrv-resolve.log`、`.tools/msrv-feature-smoke.log` |
| 工作流 lint 增量 | actionlint 1.7.12 对基础提交/当前文件分别检查并比较诊断 | 没有新增诊断；完整 lint 的既有问题见下文 |

50 个汇总执行场景由 2 个正向和 48 个负向场景组成。
8 个基线对比场景另计，用于证明原遗漏可复现。
这些场景验证汇总逻辑，不等于真实 GitHub job 已运行。

## 3. 环境与复现

工具链安装与汇总脚本验证从 YAML 读取实际内容，没有复制一份独立的生产汇总逻辑。
本机检查脚本为 `.tools/validate-ci-fixes.py`，依赖 PyYAML 6.0.3 和系统 jq；脚本、依赖及日志处于忽略目录。

```bash
.tools/python/cpython-3.14.9-macos-aarch64-none/bin/python3.14 .tools/validate-ci-fixes.py
```

MSRV 编译在 `.tools/msrv-checkout/` 的源码副本执行，输出到 `.tools/msrv-target/`，不修改主工作区依赖锁定结果。
副本先使用 MSRV 兼容解析，再检查主库 full 特性及全部 Cargo targets：

```bash
RUSTUP_TOOLCHAIN=1.85 CARGO_RESOLVER_INCOMPATIBLE_RUST_VERSIONS=fallback cargo update
RUSTUP_TOOLCHAIN=1.85 PYO3_PYTHON=python3.14 cargo check -p pyo3 --features full --all-targets --locked
```

本机实际 `PYO3_PYTHON` 指向工作区内的 CPython 3.14.9。
`cargo check` 证明该组合编译成功，不代表测试已执行或 ABI/解释器完整矩阵通过。

## 4. lint 结果与边界

actionlint 1.7.12 对基础提交和当前文件各产生 13 条相同诊断，本次新增诊断为 0。
其中 11 条是该工具尚不识别 GitHub 当前支持的 `$/` 自仓库引用。
源码保持该引用形式；适用性背景见[优化评估](../governance/optimization-assessment.md)。

另外两条基线表达式告警为：

- `check-nightly` 的 job 名引用未定义的 `matrix.rust`；
- `no_std` 的缓存配置引用 `needs.resolve`，该 job 的 needs 只有 `fmt`。

这两项保留为后续配置清理，不将完整 lint 结果表述为通过。
对比证据为 `.tools/actionlint-ci-comparison.log`、`.tools/actionlint-baseline.log`、`.tools/actionlint-current.log`。

## 5. 尚未执行的验证

未运行 GitHub Linux/Windows 等远端任务，也未读取分支保护和 required checks 配置。
本机编译覆盖 macOS arm64、Rust 1.85.1、CPython 3.14.9、full/all-targets；CI 原配置选用 Python 3.15 的完整 feature powerset 和 minimal-versions 仍需实际 CI 运行。

本次配置修正不替代 G4 完整兼容验收。
后续在同一提交的远端 CI 上确认实际 Rust/Cargo 版本、完整矩阵结果和分支门禁要求；规则应继续使失败/取消阻断，并允许按事件设计的跳过。
