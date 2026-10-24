# 使用与打包示例

现有示例包括 maturin、setuptools-rust、Meson、Rust 嵌入和其他扩展集成，按各示例清单和说明运行。
FFI 独立示例位于 `crates/r2p-ffi/examples/`。

| 示例 | 目的 |
| --- | --- |
| `decorator` | 可调用对象/装饰器实现 |
| `maturin-starter` | maturin 扩展开发模板 |
| `meson-starter` | meson-python 构建模板 |
| `setuptools-rust-starter` | setuptools-rust 构建模板 |
| `plugin` | Rust 应用使用 Python 脚本 |
| `word-count` | 使用 Rust 进行文本计数的扩展示例 |

根 `examples/Cargo.toml` 组织示例清单；生成模板在 `.template/` 下维护，模板中的发行版本依赖与本地开发路径用途不同。

复制上游模板可使用 cargo-generate；此命令生成一个新的消费项目：

```bash
cargo install cargo-generate
cargo generate --path /path/to/r2p examples/<example>
```

`<example>` 替换为具体模板目录。
本仓库尚未提交的目录迁移不能通过远端生成命令获取；修改本地模板时按 cargo-generate 的本地路径方式验证。

从根运行 `uv run --isolated --only-group nox nox -s test-py`，包含跨语言测试和各示例 Nox 会话。
部分示例依赖额外原生工具或 Python 包，实际验证范围见[验证报告](../docs/testing/validation-report.md)。

学习入口：[用户指南](../docs/guide/src/SUMMARY.md)；贡献和环境：[开发指南](../docs/development/developer-guide.md)。
