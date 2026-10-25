# 候选制品与恢复验收

日期：2026-10-25；范围：O-06；状态：本机注册表、安装行为与恢复通过，同 SHA 远端完整 CI 尚未运行。
外部 crates.io、PyPI、Netlify 发行保持关闭。
此报告不作为外部制品已交付或所有 ABI/平台已实测的证明。

候选 SDK 固定 `9bdbaeba9c8c5e3f1738abedd467f4b47bef1bb3`，保留 SDK 固定 `3a24917eb2766aa8ded8c04fefde1c1d4b133c00`，六个 crate 均为 `0.30.0`。
两组使用候选 SHA 的同一消费模板，以相同函数、类、异常和恢复行为比较；保留 SDK 本身仍来自原始提交。
工具版本为 Rust 1.99.1、CPython 3.14.9、Maturin 1.15.0；运行平台为 macOS 26.5.1 arm64。
正式运行从 `01:59:53` 至 `02:03:19 UTC`，55 条记录命令中五条为预期拒绝。
执行时长是本次工程样本，不作为性能提升或流水线成本指标。

## 1. 注册表消费

两组均从独立、干净 Git worktree 组装六个源码包，校验真实 `.cargo_vcs_info.json`、精确内部依赖、MIT/Apache 许可证和制品摘要。
`--no-verify` 仅用于组装；验收随后在仓库外项目和全新 Cargo home 内执行实际注册表解析、编译与运行。
source replacement 显式指向 localhost sparse 注册表，720 个第三方缓存包均与公开索引 checksum 一致。
SDK 来源位于新 Cargo home 的 `registry/src`，扩展/嵌入图只有一份同 SHA、同版本的 `r2p-ffi`。
内省 crate 另由真实注册表消费者解析和编译，再从已解析的源码构建 CLI wheel。
私有 Maturin 适配器和工程资产未进入六包集合。

| 源码包 | 候选字节数 | 候选 SHA-256 前缀 | 保留 SHA-256 前缀 |
| --- | --- | --- | --- |
| r2p-build-config | 43,451 | `dcce6c61d3b2950e` | `da0f97281a08b8ad` |
| r2p-macros-backend | 97,132 | `88c970fc91b4ea0f` | `08c7fd7a6d8bcb01` |
| r2p-ffi | 93,342 | `8bc62a2a2b8cbe85` | `0ca658238c635573` |
| r2p-macros | 8,499 | `c7cbbdfd398b8e7e` | `058412945a77763f` |
| r2p | 1,339,197 | `4da30a2cd3752f09` | `3e94ac7696bcab85` |
| r2p-introspection | 26,960 | `51c2f103dd6cb238` | `199260c363a01c11` |

两组各保留扩展、嵌入和 CLI 的三个实际锁文件；完整摘要见[结构化数据](../data/candidate-2026-10-25.json)。
主工作区 Cargo.lock SHA-256 保持 `16cc70db1ee458ab2f766fe09d76eec183bbe1aef0447bc5fce9cc255f4a7ea1`。

## 2. wheel 和行为

两组各生成普通、abi3 和 CLI wheel，校验元数据、许可证、标签和摘要。
扩展消费样例为 `maturin-starter 0.1.0`；它验证 SDK 的安装使用，不是额外的 SDK 发布包。
普通标签为 `cp314-cp314-macosx_11_0_arm64`，abi3 为 `cp39-abi3-macosx_11_0_arm64`；二者均在 CPython 3.14.9 隔离环境运行。
整数除法、属性读写、子模块类、除零/溢出异常及异常后的再次调用均通过。
abi3 的 py39 标签未作为 Python 3.9 已运行的证据。
Rust 嵌入消费者的类、异常与恢复行为也通过。

CLI 为 `r2p-introspection 0.30.0`，标签 `py3-none-macosx_11_0_arm64`。
缺参数和截断输入分别非零退出；含模块/函数元数据的非执行 ELF fixture 生成预期 `answer` stub，并通过 Python AST 解析。
fixture SHA-256 为 `1536ecf4c3ccf73a45a1e814d92ea1093e0ad51a1252cfe59d9f1f77a7932ce2`。
独立 CLI wheel 验收入口又在一个新虚拟环境安装并执行了同一候选 wheel，结果通过。
该 CLI wheel 不提供独立 Python runtime 产品。

## 3. 恢复与拒绝

候选安装完成后，三个相同 wheel 环境均通过 `uv pip install --reinstall` 显式安装保留 wheel，再运行相同探针；全部通过。
保留 SDK 使用独立注册表和 Cargo home 重新编译，Rust 嵌入行为通过。
这是候选制品到保留制品的本地恢复，不证明公开注册表下载和恢复已完成。
两个历史标签保持不变。

正式链路通过真实 Cargo、uv 和 Python 执行五个负例：错误依赖版本、缺少 `r2p-ffi` 索引、篡改 `.crate` 字节、移走已安装模块、错误 cp38 wheel 标签；全部阻断。
独立复核又阻断 14 个场景：错误来源、不完整状态、源码包缺件/重复、wheel 缺件、包/锁摘要错误、恢复缺失、越界路径、真实包/wheel 移除许可证、原生平台集合缺件、错误版本和发行标签。
后两项在访问 GitHub 前被发布 gate 拒绝。
候选 manifest 独立重新核验通过；六个上传请求体组装均保留原始 `.crate` 字节。
未使用模拟成功 CI gate，也未执行外部上传接口。

## 4. 流水线门禁与后续状态

完整 CI 已加入候选验收并保留制品；Rust 发布下载同 SHA 的已验收包，核对完整 CI 与 manifest 后才请求发行身份。
`release_gate` 要求 85 个必需任务成功；声明为前瞻的 nightly/beta 可以失败，但取消、未完成和支持矩阵失败仍阻断。
wheel 流程要求同 SHA 的完整 CI 与候选恢复证据，再在七个原生 OS/架构构建、隔离安装和运行 CLI。
每份记录的平台必须与 wheel 标签匹配，七份记录须对应七个独立 wheel。
完整集合复验作为常规验证任务执行，发布时下载已通过的集合并再次校验摘要。
未实际运行的 Linux 其他架构和 sdist 未纳入发行集合。
新增集合负例与原有候选测试共八项通过；完整工具回归共 37 项通过。

本机成功来源尚无同 SHA 的远端完整 CI，七个平台的 wheel 流程也尚未执行，当前不能通过正式发布 gate。
既有 [CI 40150316493](https://github.com/jelven007/r2p/actions/runs/40150316493) 在旧 SHA 的 engineering/GraalPy 路径失败，保留失败结论；修复细节见[解释器绑定报告](ci-interpreter-binding-2026-10-25.md)。
main 保护读取、私密漏洞报告启用接口再次返回 403。
连接授权随后成功，但授权工具要求新会话后才能继续该服务；本轮未推送、未更新 PR、未启动新 CI 或合并。
命名空间权限、私密渠道、支持期限和真实外部消费方样本仍是外部发行的未完成前提。

原始 manifest、55 份命令日志、12 个源码包、六个 wheel、六个锁与独立复核结果保留于 `target/optimization/candidate-20261025-4` 及相邻验证文件。
[结构化数据](../data/candidate-2026-10-25.json)保留原 manifest 摘要、制品摘要、解析图、命令摘要和拒绝结果；它是证据摘要，发布仍需原始制品及同 SHA 的成功 gate。
