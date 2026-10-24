# Python 产品包

`r2p-runtime/` 是当前独立 Python 包，使用自身 `pyproject.toml`、`src/`、测试和许可。
该包与跨语言测试扩展的用途不同；后者位于 `tests/python/`。

新 Python 产品按包划分目录，维护构建配置、测试、依赖、README 和发行身份。
不要将虚拟环境、wheel 或缓存放入源码。

入口：[运行时包说明](r2p-runtime/README.md)、[开发指南](../docs/development/developer-guide.md)、[发行方案](../docs/maintenance/release-and-rollback.md)。
