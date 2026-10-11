import os
import subprocess
import shutil
import pandas as pd
import pytest
from analyze_resources import analyze_single_file, compare_two_runs, parse_args


def test_analyze_single_file(tmp_path):
    # Create synthetic timeseries data
    csv_file = tmp_path / "test_resources.csv"
    data = {
        "Timestamp": ["2026-10-11T12:00:00Z", "2026-10-11T12:00:01Z"],
        "ElapsedSeconds": [0, 1],
        "Target": ["all", "all"],
        "Monolith_CPU_Perc": [1.0, 2.0],
        "Monolith_Mem_MiB": [50.0, 52.0],
        "Gateway_CPU_Perc": [0.5, 0.5],
        "Gateway_Mem_MiB": [55.0, 55.0],
        "ServiceA_CPU_Perc": [0.6, 0.4],
        "ServiceA_Mem_MiB": [53.0, 53.0],
        "ServiceB_CPU_Perc": [0.4, 0.6],
        "ServiceB_Mem_MiB": [45.0, 45.0],
        "Microservices_Combined_CPU_Perc": [1.5, 1.5],
        "Microservices_Combined_Mem_MiB": [153.0, 153.0],
        "Infra_Combined_CPU_Perc": [2.0, 3.0],
        "Infra_Combined_Mem_MiB": [400.0, 410.0],
    }
    pd.DataFrame(data).to_csv(csv_file, index=False)

    df_summary = analyze_single_file(str(csv_file))
    assert not df_summary.empty

    mono_row = df_summary[df_summary["Architecture Tier"].str.contains("Monolith")].iloc[0]
    assert mono_row["Mean CPU (%)"] == 1.5
    assert mono_row["Peak CPU (%)"] == 2.0
    assert mono_row["Mean Mem (MiB)"] == 51.0

    ms_row = df_summary[df_summary["Architecture Tier"].str.contains("Microservices Combined")].iloc[0]
    assert ms_row["Mean CPU (%)"] == 1.5
    assert ms_row["Mean Mem (MiB)"] == 153.0

    # Ensure infrastructure metrics are computed separately
    infra_row = df_summary[df_summary["Architecture Tier"].str.contains("Infrastructure")].iloc[0]
    assert infra_row["Mean CPU (%)"] == 2.5
    assert infra_row["Mean Mem (MiB)"] == 405.0


def test_compare_two_runs(tmp_path):
    mono_file = tmp_path / "mono.csv"
    ms_file = tmp_path / "ms.csv"

    mono_data = {
        "Monolith_CPU_Perc": [1.0, 1.0],
        "Monolith_Mem_MiB": [50.0, 50.0],
    }
    ms_data = {
        "Microservices_Combined_CPU_Perc": [2.0, 2.0],
        "Microservices_Combined_Mem_MiB": [150.0, 150.0],
    }

    pd.DataFrame(mono_data).to_csv(mono_file, index=False)
    pd.DataFrame(ms_data).to_csv(ms_file, index=False)

    comp = compare_two_runs(str(mono_file), str(ms_file))
    assert len(comp) == 4

    cpu_row = comp[comp["Metric"] == "Mean CPU (%)"].iloc[0]
    assert cpu_row["Monolith Baseline"] == 1.0
    assert cpu_row["Microservices Combined"] == 2.0
    assert cpu_row["Delta (%)"] == 100.0
    assert cpu_row["Ratio (MS / Mono)"] == 2.0

    mem_row = comp[comp["Metric"] == "Mean Memory (MiB)"].iloc[0]
    assert mem_row["Monolith Baseline"] == 50.0
    assert mem_row["Microservices Combined"] == 150.0
    assert mem_row["Delta (%)"] == 200.0
    assert mem_row["Ratio (MS / Mono)"] == 3.0


def test_compare_two_runs_identical(tmp_path):
    mono_file = tmp_path / "mono_identical.csv"
    ms_file = tmp_path / "ms_identical.csv"

    data = {
        "Monolith_CPU_Perc": [2.5, 3.5],
        "Monolith_Mem_MiB": [45.0, 45.0],
        "Microservices_Combined_CPU_Perc": [2.5, 3.5],
        "Microservices_Combined_Mem_MiB": [45.0, 45.0],
    }

    pd.DataFrame(data).to_csv(mono_file, index=False)
    pd.DataFrame(data).to_csv(ms_file, index=False)

    comp = compare_two_runs(str(mono_file), str(ms_file))
    cpu_row = comp[comp["Metric"] == "Mean CPU (%)"].iloc[0]
    assert cpu_row["Delta (%)"] == 0.0
    assert cpu_row["Ratio (MS / Mono)"] == 1.0


def test_parse_args_cli():
    # Positional files
    parsed_pos = parse_args(["mono.csv", "ms.csv"])
    assert parsed_pos.files == ["mono.csv", "ms.csv"]
    assert parsed_pos.monolith is None
    assert parsed_pos.microservices is None

    # Named flags
    parsed_named = parse_args(["--monolith", "mono.csv", "--microservices", "ms.csv"])
    assert parsed_named.monolith == "mono.csv"
    assert parsed_named.microservices == "ms.csv"

    # Single positional
    parsed_single = parse_args(["single.csv"])
    assert parsed_single.files == ["single.csv"]


def test_powershell_validation_runlocust_all():
    """Verify measure_resources.ps1 rejects -Target all when -RunLocust is used."""
    powershell_exe = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell_exe:
        pytest.skip("PowerShell is not available on this system.")

    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "measure_resources.ps1")
    cmd = [
        powershell_exe,
        "-ExecutionPolicy", "Bypass",
        "-File", script_path,
        "-Target", "all",
        "-RunLocust"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "When -RunLocust is specified" in result.stderr or "When -RunLocust is specified" in result.stdout

