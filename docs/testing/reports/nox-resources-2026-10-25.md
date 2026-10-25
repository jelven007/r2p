# Nox 拆分与临时资源验收

日期：2026-10-25；R-06 本地实施完成。
比较基线 `02cad3d1` 与本轮工作区；最终 SHA 的远端验证仍归 R-01。

## 接口与职责

文档参数/站点路由、WASM 平台元数据、内省库变体分别移入 `tools/engineering/documentation.py`、`platforms.py`、`packaging.py`。
Nox 从 2,204 行降至 2,039 行，40 个会话的名称、函数参数和 Nox decorator 配置逐项相等。
不以减少行数作为性能收益。

实际加载拆分前后函数进行比较：20 组 docs 参数/环境、15 组平台命令/路径/版本、3 组原生打包命令、12 组站点配置通过。
原 Netlify 目录根 canonical 路径在首次比较中发现遗漏，已修复后重新比较。
完整比较脚本和结果保留在 `target/optimization/nox-refactor-{check.py,result.json}`。
站点文件的规则集合相等；目录遍历顺序不构成验收承诺。

## 保留与清理

CLI wheel 的原始文件和行为结果保留在 dist；安装 venv/输入夹具改为 dist 下 `.scratch/`。
成功后清理 scratch，失败保留现场。
真实安装 baseline 的 macOS arm64 CLI 并执行参数错误、坏输入及 ELF stub 探针后，scratch 已清理。
真实离线安装不存在的包失败，安装日志和失败标记保留。
该实验使用 `3a24917e` 的已验收 wheel，不将它标为本轮源码的新 wheel。
日志与摘要在 `target/optimization/resource-cli-20261025/evidence.json`。

MSRV 有后续会话且全部成功时，将精确 Cargo.lock 和 msrv-evidence.json 复制至独立证据目录并校验摘要，再清理源码快照。
只有依赖准备、没有后续会话时仍保留可供继续验证的快照；任何失败也保留完整快照。
Rust 1.85.1 / CPython 3.14.9 的真实 `set-msrv-package-versions -- docs` 通过，原 checkout 已清理，锁和证据位于 `target/msrv/checkout-g9uprtl4-evidence/`。
工作区 Cargo.lock 摘要未变。
预期不存在的 Nox 会话用于验证失败路径，详见 `target/optimization/msrv-resources-failure-20261025.log`。

## 原始制品取回

`artifact_bundle.py` 只归档原始 crate/wheel、消费者锁和 manifest，不带 build target、Cargo home 或 venv。
取回必须提供保存的 source SHA 和归档 SHA256，并逐文件校验后运行原 manifest 验证。
目标目录必须不存在；摘要错误、重复路径、目录逃逸或非普通文件会拒绝。
取回失败现场保留，不自动覆盖既有制品。

真实 `0.30.1 fixture → 0.30.0` 验收组共 25 个文件完成归档及取回复验。
归档摘要为 `bff15cf11db4a171eb69187262e3bf772ccd955c362f37d320cb73435784b93f`。
原 manifest 摘要保持 `cb00912789f5c17e25f63ac91c15a21121bc7653c4a1d14c94db0999db851785`。
结果在 `target/optimization/artifact-retention-20261025.json`；取回目录 `target/optimization/candidate-retrieved-20261025/`。
最后验收的原始目录和两个 history 标签未删除或移动。

CI 上传的候选/发布 journal 保留 90 天；在到期前应取回并验证已验收包。
本地最终验收包、精确锁和归档没有自动到期删除。
只有确认更新制品已完成等价验收并有可取回副本时才清理旧本地组；本轮没有执行此类清理。
失败现场默认保留至调查完成后由维护者决定清理，不自动将失败记录升级为成功。
