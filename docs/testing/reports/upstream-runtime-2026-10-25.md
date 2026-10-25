# 历史运行时修复映射与回归演练

日期：2026-10-25；R-08 本地受控演练完成。
源码 `31e4f820db74b8992a378d476fcf266d925ee9e7`，macOS arm64 / Rust 1.99.1 / CPython 3.14.9，native ABI、macros、锁定离线依赖。
数据见[原始证据与摘要](../data/upstream-runtime-2026-10-25.json)。
当前 SDK 已继承以下修复，本轮没有从上游新增运行时行为或修改主工作区内核。

## 来源和映射

选定真实 PyO3 修复 [#6453 / 5619fedb](https://github.com/PyO3/pyo3/commit/5619fedbca3ad1baca82869b57df54afd0432a0b)，父提交 `3260c4835f33d3c05d39715c2b729dfdb5e31e35`。
它修复类属性初始化期间 GC 遍历再次触发类型初始化的问题，并加入 `test_gc_during_classattr_initialization`。
完整原始 format-patch 摘要 `5eaf43f317e93fa582380af72b2822f12bfb806b483cc90ee024d1d1683c4db3`。
来源完全取自本地保留的真实 Git 对象，没有本轮网络请求或伪造新的上游提交。

原补丁涉及八个文件；后续命名、布局、格式和实现演进使整包反向应用发生上下文冲突。
实际冲突包括 pycell、instance、pymethods、gc、回归测试和已迁移的 newsfragment。
本轮映射其中类型数据查找的语义改动：GC 内使用已经存在的 lazy type object，避免调用会初始化类属性的 `type_object_raw`。
它的旧查找语句与新查找块均逐字核对历史父/子提交；当前源码要求新块恰好出现一次。
保留已继承的 GC guard、借用检查、类型布局及其他依赖，不将局部演练称为整包移植。
映射补丁摘要 `81cb50a1f9d70361d9c5c9d6f162e0b1d4ba42c61b9ec948ac054acdf2d4ffae`。
负责人仍为 jelven007，本轮没有替换现有本地功能补丁或安排新的维护人员。

## 真实正负例

从固定源码归档创建独立 Git 根，先检查再反向应用查找补丁。
此时保留上游回归用例，用旧查找方式实际编译运行。
随后检查并重放补丁，再执行相同回归。

| 状态 | 独立执行次数 | 实际结果 |
| --- | --- | --- |
| 受控旧查找 | 3 | 每次 Cargo exit 101；类属性初始化重复调用；回归失败 |
| 重放安全查找 | 3 | 每次 exit 0；单项回归通过 |
| 恢复后的完整 GC 测试 | 1 | 26 项通过 |

首次 GC 运行已经复现缺陷，但验收工具误要求日志出现另一特定词，因而保留 incomplete 现场。
修正为核对回归实际断言后，在新目录重新完成三次正负例。
编译缓存仅用于减少重复第三方编译，真实编译日志确认分别使用新 checkout 的旧/新源码；运行时测试没有跳过。
日志在 `target/optimization/upstream-gc-runtime-20261025-v2/`；首次目录保留。

恢复后 pycell 文件摘要为 `a8f11b704d664e452273ca21080639b8e27cdb784bd619d562e7f4a0674e3cb6`，与演练前归档字节一致。
主工作区 pycell、GC 测试与 Cargo.lock 摘要不变；history 标签未移动。
这证明受控语义反转、映射重放和该环境下的真实回归，不能替代最终 SHA 的完整跨平台 CI。

## 未得到负例的另一尝试

真实历史 [#6404 / 7ed9ac01](https://github.com/PyO3/pyo3/commit/7ed9ac01341592cfaa631e592bd816c88b620aad) 调整终结时的附着记账顺序。
原始/路径命名映射、撤销/重放和源码摘要相等均通过。
但本机 CPython 3.9.6 的原终结测试执行后正常退出，未得到预期运行时负例；改用模块加载方式的三次实验也没有复现。
该结果保留在 `target/optimization/upstream-runtime-20261025/`，没有被计为运行时缺陷修复验收成功，也未推断具体平台原因。
工具仍提供显式 `--repair finalization` 实验入口，默认采用可验证的 GC 演练。

复现：

```bash
python -m tools.upstream_runtime --sha <固定完整 SHA> \
  --target-python <CPython 3.14> --output <新目录>
```

失败现场保留；工具测试核验来源拒绝、空补丁拒绝和继承回归函数保持。
公开上传、外部消息和上游 PR 均未执行。
