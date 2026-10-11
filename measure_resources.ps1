<#
.SYNOPSIS
    Reproducible resource-utilization measurement script for MicroGuard.
.DESCRIPTION
    Samples 'docker stats' at regular intervals during a benchmark run and saves
    timestamped CSV output. Distinguishes the monolith's single container from the
    combined CPU and memory usage of the microservices deployment (Gateway + Service A + Service B).
    Infrastructure containers (Prometheus, Grafana, Locust) are tracked separately
    and excluded from application totals.
.PARAMETER DurationSeconds
    Duration in seconds to sample stats. Default is 30. Set to 0 to run indefinitely until Ctrl+C.
.PARAMETER IntervalSeconds
    Interval in seconds between successive samples. Default is 1.
.PARAMETER OutputFile
    Path to save the timeseries CSV. Defaults to results/resource_usage_<Target>_<Timestamp>.csv.
.PARAMETER SummaryFile
    Path to save the summary CSV. Defaults to results/resource_summary_<Target>_<Timestamp>.csv.
.PARAMETER Target
    Architecture or workload label ('monolith', 'microservices', 'all'). Default is 'all'.
.PARAMETER RunLocust
    If specified, automatically launches a headless containerized Locust load test for the test duration.
.PARAMETER LocustUsers
    Number of virtual users if RunLocust is enabled. Default is 10.
.PARAMETER LocustSpawnRate
    Spawn rate if RunLocust is enabled. Default is 2.
#>

