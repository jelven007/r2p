# 工程工具

| 工具 | 作用 | 运行条件 |
| --- | --- | --- |
| `check_repository.py` | 产品身份一致性、Cargo 本地路径、工程文档链接、指南 include、doctest 输入和需求追踪检查 | Python 3.11+；从任意目录可运行 |
| `check_workflows.py` | actionlint 工作流结构/表达式检查；临时副本兼容当前 GitHub `$/` 语法 | Python 3.11+、actionlint；源码仍使用 `$/` |
| `dev.py` | 指定受测 Python 启动 Nox；记录环境和命令结果 | 工具 Python 3.14+、uv、Rust；目标 Python 须已安装 |
| `new_project.py` | 生成独立项目；SDK 与适配器统一 Git SHA/path/已验证注册表来源 | Python 3.11+、Git；不覆盖已有目录 |
| `consumer_smoke.py` | 九个模板依赖图、sdist 重建、普通/abi3 wheel 隔离安装和嵌入异常验证 | `python -m tools.consumer_smoke --output target/consumer-check`；Python 3.14、uv、Rust |
| `candidate.py` | 六个 SDK crate 的独立 sparse 注册表消费、三种 wheel 安装和 baseline 恢复 | Python 3.14、uv、Rust；不同完整 SHA；输出目录须不存在 |
| `candidate_artifacts.py` | 原始 crate/wheel 内容、精确依赖、源码、哈希和恢复 manifest 复验；CLI 行为探针 | `python -m tools.candidate_artifacts verify --manifest <path> --sha <SHA> --output <path>` |
| `release_gate.py` | 要求发行源码对应完整 CI 的全部必需任务与候选制品通过 | 已完成 Actions run、GitHub 权限；本地制品不替代完整远端 CI |
| `publish_candidate.py` | 保留验收过的原始 crate 字节进行上传；默认仅验证请求 | 同 SHA gate；执行需显式 --execute、发行开关及 registry token |
| `cli_wheel_acceptance.py` | 本机安装/执行 CLI wheel，核验七个原生平台制品集合 | 原始 wheel、完整 SHA、平台 ID；集合完整不代表本机执行了七个平台 |
| `performance.py`、`performance_report.py` | 同环境独立进程采样、编译/RSS/大小成本、描述统计与原始数据报告 | 明确基线/候选 SHA 和解释器；样本报告不自动判定 5% 门限 |
| `upstream_sync.py` | 固定上游修订、映射变更、隔离重放和本地差异清单 | 本地 Git 历史、清晰来源；不改主工作区或历史标签 |
| `verify_environment.py` | 实测 FT GIL 开/关、旧 C 扩展导入后的状态、旧解释器及安装失败 | macOS、clang、uv，显式提供普通/FT/旧 Python；不代表 SDK 全矩阵 |
| `inspect_windows_imports.py` | 读取 PE 导入表，调查 Windows Python/PyPy 动态库缺失 | Python、pefile；目标 DLL/EXE 原始文件 |
| `ci_policy.py` | 根据真实变更/事件选择检查，汇总阻断异常跳过和遗漏 | `python -m tools.ci_policy check`；CI select/conclude 使用事件与 needs JSON |
| `engineering/ci_matrix.py` | 构建、Clippy、内省、跨编译、CLI 等执行组合与发行允许结果的统一定义 | Python 3.11+；稳定 ID、动态工作流和 gate 单源；矩阵修改进入完整验证 |
| `evidence.py` | 校验 SHA/实际 GIL/步骤等级/理由；导入 Actions、离线导出、本地/候选/性能/环境数据，生成摘要 | Python 3.11+；`python -m tools.evidence check`，同 ID 不覆盖；缺少实际观测时 unrecorded |
| `engineering/`、`tests/` | 无副作用的特性矩阵、参数契约、环境快照和 MSRV 隔离；标准库回归 | `python -m unittest discover -s tools/tests` |
| `ffi-check/` | 对照 Python 头文件生成的 bindgen 定义与手写 FFI | 独立 workspace；Python 头文件、libclang 和可链接库 |
| `maturin-bridge/` | 为 Maturin 提供固定协议包名；转发 r2p FFI 与 ABI 特性 | 私有、禁止发布；仅打包示例和测试依赖 |

从根运行 `python tools/check_repository.py` 或 `uv run --isolated --only-group nox nox -s repository-check ffi-check`。
检查脚本不验证外网 URL、Markdown 锚点或业务正确性。

FFI 工具细节见[工具说明](ffi-check/README.md)；其他命令见[开发指南](../docs/development/developer-guide.md)。
SDK 名称、适配器元数据与 ABI 特性同步由仓库检查脚本验证；迁移规则见[内核命名空间迁移](../docs/development/kernel-namespace-migration.md)。
本机工具与缓存置于忽略目录，不提交运行制品。
