# walltime 性能与编译成本基线验证

日期：2026-10-25；结果：采样完成，未宣称实现运行时加速或通过 5% 性能门限。
源码：基线 `3a24917eb2766aa8ded8c04fefde1c1d4b133c00`；候选 `ba53c8a1c38498891bde3091209f9a63302f1c0d`。

在 Apple M4 / macOS 26.5.1 / Rust 1.99.1 上分别运行 CPython 3.14.9 GIL 和 3.14.9 free-threaded。
实际 `_is_gil_enabled` 与模式一致；native ABI；release、incremental=1、jobs=4；离线编译使用已缓存的第三方依赖。
每种模式为 17 个场景 × 两个源码 × 三个独立进程，共 102 条运行样本；三种构建配置 × 三次 × 三类构建，共 27 条编译样本。
两模式合计 204 条运行和 54 条编译样本。
基线/候选依赖锁在每种模式内摘要相等；采样程序摘要、实际锁、制品摘要、环境与原始值均保留。
原始数据见 [performance-2026-10-25.json](../data/performance-2026-10-25.json)；本地完整日志在 `target/optimization/performance-{gil,ft}-20261025/`。

## 方法与限制

每个进程预热后顺序测量调用、转换、容器、附着、直接/延迟释放和 1/2/4/8 线程。
第 2 轮反转基线/候选次序。
线程初始化在计时外，计时从 barrier 放行至所有线程结束；线程数改变时总工作量也随线程数增加，因此下表单位成本可比较，不等于固定总工作量的加速比。
机器未锁频、未隔离调度，期间有轻量工程检查但没有并行 Rust 编译；热状态、系统负载和次序效应仍可能影响结果。
三次样本只支持描述中位数、均值、样本标准差、极值与 CV，不估计 P95，不足以确定因果或证明 5% 门限。
free-threaded 并发样本出现高波动与明显次序差异；这是后续重复测量的重点，不能据此认定某个内部 Mutex 或释放算法导致退化。
没有修改 ReferencePool、公开调用 API 或核心同步算法；候选的主要变化属于工程入口、消费和解析边界。

## 运行样本

单位为 ns/操作；批量与容器按元素计，64 对象释放按对象计。
Δ 为候选/基线中位数 − 1；正值代表更慢。
完整原始数据包含各次耗时、均值和标准差；CV 是样本标准差/均值。

