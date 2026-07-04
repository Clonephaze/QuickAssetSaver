<#
.SYNOPSIS
    Run the Quick Asset Manager test suite across every supported Blender version.
.DESCRIPTION
    Opt-in only — this is NOT part of the normal test loop (use .\run_tests.ps1
    for that). Runs tests/blender_test_runner.py against each locally installed
    Blender version and prints a per-version pass/fail summary at the end.

    Looks for versions under "C:\Program Files\Blender Foundation" by default;
    override with -BlenderFoundationRoot if installed elsewhere. Missing
    versions are skipped with a warning rather than failing the whole run.
.EXAMPLE
    .\run_tests_all_versions.ps1
    .\run_tests_all_versions.ps1 -BlenderFoundationRoot "D:\Blender"
#>
param(
    [string]$BlenderFoundationRoot = "C:\Program Files\Blender Foundation"
)

$ErrorActionPreference = "Continue"

$TestRunner = Join-Path $PSScriptRoot "tests\blender_test_runner.py"
if (-not (Test-Path $TestRunner)) {
    Write-Error "Test runner not found at: $TestRunner"
    exit 1
}

# Map each supported Blender version to its executable, relative to $BlenderFoundationRoot.
$Versions = [ordered]@{
    "4.2" = "Blender 4.2 LTS\blender.exe"
    "4.3" = "Blender 4.3\blender.exe"
    "4.5" = "Blender 4.5\blender.exe"
    "5.0" = "Blender 5.0\blender.exe"
    "5.1" = "Blender 5.1\blender.exe"
    "5.2" = "blender-5.2.0-alpha+main.33045d0bf4e8-windows.amd64-release\blender.exe"
}

Write-Host ""
Write-Host "Quick Asset Manager - Multi-Version Test Suite" -ForegroundColor Cyan
Write-Host "Runner : $TestRunner"
Write-Host "Root   : $BlenderFoundationRoot"
Write-Host ""

$results = [ordered]@{}

foreach ($version in $Versions.Keys) {
    $exe = Join-Path $BlenderFoundationRoot $Versions[$version]

    if (-not (Test-Path $exe)) {
        Write-Host "[$version] SKIPPED - not found at $exe" -ForegroundColor Yellow
        $results[$version] = "SKIPPED"
        continue
    }

    Write-Host "----------------------------------------------------------------------"
    Write-Host "[$version] Running via $exe" -ForegroundColor Cyan
    Write-Host "----------------------------------------------------------------------"

    & $exe --background --python $TestRunner
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        $results[$version] = "PASSED"
    } else {
        $results[$version] = "FAILED (exit $exitCode)"
    }
    Write-Host ""
}

Write-Host "======================================================================"
Write-Host "  Summary" -ForegroundColor Cyan
Write-Host "======================================================================"

$anyFailed = $false
foreach ($version in $results.Keys) {
    $status = $results[$version]
    $color = switch -Wildcard ($status) {
        "PASSED"   { "Green" }
        "SKIPPED"  { "Yellow" }
        default    { $anyFailed = $true; "Red" }
    }
    Write-Host ("  Blender {0,-6} {1}" -f $version, $status) -ForegroundColor $color
}
Write-Host "======================================================================"
Write-Host ""

exit ($(if ($anyFailed) { 1 } else { 0 }))
