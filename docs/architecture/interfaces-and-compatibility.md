# 接口、数据与兼容性约束

版本：2.0；日期：2026-10-24；状态：当前 API/ABI 与工程兼容规范。
关联：FR-001–FR-006、NFR-001–NFR-004。

## 1. 接口分类

| 接口 | 入口 | 使用者 | 变化规则 |
| --- | --- | --- | --- |
| Rust 公共 API | `r2p::prelude`、类型/转换/错误模块 | Rust 库、扩展与嵌入宿主 | 按版本评估源代码兼容性，给迁移说明 |
| 宏 API | `#[pymodule]`、`#[pyfunction]`、`#[pyclass]`、`#[pymethods]`、derive | Rust 扩展开发者 | 宏语法、签名及错误信息纳入编译测试 |
| Python 导出 API | 使用方声明的函数、类、模块 | Python 调用方 | 使用方管理模块名、参数、默认值、返回值与异常 |
| 低层 FFI | `r2p-ffi` 中 Python/C API 定义 | 底层集成开发者 | 解释器版本/实现/ABI 条件严格匹配 |
| 内省协议/CLI | `r2p-introspection` | 打包/类型工具 | 格式版本明确，不兼容时报错；实验特性单独承诺 |
| 工程接口 | Cargo、Nox、mdBook、CI 和路径检查 | 维护者 | 命令/路径迁移同时更新文档和配置 |

`src/impl_`、`internal` 等实现结构不应成为新业务的长期依赖。
Python 导出模块属于扩展使用方，不是仓库根 Python 工具配置中的同名“应用”。

## 2. 所有权和线程

- `Py<T>` 持有 Python 对象引用；使用需要合适的解释器附着上下文。
- `Bound<'py, T>` 将访问绑定到 `'py` 生命周期，使用者不能让借用越过上下文有效期。
- FFI 返回 borrowed/new reference 的规则必须逐个遵守。
  `as_ptr()` 不转移所有权，临时对象被释放后不能继续使用其指针。
- 自定义类动态借用和 `Send`/`Sync` 规则需要遵守；`unsendable` 有运行时线程限制。
- free-threaded Python 中的附着不等于独占访问。
  同步、临界区、容器遍历和内部可变状态需要对应实现和测试。
- 解释器结束、子解释器和重初始化能力以具体实现/测试为准；不得从单个示例推断所有对象均支持子解释器。

证据入口：[marker.rs](../../src/marker.rs)、[instance.rs](../../src/instance.rs)、[pycell.rs](../../src/pycell.rs)、[sync/](../../src/sync/)、[线程指南](../guide/src/free-threading.md)。

## 3. 转换与错误契约

| 场景 | 契约 | 验证 |
| --- | --- | --- |
| Python → Rust | 参数通过对应转换 trait 提取；非法类型/范围返回异常 | pyfunction、FromPyObject、数字与集合用例 |
| Rust → Python | 按目标类型创建或借用对象，明确复制和所有权 | IntoPyObject、往返、类转换用例 |
| Python 调用异常 | `PyResult<T>` / `PyErr` 保持类型、消息与 traceback | exception、PyErr、方法错误用例 |
| 借用冲突 | 明确运行时错误而非继续访问无效引用 | PyCell/类借用回归 |
| panic | 按现有 trampoline/panic 实现隔离和转换 | 宏、回调和 panic 路径回归 |
| 内省版本不兼容 | 返回可诊断错误，指明升级/降级路径 | 内省和 stub 校验 |

SDK 不引入统一业务错误码、REST 状态码或数据库事务。
未来业务系统需要在语言边界以上定义业务错误和幂等性。

## 4. 版本和平台基线

