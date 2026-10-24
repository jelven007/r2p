# 文件目录规范与迁移映射

版本：2.0；日期：2026-10-24；状态：当前生产研发结构。
关联：FR-008、NFR-006；决策见 [ADR-0001](../architecture/adr/0001-repository-layout.md)。

## 1. 目录职责

| 目录/入口 | 内容 | 新增文件规则 |
| --- | --- | --- |
| 根 Cargo 包、`src/`、`build.rs` | 主 r2p 库、构建转发和公共 API | 按 Rust 模块职责放置，保持稳定公开入口 |
| `crates/` | 可独立构建的 FFI、宏、配置、内省组件 | 一个组件一个清单；实际需要才拆 crate |
| `python/` | 独立 Python 产品包 | 包内维护 pyproject、源码、测试与说明 |
| `tests/*.rs`、`tests/ui/` | 主包集成测试、编译期诊断和测试基座 | 维持 Cargo 自动发现；诊断快照随测试维护 |
| `tests/python/` | 跨语言测试用扩展、pytest、stub | 保留 Python 模块名；测试制品不发行 |
| `benchmarks/` | 性能测量程序 | 隔离 workspace；记录场景与环境 |
| `examples/` | 完整使用/打包示例及 cargo-generate 模板 | 示例必须可验证；模板依赖使用发行版本占位符 |
| `tools/` | 仓库校验、FFI 对照等开发工具 | 区分日常检查与重型/独立依赖工具 |
| `infrastructure/` | WASI/Emscripten 构建、Netlify 资源 | 按目标平台划分；实际部署配置由环境管理 |
| `assets/` | 示例运行资源与品牌素材 | 保留来源；源代码 include 的资源必须能打包 |
| `docs/` | 工程文档、用户指南、上游参考 | 生命周期职责与状态明确，不复制唯一真相 |
| `.github/` | GitHub 工作流、Actions、模板及平台工具 | 保持 GitHub 发现规则；路径变更同步更新 |
| `newsfragments/`、`CHANGELOG.md` | 上游兼容的发行说明 | 依 towncrier 分类记录，保留历史 |
| 根配置与许可证 | Cargo、product.toml、uv、Nox、格式、检查和许可入口 | product.toml 维护产品身份，其余入口遵守工具发现约定 |

根 `src/` 保留的是标准 Rust 主包结构。
根 `product.toml` 属于产品治理元数据，从主 r2p crate 的发行内容中排除。
目录分层不要求在没有服务实现时预建 `apps/`、`services/`、数据库迁移或 Kubernetes 配置。

## 2. 本次迁移清单

| 原路径 | 新路径 | 主要联动 |
| --- | --- | --- |
| `r2p-ffi/` | `crates/r2p-ffi/` | 根依赖、工具依赖、Nox、FFI 过滤器 |
| `r2p-build-config/` | `crates/r2p-build-config/` | 根/工具/测试依赖、构建检查 |
| `r2p-macros/` | `crates/r2p-macros/` | 根依赖，组件间相对路径仍有效 |
| `r2p-macros-backend/` | `crates/r2p-macros-backend/` | 宏组件依赖，组件间相对路径仍有效 |
| `r2p-introspection/` | `crates/r2p-introspection/` | wheel 工作目录、制品路径、内省测试 |
| `r2p-runtime/` | `python/r2p-runtime/` | 保持包内布局和构建入口 |
| `pytests/` | `tests/python/` | 到根库/配置的依赖、Nox、类型检查工作目录 |
| `r2p-benches/` | `benchmarks/r2p-benches/` | 根库/配置依赖、Nox、Rust 缓存、Dependabot |
| `r2p-ffi-check/` | `tools/ffi-check/` | 子 workspace 依赖、build.rs、Nox、过滤器 |
| `guide/` | `docs/guide/` | Rust doctest、宏文档、mdBook include、Nox、格式配置 |
| `branding/` | `assets/branding/` | 素材组织，内容保留 |
| `wasm/` | `infrastructure/wasm/` | Nox 平台路径、Actions 缓存键 |
| `.netlify/` | `infrastructure/netlify/` | Rustdoc 横幅路径、部署资源组织 |
| `docs/maintenance/runbook.md` | `docs/runbooks/incident-response.md` | 运维操作与环境资产独立组织 |
| `docs/maintenance/release-and-rollback.md` | `docs/releases/release-and-rollback.md` | 发行政策、两个快照、交付记录聚合 |
| `docs/testing/*validation*.md` | `docs/testing/reports/` | 策略/支持矩阵与各阶段不可混淆的证据分开 |
| 根介绍/架构/贡献/发行文档 | 根入口更新，原文保留 `docs/reference/` | crate README、指南首页/贡献 include 和使用方导航 |

