# 测试入口与环境隔离优化验证

日期：2026-10-25；范围：O-01、O-03 的本地实现验收。
来源：基线 `3a24917eb2766aa8ded8c04fefde1c1d4b133c00` 上的工作树修改；实现与本报告一同提交。
平台：macOS arm64，CPython 3.14.9（GIL），Rust stable 1.99.1 / MSRV 1.85.1。
本记录不替代本次 PR 的远端平台矩阵。

## 实现

- `test-rust` 显式校验参数，保留 `skip-full`、`careful`、`release`，新增组件/core/ABI/UI 局部 scope。
- 完整兼容矩阵抽取到 `tools/engineering/matrix.py`；Nox 的 40 个会话名及顺序保持一致。
- coverage 报告参数与 Rust 测试参数分开；失败时恢复原始报告参数。
- `.python-version` 固定默认工程 Python；`tools/dev.py` 以目标 Python 运行 Nox，记录工具和目标环境、配置/锁摘要、命令及结果。
- MSRV 会话自动复制当前源码，在保留的隔离目录解析依赖、运行后续会话并保存锁；CI 上传对应证据。
- `r2p-build-config` 继承工作区 lints，没有新增豁免。

## 实测

以下 Nox 命令通过工具入口 `python3.14 tools/dev.py --evidence <json> -- ...` 执行。
工具日志时间为 UTC，报告日期按当前工作日期记录。

| 检查 | 命令/范围 | 结果 |
| --- | --- | --- |
| 快速 Rust | `-s test-rust -- skip-full` | 6 条 Cargo 命令成功，无 full；约 81 秒 |
| 完整 Rust | `-s test-rust` | 11 条 Cargo 命令成功，包含 full、abi3、abi3-py39、UI 和 doctest；约 951 秒 |
| 严格 UI | 上述完整会话 | `UI_TEST` 未设置，使用默认严格诊断；保留用例自身的 ignored/filtered 条件 |
| 错误参数 | `-s test-rust -- skip-ful` | 退出码 1，未执行 Cargo |
| 目标解释器 | `--target-python /usr/bin/python3 -- --list-sessions` | 工具 3.14.9、目标 3.9.6 分别记录，目标 Nox 启动成功；不计为 3.9 SDK 行为验证 |
| 会话契约 | 与基线 AST 会话清单比较 | 40 个名称和顺序一致 |
| 命令/环境回归 | `python -m unittest discover -s tools/tests -p test_nox_contract.py` | 9 项成功；特性矩阵覆盖 96 种版本/GIL/平台/nightly 条件 |
| MSRV 依赖准备 | Rust 1.85.1，`-s set-msrv-package-versions` | 原锁不变，9 个实际 Cargo.lock 保存在隔离目录，约 16 秒 |
| MSRV 编译矩阵 | Rust 1.85.1，`-s set-msrv-package-versions -- check-all` | 隔离副本内 52 条 Cargo check 全部通过，9 个锁文件保留，原锁不变；约 1,032 秒 |
| 构建配置 lint | `cargo clippy -p r2p-build-config --all-targets --locked -- --deny=warnings` | 成功 |
| 格式与仓库 | Ruff、rumdl、rustfmt、repository-check | 成功 |
| 工作流 | actionlint（11 个工作流）、zizmor（受影响 CI） | 成功；zizmor 无新增发现 |

原始环境、结果和日志保存在本地 `target/optimization/{quick,full,invalid,target-python39,msrv,msrv-check}.{json,log}`。
它们是本地验证记录，未作为公开 CI 日志冒用；后续远端结果单独关联。
完整与快速的时间是单次工程执行样本，不能作为运行时性能提升数据。
跨配置通过计次为快速 1,650、完整 7,696，包含重复用例和 doctest，不表示去重测试数量。

原工作区 Cargo.lock 的 SHA-256 为 `16cc70db1ee458ab2f766fe09d76eec183bbe1aef0447bc5fce9cc255f4a7ea1`。
MSRV 源码副本包含当时未提交的源码修改，不包含忽略的工具或构建缓存。
`check-all` 使用构建配置模拟解释器组合，仅属于编译证据；PyPy/GraalPy、free-threaded 的实际运行支持仍须各自的运行测试。
