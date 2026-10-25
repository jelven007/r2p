# 候选制品验收实施契约

状态：本机候选与保留制品恢复已通过，远端完整准入待验证。
依据：优化方案 O-06；外部 crates.io、PyPI、站点发行开关保持关闭。
实际制品、来源、运行环境、拒绝和恢复记录见[候选报告](../testing/reports/candidate-acceptance-2026-10-25.md)及[结构化数据](../testing/data/candidate-2026-10-25.json)。

## 同一来源与包集合

candidate 与 baseline 各固定完整 Git SHA，从各自源码读取 SDK 版本，允许两个版本不同。
同一组的六个 SDK crate 必须版本一致，内部依赖精确绑定为 `=该组版本`，同时核验许可证、Cargo 锁与每个制品的 SHA-256。
集合为 r2p-build-config、r2p-macros-backend、r2p-ffi、r2p-macros、r2p、r2p-introspection。
私有 pyo3-ffi 适配器、性能工具、示例与 Python runtime 占位包不进入 SDK 发布集合。
在独立 checkout 打包，保留真实 Git 来源信息，主工作区锁和两个历史 tag 不变。
候选 manifest 分列源码/包元数据、制品摘要、验收命令、目标环境、结果和限制。
新 manifest 使用 schema 2；首次 schema 1 的两组 0.30.0 契约仍可复验，既有证据不改写。
当前版本政策接受规范的稳定 `MAJOR.MINOR.PATCH`，前缀 v、预发行和构建元数据尚无 Rust/Python 联合发行契约，因此拒绝。
CLI Python 分发版本由对应 r2p-introspection crate 动态提供，必须等于该组 SDK 版本。
扩展消费者的版本由模板的 Cargo/pyproject 共同提供，两者须一致，但独立于 SDK 版本。
两组消费者均使用 candidate SHA 的模板，分别替换为本组的 registry 精确依赖；模板来源与执行工具 SHA 分开记录。

## Rust 源码包

建立显式的本地 sparse 注册表镜像，逐项加入候选 SDK 的索引和 .crate。
第三方索引/包可来自现有公开缓存或官方源，但必须按索引 checksum 核验。
源码包组装允许使用 --no-verify；只有在新 Cargo home 内，从该注册表独立解析、构建和运行后才计入验收。
使用明确的 source replacement 配置保留正常注册表依赖关系，禁止以 workspace path 或隐含 patch 代替安装验收。
确认每个 SDK 的来源位于新 Cargo home，依赖图只有一份同源 r2p-ffi。
临时目录位于本仓库 target 内；生成的 CLI 消费者使用独立空 workspace。
对下载后的 CLI 包直接运行 Maturin 前，只追加空 `[workspace]` 边界以隔离祖先工作区，记录修改前后摘要，并比较全部包/依赖元数据不变；原始 .crate 字节始终保留不改。
被删除的 SDK 依赖、篡改的制品、错误版本或许可证均应阻断。
本地镜像验证不等于已在 crates.io 发布，不增加 product.toml 的公共注册表准入版本。

## 两种 wheel 行为

SDK 扩展消费者通过候选注册表依赖构建，私有 Maturin 适配器使用同一 registry FFI。
普通 cp314 和 abi3-py39 wheel 在干净目录和虚拟环境安装，验证函数、类、异常与恢复后的调用。
abi3 标签及对应解释器支持分别记录；没有旧解释器运行结果时不能推定实测成功。

r2p-introspection 当前是 bindings=bin 的 CLI wheel。
验收内容为许可证、版本、平台标签、隔离安装、CLI 错误行为和有效二进制元数据的 stub 生成。
它不包含可导入的 SDK Python 模块，不能用该 wheel 宣称 r2p-runtime 已实现。
可用包含模块/函数 introspection chunks 的小型 ELF fixture，跨平台测试解析器与生成行为。
对应架构必须真实运行；Linux 非本机架构可在声明的 QEMU/container 环境验证。
未经实际运行的 wheel 不进入可发布清单。
当前发行集合限定 Linux x86_64/aarch64、Windows x64/x86/aarch64、macOS x86_64/aarch64 七个原生 CLI wheel。
每个运行记录需匹配 wheel 平台标签，完整集合须有七个独立制品；常规验证任务和发布任务分别复核。
其他架构和 sdist 需另补实际运行验收后再扩展集合。

## 发布前与恢复

发布 gate 必须读取同一 SHA 的成功 CI 汇总和完整必需矩阵；错误 SHA、未完成、失败或异常跳过均拒绝。
目前 85 个必需任务均须成功，声明为前瞻的 nightly/beta 可失败，但取消或未完成仍阻断。
发布只消费已验收的 manifest 和制品；重建后须重新核对摘要与行为。
Rust 和 Python 发布工作流均需绑定来源、版本、验收集合和 gate。
Rust 上传按六包依赖顺序执行，每包上传后等待索引可见，并下载原始 .crate 校验 SHA-256 后才继续。
默认只校验上传体；外部执行仍要求同 SHA 成功 gate、`--execute`、发行开关和凭证。
`--local-registry http://127.0.0.1:<port>` 仅用于回环 HTTP fixture，不需要也不产生外部 CI gate。
本地 fixture journal 的 scope 为 local-fixture，不能转为 crates.io 续发记录。

执行前后均保存 upload-journal.json，绑定源码、manifest/gate 摘要、注册表地址与六包摘要，不包含凭证。
上传请求发送前标记 uploading，响应成功后标记 accepted，索引和下载核验后标记 verified。
恢复时仍逐包复核远端字节；已存在且摘要一致的版本不重传。
请求发生网络或 HTTP 错误时可能已被接受，默认只等待索引与下载，超时停止。
`--retry-unindexed` 是明确的续发选择：等待超时后仅对仍处于 uploading 的未验证请求重新发送；accepted/verified 不自动重传。
索引或下载摘要不同、已撤回、journal 绑定漂移及并发 journal 锁均阻断后续包。
进程异常退出后若遗留 journal.lock，须先确认没有活动上传，再移除该锁。
发布工作流保留成功或部分失败 journal 90 天；手动调度可通过 resume_run_id 取回同一来源记录。
CI 成功与实际外部 namespace、运营准入仍属于独立条件；回环测试不替代外部首次发行验证。

恢复验收重新校验 retained artifact，安装候选后再显式安装旧制品，运行同一消费行为。
恢复记录必须说明这是本地候选恢复；实际发布后的下载复验仍属于首次外部发行准入。
命名空间权限、私密报告渠道、维护责任和支持期限也必须真实落实，未满足项继续保留。
本机候选 9bdbaeba 已通过；该 SHA 的远端完整 CI 和七个平台 wheel 尚未运行，不得据此启用正式发行。
