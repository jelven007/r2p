# CI 目标解释器绑定修复

日期：2026-10-25；范围：O-03/O-04/O-05 后续真实矩阵反馈；状态：本地命令验证通过，远端复验待完成。

[CI 40144963618 的 Windows PyPy 3.12 任务](https://github.com/jelven007/r2p/actions/runs/40144963618/job/121024346017) 在 abi3 Rust 测试启动时返回 `0xc0000139, STATUS_ENTRYPOINT_NOT_FOUND`。
该任务的 Nox 命令没有针对 PyPy 应生成的 `--no-run`，并运行了独立 CPython Rust 测试。
复用 build 工作流此前没有将 `uv run` 显式绑定到 setup-python 的可执行文件，工具与目标解释器选择可漂移。
任务标签不构成实际解释器证据；失败和被 fail-fast 取消的完整矩阵不记为支持验证成功。

build 工作流现在从 setup-python 的 `python-path` 输出取得可执行文件，同时写入 `UV_PYTHON` 和 `R2P_PYTHON`。
记录实际 executable、实现、版本和 free-threaded 标志，Nox 与 Rust 发现使用同一目标。
唯一没有 setup-python 的既有 macOS x64 3.9 场景使用 setup-uv 安装的明确目标；其他输出缺失直接阻断。
附加 Windows PyPy 失败诊断读取测试 exe 的 Python DLL 导入与真实 DLL 导出，不修改 SDK 符号声明。

本机 Rust 1.99.1 下，工具 CPython 3.14.9 启动显式绑定的 PyPy 3.12.15。
`python tools/dev.py --target-python <PyPy> -- -s test-rust -- scope=abi skip-full` 生成 `cargo test --features=abi3 --no-run --no-default-features --all-targets`，5 个测试可执行文件编译成功，Nox 会话成功。
PyPy 没有 Py_Initialize API，独立 Rust 嵌入测试只编译；Python 扩展测试由目标 PyPy 自己运行，留待最终 CI。
未将直接执行 PyPy 嵌入测试的失败作为新的 SDK 内存错误，也未为它变更生命周期实现。
环境快照为 `target/optimization/pypy-bound-environment.json`，原始日志为 `pypy-bound.log`； Windows 原始错误日志为 `pypy-windows-failure.log`。

下载失败任务使用的官方 PyPy 8.0.1 Windows 分发并检查真实 PE 导出； 本机 ABI 测试二进制的 Python 导入与该 DLL 未发现缺失符号。
因此本次没有据此修改 FFI，Windows 专用导入的最终诊断仍由真实任务完成。
工作流 actionlint（兼容副本）和 zizmor 均通过。
最终解释器、ABI、平台行为和汇总结果必须按修复后的 SHA 重新核验。

后续 [CI 40150316493](https://github.com/jelven007/r2p/actions/runs/40150316493) 的 engineering 中，格式、仓库/证据和工具回归已通过，随后在 actionlint 安装阶段失败。
taiki-e/install-action 不支持 actionlint，回退 Cargo binstall 后报告该 crate 不存在；actionlint 是 Go 工具。
已改为下载官方 1.7.12 Linux amd64 release，并核验官方 asset SHA-256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`。
工作流兼容副本 actionlint 和 zizmor 均通过，原始失败日志为 `target/optimization/engineering-ba53-failure.log`。
该失败仍保留原始结果，新的安装步骤等待最终远端复验。

该完整周期最终结束：91 个任务已完成，engineering 和 Windows GraalPy 失败，conclusion 正确阻断。
[Windows GraalPy 任务](https://github.com/jelven007/r2p/actions/runs/40150316493/job/121040450770) 的官方 25.4.4 分发安装及 ensurepip 已成功运行 `bin/python.exe`；setup-python 的 `python-path` 却返回不存在的 `Scripts/python.exe`，绑定步骤因此退出 127，尚未运行 SDK 测试。
已针对 Windows GraalPy 使用同一安装目录的 `bin/python.exe`；其他目标仍读取原输出。
原始日志为 `target/optimization/graalpy-windows-40150316493.log`。
这是安装器路径修正，未以其他解释器代替 GraalPy，也未减少矩阵；实际版本和 SDK 行为等待新 SHA 的远端运行。
