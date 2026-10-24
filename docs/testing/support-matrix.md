# 兼容性支持矩阵与证据

版本：2.0；日期：2026-10-24；状态：当前源码交付的证据矩阵。
关联：FR-005/006、NFR-001/003/005。
支持响应见[支持政策](../operations/support-policy.md)，准入要求见[测试策略](test-strategy.md)。

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
| Linux/Windows 与其他 CPU | CI 指定版本 | CPython/PyPy/GraalPy | CI 声明组合 | CI 配置存在；本期远端结果见当前报告 | 本地未验证，不能引用 macOS 结果代替 |
| CI 声明平台 | stable/MSRV | 其他 CPython 3.9–3.15 | 原生 ABI / abi3 | FFI 元数据和测试配置存在 | 逐行实测后升级证据等级 |
| CI 声明平台 | stable/MSRV | CPython 3.14t/3.15t | free-threaded / abi3t | 源码与 CI 存在 | 本地未运行；普通 abi3 不能替代 |
| WASI/Emscripten/跨编译目标 | CI 指定版本 | 对应目标解释器 | 目标构建配置 | infrastructure 和专门 CI 存在 | 单独核验目标导入/线程/链接限制 |
| WIP no_std | 指定工具链 | 对应构建条件 | R2P_WIP_NO_STD | WIP 源码和 CI 存在 | 保持实验标识，无完整 no_std 承诺 |

详细数量、命令和已有 ignored/skip 项见[SDK 内核迁移报告](reports/kernel-migration-validation.md)及其引用的[初始报告](reports/validation-report.md)。
最新目录、工作流和交付验证见[当前报告](reports/production-baseline-validation.md)。

## 2. 矩阵维护

每次 Python/Rust 下限、ABI、特性、平台、构建适配或源码版本变化时复核受影响行。
新增行记录完整 SHA、OS/CPU、Rust/Python、GIL/ABI、特性、命令、构建/运行结果、日志、跳过及阻断问题。
PyPy/GraalPy 嵌入条件与 CPython 不同，仅编译的测试保持“编译”状态。
前瞻 beta/nightly、实验功能和平台资源故障单独呈现，不把条件跳过计为行为通过。
跨平台支持范围扩大前，更新本表、发行记录、接口说明和支持政策。