| 模式 | 场景 | 线程 | 基线中位数 | 候选中位数 | 候选 min–max | 基线/候选 CV | Δ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| free-threaded | attach_detach | 1 | 9.43 | 10.17 | 9.15–10.19 | 2.1%/6.0% | +7.8% |
| free-threaded | batch_call_64 | 1 | 22.46 | 23.10 | 19.37–25.81 | 12.2%/14.2% | +2.8% |
| free-threaded | bytes_roundtrip_256 | 1 | 19.18 | 19.78 | 16.98–21.73 | 11.6%/12.3% | +3.1% |
| free-threaded | dict_iter_1024 | 1 | 16.12 | 16.91 | 16.33–18.84 | 0.2%/7.6% | +4.9% |
| free-threaded | drop_attached_64 | 1 | 12.35 | 13.23 | 13.13–13.91 | 1.9%/3.2% | +7.1% |
| free-threaded | drop_deferred_64 | 1 | 20.84 | 22.08 | 21.70–22.95 | 1.9%/2.9% | +6.0% |
| free-threaded | list_iter_1024 | 1 | 8.99 | 9.63 | 8.67–10.06 | 1.7%/7.5% | +7.1% |
| free-threaded | scalar_calls_64 | 1 | 24.73 | 25.68 | 19.97–27.55 | 4.1%/16.2% | +3.8% |
| free-threaded | string_roundtrip_240 | 1 | 31.94 | 32.68 | 27.67–35.60 | 9.3%/12.5% | +2.3% |
| free-threaded | threaded_call_attach_detach | 1 | 54562.38 | 56744.71 | 54202.56–57424.62 | 0.7%/3.0% | +4.0% |
| free-threaded | threaded_call_attach_detach | 2 | 13139.28 | 13254.92 | 13204.61–19124.73 | 18.2%/22.4% | +0.9% |
| free-threaded | threaded_call_attach_detach | 4 | 2383.14 | 5710.92 | 3168.11–6113.59 | 41.1%/32.0% | +139.6% |
| free-threaded | threaded_call_attach_detach | 8 | 4622.48 | 5315.46 | 3675.82–7481.38 | 18.3%/34.8% | +15.0% |
| free-threaded | threaded_deferred_drop_64 | 1 | 2878.17 | 2918.09 | 2870.60–3431.03 | 3.0%/10.1% | +1.4% |
| free-threaded | threaded_deferred_drop_64 | 2 | 593.26 | 639.23 | 495.60–752.63 | 9.8%/20.5% | +7.7% |
| free-threaded | threaded_deferred_drop_64 | 4 | 99.29 | 175.51 | 110.64–257.57 | 46.5%/40.6% | +76.8% |
| free-threaded | threaded_deferred_drop_64 | 8 | 171.23 | 179.06 | 156.02–202.34 | 21.1%/12.9% | +4.6% |
| gil | attach_detach | 1 | 23.38 | 24.12 | 22.26–24.78 | 2.8%/5.5% | +3.2% |
| gil | batch_call_64 | 1 | 19.16 | 19.53 | 18.77–20.17 | 3.8%/3.6% | +1.9% |
| gil | bytes_roundtrip_256 | 1 | 17.02 | 17.12 | 16.99–17.24 | 0.9%/0.7% | +0.6% |
| gil | dict_iter_1024 | 1 | 7.68 | 7.63 | 7.55–7.85 | 1.0%/2.0% | -0.6% |
| gil | drop_attached_64 | 1 | 12.40 | 13.42 | 12.23–13.64 | 3.8%/5.8% | +8.2% |
| gil | drop_deferred_64 | 1 | 21.53 | 22.57 | 21.49–23.87 | 2.2%/5.3% | +4.8% |
| gil | list_iter_1024 | 1 | 3.44 | 3.32 | 3.27–3.43 | 4.0%/2.5% | -3.5% |
| gil | scalar_calls_64 | 1 | 20.94 | 20.81 | 19.69–21.35 | 6.8%/4.1% | -0.6% |
| gil | string_roundtrip_240 | 1 | 31.95 | 30.34 | 29.31–31.28 | 3.7%/3.3% | -5.0% |
| gil | threaded_call_attach_detach | 1 | 111.83 | 106.79 | 106.11–109.25 | 6.6%/1.5% | -4.5% |
| gil | threaded_call_attach_detach | 2 | 261.25 | 269.61 | 252.93–280.28 | 8.3%/5.1% | +3.2% |
| gil | threaded_call_attach_detach | 4 | 935.94 | 864.82 | 833.93–1110.49 | 7.9%/16.2% | -7.6% |
| gil | threaded_call_attach_detach | 8 | 5264.62 | 4989.20 | 4978.10–5087.57 | 11.1%/1.2% | -5.2% |
| gil | threaded_deferred_drop_64 | 1 | 24.54 | 22.77 | 21.95–25.06 | 6.2%/6.9% | -7.2% |
| gil | threaded_deferred_drop_64 | 2 | 50.73 | 53.07 | 51.67–53.22 | 4.8%/1.6% | +4.6% |
| gil | threaded_deferred_drop_64 | 4 | 85.32 | 84.88 | 84.50–85.66 | 11.3%/0.7% | -0.5% |
| gil | threaded_deferred_drop_64 | 8 | 119.08 | 116.48 | 116.28–121.06 | 12.1%/2.3% | -2.2% |

## 编译与制品

