import os
import pandas as pd
import pytest
from analyze_results import parse_locust_stats_df, load_and_parse_stats, compare_stats


def test_parse_locust_stats_df_valid():
    data = {
        "Type": ["GET", ""],
        "Name": ["/process", "Aggregated"],
        "Request Count": [100, 100],
        "Failure Count": [5, 5],
        "Median Response Time": [25.0, 25.0],
        "Average Response Time": [28.5, 28.5],
        "Min Response Time": [10.0, 10.0],
        "Max Response Time": [80.0, 80.0],
        "Requests/s": [9.5, 9.5],
        "95%": [55.0, 55.0],
    }
    df = pd.DataFrame(data)
    stats = parse_locust_stats_df(df, "Test Run")

    assert stats["Test"] == "Test Run"
    assert stats["Requests"] == 100
    assert stats["Failures"] == 5
    assert stats["Failure Rate (%)"] == 5.0
    assert stats["Average Latency (ms)"] == 28.5
    assert stats["Median Latency (ms)"] == 25.0
    assert stats["P95 Latency (ms)"] == 55.0
    assert stats["Requests/sec"] == 9.5


def test_parse_locust_stats_df_empty_raises():
    df_empty = pd.DataFrame()
    with pytest.raises(ValueError, match="empty"):
        parse_locust_stats_df(df_empty, "Empty Run")


def test_parse_locust_stats_df_missing_column_raises():
    df_missing = pd.DataFrame({
        "Name": ["Aggregated"],
        "Request Count": [10],
        # Missing 'Failure Count' and 'Average Response Time'
    })
    with pytest.raises(ValueError, match="Missing required column"):
        parse_locust_stats_df(df_missing, "Incomplete Run")


def test_load_and_parse_stats_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_and_parse_stats("non_existent_locust_stats.csv", "Missing")


def test_compare_stats_e2e(tmp_path):
    file1 = tmp_path / "mono_stats.csv"
    file2 = tmp_path / "ms_stats.csv"

    d1 = {
        "Name": ["Aggregated"],
        "Request Count": [291],
        "Failure Count": [0],
        "Average Response Time": [4.6],
        "Median Response Time": [4.0],
        "95%": [8.0],
        "Requests/s": [10.0],
    }
    d2 = {
        "Name": ["Aggregated"],
        "Request Count": [257],
        "Failure Count": [0],
        "Average Response Time": [55.26],
        "Median Response Time": [45.0],
        "95%": [110.0],
        "Requests/s": [8.83],
    }

    pd.DataFrame(d1).to_csv(file1, index=False)
    pd.DataFrame(d2).to_csv(file2, index=False)

    comp = compare_stats(str(file1), "Monolith", str(file2), "Microservices")
    assert len(comp) == 2
    assert comp.iloc[0]["Requests"] == 291
    assert comp.iloc[1]["Requests"] == 257
    assert comp.iloc[0]["P95 Latency (ms)"] == 8.0
    assert comp.iloc[1]["P95 Latency (ms)"] == 110.0
