# SDK 内核命名空间迁移

日期：2026-10-24。
产品与 SDK 内核标识统一为 `r2p`，源码版本保留 `0.30.0`。
这是源码与模块名称的不兼容变更；注册表发布、仓库改名与站点部署不属于本次迁移。

## 使用方修改

| 原标识 | 当前标识 |
| --- | --- |
| `pyo3`、`pyo3-*` SDK crate | `r2p`、`r2p-*` |
| `use pyo3::prelude::*` | `use r2p::prelude::*` |
| `#[pyo3(...)]` | `#[r2p(...)]` |
| `pyo3_build_config::use_pyo3_cfgs()` | `r2p_build_config::use_r2p_cfgs()` |
| `PYO3_*` 构建变量 | `R2P_*` |
| `pyo3_disable_reference_pool` 等 SDK cfg | `r2p_disable_reference_pool` 等 |
| `pyo3-runtime` / `pyo3_runtime` | `r2p-runtime` / `r2p_runtime` |
| `pyo3-introspection` CLI | `r2p-introspection` CLI |
| `pyo3_pytests` 测试模块 | `r2p_pytests` 测试模块 |
| `PYO3_INTROSPECTION_1_*` | `R2P_INTROSPECTION_1_*` |

`Python`、`Py<T>`、`Bound`、`PyErr`、`PyResult`、`#[pyclass]`、`#[pyfunction]`、`#[pymodule]` 与 CPython 的 `Py_*` 标识维持原有语义。
内省 CLI 和二进制应来自同一 SDK 版本，迁移后重新编译扩展。

## 构建与打包

```bash
export R2P_PYTHON=/absolute/path/to/python
cargo check -p r2p
cargo test -p r2p --features full
```

当前 Maturin 通过依赖包名 `pyo3` / `pyo3-ffi` 识别绑定，Cargo 依赖别名不能改变它的判断。
因此 Maturin 示例额外依赖[私有适配器](../../tools/maturin-bridge/Cargo.toml)，其固定协议包名为 `pyo3-ffi`，Rust 库名为 `r2p_maturin_bridge`。
它重新导出 `r2p-ffi`，同步解释器元数据与 ABI 特性，`publish = false`，不进入 SDK 主包依赖图。

```toml
[dependencies]
r2p = { path = "/path/to/r2p" }
r2p-maturin-bridge = { package = "pyo3-ffi", path = "/path/to/r2p/tools/maturin-bridge" }

[features]
abi3 = ["r2p/abi3-py39", "r2p-maturin-bridge/abi3-py39"]
```

稳定 ABI 特性必须同时传给适配器，保证 wheel 标签与实际 ABI 一致。
生成模板自带私有适配器；2026-10-25 起默认将 SDK 和适配器固定到 `product.toml` 中同一已验证 Git SHA。
`tools/new_project.py` 支持显式 Git、本地 path 及已验证注册表版本三种来源，当前注册表准入列表为空。
仓库外生成、sdist/wheel 和嵌入验证入口见 [SDK 入门](../sdk/README.md)；迁移时使用的 path 方式仍适合本地开发。
setuptools-rust 示例使用 `binding = "NoBinding"` 与显式 `features = ["r2p/extension-module"]`，避免其默认绑定自动传入 `pyo3/extension-module`；应用 Rust 代码使用 `r2p`。

构建配置优先读取 `R2P_*`，值为空时也视为明确设置；未设置时才回退到外部打包工具传入的 `PYO3_*`。
两种变量变化均触发 Cargo 重建。
Cargo 元数据改为 `R2P_CONFIG`，FFI 的 `links` 为 `r2p-ffi-python`，主包为 `r2p-python`。
Maturin 自动传入的 `PYO3_BUILD_EXTENSION_MODULE` 仍可正确启用扩展链接模式。

## 来源保留

根许可证、组件版权、上游 README/贡献/发行归档、CHANGELOG 与既有发行片段保留历史身份。
上游问题链接、外部 GitHub Actions、Maturin/setuptools 的协议标识以及外部生态 crate 使用真实名称。
上游品牌素材保留在 `assets/branding/`，用于来源追溯。
依赖 PyO3 类型的第三方生态 crate 需要独立适配；不能仅修改其依赖名便视为兼容 r2p。

验证记录见[内核迁移验证](../testing/reports/kernel-migration-validation.md)，产品边界见[ADR-0002](../architecture/adr/0002-product-and-release-boundaries.md)。
