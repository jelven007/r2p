# 固定实施提交的本机验收

日期：2026-10-25；状态：下列本机范围通过，完整远端交付未完成。
受测实施提交：`b04b79e7130c9f7694962cb70a45585e276cf41a`。
所有受测 Nox 快照均记录此 SHA 和 `dirty=false`；验收完成后新增的报告、数据与索引不自动取得新的源码验收结论。
环境：macOS 26.5.1 arm64、Rust 1.99.1、CPython 3.14.9 / 3.14.9t。
原始摘要和每个日志的 SHA-256 见[结构化数据](../data/local-acceptance-2026-10-25.json)。

## 实际执行

| 范围 | 结果 | 限定 |
| --- | --- | --- |
| 普通 GIL Rust 完整入口 | 11 条 Cargo 测试命令全部成功 | 组件、native、abi3、full、UI 与 abi3-py39；都使用本机 CPython 3.14.9 |
| 无 GIL Rust core 入口 | 无默认特性与 macros 两条命令全部成功 | 包含线程附着/延迟 decref 和 26 项 GC；不代表 FT full 或远端矩阵 |
| 无 GIL Python 扩展 | 26 项通过 | finalization、pyclasses、exception 三个文件；导入 `r2p_pytests` 前后实际 GIL 均关闭 |
| 内省入口 | 24 项解析回归；16 项 stub 通过，2 项既有条件跳过 | 原始、strip 和 fat Mach-O 三种本机库变体；不外推 ELF/PE 正常库输出 |
| 工程入口 | 72 项工具回归与仓库/证据检查通过 | 25 个 Cargo manifests、68 篇工程文档，数量属于新增本报告前的受测树 |
| 候选与恢复 | 55 条命令完成，含五项预期拒绝 | 两组各六 crate、三 wheel、三个锁；相同 SDK 版本的源码恢复 |
| CLI wheel 本机安装/执行 | `macos-aarch64` 成功，scratch 清理 | 七平台集合检查因另外六份原生验收缺失而正确阻断 |
| 原始制品取回 | 25 个文件摘要与 manifest 复验通过 | 归档和取回均绑定受测 SHA；没有清理最后原始组或历史恢复点 |

普通入口命令为 `python tools/dev.py --target-python <CPython 3.14.9> -- -s test-rust`。
FT Rust 命令由 CPython 3.14.9t 启动同一工具，指定目标 3.14.9t、`PYTHON_GIL=0` 和 `-s test-rust -- scope=core`。
FT Python 使用 `-f tests/python/noxfile.py -s test -- tests/test_finalization.py tests/test_pyclasses.py tests/test_exception.py`，独立 envdir 保留。
FT optional gevent 二进制分发不存在，既有 Nox 会话捕获安装失败并继续；所选 26 项测试没有跳过。
这不提供 gevent 兼容性结果；启动探针与模块后的 GIL 状态分别保存。

内省命令为 `python tools/dev.py --target-python <CPython 3.14.9> -- -s test-introspection`，使用新 envdir。
工程入口使用同一工具执行 `-s repository-check`。
Ruff 0.16.10 的格式/静态检查、Cargo fmt、rumdl 0.2.78 的 96 文件检查、actionlint 1.7.12 的 11 工作流检查和 zizmor 1.30.1 离线检查通过。
文档入库后的路径、证据和格式检查另外执行，不改写上述受测源码状态。

## 候选、恢复与摘要

候选和执行工具均固定在受测实施 SHA；baseline 固定 `3a24917eb2766aa8ded8c04fefde1c1d4b133c00`。
两组 SDK/CLI 为 0.30.0，消费者为同一候选模板的 `maturin-starter 0.1.0`。
每组在独立 Cargo home 解析隔离 sparse 注册表中的六个原始源码包，并构建/执行 Rust 嵌入、普通扩展、abi3 扩展和 CLI。
三种 wheel 环境随后显式重装 baseline，再运行同一行为探针，均成功。
本次是相同版本、不同源码的恢复；不同版本恢复另见[0.30.1 fixture → 0.30.0 报告](continuous-release-2026-10-25.md)。
未重新生成跨版本 fixture，也未把本机注册表恢复解释为公开下载恢复。

