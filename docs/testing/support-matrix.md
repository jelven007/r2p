# 兼容性支持矩阵与证据

版本：2.0；日期：2026-10-24；最终核验：2026-10-25；状态：当前源码交付的证据矩阵。
关联：FR-005/006、NFR-001/003/005。
支持响应见[支持政策](../operations/support-policy.md)，准入要求见[测试策略](test-strategy.md)。
逐条 SHA、环境、结果和限制的机器来源为 [evidence.json](evidence.json)，[生成摘要](evidence-summary.md)由 `python -m tools.evidence render` 更新。
下表保留原阶段的解释；新候选不能复用旧 SHA 的结论，新运行以结构化记录区分。

## 1. 证据等级

配置存在、编译成功、行为运行成功、正式发行支持分别记录。
本期提供源码和尽力维护，不提供跨平台商用认证或响应时间保证。
正式制品支持范围必须附该发行 SHA 的目标环境构建、安装和运行证据。

| OS/CPU | Rust | Python / GIL | ABI / 特性 | 当前证据 | 等级/限制 |
| --- | --- | --- | --- | --- | --- |
| macOS arm64 | stable 1.99.1 | CPython 3.14.9 / GIL | 默认、无默认、full | 主库、集成、严格 UI、doctest、Python 行为通过 | 本地运行已验证，非跨平台结论 |
| macOS arm64 | 1.85.1 | CPython 3.14.9 / GIL | full / all-targets / locked | MSRV 兼容依赖解析后编译通过 | 编译证据，未把全部行为测试算作 MSRV 实测 |
| macOS arm64 | stable 1.99.1 | CPython 3.14.9 / GIL | abi3-py39 | cp39-abi3 wheel 安装、类 getter/setter 和严格 UI 通过 | 没有运行 Python 3.9–3.13，标签不证明所有版本运行通过 |
| macOS arm64 | stable 1.99.1 | CPython 3.14.9 / GIL | experimental inspect/async | 原始/stripped/fat Mach-O 输出一致，16 stub 测试通过 | 实验路径；不扩大到 ELF/PE |
| macOS arm64 | stable 1.99.1 | CPython 3.14.9 / GIL | Maturin/setuptools/Meson 示例 | 九个示例构建/安装及各自 pytest 通过 | Meson 后端 Rust 1.87+；未跑远端 cargo-generate |
| Linux x64/arm64、macOS arm64 | stable | CPython 3.14 / GIL | PR Nox 特性组合 | 三个远端 build 任务通过，包含 FFI/文档/Rust/Python | 受测提交见下文；不扩大到其他 Python 版本 |
| Windows x64/x86/arm64 | stable | CPython 3.14 / GIL | PR Nox 特性组合 | 三个远端 build 任务通过，包含 FFI/文档/Rust/Python | Windows 三种架构分别运行 |
| Linux x64 | stable | CPython 3.15 / GIL | PR Nox 特性组合 | 远端 build 任务通过 | 不扩大到其他 OS |
| Linux x64 | stable | CPython 3.14t/3.15t | free-threaded，按 Nox 枚举 ABI 特性 | 两个远端 build 任务分别通过 | 普通 abi3 不能替代；用例跳过保留在日志 |
| Linux x64 | MSRV 1.85 | CPython 3.14 | Nox MSRV 依赖准备与 check-all | 远端 check-msrv 通过 | 编译证据，未将其算作 MSRV 全量行为测试 |
| Linux x64 | nightly | CPython 3.14 / GIL | PR Nox 特性组合 | 远端 build 和 nightly check 通过 | UI_TEST=ignore，无严格诊断结论；FFI 条件跳过 |
| CI 声明平台 | stable/MSRV | 其他 CPython 3.9–3.15 | 原生 ABI / abi3 | FFI 元数据和测试配置存在 | 逐行实测后升级证据等级 |
| CI 声明平台 | CI 指定版本 | PyPy/GraalPy | CI 声明组合 | 本期 PR 未启用完整矩阵 | 不能引用 CPython 结果代替 |
| WASI/Emscripten/跨编译目标 | CI 指定版本 | 对应目标解释器 | 目标构建配置 | infrastructure 和专门 CI 存在 | 单独核验目标导入/线程/链接限制 |
| WIP no_std / Linux x64 | stable | CPython 3.14 | R2P_WIP_NO_STD | Rust/Python/Clippy 三任务通过；full/macros 严格 UI 均通过 | 保持实验标识，无完整 no_std 承诺 |

详细数量、命令和已有 ignored/skip 项见[SDK 内核迁移报告](reports/kernel-migration-validation.md)及其引用的[初始报告](reports/validation-report.md)。
生产工程基线的目录、工作流和交付验证见[历史报告](reports/production-baseline-validation.md)。
后续本地候选、性能采样、环境修正与失败记录见[当前结构化摘要](evidence-summary.md)及[持续实施记录](../governance/optimization-continuation-2026-10-25.md)。
固定实施提交 `b04b79e7` 的 macOS arm64 本机验收见[报告](reports/local-acceptance-2026-10-25.md)。
普通 GIL 完整 Rust 入口、FT core 与 26 项 Python 回归、内省和候选/恢复通过；FT 模块导入前后的实际 GIL 均关闭。
CLI 只有 macos-aarch64 的新原生验收，七平台集合仍阻断；该结果不扩展表中的历史远端支持范围。
上述远端证据对应源码 `839ddb30dc3c936049a26f946b6206af25a99ba9` 的 [CI 运行](https://github.com/jelven007/r2p/actions/runs/40112259362)。
主分支合并 `2cc5fbcddea3b35d6a0a95caf6177478b79e79be` 与该提交的文件树一致；后续交付回执仅更新文档。
九个 stable Clippy 跨目标检查也通过，但仅有 Clippy 结果的目标不据此声明运行支持。

## 2. 矩阵维护

每次 Python/Rust 下限、ABI、特性、平台、构建适配或源码版本变化时复核受影响行。
使用 `python -m tools.evidence import-actions --run-id <completed-run>` 导入完成的 CI；未完成运行不能导入支持证据。
本地工具快照使用 `import-local --snapshot <json> --id <unique-id> --features <features> --report <report>` 导入。
记录同 ID 不允许改写；`python -m tools.evidence check` 阻断重复 ID、缺失来源/环境/理由和摘要漂移。
free-threaded 编译标志与当前 GIL 分开记录；模块导入后的状态须在同一进程观测。
新导入对缺少实际接口或旧快照没有状态字段的情况记 unrecorded；历史字段仍按原报告解释，不补推模块后的状态。
安装和解释器绑定失败只记录配置失败；SDK 步骤已尝试的 failure 不表示行为通过，详见[环境修正报告](reports/evidence-environment-2026-10-25.md)。
新增行记录完整 SHA、OS/CPU、Rust/Python、GIL/ABI、特性、命令、构建/运行结果、日志、跳过及阻断问题。
PyPy/GraalPy 嵌入条件与 CPython 不同，仅编译的测试保持“编译”状态。
前瞻 beta/nightly、实验功能和平台资源故障单独呈现，不把条件跳过计为行为通过。
跨平台支持范围扩大前，更新本表、发行记录、接口说明和支持政策。
