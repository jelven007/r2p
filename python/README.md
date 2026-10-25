# Python 产品包

`r2p-runtime/` 是独立 Python runtime 的预留目录，仅有版本常量，尚未实现运行时功能，禁止公开发行。
当前 SDK 跨语言测试扩展位于 `tests/python/`；已实现的 SDK、嵌入和 CLI 入口见[SDK 入门](../docs/sdk/README.md)。

新 Python 产品按包划分目录，维护构建配置、测试、依赖、README 和发行身份。
不要将虚拟环境、wheel 或缓存放入源码。

入口：[运行时包说明](r2p-runtime/README.md)、[开发指南](../docs/development/developer-guide.md)、[发行方案](../docs/releases/release-and-rollback.md)。
