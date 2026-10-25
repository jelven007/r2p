# 实际环境与证据等级修正

日期：2026-10-25；范围：R-02，本地环境验证与已保存 CI 失败日志。
探针执行源码基点为 `643b3204aedd825d2c48107a45b8d580f6d09a0f`，包含本轮未提交工程变更；不作为该 SHA 的 SDK 完整验收。
原始数据见[环境探针](../data/environment-2026-10-25.json)及[历史 CI 失败摘录](../data/ci-failures-2026-10-25.json)。

## 实际结果

| 情况 | 编译模式 | 启动 GIL | 导入后 GIL | 结果 |
| --- | --- | --- | --- | --- |
| CPython 3.14.9 | 普通 | enabled | enabled | 通过 |
| CPython 3.14.9t，PYTHON_GIL=0 | FT | disabled | disabled | 通过 |
| CPython 3.14.9t，PYTHON_GIL=1 | FT | enabled | enabled | 通过 |
| CPython 3.14.9t，自动模式，导入旧 C 扩展 | FT | disabled | enabled | 通过 |
| CPython 3.9.6，无实际状态接口 | 普通 | unrecorded | unrecorded | 通过 |
| FT，导入不存在模块 | FT | disabled | disabled | 真实导入拒绝，状态记录通过 |
| 新 venv，离线安装不存在包 | 未运行目标 | unrecorded | unrecorded | 真实安装拒绝；无 SDK 执行 |

旧 C 扩展由 clang 在本机编译，采用没有 Py_mod_gil 声明的单阶段模块。
CPython 实际发出重新开启 GIL 的提示，探针分别记录导入前后的状态。
此扩展仅用于测量环境语义，不提供 r2p SDK 正确性证据。

## 工具行为

`tools.engineering.environment` 分开记录 free_threaded、gil_enabled 和 gil_after_imports，并保留每次模块导入的结果和错误。
缺少实际接口或旧快照缺少状态字段时，导入器记录 unrecorded，不再从编译标志、任务标签或 wheel ABI 推导。
消费者行为探针在同一进程内记录 SDK 导入前后的状态；CLI 和嵌入尚无同一进程观测时保留 unrecorded。

Actions 导入通过成功的实际步骤区分 configured、compiled、run；失败的测试命令组可能失败于安装或编译，只提供 check。
成功的 Rust 测试步骤在实际 CPython 下提升为 run；PyPy/GraalPy 使用 --no-run，或实现未观测时保留 compiled。
整体 failure 仍可关联此前成功的运行步骤，但不证明全部测试通过。
没有 SDK 步骤的成功任务也不升级为行为成功。
可以离线导入已保存的 API 导出及同源码环境快照，不需要重新查询远端。
环境快照 SHA 不同或工作区有改动会被拒绝。
工作流新增环境制品保留，实际远端产出仍待后续完整 CI。
本地失败的 Nox 命令组降为 configured，成功命令的等级由显式选定范围声明，默认 check。
这避免把安装失败、列举会话和整体运行结果自动视为 SDK 行为。

旧 evidence.json 记录保持不可变；新消费者、候选和 Actions 导入使用新的记录 ID。
历史记录中的 GIL 字段按原报告解释，不能补推未观测的模块后状态；新结构化环境与 GIL 标签不一致时检查拒绝。

## 保存的真实失败

CI 40150316493 的 Windows GraalPy 25.4.4 在绑定解释器时以 127 退出，SDK 测试尚未启动。
对应实际 checkout 为 `ba53c8a1c38498891bde3091209f9a63302f1c0d`。
engineering 的 actionlint 安装以 76 退出；该任务实际 checkout 为 PR 合并快照 `d874da8e66ff30a133bb6d659354f09b29b6608c`。
分别保留配置失败记录；不从请求配置推导实际 Rust 或 Python 运行版本。
这些内容来自之前保存的原始日志，本轮未访问 GitHub，也未将失败记录标为本轮已重新通过。

## 复现

```bash
python -m tools.verify_environment \
  --gil-python <CPython-3.14> \
  --ft-python <CPython-3.14t> \
  --legacy-python <CPython-3.9> \
  --output <new-directory>
python -m tools.evidence import-environment --snapshot <saved-evidence.json>
python -m unittest tools.tests.test_evidence -v
python -m tools.check_workflows --actionlint <actionlint>
```

工具测试覆盖 FT 编译标志与实际状态不同、导入后状态变化、缺失观测、失败等级、不同 SHA 拒绝，以及旧记录和摘要契约。
实际六种解释器/导入情况与离线安装负例已通过；工作流语法检查通过。
最终源码、完整 SDK 矩阵与跨平台运行仍须分别验收。
