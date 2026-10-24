# 仓库外源码消费验证

日期：2026-10-25；范围：O-02；状态：本地验收通过。
SDK 来源为 `https://github.com/jelven007/r2p` 的 `3a24917eb2766aa8ded8c04fefde1c1d4b133c00`。
生成器、模板与示例为本轮工作区候选；生成时 HEAD 为 `41f76e752956f889caeb1c50827f2284544d95c5`，不将未提交模板算作该 SHA 的内容。
工具环境为 macOS arm64、Rust 1.99.1、CPython 3.14.9、uv 0.13.5、Maturin 1.15.0、cargo-generate 0.25.1。

## 实现与验证

`tools/new_project.py` 显式选择 Git SHA、本地 checkout 或已验证注册表版本，不覆盖已有目录。
九个模板默认使用同一 Git 来源；私有适配器的 FFI 来源同步，注册表准入列表当前为空。
去掉模板适配器的嵌套 workspace，解决真实 Cargo 构建错误。
`.genignore` 排除本机缓存、Meson staged subprojects、旧锁及 macOS 元数据，解决 cargo-generate 误处理二进制缓存的问题。

```sh
python -m tools.consumer_smoke --output target/optimization/consumer-git-2
```

该命令在系统临时目录生成全部九个项目，逐个执行 Cargo metadata，保存九个消费方锁。
SDK 和适配器只解析出一份同 SHA 的 `r2p-ffi`。
Maturin 先生成 sdist，再从解包目录构建 native/abi3 两个 release wheel。
两个新虚拟环境分别安装 wheel，用 `python -I` 从消费项目外导入并验证函数、类 getter/setter、子模块、零除/整数溢出 ValueError 和异常后恢复。
Rust plugin 独立执行，验证 Rust/Python 类交换、捕获 Python ValueError 和继续计算。
24 条实际命令全部成功，命令合计约 83 秒；这是一次执行样本，不是性能基线。

| 制品 | SHA-256 |
| --- | --- |
| sdist `maturin_starter-0.1.0.tar.gz` | `8ccd18e8e6cc0276101e258df2875b3b677941f9f2bc29e8737837bdd46ad919` |
| native `cp314-cp314-macosx_11_0_arm64` | `d19a33751d555784937c4d0eae4c83b6e2a02074ef40bf8ca36c3fbdfa08c3ce` |
| abi3 `cp39-abi3-macosx_11_0_arm64` | `a7521ef3cada6fe2c2b0c054a1319bd242b633151eeb45a452e597db1644b45d` |

实际 WHEEL 元数据与文件名一致；两个 wheel 均在 CPython 3.14.9 运行。
没有将 cp39 标签当作 Python 3.9–3.13 的运行证据。

另用 `cargo generate --path <template> --name <name> --destination <existing-parent> --silent --define authors=r2p --no-workspace` 生成九个项目，逐个 metadata 和同源 FFI 检查均成功。
本机原始日志为 `target/optimization/cargo-generate-check-3.log`，消费链路的命令、输出、锁、制品和结构化记录保存在 `target/optimization/consumer-git-2/`。
五项模板契约测试覆盖浮动/未验证来源拒绝、同源依赖、特性保留、不覆盖目录、重复 FFI/混合来源阻断。

## 持续验证与限制

CI 的 `consumer-smoke` 使用受审 SDK SHA 生成仓库外项目，保存完整消费记录及制品。
SDK 文档与工具说明已同步入口；Python 模块名独立于发行包名。
本次证明两个真实集成场景在上述环境成功，不代表已取得外部用户采用或其他 OS 的安装证据。
外部注册表和站点发行继续采用独立准入。
