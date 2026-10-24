# 项目分析与现状评估

日期：2026-10-24。
状态：代码分析基线。
证据来源：本地克隆、Git 提交、配置、源码与测试目录。
负责人：技术负责人角色，待分配。

## 1. 来源与范围

| 项目 | 核验结果 |
| --- | --- |
| 产品名称 | `r2p`，由用户确认；元数据见 [product.toml](../../product.toml) |
| 源仓库 | `https://github.com/jelven007/p2r.git` |
| 默认分支 | `main`，通过 `git ls-remote --symref` 核验 |
| 最新拉取提交 | `424149e8a1c42128b05a090941673008fc46c478` |
| 提交时间与内容 | 2026-10-23 11:42:30 UTC；`Use PyType_FastSubclass on RustPython (#6541)` |
| 本地位置 | 仓库根目录，即本地 `p2r/` 工作区 |
| 初始状态 | 空目录，全量克隆；无已有本地修改需要合并 |
| 包定位 | 主包及 SDK 组件为 `r2p` / `r2p-*`；源码网址指向本仓库，保留 PyO3 作者与版权 |
| GitHub 获取方式 | 加载 GitHub 插件技能；当前无可调用的仓库连接器接口，以本地 Git 执行克隆 |

代码与元数据表明这是以 PyO3 为基础、内核命名空间已迁移为 r2p 的工程。
本次没有通过 GitHub 仓库 API 核验平台的 fork 标记、Issue/PR 状态或线上发行状态。
包清单中的 `0.30.0` 只作为源码版本声明。

基线共有 854 个 Git 跟踪文件，其中 Rust 文件 477 个、Python 文件 59 个；根 Rust 集成测试 43 个文件，Python 测试 20 个模块，Rust 基准 21 个文件。
这些是文件数量，不是测试通过数量或覆盖率。

## 2. 产品定位和用户

r2p 的直接产品是开发者基础软件。
Python 开发者使用它把性能敏感逻辑写成 Rust 扩展；Rust 开发者使用它调用 Python 生态；打包维护者处理 Python 版本、平台和 ABI 兼容；项目维护者管理 FFI、宏、版本迁移与发行。

代码具有两条主链路：

1. Python → 原生扩展模块 → r2p 宏生成入口 → 参数提取和类型转换 → Rust 函数 → 返回值/异常。
2. Rust → 初始化或附着解释器 → 获取 Python 对象 → 调用 Python/C API → 提取结果 → 引用与生命周期处理。

当前范围不包含产品账号、订单、HTTP API、业务存储和页面。
以“生产系统”推进时，首先建立可维护、可测试、可发行、可支持的 SDK 工程；若需增加特定业务系统，应先定义业务领域及 SDK 集成边界。

## 3. 组件盘点

| 组件 | 代码证据 | 责任与边界 |
| --- | --- | --- |
| 核心安全 API | [src/lib.rs](../../src/lib.rs)、[instance.rs](../../src/instance.rs)、[marker.rs](../../src/marker.rs) | `Py<T>`、`Bound`、线程附着及公共 API |
| 内置类型与转换 | [types/](../../src/types/)、[conversions/](../../src/conversions/) | Python 对象访问、Rust/Python 转换、可选生态集成 |
| 自定义类与错误 | [pyclass.rs](../../src/pyclass.rs)、[pycell.rs](../../src/pycell.rs)、[err/](../../src/err/) | 借用、自定义类、异常与跨语言错误 |
| FFI | [crates/r2p-ffi/](../../crates/r2p-ffi/) | Python/C API、版本与解释器条件编译；包含 unsafe 边界 |
| 构建配置 | [crates/r2p-build-config/](../../crates/r2p-build-config/)、[build.rs](../../build.rs) | Python 探测、链接参数、跨编译和 ABI 配置 |
| 宏入口/后端 | [r2p-macros/](../../crates/r2p-macros/)、[r2p-macros-backend/](../../crates/r2p-macros-backend/) | 宏解析、代码生成、编译期诊断 |
| 内省 | [crates/r2p-introspection/](../../crates/r2p-introspection/) | 从二进制元信息生成 `.pyi`；实验性质需控制版本 |
| Python 运行时包 | [python/r2p-runtime/](../../python/r2p-runtime/) | 独立 Python 包；不将其视为所有扩展必需服务 |
| Rust / Python 测试 | [tests/](../../tests/)、[tests/python/](../../tests/python/) | 集成、编译诊断、扩展模块行为和 stub 校验 |
| FFI 对照工具 | [tools/ffi-check/](../../tools/ffi-check/) | 对比 bindgen 和手写 FFI 的定义、布局、签名 |
| 性能基准 | [benchmarks/r2p-benches/](../../benchmarks/r2p-benches/) | 跨语言调用、附着、对象访问和转换等基准 |
| 示例与指南 | [examples/](../../examples/)、[docs/guide/](../guide/) | maturin、setuptools-rust、Meson、嵌入和模板 |
| 自动化 | [noxfile.py](../../noxfile.py)、[.github/workflows/](../../.github/workflows/) | 编译、测试、格式、兼容矩阵、覆盖、文档和发布 |

