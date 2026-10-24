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
模板包含 r2p 发行依赖和必要私有适配器；注册表版本未启用时先使用本地路径/固定 Git SHA 验证。
本期没有实测远端 cargo-generate，不能把结构检查视为远端生成成功。

从根运行 `uv run --isolated --only-group nox nox -s test-py`，包含跨语言测试和各示例 Nox 会话。
部分示例依赖额外原生工具或 Python 包，实际验证范围见[SDK 验证](../docs/testing/reports/kernel-migration-validation.md)和[当前验证](../docs/testing/reports/production-baseline-validation.md)。

学习入口：[用户指南](../docs/guide/src/SUMMARY.md)；贡献和环境：[开发指南](../docs/development/developer-guide.md)。
