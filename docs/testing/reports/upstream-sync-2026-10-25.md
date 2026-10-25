# 首次上游同步演练

日期：2026-10-25；范围：O-07；状态：真实上游工程依赖同步已完成本地重放，最终远端验证待核验。
负责人为 [jelven007](https://github.com/jelven007)；配置与决策见[同步清单](../../governance/upstream-sync.json)。

本次观察 [PyO3 upstream](https://github.com/PyO3/pyo3) 的最新提交为 [`fda3c5846d30042c9352885f415435c06f2e4985`](https://github.com/PyO3/pyo3/commit/fda3c5846d30042c9352885f415435c06f2e4985)， 父提交就是本仓库保留的技术来源 `424149e8a1c42128b05a090941673008fc46c478`。
该提交更新 taiki-e/install-action 2.87.27 → 2.87.28 和 CodSpeedHQ/action 5.4.2 → 5.5.0。
这是观察时唯一新增的上游提交，没有新 SDK 运行时修复可移植。
本次用真实依赖更新完成同步、冲突处理和回归流程；不宣称已完成 SDK 版本升级或运行时修复的冲突演练。

从真实 GitHub API 下载完整原始 patch，SHA-256 为 `abafb1bed41840b8f4424917db4b8996d9338720379b48b120764e0d3e1cc495`。
在 `25bf6fde2c074b0fd54804ffa4e16cc74462145d` 的独立 Git checkout 内，原始 patch 检查失败： benches 第 49 行和 CI 第 693 行上下文因本地矩阵/分流实现发生变化。
映射只更换精确 Action pin，并覆盖 r2p 新增的两个 installer 使用点。
保留矩阵选择、simulation、上传开关及站点发行开关；更新本地 runner 注释。
没有替换或撤回本地 SDK 补丁。

映射后的 patch SHA-256 为 `77ee689210f8eeffe0c4747793ead7a7e2342fef2a7382cdb2de938fd112a4db`。
`git apply --check`、真实应用和三个完整工作流文件的内容摘要对比均通过。
破坏源 patch 内容以及修改预期 pin 数量的负向验证均被阻断。
重放副本必须有独立 Git 根；否则 Git 会按父仓库子目录前缀忽略 patch 路径。
工具同时检查应用后内容，防止这种无修改的“成功”被接受。

按来源基线与演练前 r2p SHA 的实际树差异生成 1,166 条文件清单，每条包括路径、变更类型、分组和负责人。
文件分组为身份/清单 34、打包适配 66、源码与工程 872、文档/素材 194。
这是未折叠 rename 的路径清单，包含机械命名迁移，不等于 872 项语义修改。
目录/身份差异由命名迁移和 product.toml 管理；私有 Maturin 适配器由消费回归管理； 快速测试、环境/MSRV、CI 分流和内省预算由本地独立提交及对应报告管理；治理/来源文档保留原始历史。
四类 patch owner 均为当前真实维护者，没有将 Cargo 别名视作生态类型适配。
SDK 版本仍为 0.30.0，运行时来源仍为 424149e8，工程 Action 对应新增提交；版本关系不变。

可复现命令：

```bash
gh api repos/PyO3/pyo3/commits/fda3c5846d30042c9352885f415435c06f2e4985 \
  -H Accept:application/vnd.github.patch > upstream.patch
python tools/upstream_sync.py --patch upstream.patch --output target/upstream-replay
```

工具要求 Python 3.14，验证源 patch SHA 和 header，保留原始/映射 patch、冲突输出、内容摘要及文件清单。
本次原始日志与数据位于 `target/optimization/upstream-sync/` 和 `upstream-sync.log`。
更新后工作流 actionlint（兼容副本）和 zizmor 通过；工程命令、policy 与回归结果见对应当前报告及最终 CI。
实际 CodSpeed simulation 运行和 installer 网络下载仍以远端运行结果验收。