`src/impl_` 等内部模块主要服务宏生成和底层实现；公开 Rust 模块不等于稳定的内部扩展契约。
稳定性和支持条件应以源码标注和版本策略为准。

## 4. 技术基线

- Rust：Edition 2024；MSRV 1.85。
- CPython：FFI 元数据范围为 3.9–3.15；现有 CI 包含 3.14t/3.15t。
- PyPy：FFI 元数据为 Python 3.11–3.12；README 要求 PyPy 7.3 系列。
- GraalPy：FFI 元数据为 Python 3.12–3.13，README 说明 GraalPy 25.4+ / Python 3.13+，CI 配置为 `graalpy25.4`。
  生产支持口径需取实际验证矩阵，不能仅以最低版本字段推断。
- `abi3` 与 `abi3t` 是不同构建条件，解释器版本、GIL 模式和功能组合必须一同记录。
- 工程工具使用 uv/Nox，工具依赖组要求 Python 3.14；这不提高 SDK 的 Python 最低要求。
- Python 打包包含 maturin、Hatchling 和示例中的 setuptools-rust/Meson。
- 许可：MIT OR Apache-2.0；保留根许可证、组件许可证及上游版权。

## 5. 生产研发缺口

| 缺口 | 依据/影响 | 处理 |
| --- | --- | --- |
| 发行身份待落实 | 产品与实现包名已确定为 `r2p`；独立制品尚未发布 | ADR-0002 已落实 SDK 迁移；独立发行前配置注册表与站点 |
| 全生命周期文档不足 | 原文集中于库使用/贡献/上游发行，缺需求、运营与事故闭环 | 本次建立结构化工程文档 |
| 目录责任散布 | crates、Python 测试、基准、指南分散根层 | 本次迁移并同步配置 |
| 路径耦合广泛 | Cargo、Nox、doctest、mdBook、CI、缓存和覆盖引用目录 | 增加一致性检查和迁移验证 |
| 发行权限未知 | 上游发行工作流存在，不证明本仓库配置可用 | 发布前核验注册表、环境、OIDC 和审批 |
| 支持承诺未定义 | 支持矩阵、SLO、响应时限没有 r2p 独立承诺 | 本文档群提出目标，负责人批准后生效 |
| 实验功能风险 | async、inspect、no_std 等有实验/WIP 标记 | 默认稳定路径与实验路径分开验收 |
| 线上证据缺失 | 没有本仓库运行指标、发布日志和用户采用数据 | 运营/运维建立采集与复盘流程 |

现有源码和自动化覆盖面较广，但本次不据此给出“已生产就绪”的判断。
目录与文档更新是研发基线，线上准入需要实际测试和发布记录。

## 6. 本次交付与后续边界

本次交付：最新代码本地基线、责任明确的目录、联动路径配置、项目介绍、需求/方案/开发/测试/运营/运维文档、目录检查工具及验证记录。

后续目标：平台完整兼容验证、可追溯制品、独立发行决策、权限配置、支持值守和业务系统范围。
具体任务与状态见[交付计划](delivery-plan.md)，实际检查见[验证报告](../testing/validation-report.md)。