| 维度 | 源码/CI 声明 | 生产判定规则 |
| --- | --- | --- |
| Rust | MSRV 1.85；稳定版本；beta/nightly 辅助检查 | MSRV 和 stable 必需项通过；非 stable 不扩大正式承诺 |
| CPython | 3.9–3.15；CI 含 3.14t / 3.15t | 每个目标组合都有对应构建/运行证据 |
| PyPy | Python 3.11–3.12；README 为 PyPy 7.3 | 嵌入相关测试可能只编译不执行，需标注 |
| GraalPy | 元数据 Python 3.12–3.13；README/CI 指向 25.4 / 3.13 | 生产清单以验证版本为准，处理声明差异 |
| 操作系统 | Linux、macOS、Windows，多架构 CI | 操作系统、CPU、位宽分别列项；不能由 x64 推断 arm64 |
| WebAssembly | Emscripten、WASI 构建资源和 CI | 单独说明线程、模块/链接和解释器限制 |
| no_std | `R2P_WIP_NO_STD` 为 WIP | 不宣称完整无 std 生产支持 |

“有配置”“可编译”“已运行通过”“正式支持”使用四个独立状态。
不能将 CI 配置中的组合当作本次已通过记录。
本期具体证据见[支持矩阵](../testing/support-matrix.md)，维护响应按[支持政策](../operations/support-policy.md)。

## 5. ABI、特性与打包

- 版本专用扩展依据对应解释器 API/ABI 构建并测试。
- `abi3` 使用有限 API 和最低 Python 版本特性；仍需目标系统/架构、动态依赖和版本验证。
- `abi3t` 对应 free-threaded 稳定 ABI 路径，当前源码包括 `abi3t-py315`；不可把普通 `abi3` wheel 当成 free-threaded 通用制品。
- 宏默认启用；async/inspect 为实验特性；`full` 主要是测试集合，不应作为所有使用方的默认生产选择。
- `extension-module` 特性已有弃用说明，优先使用打包工具设置的 `R2P_BUILD_EXTENSION_MODULE`；嵌入宿主有不同的链接需求。
- wheel 的 Python/ABI/platform 标签、导出模块名和动态依赖必须与安装环境匹配。

参考：[features.md](../guide/src/features.md)、[构建与发行](../guide/src/building-and-distribution.md)、[兼容实现](../../crates/r2p-ffi/Cargo.toml)。

## 6. 配置契约

| 配置 | 用途 | 操作约束 |
| --- | --- | --- |
| `R2P_PYTHON` | 指定构建所用解释器 | 使用明确路径/版本，记录在验证和发行证据中 |
| `R2P_CONFIG_FILE` | 指定构建配置文件 | 版本受控；区分宿主和目标信息 |
| `R2P_BUILD_EXTENSION_MODULE` | 扩展构建的链接模式 | 由打包工具设置或明确配置，不用于默认嵌入测试 |
| `R2P_NO_PYTHON` | 特定无需本机 Python 的构建路径 | 仅按支持的 ABI/构建条件使用 |
| `R2P_CROSS_*` | 交叉编译目标信息 | 匹配目标解释器、实现、库目录和架构 |
| `CARGO_TARGET_DIR` | 构建/覆盖目录 | 隔离或共享策略明确，避免不兼容缓存 |
| `UI_TEST` | 编译诊断测试的策略 | skip/ignore 必须留原因，不计作严格快照通过 |

其他变量详见源码和用户指南；本表不替代所有 Cargo/Python 环境配置。
完整注册表和旧工具协议兼容优先级见[配置说明](../development/configuration-reference.md)。

## 7. 工程数据与保留

最小发行记录：发行主体、制品名称/版本、源码 SHA、Rust/Python/OS/CPU、特性/ABI/GIL 模式、依赖锁定快照、执行命令/结果、构建流水线、文件清单/校验和、审批角色、迁移和回退说明。

本期源码 SHA 和两个推荐历史快照在 Git 及[快照清单](../releases/history.json)中保留。
本地大日志/候选二进制不随源码提交；报告保留运行摘要和限制，正式发行证据须覆盖整个支持周期。
仓库里的验证报告只记录本次执行，不能替代未来每次发行记录。

## 8. 兼容变更流程

影响分析 → 需求编号和 ADR → 针对性回归 → MSRV/平台矩阵 → 迁移文档 → 发行记录。
调整 Python 最低版本、ABI 或 Rust MSRV 时同时核对 Cargo 特性、FFI 元数据、构建配置、Nox、CI、示例、模板和指南。
