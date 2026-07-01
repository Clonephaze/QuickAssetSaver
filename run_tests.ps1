<#
.SYNOPSIS
    Run the Quick Asset Manager test suite inside Blender.
.DESCRIPTION
    Launches Blender in background mode with the test runner script.
    Blender must be on PATH, or set $env:BLENDER_EXE to the full path.
.EXAMPLE
    .\run_tests.ps1
    .\run_tests.ps1 -Verbose
#>
param(
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

$BlenderExe = if ($env:BLENDER_EXE) { $env:BLENDER_EXE } else { "blender" }
$TestRunner  = Join-Path $PSScriptRoot "tests\blender_test_runner.py"

if (-not (Test-Path $TestRunner)) {
    Write-Error "Test runner not found at: $TestRunner"
    exit 1
}

Write-Host ""
Write-Host "Quick Asset Manager - Test Suite" -ForegroundColor Cyan
Write-Host "Runner : $TestRunner"
Write-Host "Blender: $BlenderExe"
Write-Host ""

$blenderArgs = @(
    "--background",
    "--python", $TestRunner
)

if ($Verbose) {
    $blenderArgs += "--verbose"
}

& $BlenderExe @blenderArgs
exit $LASTEXITCODE
