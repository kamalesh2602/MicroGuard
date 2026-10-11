
import pandas as pd

normal = pd.read_csv("results/normal_load_stats.csv")
fault = pd.read_csv("results/fault_injection_stats.csv")


def get_stats(df, label):
    # Locust's statistics CSV contains an aggregated row.
    row = df[df["Name"] == "Aggregated"]

    if row.empty:
        row = df[df["Name"] == "/process"]

    row = row.iloc[0]

    total = row["Request Count"]
    failures = row["Failure Count"]

    return {
        "Test": label,
        "Requests": int(total),
        "Failures": int(failures),
        "Failure Rate (%)": round(
            failures / total * 100, 2
        ) if total else 0,
        "Average Latency (ms)": row["Average Response Time"],
        "Median Latency (ms)": row["Median Response Time"],
        "P95 Latency (ms)": row["95%"]
        if "95%" in row.index else row.get("95%ile (ms)", None),
        "Requests/sec": row["Requests/s"],
    }


comparison = pd.DataFrame([
    get_stats(normal, "Normal"),
    get_stats(fault, "Fault Injection"),
])

print("\nMicroGuard Load Test Comparison\n")
print(comparison.to_string(index=False))

comparison.to_csv("results/comparison_report.csv", index=False)
print("\nSaved: results/comparison_report.csv")