[CmdletBinding()]
param (
    [int]$DurationSeconds = 30,
    [int]$IntervalSeconds = 1,
    [string]$OutputFile = "",
    [string]$SummaryFile = "",
    [ValidateSet("monolith", "microservices", "all")]
    [string]$Target = "all",
    [switch]$RunLocust,
    [int]$LocustUsers = 10,
    [int]$LocustSpawnRate = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# Helper function to parse memory strings into Mebibytes (MiB)
function Convert-MemoryToMiB ([string]$memString) {
    if ([string]::IsNullOrWhiteSpace($memString)) { return 0.0 }
    $used = $memString.Split('/')[0].Trim()
    if ($used -match '^([0-9.]+)\s*([a-zA-Z]+)$') {
        $val = [double]$Matches[1]
        $unit = $Matches[2].ToUpper()
        switch ($unit) {
            'B'   { return [math]::Round($val / 1048576.0, 3) }
            'KB'  { return [math]::Round($val * 1000.0 / 1048576.0, 3) }
            'KIB' { return [math]::Round($val * 1024.0 / 1048576.0, 3) }
            'MB'  { return [math]::Round($val * 1000000.0 / 1048576.0, 3) }
            'MIB' { return [math]::Round($val, 3) }
            'GB'  { return [math]::Round($val * 1000000000.0 / 1048576.0, 3) }
            'GIB' { return [math]::Round($val * 1024.0, 3) }
            default { return [math]::Round($val, 3) }
        }
    }
    return 0.0
}

# Helper function to map container name to architectural role
function Get-ContainerRole ([string]$containerName) {
    switch -wildcard ($containerName) {
        '*monolith*'   { return 'monolith' }
        '*gateway*'    { return 'gateway' }
        '*service_a*'  { return 'service_a' }
        '*service-a*'  { return 'service_a' }
        '*service_b*'  { return 'service_b' }
        '*service-b*'  { return 'service_b' }
        '*prometheus*' { return 'prometheus' }
        '*grafana*'    { return 'grafana' }
        '*locust*'     { return 'locust' }
        default        { return 'other' }
    }
}

# Ensure results directory exists
$ResultsDir = Join-Path -Path $PSScriptRoot -ChildPath "results"
if (-not (Test-Path $ResultsDir)) {
    New-Item -ItemType Directory -Path $ResultsDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $ResultsDir "resource_usage_${Target}_${Timestamp}.csv"
}
if ([string]::IsNullOrWhiteSpace($SummaryFile)) {
    $SummaryFile = Join-Path $ResultsDir "resource_summary_${Target}_${Timestamp}.csv"
}

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "              MICROGUARD RESOURCE UTILIZATION MONITOR                     " -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " Target Architecture : $Target"
Write-Host " Sampling Interval   : ${IntervalSeconds}s"
Write-Host " Total Duration      : $(if ($DurationSeconds -gt 0) { "${DurationSeconds}s" } else { 'Until Ctrl+C' })"
Write-Host " Raw Timeseries CSV  : $OutputFile"
Write-Host " Summary CSV         : $SummaryFile"
Write-Host " Units               : CPU in %, Memory in MiB"
Write-Host "--------------------------------------------------------------------------"

# If -RunLocust is specified, start Locust in background
$LocustJob = $null
if ($RunLocust) {
    $targetUrl = if ($Target -eq "monolith") { "http://monolith:8001" } else { "http://gateway:8000" }
    Write-Host " Starting headless Locust load test against $targetUrl..." -ForegroundColor Yellow
    $locustCmd = "docker compose run --rm locust -f /mnt/locust/locustfile.py --host $targetUrl --headless -u $LocustUsers -r $LocustSpawnRate --run-time ${DurationSeconds}s --csv /mnt/locust/results/${Target}_${Timestamp}"
    $scriptDir = $PSScriptRoot
    $LocustJob = Start-Job -ScriptBlock {
        param($cmd, $dir)
        Set-Location $dir
        Invoke-Expression $cmd
    } -ArgumentList $locustCmd, $scriptDir
}

$samples = [System.Collections.Generic.List[PSCustomObject]]::new()
$startTime = Get-Date
$sampleIndex = 0

try {
    while ($true) {
        $elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
        if ($DurationSeconds -gt 0 -and $elapsed -ge $DurationSeconds) {
            break
        }

        # Query docker stats in non-streaming JSON format
        $statsRaw = docker stats --no-stream --format json 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($statsRaw)) {
            Start-Sleep -Seconds $IntervalSeconds
            continue
        }

        $roleData = @{
            'monolith'   = @{ CPU = 0.0; Mem = 0.0 }
            'gateway'    = @{ CPU = 0.0; Mem = 0.0 }
            'service_a'  = @{ CPU = 0.0; Mem = 0.0 }
            'service_b'  = @{ CPU = 0.0; Mem = 0.0 }
            'prometheus' = @{ CPU = 0.0; Mem = 0.0 }
            'grafana'    = @{ CPU = 0.0; Mem = 0.0 }
            'locust'     = @{ CPU = 0.0; Mem = 0.0 }
        }

        foreach ($line in $statsRaw) {
            if ([string]::IsNullOrWhiteSpace($line)) { continue }
            try {
                $item = $line | ConvertFrom-Json
                $role = Get-ContainerRole $item.Name
                if ($roleData.ContainsKey($role)) {
                    $cpu = [double]($item.CPUPerc.TrimEnd('%').Trim())
                    $mem = Convert-MemoryToMiB $item.MemUsage
                    $roleData[$role].CPU = $cpu
                    $roleData[$role].Mem = $mem
                }
            }
            catch {
                # Ignore transient JSON parsing errors on container transitions
            }
        }

        $sampleIndex++
        $isoTimestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")

        # Application totals
        $msCombinedCpu = [math]::Round($roleData['gateway'].CPU + $roleData['service_a'].CPU + $roleData['service_b'].CPU, 2)
        $msCombinedMem = [math]::Round($roleData['gateway'].Mem + $roleData['service_a'].Mem + $roleData['service_b'].Mem, 2)

        # Infrastructure totals (strictly separated)
        $infraCombinedCpu = [math]::Round($roleData['prometheus'].CPU + $roleData['grafana'].CPU + $roleData['locust'].CPU, 2)
        $infraCombinedMem = [math]::Round($roleData['prometheus'].Mem + $roleData['grafana'].Mem + $roleData['locust'].Mem, 2)

        $row = [PSCustomObject]@{
            Timestamp                       = $isoTimestamp
            ElapsedSeconds                  = $elapsed
            Target                          = $Target
            # Monolith Single Container
            Monolith_CPU_Perc               = $roleData['monolith'].CPU
            Monolith_Mem_MiB                = $roleData['monolith'].Mem
            # Microservices Component Breakdown
            Gateway_CPU_Perc                = $roleData['gateway'].CPU
            Gateway_Mem_MiB                 = $roleData['gateway'].Mem
            ServiceA_CPU_Perc               = $roleData['service_a'].CPU
            ServiceA_Mem_MiB                = $roleData['service_a'].Mem
            ServiceB_CPU_Perc               = $roleData['service_b'].CPU
            ServiceB_Mem_MiB                = $roleData['service_b'].Mem
            # Microservices Combined Total
            Microservices_Combined_CPU_Perc = $msCombinedCpu
            Microservices_Combined_Mem_MiB  = $msCombinedMem
            # Infrastructure Tiers (Reported Separately)
            Infra_Prometheus_CPU_Perc       = $roleData['prometheus'].CPU
            Infra_Prometheus_Mem_MiB        = $roleData['prometheus'].Mem
            Infra_Grafana_CPU_Perc          = $roleData['grafana'].CPU
            Infra_Grafana_Mem_MiB           = $roleData['grafana'].Mem
            Infra_Locust_CPU_Perc           = $roleData['locust'].CPU
            Infra_Locust_Mem_MiB            = $roleData['locust'].Mem
            Infra_Combined_CPU_Perc         = $infraCombinedCpu
            Infra_Combined_Mem_MiB          = $infraCombinedMem
        }

        $samples.Add($row)

        # Progress display
        $durStr = if ($DurationSeconds -gt 0) { "${DurationSeconds}s" } else { "live" }
        Write-Host ("[{0:D2} | {1,4:F1}s/{2}] Monolith: {3,5:F2}% CPU, {4,6:F1} MiB | Microservices (Combined): {5,5:F2}% CPU, {6,6:F1} MiB" -f `
            $sampleIndex, $elapsed, $durStr, $row.Monolith_CPU_Perc, $row.Monolith_Mem_MiB, $row.Microservices_Combined_CPU_Perc, $row.Microservices_Combined_Mem_MiB)

        Start-Sleep -Seconds $IntervalSeconds
    }
}
finally {
    if ($null -ne $LocustJob) {
        Write-Host "`nWaiting for background Locust benchmark job to complete..." -ForegroundColor Yellow
        $locustOutput = Receive-Job -Job $LocustJob -Wait -ErrorAction SilentlyContinue
        Remove-Job -Job $LocustJob -Force -ErrorAction SilentlyContinue
        if ($locustOutput) {
            Write-Host ($locustOutput -join "`n")
        }
    }
}

if ($samples.Count -eq 0) {
    Write-Warning "No samples collected. Ensure Docker containers are running with 'docker compose ps'."
    exit 0
}

# Export timeseries CSV
$samples | Export-Csv -Path $OutputFile -NoTypeInformation -Encoding UTF8
Write-Host "`nSaved timeseries data: $OutputFile" -ForegroundColor Green

# Compute statistical summary
function Get-StatsSummary ([string]$scope, [double[]]$cpuValues, [double[]]$memValues) {
    $cpuSorted = $cpuValues | Sort-Object
    $memSorted = $memValues | Sort-Object
    $count = $cpuSorted.Count
    if ($count -eq 0) { return $null }

    $cpuMean = [math]::Round(($cpuValues | Measure-Object -Average).Average, 2)
    $cpuPeak = ($cpuValues | Measure-Object -Maximum).Maximum
    $cpuMin  = ($cpuValues | Measure-Object -Minimum).Minimum
    $cpuMed  = $cpuSorted[[math]::Floor($count / 2)]

    $memMean = [math]::Round(($memValues | Measure-Object -Average).Average, 2)
    $memPeak = ($memValues | Measure-Object -Maximum).Maximum
    $memMin  = ($memValues | Measure-Object -Minimum).Minimum
    $memMed  = $memSorted[[math]::Floor($count / 2)]

    return [PSCustomObject]@{
        Scope           = $scope
        Mean_CPU_Perc   = $cpuMean
        Median_CPU_Perc = $cpuMed
        Peak_CPU_Perc   = $cpuPeak
        Min_CPU_Perc    = $cpuMin
        Mean_Mem_MiB    = $memMean
        Median_Mem_MiB  = $memMed
        Peak_Mem_MiB    = $memPeak
        Min_Mem_MiB     = $memMin
    }
}

$summaryList = [System.Collections.Generic.List[PSCustomObject]]::new()
$summaryList.Add((Get-StatsSummary "Monolith Baseline (1 container)" `
    ($samples | ForEach-Object { $_.Monolith_CPU_Perc }) `
    ($samples | ForEach-Object { $_.Monolith_Mem_MiB })))

$summaryList.Add((Get-StatsSummary "Gateway (microservice)" `
    ($samples | ForEach-Object { $_.Gateway_CPU_Perc }) `
    ($samples | ForEach-Object { $_.Gateway_Mem_MiB })))

$summaryList.Add((Get-StatsSummary "Service A (microservice)" `
    ($samples | ForEach-Object { $_.ServiceA_CPU_Perc }) `
    ($samples | ForEach-Object { $_.ServiceA_Mem_MiB })))

$summaryList.Add((Get-StatsSummary "Service B (microservice)" `
    ($samples | ForEach-Object { $_.ServiceB_CPU_Perc }) `
    ($samples | ForEach-Object { $_.ServiceB_Mem_MiB })))

$summaryList.Add((Get-StatsSummary "Microservices Combined (3 containers)" `
    ($samples | ForEach-Object { $_.Microservices_Combined_CPU_Perc }) `
    ($samples | ForEach-Object { $_.Microservices_Combined_Mem_MiB })))

$summaryList.Add((Get-StatsSummary "Infrastructure (Prometheus+Grafana+Locust - separate)" `
    ($samples | ForEach-Object { $_.Infra_Combined_CPU_Perc }) `
    ($samples | ForEach-Object { $_.Infra_Combined_Mem_MiB })))

$summaryList | Export-Csv -Path $SummaryFile -NoTypeInformation -Encoding UTF8
Write-Host "Saved summary statistics: $SummaryFile`n" -ForegroundColor Green

# Print report table
Write-Host "==========================================================================================" -ForegroundColor Cyan
Write-Host "                         MICROGUARD RESOURCE UTILIZATION REPORT                           " -ForegroundColor Cyan
Write-Host "==========================================================================================" -ForegroundColor Cyan
$summaryList | Format-Table -Property Scope, Mean_CPU_Perc, Peak_CPU_Perc, Mean_Mem_MiB, Peak_Mem_MiB -AutoSize

$mono = $summaryList | Where-Object { $_.Scope -like "Monolith*" }
$ms   = $summaryList | Where-Object { $_.Scope -like "Microservices Combined*" }

if ($mono -and $ms -and $mono.Mean_CPU_Perc -gt 0 -and $mono.Mean_Mem_MiB -gt 0) {
    $cpuDiff = [math]::Round((($ms.Mean_CPU_Perc - $mono.Mean_CPU_Perc) / $mono.Mean_CPU_Perc) * 100, 1)
    $memDiff = [math]::Round((($ms.Mean_Mem_MiB - $mono.Mean_Mem_MiB) / $mono.Mean_Mem_MiB) * 100, 1)
    Write-Host "Key Architectural Findings:" -ForegroundColor Yellow
    Write-Host " - CPU Usage: Combined Microservices used $cpuDiff% more mean CPU than the Monolith."
    Write-Host " - Memory Footprint: Combined Microservices used $memDiff% more mean RAM than the Monolith."
}
Write-Host "==========================================================================================`n" -ForegroundColor Cyan
