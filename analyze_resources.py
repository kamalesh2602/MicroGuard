"""MicroGuard Resource Utilization Analysis Pipeline.

Analyzes time-series resource measurements exported by measure_resources.ps1.
Computes mean, median, peak, and comparative overhead metrics for:
- Monolith Baseline (single container)
- Microservices Pipeline (Gateway + Service A + Service B combined)
- Infrastructure Tiers (Prometheus, Grafana, Locust - reported separately)
"""

import glob
import os
import sys
import pandas as pd


def analyze_single_file(filepath: str) -> pd.DataFrame:
    """Analyze a single resource usage time-series CSV and return summary metrics."""
    df = pd.read_csv(filepath)

    tiers = [
        ("Monolith Baseline (1 container)", "Monolith_CPU_Perc", "Monolith_Mem_MiB"),
        ("Gateway (microservice)", "Gateway_CPU_Perc", "Gateway_Mem_MiB"),
        ("Service A (microservice)", "ServiceA_CPU_Perc", "ServiceA_Mem_MiB"),
        ("Service B (microservice)", "ServiceB_CPU_Perc", "ServiceB_Mem_MiB"),
        ("Microservices Combined (3 containers)", "Microservices_Combined_CPU_Perc", "Microservices_Combined_Mem_MiB"),
        ("Infrastructure (Prometheus+Grafana+Locust)", "Infra_Combined_CPU_Perc", "Infra_Combined_Mem_MiB"),
    ]

    records = []
    for label, cpu_col, mem_col in tiers:
        if cpu_col in df.columns and mem_col in df.columns:
            cpu_series = df[cpu_col].dropna()
            mem_series = df[mem_col].dropna()

            records.append({
                "Architecture Tier": label,
                "Mean CPU (%)": round(cpu_series.mean(), 2),
                "Median CPU (%)": round(cpu_series.median(), 2),
                "Peak CPU (%)": round(cpu_series.max(), 2),
                "Min CPU (%)": round(cpu_series.min(), 2),
                "Mean Mem (MiB)": round(mem_series.mean(), 2),
                "Median Mem (MiB)": round(mem_series.median(), 2),
                "Peak Mem (MiB)": round(mem_series.max(), 2),
                "Min Mem (MiB)": round(mem_series.min(), 2),
            })

    summary_df = pd.DataFrame(records)
    return summary_df


def compare_two_runs(monolith_file: str, microservices_file: str) -> pd.DataFrame:
    """Compare a dedicated monolith run against a dedicated microservices run."""
    mono_df = pd.read_csv(monolith_file)
    ms_df = pd.read_csv(microservices_file)

    mono_cpu = mono_df["Monolith_CPU_Perc"].dropna()
    mono_mem = mono_df["Monolith_Mem_MiB"].dropna()

    ms_cpu = ms_df["Microservices_Combined_CPU_Perc"].dropna()
    ms_mem = ms_df["Microservices_Combined_Mem_MiB"].dropna()

    comparison = pd.DataFrame([
        {
            "Metric": "Mean CPU (%)",
            "Monolith Baseline": round(mono_cpu.mean(), 2),
            "Microservices Combined": round(ms_cpu.mean(), 2),
            "Delta (%)": round(((ms_cpu.mean() - mono_cpu.mean()) / mono_cpu.mean()) * 100, 1) if mono_cpu.mean() else 0,
            "Ratio (MS / Mono)": round(ms_cpu.mean() / mono_cpu.mean(), 2) if mono_cpu.mean() else 0,
        },
        {
            "Metric": "Peak CPU (%)",
            "Monolith Baseline": round(mono_cpu.max(), 2),
            "Microservices Combined": round(ms_cpu.max(), 2),
            "Delta (%)": round(((ms_cpu.max() - mono_cpu.max()) / mono_cpu.max()) * 100, 1) if mono_cpu.max() else 0,
            "Ratio (MS / Mono)": round(ms_cpu.max() / mono_cpu.max(), 2) if mono_cpu.max() else 0,
        },
        {
            "Metric": "Mean Memory (MiB)",
            "Monolith Baseline": round(mono_mem.mean(), 2),
            "Microservices Combined": round(ms_mem.mean(), 2),
            "Delta (%)": round(((ms_mem.mean() - mono_mem.mean()) / mono_mem.mean()) * 100, 1) if mono_mem.mean() else 0,
            "Ratio (MS / Mono)": round(ms_mem.mean() / mono_mem.mean(), 2) if mono_mem.mean() else 0,
        },
        {
            "Metric": "Peak Memory (MiB)",
            "Monolith Baseline": round(mono_mem.max(), 2),
            "Microservices Combined": round(ms_mem.max(), 2),
            "Delta (%)": round(((ms_mem.max() - mono_mem.max()) / mono_mem.max()) * 100, 1) if mono_mem.max() else 0,
            "Ratio (MS / Mono)": round(ms_mem.max() / mono_mem.max(), 2) if mono_mem.max() else 0,
        },
    ])
    return comparison


def main():
    args = sys.argv[1:]

    if len(args) == 2:
        print(f"\nComparing Monolith [{args[0]}] vs Microservices [{args[1]}]...\n")
        report = compare_two_runs(args[0], args[1])
        print(report.to_string(index=False))
        out_file = "results/resource_comparison_report.csv"
        report.to_csv(out_file, index=False)
        print(f"\nSaved comparison report to: {out_file}\n")
        return

    target_file = None
    if len(args) == 1:
        target_file = args[0]
    else:
        pattern = os.path.join("results", "resource_usage_*.csv")
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
        if files:
            target_file = files[0]
        else:
            print("No resource_usage_*.csv files found in results/ directory.")
            print("Run '.\\measure_resources.ps1 -DurationSeconds 30' first.")
            sys.exit(1)

    print(f"\nAnalyzing resource measurements from: {target_file}\n")
    summary = analyze_single_file(target_file)
    print(summary.to_string(index=False))

    out_file = os.path.join("results", "resource_summary_report.csv")
    summary.to_csv(out_file, index=False)
    print(f"\nSaved summary report to: {out_file}\n")

    mono = summary[summary["Architecture Tier"].str.contains("Monolith", na=False)]
    ms = summary[summary["Architecture Tier"].str.contains("Microservices Combined", na=False)]
    if not mono.empty and not ms.empty:
        mono_cpu = mono["Mean CPU (%)"].values[0]
        ms_cpu = ms["Mean CPU (%)"].values[0]
        mono_mem = mono["Mean Mem (MiB)"].values[0]
        ms_mem = ms["Mean Mem (MiB)"].values[0]

        if mono_cpu > 0 and mono_mem > 0:
            cpu_delta = round(((ms_cpu - mono_cpu) / mono_cpu) * 100, 1)
            mem_delta = round(((ms_mem - mono_mem) / mono_mem) * 100, 1)
            print("Key Architectural Findings:")
            print(f" - CPU Overhead: Microservices pipeline used {cpu_delta}% more mean CPU than Monolith.")
            print(f" - Memory Overhead: Microservices pipeline used {mem_delta}% more mean RAM than Monolith.\n")


if __name__ == "__main__":
    main()
