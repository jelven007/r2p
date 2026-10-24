# 平台构建与站点资源

| 位置 | 内容 |
| --- | --- |
| `wasm/` | WASI/Emscripten Makefile、runner 及共享构建配置 |
| `netlify/` | 内部 Rustdoc 横幅和保留的重定向脚本 |
| `.github/`（根） | 实际平台发现的工作流、Actions 及 Netlify Node 工具 |

根 Nox 和 Actions 引用此目录。
Netlify 站点构建仍包含上游域名/版本内容，独立部署前须完成身份、目标和权限调整；保留资源不代表本仓库已有线上环境。
站点部署由 `R2P_ENABLE_NETLIFY` 显式控制，当前默认关闭。

WebAssembly 使用对应 Nox 会话和工具链，不能以 macOS 原生回归代替平台验证。
当前没有定义业务服务容器、数据库或 Kubernetes 资源。

入口：[目录映射](../docs/development/repository-layout.md)、[运维手册](../docs/runbooks/incident-response.md)、[发行与回退](../docs/releases/release-and-rollback.md)。
