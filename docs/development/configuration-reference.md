# r2p 构建配置注册表

版本：2.0；日期：2026-10-24；状态：当前源码配置契约。
源码依据：[环境读取与配置解析](../../crates/r2p-build-config/src/impl_.rs)、[构建逻辑](../../crates/r2p-ffi/build.rs)。

## 1. 读取与优先级

`R2P_*` 是 SDK 配置入口。
仅当对应新变量未设置时，环境读取边界回退到同名后缀 `PYO3_*`，兼容现有打包工具。
新变量存在但为空时仍优先；非法新解释器不会因旧变量有效而被忽略。
包名、Rust 导入、内省格式和模块名不提供这种环境变量兼容。
已验证四种优先级情形，见[内核迁移报告](../testing/reports/kernel-migration-validation.md)。

| 变量 | 输入/含义 | 缺省与操作规则 | 影响 |
| --- | --- | --- | --- |
| `R2P_PYTHON` | Python 可执行文件路径/名称 | 未设时按虚拟环境和默认解释器探测；记录实际选择 | API/ABI、架构、链接 |
| `R2P_CONFIG_FILE` | 绝对路径的解释器配置文件 | 未设时使用探测；文件格式按源码解析 | 固定目标配置，避免误用宿主 |
| `R2P_PRINT_CONFIG` | 构建诊断开关 | 用于输出构建配置并停止诊断构建，随后移除再构建 | 配置定位，不计为构建成功 |
| `R2P_NO_PYTHON` | 存在即选择无本机 Python 路径 | 仅用于支持的稳定 ABI/跨编译配置，不是通用禁用解释器 | ABI/链接探测 |
| `R2P_BUILD_EXTENSION_MODULE` | 存在即启用扩展链接模式 | 通常由打包工具设置；不要在嵌入测试全局设置 | 动态库与 libpython 链接 |
| `R2P_CROSS` | 存在即强制跨编译配置 | 与目标 triple 及下列配置一起核对 | 宿主/目标分离 |
| `R2P_CROSS_LIB_DIR` | 目标 Python 库/配置目录 | 需要匹配目标架构和 sysconfig 信息 | 目标链接/布局 |
| `R2P_CROSS_PYTHON_VERSION` | 目标主/次 Python 版本，可含线程标记 | 不得由宿主版本猜测；与 abi3/abi3t 下限一致 | 条件 API/GIL |
| `R2P_CROSS_PYTHON_IMPLEMENTATION` | 目标实现名称 | 按源码允许值填写，如 CPython/PyPy/GraalPy | 实现差异 |
| `R2P_ENVIRONMENT_SIGNATURE` | 环境变更标识 | 改变时触发重新构建，不能替代真实配置 | 缓存一致性 |
| `R2P_WIP_NO_STD` | WIP 构建选择 | Cargo/Meson 分别读取；保持实验边界 | 非完整 no_std 承诺 |
| `UI_TEST` | `ignore` / `skip` 等测试模式 | stable 合并验收使用严格模式；跳过单独报告 | 编译诊断证据 |
| `RUSTUP_TOOLCHAIN` | stable/MSRV/指定 Rust | 与缓存和诊断快照配套 | Rust 兼容 |
| `CARGO_TARGET_DIR` | 构建输出目录 | MSRV/覆盖/跨编译按需隔离 | 缓存/产物 |

存在性开关不能通过设置为字符串 `0` 假定关闭；关闭时应移除变量。
不要批量打印整个环境，诊断只记录相关变量及脱敏后的路径。

## 2. 场景配置

嵌入测试使用可链接的 Python，例如 `R2P_PYTHON=python3.14 cargo test -p r2p --lib --locked`。
扩展构建从示例的 pyproject/Nox 入口执行，Maturin 通过私有适配器将 ABI 特性转发给 r2p。
setuptools-rust 示例采用 `NoBinding` 和显式 r2p 扩展特性；Meson 使用本地后端和 Rust 1.87+。
交叉编译必须先确认目标解释器实现、版本、架构、GIL、ABI、库路径和 linker；本机成功不能替代目标导入验证。

## 3. 外部发行开关

GitHub 仓库变量 `R2P_ENABLE_CRATES_IO`、`R2P_ENABLE_PYPI`、`R2P_ENABLE_NETLIFY` 仅在相应值为 `true` 时允许发布/部署 job。
未设置时默认关闭；Git 推送和 `history/*` 标签不等于外部发行。
这些是发行控制变量，与 SDK 编译变量无关。
启用时引用[发行准入记录](../releases/release-and-rollback.md)，核对具体平台环境/OIDC 及已验收制品。
