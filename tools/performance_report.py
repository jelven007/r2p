"""Preserve raw walltime measurements and render their bounded conclusions."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from tools.candidate_artifacts import digest
from tools.performance import summarize, validate_work


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gil", required=True, type=Path)
    parser.add_argument("--free-threaded", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    datasets = [json.loads(path.read_text()) for path in (args.gil, args.free_threaded)]
    for data in datasets:
        if not data.get("finished_at") or data["mode"] != "walltime":
            parser.error("both immutable measurements must be completed walltime runs")
        if data["schema_version"] == 1:
            if len(data["samples"]) != 102 or len(data["builds"]) != 27:
                parser.error(
                    "expected three independent processes and all build profiles"
                )
        elif data["schema_version"] == 2:
            repeats = data["runtime_samples"]
            cases = 16 if data["threaded_only"] else 25
            if (
                repeats < 3
                or len(data["samples"]) != 2 * repeats * cases
                or len(data["processes"]) != 2 * repeats
                or len(data["builds"]) != 9 * data["build_samples"]
                or (not data["builds"] and len(data["runtime_setup"]) != 2)
            ):
                parser.error("incomplete runtime/build sampling")
            for variant in ("baseline", "candidate"):
                for repeat in range(repeats):
                    validate_work(
                        [
                            row
                            for row in data["samples"]
                            if row["variant"] == variant and row["repeat"] == repeat
                        ],
                        data["iterations"],
                        data["threaded_only"],
                    )
        else:
            parser.error("unsupported measurement schema")
    if (
        datasets[0]["baseline"] != datasets[1]["baseline"]
        or datasets[0]["candidate"] != datasets[1]["candidate"]
    ):
        parser.error("the interpreter measurements must compare identical revisions")
    preserved = {
        "schema_version": 1,
        "input_sha256": {
            "gil": digest(args.gil),
            "free-threaded": digest(args.free_threaded),
        },
        "datasets": datasets,
    }
    args.data.parent.mkdir(parents=True, exist_ok=True)
    args.data.write_text(json.dumps(preserved, indent=2) + "\n")
    lines = [
        "# walltime 性能与编译成本基线验证",
        "",
        "日期：2026-10-25；结果：采样完成，未宣称实现运行时加速或通过 5% 性能门限。",
        f"源码：基线 `{datasets[0]['baseline']}`；候选 `{datasets[0]['candidate']}`。",
        "",
        "在 Apple M4 / macOS 26.5.1 / Rust 1.99.1 上分别运行 CPython 3.14.9 GIL 和 3.14.9 free-threaded。",
        "实际 `_is_gil_enabled` 与模式一致；native ABI；release、incremental=1、jobs=4；离线编译使用已缓存的第三方依赖。",
        f"两模式合计 {sum(len(data['samples']) for data in datasets)} 条运行和 {sum(len(data['builds']) for data in datasets)} 条编译成本样本。",
        "runtime_setup 中的编译仅用于产生可执行文件，不纳入独立编译成本样本。",
        "基线/候选依赖锁在每种模式内摘要相等；采样程序摘要、实际锁、制品摘要、环境与原始值均保留。",
        f"原始数据见 [{args.data.name}]({Path('../data') / args.data.name})；本地完整日志在 `target/optimization/performance-{{gil,ft}}-20261025/`。",
        "",
        "## 方法与限制",
        "",
        "每个进程预热后顺序测量调用、转换、容器、附着、直接/延迟释放和 1/2/4/8 线程。",
        "schema 1 第 2 轮反转次序；schema 2 采用 ABBA，分别记录进程次序、负载和执行时 GIL。",
        "线程初始化在计时外，计时从 barrier 放行至所有线程结束。",
        "fixed_per_thread 的总工作量随线程数增加；fixed_total 将同一总工作量分摊到线程，余数也计入。",
        "机器未锁频、未隔离调度，期间有轻量工程检查但没有并行 Rust 编译；热状态、系统负载和次序效应仍可能影响结果。",
        "这些本地样本只支持描述中位数、均值、样本标准差、极值与 CV，不估计 P95，不足以确定因果或证明 5% 门限。",
        "free-threaded 并发样本出现高波动与明显次序差异；这是后续重复测量的重点，不能据此认定某个内部 Mutex 或释放算法导致退化。",
        "没有修改 ReferencePool、公开调用 API 或核心同步算法；候选的主要变化属于工程入口、消费和解析边界。",
        "",
        "## 运行样本",
        "",
        "单位为 ns/操作；批量与容器按元素计，64 对象释放按对象计。",
        "Δ 为候选/基线中位数 − 1；正值代表更慢。",
        "完整原始数据包含各次耗时、均值和标准差；CV 是样本标准差/均值。",
        "",
        "| 模式 | 场景 | 工作量模型 | 线程 | 基线中位数 | 候选中位数 | 候选 min–max | 基线/候选 CV | Δ |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows = summarize(datasets[0]["samples"] + datasets[1]["samples"])
    indexed = {
        (
            row["python_mode"],
            row["variant"],
            row["case"],
            row["threads"],
            row["work_model"],
        ): row
        for row in rows
    }
    for row in rows:
        if row["variant"] != "candidate":
            continue
        baseline = indexed[
            (
                row["python_mode"],
                "baseline",
                row["case"],
                row["threads"],
                row["work_model"],
            )
        ]
        values = [
            sample["elapsed_ns"] / sample["units"]
            for data in datasets
            for sample in data["samples"]
            if all(
                sample[key] == row[key]
                for key in ("python_mode", "variant", "case", "threads")
            )
            and sample.get("work_model", "fixed_per_thread") == row["work_model"]
        ]
        lines.append(
            f"| {row['python_mode']} | {row['case']} | {row['work_model']} | {row['threads']} "
            f"| {baseline['median_ns_per_unit']:.2f} | {row['median_ns_per_unit']:.2f} "
            f"| {min(values):.2f}–{max(values):.2f} | {baseline['cv']:.1%}/{row['cv']:.1%} "
            f"| {row['relative_median_change']:+.1%} |"
        )
    lines += [
        "",
        "## 编译与制品",
        "",
        "clean 使用独立且空的 target；consumer-edit 与 sdk-edit 分别追加注释后编译，再恢复源码。",
        "这测量无语义编辑引发的增量失效成本，不代表修改公开 API 后的重编译成本。",
        "依赖下载与安装不计入这些离线 build 时间。",
        "RSS 为 `/usr/bin/time -l` 报告的最大子进程驻留集，不是同时并行的进程内存总和；表中 RSS 取三次最大值。",
        "二进制大小取三次中位数；启用 full 的未使用代码可能被移除，不能把此探针大小外推到实际产品。",
        "",
        "| 模式 | 源码/特性 | 构建 | 中位数 s | min–max s | 最大 RSS MiB | 二进制 bytes |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for data in datasets:
        if not data["builds"]:
            continue
        for variant, profile in (
            ("baseline", "minimal"),
            ("candidate", "minimal"),
            ("candidate", "full-sdk"),
        ):
            for kind in ("clean", "consumer-edit", "sdk-edit"):
                builds = [
                    row
                    for row in data["builds"]
                    if (row["variant"], row["profile"], row["kind"])
                    == (variant, profile, kind)
                ]
                seconds = [row["seconds"] for row in builds]
                lines.append(
                    f"| {builds[0]['python_mode']} | {variant}/{profile} | {kind} "
                    f"| {statistics.median(seconds):.2f} | {min(seconds):.2f}–{max(seconds):.2f} "
                    f"| {max(row['peak_rss_bytes'] for row in builds) / 1024**2:.1f} "
                    f"| {int(statistics.median(row['binary_bytes'] for row in builds))} |"
                )
    lines += [
        "",
        "## simulation 与后续决策",
        "",
        "[benches 40150316510](https://github.com/jelven007/r2p/actions/runs/40150316510) 已成功完成，但它的 CodSpeed simulation 结果与本表 walltime 分开管理。",
        "simulation 中被排除的并发扩展性、Python custom iterations 跳过不回填为 walltime 支持，也不以套件成功代替退化判断。",
        "编译成本结论仅由独立 clean/edit 样本支持；runtime_setup 的单次编译不作成本比较。",
        "保留现有同步实现；下次在固定总工作量、独占且稳定热状态的环境扩大并发重复样本，再决定是否深入竞争分析。",
        "",
        "复现：`python -m tools.performance --baseline <上述完整 SHA> --candidate <上述完整 SHA> --gil-python <CPython 3.14.9> --free-threaded-python <3.14.9t> --output <新目录>`。",
        "报告生成：`python -m tools.performance_report --gil <GIL samples.json> --free-threaded <FT samples.json> --data <JSON> --report <Markdown>`。",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
