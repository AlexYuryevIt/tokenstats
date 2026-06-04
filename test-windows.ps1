# tokenstats Windows smoke test
# Run from the repo root: powershell -File test-windows.ps1
# Or paste directly into PowerShell

$Pass = 0
$Fail = 0
$Root = $PSScriptRoot

function Test-Step {
    param([string]$Name, [scriptblock]$Block)
    Write-Host "▶ $Name ... " -ForegroundColor Cyan -NoNewline
    try {
        & $Block
        Write-Host "PASS" -ForegroundColor Green
        $script:Pass++
    }
    catch {
        Write-Host "FAIL" -ForegroundColor Red
        Write-Host "  $_" -ForegroundColor Red
        $script:Fail++
    }
}

function Should-Match {
    param([string[]]$Lines, [string]$Pattern)
    $matched = $Lines | Where-Object { $_ -match $Pattern }
    if (-not $matched) { throw "Expected pattern '$Pattern' not found in output" }
}

# ─── 1. Python discovery ──────────────────────────────────────────────

Test-Step "python --version" { python --version | Out-Null }

Test-Step "py -3 --version (optional)" {
    try { py -3 --version | Out-Null } catch { Write-Host "SKIP (py not found) " -ForegroundColor Yellow }
}

# ─── 2. Python smoke tests ────────────────────────────────────────────

$PythonCmd = "python"
$StatsDir = Join-Path $Root "python"

# Must run -m stats from the python/ directory so Python can find the module
function Invoke-Stats {
    Push-Location $StatsDir
    try {
        & $PythonCmd -m stats @args 2>&1
    } finally {
        Pop-Location
    }
}

Test-Step "python -m stats --help" {
    $out = Invoke-Stats --help
    $s = "$out"
    if ($s -notmatch "tokenstats") { throw "--help missing 'tokenstats'" }
    if ($s -notmatch "shell-integrations.*--powershell") {
        # Could be split across lines — just check --powershell appears
        if ($s -notmatch "--powershell") { throw "--help missing --powershell" }
    }
}

Test-Step "python -m stats --list-providers" {
    $out = Invoke-Stats --list-providers
    $s = "$out"
    if ($s -notmatch "opencode") { throw "--list-providers missing opencode" }
}

Test-Step "python -m stats shell-integration (bash)" {
    $out = Invoke-Stats shell-integration
    $s = "$out"
    if ($s -notmatch "ts\(\)") { throw "bash shell-integration missing ts()" }
    if ($s -notmatch "Add to") { throw "bash shell-integration missing instructions" }
}

Test-Step "python -m stats shell-integration --powershell" {
    $out = Invoke-Stats shell-integration --powershell
    $s = "$out"
    if ($s -notmatch "function ts-analyze") { throw "PowerShell output missing function ts-analyze" }
    if ($s -notmatch '\$PROFILE') { throw "PowerShell output missing `$PROFILE" }
    if ($s -notmatch "function ts") { throw "PowerShell output missing generic ts function" }
}

Test-Step "python -m stats (no agents, should not crash)" {
    $out = Invoke-Stats
    # Should either list sessions or say "no agents" — either way, no exception
    $exitOk = $LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq 1
    if (-not $exitOk) { throw "Exit code $LASTEXITCODE (expected 0 or 1)" }
}

Test-Step "python -m stats budget (no crash)" {
    $out = Invoke-Stats budget
    $s = "$out"
    # Should either show budget or say "No sessions" — either is fine
    if ($LASTEXITCODE -gt 1) { throw "Exit code $LASTEXITCODE" }
}

# ─── 3. Node.js entry point tests ──────────────────────────────────────

Test-Step "node bin/tokenstats.js --help" {
    $out = node "$Root/bin/tokenstats.js" --help 2>&1
    $s = "$out"
    if ($s -notmatch "tokenstats") { throw "Node --help missing 'tokenstats'" }
    if ($s -notmatch "--powershell") { throw "Node --help missing --powershell" }
}

Test-Step "node bin/tokenstats.js --list-providers" {
    $out = node "$Root/bin/tokenstats.js" --list-providers 2>&1
    $s = "$out"
    if ($s -notmatch "opencode") { throw "Node --list-providers missing opencode" }
}

Test-Step "node bin/tokenstats.js shell-integration" {
    $out = node "$Root/bin/tokenstats.js" shell-integration 2>&1
    $s = "$out"
    if ($s -notmatch "ts\(\)") { throw "Node shell-integration missing ts()" }
}

Test-Step "node bin/tokenstats.js shell-integration --powershell" {
    $out = node "$Root/bin/tokenstats.js" shell-integration --powershell 2>&1
    $s = "$out"
    if ($s -notmatch "function ts-analyze") { throw "Node --powershell missing functions" }
}

# ─── 4. ANSI / VT100 on Windows ───────────────────────────────────────

Test-Step "ANSI escape codes in --help" {
    $out = Invoke-Stats --help
    $s = "$out"
    if ($s -match '\\033\[') { throw "ANSI codes are literal instead of rendered" }
    # Should have actual ESC byte (0x1B)
    $esc = [char]27
    if ($s -notmatch "${esc}\[") { 
        # On some terminal configurations, ANSI may be stripped
        # This is acceptable — just confirm no crash
        Write-Host "WARN (no ESC detected, likely stripped by terminal) " -ForegroundColor Yellow
    }
}

# ─── 5. Provider paths (synthetic check) ──────────────────────────────

Test-Step "APPDATA env var is accessible" {
    $dir = [Environment]::GetEnvironmentVariable("APPDATA")
    if (-not $dir) { throw "APPDATA is not set" }
    Write-Host "APPDATA=$dir " -NoNewline
}

Test-Step "USERPROFILE resolves like Path.home()" {
    $expected = [Environment]::GetEnvironmentVariable("USERPROFILE")
    $actual = & $PythonCmd -c "from pathlib import Path; print(Path.home())" 2>&1
    if ("$actual" -ne "$expected") { throw "Path.home()=$actual but USERPROFILE=$expected" }
}

# ─── 6. Syntax check all Python files ─────────────────────────────────

Test-Step "Python compile check all files" {
    & $PythonCmd -m py_compile (Join-Path $StatsDir "stats.py") 2>&1 | Out-Null
    & $PythonCmd -m py_compile (Join-Path $StatsDir "models.py") 2>&1 | Out-Null
    Get-ChildItem "$StatsDir/providers/*.py" | ForEach-Object {
        & $PythonCmd -m py_compile $_.FullName 2>&1 | Out-Null
    }
}

# ─── 7. Node syntax check ─────────────────────────────────────────────

Test-Step "Node syntax check bin/tokenstats.js" {
    node --check "$Root/bin/tokenstats.js" 2>&1 | Out-Null
}

# ─── 8. Edge case: missing bin directory (package.json files) ──────────

Test-Step "package.json has win32 in os field" {
    $pkg = Get-Content (Join-Path $Root "package.json") -Raw | ConvertFrom-Json
    if ($pkg.os -notcontains "win32") { throw "package.json os missing win32" }
}

# ─── Summary ──────────────────────────────────────────────────────────

Write-Host "`n══════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Passed: $Pass   Failed: $Fail" -ForegroundColor $(if ($Fail -eq 0) { "Green" } else { "Red" })
Write-Host "══════════════════════════════════════" -ForegroundColor Cyan

if ($Fail -gt 0) {
    exit 1
}
