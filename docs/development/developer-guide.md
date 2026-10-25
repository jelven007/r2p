# 开发指南

版本：2.1；日期：2026-10-25；状态：当前源码研发流程。
关联：FR-001–FR-008、NFR-001、NFR-003–NFR-006。

## 1. 环境要求

| 工具/条件 | 要求 | 说明 |
| --- | --- | --- |
| Rust / Cargo | Rust 1.85+，stable 日常开发 | MSRV 单独验证；UI 快照与工具链有关 |
| Python | SDK 以声明支持版本测试 | 嵌入测试需要有效 libpython/框架链接 |
| uv / Nox 工程环境 | 工程默认 Python 3.14 | 与 SDK 最低 Python 3.9 分开 |
| rustfmt / clippy / rust-src | 对应工具链组件 | rust-src 用于匹配编译诊断测试环境 |
| C/C++ 工具链 | 操作系统对应编译/链接工具 | FFI 校验还需要 Python 头文件和 libclang |
| mdBook / mdbook-tabs | 构建指南时安装 | 指南使用 mdBook 0.5 系列预处理接口 |

本次本机验证工具安装在忽略目录；团队可以使用已有全局工具。
不要将本机绝对路径写入仓库共享配置。

## 2. 获取与同步

```bash
git clone https://github.com/jelven007/r2p.git r2p
cd r2p
git status --short --branch
git fetch origin
git log -1 --format=fuller origin/main
```

`r2p` 是产品、SDK 和交付仓库名称。
在干净分支同步；已有工作先保留。
维护分支可按团队约定 merge/rebase；目录结构已调整后，未来同步上游需要处理映射冲突并验证，不能认为普通 `git pull` 自动保证所有路径有效。

日常从 `main` 创建需求/缺陷分支，通过 PR 和相关检查合并；上游同步单独处理。
本次分支与恢复点见[交付记录](../releases/records/2026-10-24-production-baseline.md)。

## 3. 快速检查

从根目录执行：

```bash
cargo metadata --no-deps --format-version 1
cargo check -p r2p --locked
cargo test -p r2p --lib --locked
uv run --isolated --only-group nox nox -s repository-check
uv run --isolated --only-group nox nox -s fmt
```

必要时指定 Python：

```bash
R2P_PYTHON=python3.14 cargo test -p r2p --lib
uv run --only-group nox python tools/dev.py --target-python /path/to/python3.14 --evidence target/environment.json -- -s test-rust -- skip-full
```

`R2P_PYTHON` 需指向实际安装的解释器。
`.python-version` 固定默认工程 Python 为 3.14；`tools/dev.py` 由工具 Python 运行，再以指定的目标 Python 启动 Nox。
因此会话中的 `sys.version_info`、实现和 GIL 状态与 Rust 的 `R2P_PYTHON` 一致；直接运行 Nox 时也须自行保证这一点。
`--target-python` 优先于已有 `R2P_PYTHON`，未指定时取该环境变量或启动器的实际解释器。
快照保存工具/目标 executable、版本、GIL、Rust、目标 triple、Nox 参数、配置文件与锁文件摘要，以及开始/结束时间和退出码。
跨编译配置只表示目标构建条件，不将工具或宿主解释器的版本记为目标运行验证。
多解释器开发记录完整命令和环境；不要长期保留无意的扩展构建变量导致嵌入测试链接失败。
新旧构建变量的优先级、空值和扩展/嵌入条件见[配置注册表](configuration-reference.md)。

## 4. 验证入口

| 工作 | 命令 |
| --- | --- |
| 快速 Rust 特性集 | `uv run --isolated --only-group nox nox -s test-rust -- skip-full` |
| 完整 Rust 测试 | `uv run --isolated --only-group nox nox -s test-rust` |
| 跨语言和示例 | `uv run --isolated --only-group nox nox -s test-py` |
| Python 测试单独运行 | `uv run --isolated --only-group nox nox -f tests/python/noxfile.py -s test` |
| 内省 / stub | `uv run --isolated --only-group nox nox -s test-introspection` |
| 格式/静态检查 | `uv run --isolated --only-group nox nox -s fmt clippy` |
| 基准 | `uv run --isolated --only-group nox nox -s bench` |
| FFI 头文件对照 | `uv run --isolated --only-group nox nox -s ffi-check` |
| Rust API 文档 | `uv run --isolated --only-group nox nox -s docs` |
| 用户指南 | `uv run --isolated --only-group nox nox -s build-guide` |
| 文档链接完整检查 | `uv run --isolated --only-group nox nox -s check-guide` |
| 覆盖 | `uv run --isolated --only-group nox nox -s coverage -- --lcov` |

