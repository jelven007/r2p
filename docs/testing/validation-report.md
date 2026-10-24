# 本次工程迁移验证报告

日期：2026-10-24；状态：本机验证记录。
源码基线：`424149e8a1c42128b05a090941673008fc46c478`；工作分支：`refactor/production-layout-docs`。
下述结果包含基于该 SHA 的本地未提交目录、配置和文档变更。
后续 MSRV 特性任务和 CI 汇总修正的新增证据见[CI 修正验证](ci-fixes-validation.md)；本报告保留目录迁移阶段的原验证范围。

## 1. 结论范围

已执行主库、组件、严格 UI、doctest 和 Python 扩展测试，验证迁移后的主要构建与语言交互链路。
仓库/格式、类型内省、Rustdoc、指南构建和本次选定的制品检查均通过。
854 个基线文件均保留，354 个文件迁移到新目录，四份上游文档原文保持逐字节一致。

本机结果仅覆盖 macOS arm64、Rust stable 1.99.1 和 CPython 3.14.9 有 GIL 模式。
未据此判定所有解释器/平台/ABI 兼容或正式生产发行通过。

## 2. 环境和复现

| 项目 | 实际条件 |
| --- | --- |
| 操作系统/架构 | macOS / arm64；Rust target `aarch64-apple-darwin` |
| Rust/Cargo | stable 1.99.1；rustfmt、rust-src |
| Python | uv 管理的 CPython 3.14.9；默认有 GIL |
| 工具 | uv 0.13.5、Nox、ruff、rumdl；mdBook 0.5.4、mdbook-tabs 0.3.4；工程工具按锁文件解析 |
| 源码 | 上述基础 SHA + 当前工作区修改；未提交、未推送 |
| 本地输出 | `.tools/*.log`、`target/`、`.nox/`、`.venv/`，均由 Git 忽略 |

本机工具放在工作区忽略目录，以下配置只用于复现本机验证：

```bash
export CARGO_HOME="$PWD/.tools/cargo"
export RUSTUP_HOME="$PWD/.tools/rustup"
export PATH="$PWD/.tools/uv-bootstrap/bin:$PWD/.tools/cargo/bin:$PWD/.venv/bin:$PATH"
export UV_CACHE_DIR="$PWD/.tools/uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.tools/python"
export PYO3_PYTHON="$PWD/.tools/python/cpython-3.14.9-macos-aarch64-none/bin/python3.14"
```

团队可用已有工具，正常入口见[开发指南](../development/developer-guide.md)。
实际 Python/Nox 命令由 `uv run --python "$PYO3_PYTHON" --isolated --only-group nox nox` 启动，以确保 Nox 本身运行于对应解释器。

## 3. 执行结果

| 检查 | 命令/模式 | 实际结果 | 本地证据 |
| --- | --- | --- | --- |
| 主库编译 | `cargo check -p pyo3` | 通过 | `.tools/cargo-check.log` |
| 主库默认单元 | `cargo test -p pyo3 --lib` | 885 通过，0 失败 | `.tools/test-lib-314.log` |
| 主库 full 单元 | `cargo test -p pyo3 --features full` | 1090 通过，0 失败 | `.tools/test-full.log` |
| full 集成 | 同上 | 普通集成 389 通过，1 个已有 ignored | `.tools/test-full.log` |
| 严格 UI | 同上，未设置 `UI_TEST` | 59 通过、10 ignored、7 条件过滤；未改快照 | `.tools/test-full.log` |
| full doctest | 同上 | 502 通过、99 ignored；含迁移后指南/README 和 compile-fail 示例 | `.tools/test-full.log` |
| 五个组件 | `cargo test -p pyo3-build-config -p pyo3-macros-backend -p pyo3-macros -p pyo3-ffi -p pyo3-introspection` | 107 单元 + 3 doctest 通过；4 doctest ignored | `.tools/test-components.log` |
| Python 扩展 | 下方 Nox 命令；maturin 构建/安装 | 197 通过，0 失败；常规会话按上游规则排除 stub 专项 | `.tools/test-python.log` |
| 内省/stub | Nox `test-introspection`，experimental-async/inspect | 原始、stripped、fat Mach-O 生成 stub 均一致；16 通过、2 因无 `__all__` 跳过 | `.tools/test-introspection.log` |
| Rustdoc | Nox `docs`，warnings 视为错误 | workspace 文档构建通过 | `.tools/rustdoc.log` |
| 用户指南 | Nox `build-guide` | 成功生成 `target/guide/`；已有 HTML 警告见下文 | `.tools/guide-build.log` |
| 独立 workspace | 下方两条 metadata 命令 | 基准和 FFI 工具清单解析通过 | `.tools/metadata-*.json` |
| Rust 候选文件 | `cargo package` 对根和五个组件执行 `--allow-dirty --list` | 清单生成通过；根包 299 个候选文件，必要 include/许可齐全，非 SDK 分组排除 | `.tools/package-list*.log`、`.tools/artifact-integrity.log` |
| Python runtime 制品 | `uv build --python "$PYO3_PYTHON" python/pyo3-runtime --out-dir .tools/runtime-dist` | sdist → wheel 构建成功；两份许可证正文一致；独立 target 安装/导入 `0.0.1` 成功 | `.tools/build-python-runtime.log`、`.tools/runtime-import.log` |
| 完整格式/静态入口 | Nox `fmt` | fmt、ruff、rustfmt、rumdl、check-test-features、repository-check、typos 七项均成功 | `.tools/fmt.log` |
| 路径/追踪/许可 | `python tools/check_repository.py`（3.14） | 23 个 Cargo 清单、30 份工程文档、本地链接、指南 include、doctest、16 条需求追踪、许可证检查通过 | `.tools/fmt.log` |

