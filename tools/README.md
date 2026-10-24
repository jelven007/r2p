# 工程工具

| 工具 | 作用 | 运行条件 |
| --- | --- | --- |
| `check_repository.py` | 产品身份一致性、Cargo 本地路径、工程文档链接、指南 include、doctest 输入和需求追踪检查 | Python 3.11+；从任意目录可运行 |
| `ffi-check/` | 对照 Python 头文件生成的 bindgen 定义与手写 FFI | 独立 workspace；Python 头文件、libclang 和可链接库 |
| `maturin-bridge/` | 为 Maturin 提供固定协议包名；转发 r2p FFI 与 ABI 特性 | 私有、禁止发布；仅打包示例和测试依赖 |

从根运行 `python tools/check_repository.py` 或 `uv run --isolated --only-group nox nox -s repository-check ffi-check`。
检查脚本不验证外网 URL、Markdown 锚点或业务正确性。

FFI 工具细节见[工具说明](ffi-check/README.md)；其他命令见[开发指南](../docs/development/developer-guide.md)。
SDK 名称、适配器元数据与 ABI 特性同步由仓库检查脚本验证；迁移规则见[内核命名空间迁移](../docs/development/kernel-namespace-migration.md)。
本机工具与缓存置于忽略目录，不提交运行制品。
