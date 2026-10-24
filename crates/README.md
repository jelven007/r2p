# Rust 辅助组件

主 `r2p` 包保留根 `Cargo.toml` 和 `src/`。
辅助组件与主库共用根 workspace 的版本、许可、MSRV 和测试流程。

| crate | 职责 |
| --- | --- |
| `r2p-ffi` | Python/C API、解释器和 ABI 条件编译；含独立 FFI 示例 |
| `r2p-build-config` | 解释器探测、链接、跨编译和条件配置 |
| `r2p-macros` | 用户过程宏入口 |
| `r2p-macros-backend` | 宏解析、校验、代码生成和内省元信息 |
| `r2p-introspection` | 二进制元信息读取及 `.pyi` 生成，实验组件 |

从根运行 `cargo test -p r2p-build-config` 等组件命令。
完整关系见[架构](../docs/architecture/system-design.md)，贡献与兼容见[开发指南](../docs/development/developer-guide.md)。
