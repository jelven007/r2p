# SDK 内核迁移验证

日期：2026-10-24。对应用户要求：将 SDK 内核标识 PyO3 改为 `r2p`。
本报告记录本地源码迁移与实际验证；远端 CI、注册表发布与站点部署未执行。
此前的[工程基线验证](validation-report.md)和[CI 修正验证](ci-fixes-validation.md)保留原始命令与结果，属于迁移前的历史证据。

## 变更范围

主 crate 与五个组件、Rust 导入与 `#[r2p(...)]` 属性、宏生成路径/符号、
`R2P_*` 构建变量、Cargo links/cfg/元数据、Python runtime/测试模块、
内省协议标识、stub、目录、基准与工具、示例/模板、CI 和指南已同步。
版本声明保持 `0.30.0`。使用方规则见[内核迁移说明](../development/kernel-namespace-migration.md)。

SDK 主包的正常与构建依赖图没有 `pyo3` 实现包。
Maturin 的固定探测包名由私有 `tools/maturin-bridge` 提供，解释器边界与 ABI 特性由仓库检查脚本核对。
setuptools-rust 示例使用 `NoBinding` 和显式 r2p 扩展特性。
Meson 使用现有本地打包适配后端，其要求 Rust 1.87+，从 1.85 的 Nox 依赖准备范围中排除。

## 环境与结果

本机 macOS arm64，Rust 1.99.1 / MSRV 1.85.1，CPython 3.14.9，Maturin 1.15.0。
工具链、Python、uv 和缓存位于 `.tools/`；运行日志为 `.tools/r2p-*.log`。

| 验证 | 结果 | 日志 |
| --- | --- | --- |
| full + all-targets 编译 | 通过 | `r2p-check.log` |
| 默认特性测试 | 885 单元；Rust 集成、59 项严格 UI 与 482 项 doctest 通过 | `r2p-test-default.log` |
| full 特性测试 | 1090 单元；Rust 集成、59 项严格 UI 与 502 项 doctest 通过 | `r2p-test-full.log` |
| 无默认特性 | 806 单元通过 | `r2p-no-default.log` |
| 五个 SDK 组件 | 107 单元与 3 项 doctest 通过 | `r2p-test-components.log` |
| ABI3 严格 UI | 59 项通过 | `r2p-ui-abi3.log` |
| Python 行为 | 197 项通过 | `r2p-python-tests.log` |
| 内省与 stub | 普通、stripped、fat 三种二进制输出一致；16 项 stub 检查通过 | `r2p-introspection.log` |
| 打包示例 | 九个示例均构建/安装并通过各自 pytest | `r2p-example-*.log`、`r2p-retest-*.log`、`r2p-setuptools-retest.log` |
| MSRV | Nox 依赖准备通过；1.85.1 的 full + all-targets + locked 编译通过 | `r2p-msrv-prepare.log`、`r2p-msrv.log` |
| 构建变量兼容 | 新变量优先、旧变量回退、空值优先、不覆盖错误新解释器四项通过 | `r2p-env-compatibility.log` |
| ABI3 wheel | `cp39-abi3-macosx_11_0_arm64` 标签；安装后 Rust 类创建/getter/setter 通过 | `r2p-abi3-wheel.log`、`r2p-wheel-smoke.log` |
| Python runtime | sdist → wheel 构建；安装/导入 `r2p_runtime` 及许可证正文校验通过 | `r2p-runtime-build.log`、`r2p-wheel-smoke.log` |
| 内省 CLI wheel | `r2p_introspection-0.30.0` 二进制 wheel 构建通过 | `r2p-introspection-wheel.log` |
| 六个 Rust 制品 | `r2p` 和五组件 `.crate` 打包通过 | `r2p-sdk-package.log` |
| 文档 | Rust API 文档、mdBook 构建通过 | `r2p-docs-guide.log`、`r2p-guide-final.log` |
| 规范与身份 | rustfmt、Ruff 格式/检查；仓库路径、SDK 版本/名称、适配器/模板 ABI 元数据检查 | 仓库检查入口 `tools/check_repository.py` |

九个示例为 maturin-starter、setuptools-rust-starter、meson-starter、decorator、
getitem、word-count、plugin_api、FFI string-sum、FFI sequential。
编译诊断快照共修正 21 个文件，仅涉及 `pyo3` → `r2p` 后的列号与插入符位置；严格门禁保持启用。

首次使用既有 stable 锁文件执行 MSRV 检查时，部分最新依赖要求更高 Rust 版本；
按 CI 的 `set-msrv-package-versions` 流程采用兼容版本后通过。
setuptools 的旧自动特性、Meson 的跨 workspace path 限制及 plugin_api 缺少动态版本声明已修正并复测。

## 证据边界

Rust 制品使用 `cargo package --no-verify --allow-dirty --exclude-lockfile`；
制品打包与本地源码编译/运行分别验证，未宣称通过注册表下载验证。
模板适配器与保留钩子做结构检查；未执行 cargo-generate 的远端生成。
上述矩阵不覆盖 Windows/Linux、全部 Python 实现/版本、free-threaded 或跨编译目标。
mdBook 仍报告既有 `class/protocols.md` 的 details 标签警告，构建成功。

根许可证、Python runtime 许可证、三份上游归档和 CHANGELOG 与迁移前逐字节一致。
上游问题/历史链接、外部生态 crate、GitHub Actions 与打包工具协议保持真实身份。
完整迁移前快照与目录映射位于忽略目录 `.tools/r2p-kernel-migration/`。