Rust 集成测试仍处于 `tests/`；FFI 示例随 crate 移动，因此其 crate 内相对路径保持有效。
根示例依赖主库的相对路径保持有效。
CodeCov 原 `pytests/` 排除由现有 `tests/` 规则覆盖。

## 3. 文档结构

```text
docs/
├── README.md
├── requirements/       # 需求规格、追踪矩阵
├── architecture/       # 总体方案、接口与兼容、adr/
├── development/        # 环境、流程、目录规范
├── testing/            # 策略、支持矩阵、reports/ 验证证据
├── operations/         # 采用、支持、反馈和指标
├── runbooks/           # 环境资产、故障与恢复操作
├── releases/           # 版本政策、history.json、records/ 交付记录
├── governance/         # 分析、计划、文档管理和记录模板
├── guide/              # 保留 r2p mdBook 用户指南
└── reference/          # 本次拉取版本的上游原文
```

用户指南包含已有 API 示例，工程文档描述本仓库的开发/交付约束。
上游参考保留原始路径与历史描述，因此不作为当前目录的唯一依据。

## 4. 构建和工具约束

- 主 workspace：根 Cargo 包、5 个辅助 crate、Rust UI 基座、Python 测试 crate 和示例清单。
- 独立 workspace：`benchmarks/r2p-benches`、`tools/ffi-check`；各自依赖主库和 `crates/` 中配置/FFI。
- Nox 从根目录执行；Python 子测试通过指定 noxfile 进入自己的环境。
- root crate 打包保留 `docs/guide/` 和上游 README 等编译/文档资源；非 SDK 的工程文档、Python 产品包、基准、工具和基础设施从主 crate 排除。
- 工作流中的包名仍为 `r2p-*`，只有文件路径迁移；路径和包名不能机械地同时替换。
- 生成模板中的版本依赖保留，不替换为开发树绝对路径。
- Rust 组件共享许可证的符号链接随目录深度调整为 `../../LICENSE-*`；Python 运行时包保存与根许可证逐字节一致的普通文件，避免 sdist 包含越出包根的链接，校验脚本检查副本内容一致。
- `meson/meson.build` 保留根级工具发现入口；Meson cargo workspace 通过包子项目查询 FFI，不按文档分类移动发现路径。

## 5. 提交内容和忽略内容

提交源码、清单、锁定的工程依赖、示例、模板、文档与工作流。
构建输出、wheel、缓存、虚拟环境、机器本地工具和系统杂项由 `.gitignore` 管理。

本次验证工具位于 `.tools/`、`.venv/`，不属于交付源码。
根 `Cargo.lock` 已跟踪；`.gitignore` 只忽略子目录新生成的锁文件，并显式保留 `/Cargo.lock`。
根锁和 `uv.lock` 用于工程复现；MSRV 依赖兼容解析在隔离副本执行。
正式制品仍保存实际构建使用的解析快照和工具链，消费方管理自己的锁文件。

## 6. 后续迁移规则

先列影响面和原→新映射，再移动和更新路径；通过 G1 后运行相关行为回归。
后续上游同步在单独分支处理，参考本表解决目录冲突，不直接覆盖当前目录。

至少运行：

```bash
cargo metadata --no-deps --format-version 1
cargo metadata --manifest-path benchmarks/r2p-benches/Cargo.toml --no-deps --format-version 1
cargo metadata --manifest-path tools/ffi-check/Cargo.toml --no-deps --format-version 1
python tools/check_repository.py
```

完整验证范围和本次结果分别见[测试策略](../testing/test-strategy.md)、[当前验证](../testing/reports/production-baseline-validation.md)。