默认单元与 full 单元存在重叠，不能相加为独立测试总量。
full 主库合计 2040 通过、110 ignored、7 条件过滤；包括 UI，未包含单独组件和 Python 测试。
ignored/过滤是已有测试规则或特性条件，不能解释为本次通过的场景。

关键独立命令：

```bash
cargo metadata --no-deps --format-version 1
cargo metadata --manifest-path benchmarks/pyo3-benches/Cargo.toml --no-deps --format-version 1
cargo metadata --manifest-path tools/ffi-check/Cargo.toml --no-deps --format-version 1
uv run --python "$PYO3_PYTHON" --isolated --only-group nox nox -f tests/python/noxfile.py --default-venv-backend uv --force-python "$PYO3_PYTHON" -s test
uv run --python "$PYO3_PYTHON" --isolated --only-group nox nox --default-venv-backend uv -s test-introspection
```

## 4. 文件保全与迁移修复

基线有 854 个 Git 跟踪文件。
按[迁移映射](../development/repository-layout.md)逐项检查：354 个文件迁移，缺失 0 个；13 个原目录均已移除。
30 个既有普通文件因入口文档、清单、工具/CI 路径、指南 include 和测试提示产生修改，其余普通文件与基线 blob 一致。
保全证据为 `.tools/migration-integrity.log`。

发现并修复：10 个组件/Python 包许可证符号链接原指向 `../LICENSE-*`，移入第二层目录后失效。
8 个 Rust 组件链接已改为 `../../LICENSE-*`。
Python 运行时包的 2 个链接改为根许可证的普通文件副本，解决隔离 sdist 构建拒绝越出包根链接的问题。
修正保留根许可证原文，不改许可内容。
仓库检查增加符号链接和 Python 许可证副本内容检测；sdist 与 wheel 的许可证正文均已与根文件比对通过。

四份根文档的上游原文分别保存在 `docs/reference/upstream-*.md`；Git blob 哈希比对均与原文一致。
结束前重新读取远端 `main`，仍为本报告的基础 SHA。

## 5. 初始失败与处置

初次主库测试自动选择本机 Xcode Python 3.9；链接器找不到所配置的 libpython，日志为 `.tools/test-lib.log`。
改用工作区内可链接的 CPython 3.14.9 后，同一主库测试通过。
该失败不构成 Python 3.9 不兼容结论；3.9 的正式平台验证仍未执行。

启动工具时纠正了 Nox 参数：当前使用 `--default-venv-backend uv`；未参数化会话使用 `--force-python` 选择解释器。
前两次启动失败发生在测试收集前，不算行为测试失败。

初次格式检查发现新增中文文档没有按上游规则每句一行、Nox 路径语句需要格式化、检查脚本 import 分组不匹配；已修正并通过完整 `fmt`。
uv 首次同步开发环境移除了用于启动的同环境 uv，改用独立忽略目录 `.tools/uv-bootstrap/bin/uv` 后复验通过。

指南生成有两条继承自 `class/protocols.md` 的 `<details>` 标签平衡警告，构建退出成功；该文件内容与基线一致，本次未修复其 HTML 结构。

未使用 UI bless、ignore 或 skip 掩盖严格诊断；没有修改运行时算法、公开 API、包身份或版本声明。

## 6. 未覆盖与生产门禁

| 范围 | 当前结论 | 下一步 |
| --- | --- | --- |
| Rust MSRV 1.85、beta/nightly | 未运行 | 按 Nox/CI 依赖条件执行 |
| Linux/Windows、其他架构 | 未运行 | 完整平台矩阵 |
| 其他 CPython、PyPy、GraalPy | 未运行 | 支持口径确认后逐行构建/运行 |
| free-threaded、abi3/abi3t、所有特性组合、WIP no_std | 未完整验证 | 按独立组合测试；本次 full 不代表 all-features |
| 完整 `test-py` 全部消费方示例 | 未运行全部 | 首期使用的打包/嵌入示例及完整 CI |
| FFI 头文件对照、WASI/Emscripten | 未运行 | 准备额外原生/交叉工具后执行 |
| 性能、覆盖率、外网链接/锚点 | 未执行完整测量 | 建立基线和对应工具验证 |
| Rust 注册表候选包隔离编译/安装 | 只检查候选文件，尚未完成 | 解决发行身份和精确版本依赖，执行 G5 |
| 远端 CI、权限、正式发行、线上部署与恢复演练 | 未执行 | Q-01–Q-05 与 G4–G6 |

G1 与本次选定的 G2/G3 回归通过；未执行的特性和平台行保持未验证，G4–G6 不具备完成证据。
生产就绪结论需覆盖所有必需矩阵、制品、责任和恢复条件。
