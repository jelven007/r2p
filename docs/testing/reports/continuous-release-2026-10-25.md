# 跨版本候选恢复与上传续发验收

日期：2026-10-25；范围：R-03 本地实施与真实回环 HTTP 验证。
结果见[结构化数据](../data/continuous-release-2026-10-25.json)，执行规则见[候选契约](../../governance/candidate-acceptance.md)。
外部发行仍关闭；本报告不提供远端完整 CI、namespace 授权或公开下载验收。

candidate/baseline 从各自不可变源码读取版本，六包必须同版本，内部依赖精确绑定。
CLI 分发版本由对应 SDK crate 动态生成，扩展消费者版本独立由 Cargo/pyproject 模板共同定义。
schema 2 明确版本政策、模板 SHA、执行工具 SHA、目标解释器和恢复前后版本。
schema 1 的首次两组 0.30.0 manifest 已用新验证器重新核验通过，原始历史证据未修改。
新验证器同时拒绝混合 SDK 版本、非精确内部依赖、预发行/非规范版本、错误消费者/CLI 版本、模板来源漂移、错误包集合与 ABI。
wheel 文件名的名称/版本必须匹配元数据，原生 ABI 必须匹配记录中的目标 CPython。

## 实际跨版本恢复

测试候选为本地隔离 fixture `e813ff6e02bd8a39da67d78e7084e7475ca0b736`。
其父提交为 `96e987fcce686330799d95d8b9a5f0f34aebe948`，只在独立 worktree 更新版本并加入禁止外部发布的 fixture 标记。
主分支工作区 SDK 版本仍为 0.30.0，两个历史标签未移动。
执行工具源码为 `827291d6`；后续原始制品复验与上传测试工具为 `0a6e6354`。

| 组 | SDK / CLI 版本 | 扩展消费者版本 | 原始制品与锁 | 实际行为 |
| --- | --- | --- | --- | --- |
| candidate | 0.30.1 | 0.2.0 | 6 crate、native/abi3/CLI 三 wheel、三锁 | 注册表构建、扩展函数/类/异常、嵌入与 CLI stub 生成通过 |
| baseline | 0.30.0 | 0.2.0 | 6 crate、native/abi3/CLI 三 wheel、三锁 | 独立注册表解析，在同三安装环境显式重装，运行相同行为通过 |

baseline 来源为 `3a24917eb2766aa8ded8c04fefde1c1d4b133c00`，两组都使用 candidate SHA 的消费者模板。
在 Rust 1.99.1、macOS arm64、CPython 3.14.9 GIL 开启环境完成 55 条记录命令；其中五条是预期拒绝，没有意外失败。
五条真实拒绝覆盖错误版本、缺失依赖、crate 字节篡改、模块缺失与错误 Python ABI。
abi3-py39 在记录的 CPython 上运行，不推定所有旧解释器或七个平台已运行。
fixture 制品被外部上传入口直接拒绝，未生成合成成功 CI gate。

原始制品位于 `target/optimization/candidate-cross-version-20261025-v3`。
manifest SHA-256 为 `cb00912789f5c17e25f63ac91c15a21121bc7653c4a1d14c94db0999db851785`。
复验全部原始 crate/wheel/锁摘要与行为记录成功。

## 上传与恢复

实际运行 `tools.publish_candidate` CLI，上传体使用上述已验收的六个原始 .crate。
回环 HTTP 服务按 Cargo 上传协议接收字节，提供延迟索引与下载；这些协议结果不能替代 crates.io 的外部运营结果。
五种场景共十个 CLI 阶段全部符合预期，日志与逐包 journal 保留在 `target/optimization/registry-upload-20261025`。

| 场景 | 实际结果 |
| --- | --- |
| 默认 dry-run、延迟索引/下载、再次恢复 | dry-run 零上传且不写 journal；六包逐一等待并核对下载摘要；再次恢复没有新增上传 |
| 第二包在保存前返回 HTTP 503 | 第一包保留 verified；默认恢复只等待且超时停止；显式重试后完成剩余五包 |
| 第二包保存后返回 HTTP 503 | 恢复根据索引/下载确认已接受的原始字节，没有重复上传第二包 |
| 索引 checksum 不符 | 停在第一包，后续五包零上传 |
| 下载字节不符 | 停在第一包，后续五包零上传 |

journal 绑定源码、manifest/gate 摘要、注册表地址与制品摘要，并在请求前写入 uploading。
不同来源/制品/注册表的 journal 不可复用；并发锁阻断另一上传；日志不保存凭证。
外部上传要求成功同 SHA gate、显式 execute、发行开关及 token。
工作流提供 prior run journal 取回与显式 retry-unindexed 输入，并在成功或部分失败后保留 journal 90 天。
该工作流仅通过本地静态检查，尚未有真实外部上传/续发证据。

## 真实失败与检查

第一次 fixture 漏更新模板内 pyproject，消费者 Rust/Python 版本不一致被正确拒绝；修正 fixture 生成器后重新运行。
第二次把临时目录移入 target，直接 CLI 项目被祖先 workspace 吸收而失败。
生成 CLI 消费者已加入空 workspace；直接在下载 CLI 包运行 Maturin 前追加空 workspace 边界，并记录修改前后摘要、校验所有包/依赖元数据不变。
原始 .crate 保留不修改。
两次失败 manifest、日志及摘要保留在数据中，没有将失败覆盖为成功。

56 项工具测试、Ruff、11 工作流 actionlint、zizmor 1.30.1 离线检查、变更文档 rumdl 与仓库检查通过。
本地持续发行与跨版本恢复已验收；最终源码候选、真实完整远端 CI、七平台 CLI 和合并仍归 R-01。
外部 namespace、私密渠道、维护替代责任、真实采用/升级及公开下载恢复仍归 R-09。