`test-rust` 默认保留完整矩阵，`skip-full` 跳过含 `full` 的组合及其 UI/前向 ABI 派生测试。
CPython 3.14、GIL、stable 下为完整 11 条、快速 6 条 Cargo 命令；其他解释器按适用 ABI 选择。
`release`、`careful` 可继续组合使用；未知参数在执行 Cargo 前失败。
定位问题可选 `scope=components`（四个基础组件）、`scope=core`（无默认和 macros）、`scope=abi` 或 `scope=ui`（严格编译诊断）。
局部 scope 不替代完整门禁；coverage 的参数仅传给报告生成，不传给 Rust 测试选择。

覆盖、链接、基准、FFI 和指南构建可能需要额外工具；使用 `nox --list-sessions` 查看实际支持的会话。
测试矩阵与准入以[测试策略](../testing/test-strategy.md)为准。

## 5. 开发流程

1. 定位需求编号，说明用户场景和失败行为。
2. 查阅接口/兼容约束；影响公共 API、ABI、目录或发行时更新方案/ADR。
3. 在职责所属模块实现；以具体调用场景验证边界。
4. 新增或修改能捕捉问题的测试，更新必要的 UI 快照、stub 和指南示例。
5. 同步需求追踪、迁移说明和发行片段。
6. 运行相关检查，保存命令/结果/限制并形成审阅材料。
7. 通过版本/平台准入后按发行流程交付；运营问题继续反馈需求。

小修改选择相关回归；unsafe、宏、引用生命周期、ABI 和路径组织变化应覆盖更广的受影响链路。

## 6. 编码与兼容规范

- 公共 API 说明参数、返回值、错误、线程和生命周期条件，示例可测试。
- unsafe 边界明确指针/布局/引用/版本不变量；避免持有已释放临时对象的裸指针。
- Rust/Python 转换区分借用、所有权、复制和错误传播。
- GIL 与 free-threaded 条件分别推理，不以线程附着替代数据同步。
- 宏变化验证合法输入和错误诊断；内部生成路径保持 crate 名称解析一致。
- 可选特性应能独立组合；新增需要广泛测试的功能核对 `full` 集合与 CI。
- MSRV、解释器范围或 ABI 变化同步清单、构建配置、Nox、CI、模板和文档。

上游风格与贡献要求保留在[上游贡献原文](../reference/upstream-contributing.md)，本仓库路径以[目录规范](repository-layout.md)为准。
根 Cargo.lock/uv.lock 已纳入 Git，日常检查使用锁定依赖。
MSRV 1.85 可能不能使用 stable 解析的全部最新开发依赖。
选择 MSRV 工具链后执行 `nox -s set-msrv-package-versions -- check-all`，会话自动复制当前已跟踪及未忽略的源码（包含未提交修改），在 `target/msrv/checkout-*` 内解析依赖并运行后续会话。
只准备锁时省略 `-- check-all`；使用空格将两个会话直接放在 `-s` 后会让第二个会话回到原工作区，不能用于 MSRV 验收。
隔离目录、所有实际 Cargo.lock 和 `msrv-evidence.json` 均保留；失败时也可检查。
原工作区锁不变，忽略的工具和构建缓存不复制。
Meson 示例打包后端另要求 Rust 1.87+，不改变 SDK 本体的 1.85 MSRV。

## 7. 编译诊断与 stub 更新

UI 测试使用 `ui_test`，快照受 Rust 版本、特性和 rust-src 影响。
准备相同工具链后运行针对性测试；确需批量调整时使用 `nox -s update-ui-tests`，人工确认诊断仍指向期望问题。

内省 stub 由实验特性构建生成。
使用 `test-introspection` 验证二进制和 stub 一致性；不要仅修改 `.pyi` 来掩盖实际模块输出不匹配。

## 8. 常见问题

| 症状 | 优先检查 |
| --- | --- |
| 找不到 Cargo / Rust | 工具链安装和 PATH；不要把本机工具加入源码 |
| Python 符号未定义 | 扩展/嵌入模式、libpython、解释器架构、配置变量 |
| wheel 导入失败 | Python/ABI/platform 标签、导出模块名、动态依赖 |
| UI 快照不同 | Rust 版本、rust-src、特性和 `UI_TEST`；记录真实差异 |
| 路径/指南 include 失败 | `repository-check`、迁移映射和相对路径 |
| free-threaded 失败 | GIL 假设、同步、附着、容器访问路径 |
| FFI 校验失败 | Python 头文件、libclang、符号/布局、版本条件 |
| uv 工程会话失败 | Python 3.14 工具环境、锁文件和下载状态 |

## 9. 审阅和发行材料

变更说明包含问题/行为、需求编号、接口/兼容影响、验证结果、未覆盖项、文档和回退方式。
模板见[变更记录](../governance/change-record-template.md)。
测试摘要保存到 `docs/testing/reports/`，发行/源码交付记录保存到 `docs/releases/records/`。
推送与合并固定最终 SHA 和两个历史引用，遵循[版本政策](../releases/version-policy.md)。
涉及上游协作时遵循上游的版权、行为规范和 AI 辅助贡献责任。
