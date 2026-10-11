
"""MicroGuard Load Test Analysis Pipeline.

Processes and compares Locust statistics CSV files.
Extracts Request Count, Failures, Failure Rate, Latency (Average, Median, P95), and Throughput.
"""

import argparse
import os
import sys
import pandas as pd


def parse_locust_stats_df(df: pd.DataFrame, label: str) -> dict:
    """Extract and validate summary performance statistics from a Locust DataFrame."""
    if df is None or df.empty:
        raise ValueError(f"Locust statistics dataset for '{label}' is empty.")

    # Locate summary row (Locust generates 'Aggregated', fallback to '/process' or first route)
    row = df[df["Name"] == "Aggregated"]
    if row.empty:
        row = df[df["Name"] == "/process"]
    if row.empty:
        # Fall back to first non-empty route row
        row = df[df["Request Count"] > 0]
    if row.empty:
        raise ValueError(f"No valid request records found in Locust statistics for '{label}'.")

    record = row.iloc[0]

    # Required metrics validation
    for col in ["Request Count", "Failure Count", "Average Response Time"]:
        if col not in record.index or pd.isna(record[col]):
            raise ValueError(f"Missing required column '{col}' in Locust statistics for '{label}'.")

    total = int(record["Request Count"])
    failures = int(record["Failure Count"])

    if total < 0 or failures < 0:
        raise ValueError(f"Invalid negative count in Locust statistics for '{label}': requests={total}, failures={failures}")

    # Latency percentiles
    avg_latency = round(float(record["Average Response Time"]), 2)

    # Median: use 'Median Response Time' or '50%'
    if "Median Response Time" in record.index and not pd.isna(record["Median Response Time"]):
        median_latency = round(float(record["Median Response Time"]), 2)
    elif "50%" in record.index and not pd.isna(record["50%"]):
        median_latency = round(float(record["50%"]), 2)
    else:
        median_latency = None

    # P95: use '95%' or '95%ile (ms)'
    if "95%" in record.index and not pd.isna(record["95%"]):
        p95_latency = round(float(record["95%"]), 2)
    elif "95%ile (ms)" in record.index and not pd.isna(record["95%ile (ms)"]):
        p95_latency = round(float(record["95%ile (ms)"]), 2)
    else:
        p95_latency = None

    # Throughput (requests/sec)
    rps = 0.0
    if "Requests/s" in record.index and not pd.isna(record["Requests/s"]):
        rps = round(float(record["Requests/s"]), 2)

    failure_rate = round((failures / total * 100), 2) if total > 0 else 0.0

    return {
        "Test": label,
        "Requests": total,
        "Failures": failures,
        "Failure Rate (%)": failure_rate,
        "Average Latency (ms)": avg_latency,
        "Median Latency (ms)": median_latency,
        "P95 Latency (ms)": p95_latency,
        "Requests/sec": rps,
    }


def load_and_parse_stats(filepath: str, label: str) -> dict:
    """Load a Locust statistics CSV file and parse its summary metrics with error checks."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Locust stats file not found at: {filepath}")

    if os.path.getsize(filepath) == 0:
        raise ValueError(f"Locust stats file is empty: {filepath}")

    df = pd.read_csv(filepath)
    return parse_locust_stats_df(df, label)


def compare_stats(file1: str, label1: str, file2: str, label2: str) -> pd.DataFrame:
    """Compare two Locust statistics CSV files."""
    stats1 = load_and_parse_stats(file1, label1)
    stats2 = load_and_parse_stats(file2, label2)
    return pd.DataFrame([stats1, stats2])


def main():
    parser = argparse.ArgumentParser(description="MicroGuard Load Test Analysis Pipeline.")
    parser.add_argument("files", nargs="*", help="Optional pair of CSV files to compare.")
    parser.add_argument("--monolith", help="Path to Monolith Locust stats CSV.")
    parser.add_argument("--microservices", help="Path to Microservices Locust stats CSV.")
    parser.add_argument("--normal", help="Path to Normal Load Locust stats CSV.")
    parser.add_argument("--fault", help="Path to Fault Injection Locust stats CSV.")
    parser.add_argument("--output", help="Output path for comparison CSV.")

    args = parser.parse_args()

    # Determine files and labels
    if args.monolith and args.microservices:
        f1, l1 = args.monolith, "Monolith Baseline"
        f2, l2 = args.microservices, "Microservices Pipeline"
        default_out = "results/locust_architecture_report.csv"
        title = "MicroGuard Architecture Benchmark: Monolith vs Microservices"
    elif args.normal and args.fault:
        f1, l1 = args.normal, "Normal"
        f2, l2 = args.fault, "Fault Injection"
        default_out = "results/comparison_report.csv"
        title = "MicroGuard Load Test Comparison (Normal vs Fault Injection)"
    elif len(args.files) == 2:
        f1, l1 = args.files[0], "Benchmark A"
        f2, l2 = args.files[1], "Benchmark B"
        if "mono" in f1.lower(): l1 = "Monolith Baseline"
        if "micro" in f2.lower() or "gate" in f2.lower(): l2 = "Microservices Pipeline"
        default_out = "results/comparison_report.csv"
        title = f"MicroGuard Load Test Comparison: {l1} vs {l2}"
    else:
        # Default fallback
        f1, l1 = "results/normal_load_stats.csv", "Normal"
        f2, l2 = "results/fault_injection_stats.csv", "Fault Injection"
        default_out = "results/comparison_report.csv"
        title = "MicroGuard Load Test Comparison"

    out_file = args.output or default_out

    try:
        comparison = compare_stats(f1, l1, f2, l2)
        print(f"\n{title}\n")
        print(comparison.to_string(index=False))

        os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)
        comparison.to_csv(out_file, index=False)
        print(f"\nSaved report to: {out_file}\n")
    except Exception as exc:
        print(f"\nError analyzing load test results: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