clean 使用独立且空的 target；consumer-edit 与 sdk-edit 分别追加注释后编译，再恢复源码。
这测量无语义编辑引发的增量失效成本，不代表修改公开 API 后的重编译成本。
依赖下载与安装不计入这些离线 build 时间。
RSS 为 `/usr/bin/time -l` 报告的最大子进程驻留集，不是同时并行的进程内存总和；表中 RSS 取三次最大值。
二进制大小取三次中位数；启用 full 的未使用代码可能被移除，不能把此探针大小外推到实际产品。

| 模式 | 源码/特性 | 构建 | 中位数 s | min–max s | 最大 RSS MiB | 二进制 bytes |
| --- | --- | --- | --- | --- | --- | --- |
| gil | baseline/minimal | clean | 26.00 | 23.67–26.52 | 396.7 | 674480 |
| gil | baseline/minimal | consumer-edit | 1.31 | 1.29–1.49 | 308.6 | 674480 |
| gil | baseline/minimal | sdk-edit | 2.92 | 2.53–4.21 | 308.6 | 674480 |
| gil | candidate/minimal | clean | 25.29 | 24.30–25.84 | 397.7 | 674432 |
| gil | candidate/minimal | consumer-edit | 1.27 | 1.18–1.47 | 308.6 | 674432 |
| gil | candidate/minimal | sdk-edit | 2.72 | 2.66–3.15 | 308.6 | 674432 |
| gil | candidate/full-sdk | clean | 48.60 | 47.74–51.37 | 582.8 | 674720 |
| gil | candidate/full-sdk | consumer-edit | 1.59 | 1.36–1.64 | 308.7 | 674720 |
| gil | candidate/full-sdk | sdk-edit | 4.84 | 4.20–4.86 | 433.0 | 674720 |
| free-threaded | baseline/minimal | clean | 26.96 | 25.33–30.54 | 400.9 | 675312 |
| free-threaded | baseline/minimal | consumer-edit | 1.39 | 1.14–1.42 | 308.6 | 675312 |
| free-threaded | baseline/minimal | sdk-edit | 2.74 | 2.45–4.25 | 308.6 | 675312 |
| free-threaded | candidate/minimal | clean | 29.52 | 25.00–30.13 | 400.5 | 675296 |
| free-threaded | candidate/minimal | consumer-edit | 1.26 | 1.22–1.28 | 308.6 | 675296 |
| free-threaded | candidate/minimal | sdk-edit | 3.70 | 3.25–3.98 | 308.6 | 675296 |
| free-threaded | candidate/full-sdk | clean | 65.10 | 44.66–70.41 | 582.4 | 675488 |
| free-threaded | candidate/full-sdk | consumer-edit | 1.56 | 1.55–2.23 | 308.7 | 675488 |
| free-threaded | candidate/full-sdk | sdk-edit | 4.82 | 4.16–6.01 | 434.5 | 675488 |

## simulation 与后续决策

[benches 40150316510](https://github.com/jelven007/r2p/actions/runs/40150316510) 已成功完成，但它的 CodSpeed simulation 结果与本表 walltime 分开管理。
simulation 中被排除的并发扩展性、Python custom iterations 跳过不回填为 walltime 支持，也不以套件成功代替退化判断。
最小特性明显降低本探针的干净编译成本；默认调用与 batch 的效果随解释器和 Python 函数内部工作变化，未形成通用批量加速承诺。
保留现有同步实现；下次在固定总工作量、独占且稳定热状态的环境扩大并发重复样本，再决定是否深入竞争分析。

复现：`python -m tools.performance --baseline <上述完整 SHA> --candidate <上述完整 SHA> --gil-python <CPython 3.14.9> --free-threaded-python <3.14.9t> --output <新目录>`。
报告生成：`python -m tools.performance_report --gil <GIL samples.json> --free-threaded <FT samples.json> --data <JSON> --report <Markdown>`。
