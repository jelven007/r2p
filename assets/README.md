# 资源文件

根资源文件服务于已有测试/示例；`branding/` 保留上游 PyO3 品牌素材及 favicon。
保留素材不代表本仓库取得独立品牌身份。

Rust `include_bytes!` / `include_str!` 使用的资源应保持可解析并纳入相应 Cargo 包。
新增素材记录来源、用途和许可，不将生成的构建输出或机器截图混入源码资源。

目录规则见[目录规范](../docs/development/repository-layout.md)，产品来源见[项目分析](../docs/governance/project-assessment.md)。
