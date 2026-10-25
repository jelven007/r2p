# 工程工具

| 工具 | 作用 | 运行条件 |
| --- | --- | --- |
| `check_repository.py` | 产品身份一致性、Cargo 本地路径、工程文档链接、指南 include、doctest 输入和需求追踪检查 | Python 3.11+；从任意目录可运行 |
| `check_workflows.py` | actionlint 工作流结构/表达式检查；临时副本兼容当前 GitHub `$/` 语法 | Python 3.11+、actionlint；源码仍使用 `$/` |
| `dev.py` | 指定受测 Python 启动 Nox；记录环境和命令结果 | 工具 Python 3.14+、uv、Rust；目标 Python 须已安装 |
| `new_project.py` | 生成独立项目；SDK 与适配器统一 Git SHA/path/已验证注册表来源 | Python 3.11+、Git；不覆盖已有目录 |
| `consumer_smoke.py` | 九个模板依赖图、sdist 重建、普通/abi3 wheel 隔离安装和嵌入异常验证 | `python -m tools.consumer_smoke --output target/consumer-check`；Python 3.14、uv、Rust |
| `ci_policy.py` | 根据真实变更/事件选择检查，汇总阻断异常跳过和遗漏 | `python -m tools.ci_policy check`；CI select/conclude 使用事件与 needs JSON |
| `engineering/ci_matrix.py` | PR 10 / 完整 45 个构建组合的统一定义 | Python 3.11+；矩阵修改进入完整验证 |
| `evidence.py` | 校验 SHA/环境/结果/理由、导入已完成 Actions 或本地快照、生成支持摘要 | Python 3.11+；`python -m tools.evidence check`，同 ID 不覆盖 |
| `engineering/`、`tests/` | 无副作用的特性矩阵、参数契约、环境快照和 MSRV 隔离；标准库回归 | `python -m unittest discover -s tools/tests` |
| `ffi-check/` | 对照 Python 头文件生成的 bindgen 定义与手写 FFI | 独立 workspace；Python 头文件、libclang 和可链接库 |
| `maturin-bridge/` | 为 Maturin 提供固定协议包名；转发 r2p FFI 与 ABI 特性 | 私有、禁止发布；仅打包示例和测试依赖 |

从根运行 `python tools/check_repository.py` 或 `uv run --isolated --only-group nox nox -s repository-check ffi-check`。
检查脚本不验证外网 URL、Markdown 锚点或业务正确性。

FFI 工具细节见[工具说明](ffi-check/README.md)；其他命令见[开发指南](../docs/development/developer-guide.md)。
SDK 名称、适配器元数据与 ABI 特性同步由仓库检查脚本验证；迁移规则见[内核命名空间迁移](../docs/development/kernel-namespace-migration.md)。
本机工具与缓存置于忽略目录，不提交运行制品。
