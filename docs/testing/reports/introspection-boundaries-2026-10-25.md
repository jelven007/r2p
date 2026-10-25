# 内省解析与生命周期边界验证

日期：2026-10-25；范围：O-10；状态：本地验收通过，最终跨平台 CI 待核验。
受测源码为 `36e76e56807c327c3840905feff8d77902667725` 加本工作包变更，明确属于 worktree-changes。
环境：macOS arm64、Rust 1.99.1、CPython 3.14.9、GIL enabled、native ABI。

解析入口先限制二进制读取为 512 MiB；单条元数据为 1 MiB，总量 64 MiB，最多 16,384 条。
JSON 每条最多 65,536 个节点、64 层嵌套；元数据关系在递归转换前迭代验证。
重复 ID、同名根、包含环、超过 64 层的包含关系均返回错误。
共享 DAG 的展开成员最多 65,536 个，展开文本按序列化字节乘包含深度保守限制为 64 MiB，防止重复复制大文档或类型路径。
缺失成员仍产生 incomplete 模块，保持已有消费语义。
ELF 地址加法、Mach-O 节内地址和文件偏移检查保持明确错误；长度计算使用 checked_add，错误预览最多 160 字节。
这些是实验内省接口的默认资源上限，合法但超过上限的库也会拒绝；本次没有改变格式版本或 SDK 生命周期实现。

`cargo test -p r2p-introspection --locked`：24 项通过，包括新增 11 项边界回归。
覆盖两种端序和所有 chunk 截断位置、未知版本、错误结构、超大长度、错误预览上限、JSON 深度/宽度、 重复 ID、同名根、缺失成员、成员环/父关系环、深度临界值、DAG 放大、重复大文档、条数/总量、ELF 缺失段/偏移溢出和超限稀疏文件。
固定种子对 ELF、Mach-O、fat Mach-O、PE 魔数生成 4,096 个不超过 511 字节的变异输入，同时调用容器和 chunk 解析；没有 panic。
这是有限确定性回归，不宣称覆盖所有输入或替代持续 fuzzing。

`cargo clippy -p r2p-introspection --all-targets --locked -- -D warnings` 通过。
`python tools/dev.py -- -r -s test-introspection` 通过：普通、`strip -x`、fat Mach-O 三种库生成的 18 个 stub 文件均与既有快照一致； Python stub 测试为 16 通过、2 按既有条件跳过。
该 Nox 会话现在也运行解析器单元测试，跨平台内省任务会执行相同边界回归。
ELF/PE 的正常输出留待最终 Linux/Windows CI，本机不外推为已运行。

现有生命周期状态测试 10 项通过，含延迟 decref、detach 恢复、递归 attach 和 decref 重入不死锁。
GC 26、异常 4、初始化竞态 1、脱离解释器后的 buffer drop 1、不可格式化异常 1，共 33 项集成回归通过。
命令为 `cargo test -p r2p --locked --features full --lib internal::state::tests`， 以及同特性下的 `--test test_gc --test test_exceptions --test test_init_race --test test_pybuffer_drop_without_interpreter --test test_pyerr_debug_unformattable`。
free-threaded 和完整兼容矩阵另外登记，未用本机 GIL 测试替代。

本地原始日志及 SHA-256：

| 路径（相对仓库） | SHA-256 |
| --- | --- |
| target/optimization/introspection-boundaries.log | 1edede540413faabe859c342ccacf1639d50fb9b6ef539d729888b92680fde67 |
| target/optimization/introspection-clippy.log | c5e276006827fc2ee1ec27eabf43de96f0a4cd2cc94e78d3dac39b298b5803be |
| target/optimization/introspection-real-final.log | 8e23821d8f3289b42896c55c1e952b757f9c8b432304811dd0b9d52865e16be1 |
| target/optimization/lifecycle-state.log | 2f30f91b9a7e451e5d2ff2bfe59fae50d82c57b996de8b14629b3a2ea010c36d |
| target/optimization/lifecycle-integration.log | 38e18d80de38e701ad92ab7d674b293cdb8990bbab08dfd80220174ba6282eb0 |

日志保留在本地 target 目录，环境快照为 `introspection-environment-final.json`。
最终 CI 日志和来源 SHA 在完成后补充到结构化证据。