错误版本、缺少依赖索引、篡改 crate、缺少已安装模块和错误 cp38 wheel 标签五项真实拒绝通过。
独立 `candidate_artifacts verify` 重新核对制品、许可证、版本、来源、锁、行为和恢复结果。
额外 CLI 安装使用原候选 wheel 的相同字节，成功后 scratch 已清理。
`cli_wheel_acceptance --verify-set` 实际非零退出，理由为缺少其他六份原生验收；没有生成成功的七平台或外部 gate。

原始目录：`target/optimization/candidate-final-local-20261025/`。
独立本机 CLI 目录：`target/optimization/final-local-cli-dist-20261025/`。
取回目录：`target/optimization/final-local-candidate-retrieved-20261025/`。

| 原始对象 | SHA-256 |
| --- | --- |
| candidate manifest | `25ba836ef2d642ab3e5b1d478803c3b02068544213505b6b1d8ee781a8807531` |
| macos-aarch64 CLI wheel | `ee6284a6622b561a15571b76bc5ff3c28f86829279487f4a86166a6eaa881e46` |
| 25 文件原始归档 | `93867911ff7230eb9fe95ccc0ac1deaa041b5d90ec1d550a88f83915857c9be3` |
| 主工作区 Cargo.lock | `16cc70db1ee458ab2f766fe09d76eec183bbe1aef0447bc5fce9cc255f4a7ea1` |
| 主工作区 uv.lock | `8308bf443277f49926a1c152cd3e515dd4008a116f3c07e9873dd00143165b2e` |

归档仅保留 manifest、原始 crate/wheel 和消费者锁；取回验证归档及逐文件摘要，再执行原 manifest 验证。
主工作区锁摘要未变。
两个本地历史标签仍对应 `f9e8d6461f51b7149b436844339dd9df7abb9e00` 和 `424149e8a1c42128b05a090941673008fc46c478`。
此检查只说明本地引用和字节；远端状态未重新查询。

## 保留的启动失败

首次 FT 启动将 `PYTHON_GIL=0` 传给普通 CPython，解释器在启动时拒绝，尚未执行工程工具或 SDK。
原始 `final-local-ft-rust-20261025.log` 保留；改为 FT 解释器启动后，v2 的 Rust/Python 验收通过。
首次 CLI 命令使用不存在的 `macos-arm64` 平台 ID，参数检查拒绝；改为政策定义的 `macos-aarch64` 后安装和执行通过。
原日志保留，不将这两项启动/参数失败描述为 SDK 运行时故障。
汇总脚本在 FT Rust 尚未结束时也拒绝缺少 exit_code 的快照；之后只汇总实际完成且成功的快照。

结构化证据新增 13 条，其中 11 条成功、两条配置失败；原有 39 条逐项保持不变。
导入后的记录总数为 52，源码、环境、原始路径、摘要、结果和限制分别登记。
旧候选、跨版本 fixture、性能样本和上游演练仍按各自来源解释。
证据与索引入库后，仓库检查为 25 个 manifests / 69 篇工程文档，52 条证据及 72 项工具回归再次通过。
改动文档的 rumdl、Ruff 格式/静态检查和 diff 检查通过；该次检查记录为 b04b79e7 加文档工作区变更，仅验证新增证据和索引。

## 仍需完成

R-01 需要最终交付 SHA 的完整远端 CI、七平台原生 CLI、实际 gate、源码合并与远端 main 核验。
最近 GitHub 授权工具要求新会话后才可继续该服务，本轮没有通过 CLI、API、push 或上下文切换绕过限制。
R-07 仍需独占稳定环境、真实用户负载与连续远端成本；R-08 的 #6404 本机负例仍未复现。
R-09 的 namespace、私密渠道、备份责任、真实采用/升级和公开下载恢复仍需外部证据。
公开 crates.io、PyPI 和 Netlify 发行继续关闭；本报告不表示九个工作包或正式发行准入全部完成。
