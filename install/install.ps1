<#
.SYNOPSIS
  One-command setup for Spec2Ship on Windows: checks every prerequisite and installs only what is missing.

.DESCRIPTION
  Checks: Claude Code CLI, Git (Git Bash runs the plugin hooks), Python 3.9+, Node.js 20+ (bundled Figma bridge),
  pypdf (better PDF extraction, optional), Figma Desktop (optional, for design capture), the claude-code-harness
  plugin and the Spec2Ship plugin.
  Missing tools are installed with winget after a confirmation (use -Yes to accept all, -CheckOnly to only report).
  Nothing is downloaded unless you confirm. The script never reads .env files or secrets.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install\install.ps1
  powershell -ExecutionPolicy Bypass -File install\install.ps1 -CheckOnly
#>
param(
  [switch]$Yes,
  [switch]$CheckOnly,
  [switch]$SkipFigma
)
$ErrorActionPreference = "Continue"  # native tools write to stderr; exit codes are checked explicitly
$Marketplace = "hthai1523/spec2ship"
$HarnessMarketplace = "Chachamaru127/claude-code-harness"
$results = New-Object System.Collections.ArrayList

function Add-Result($name, $status, $detail) {
  [void]$results.Add([pscustomobject]@{ Item = $name; Status = $status; Detail = $detail })
  $color = @{ OK = "Green"; INSTALLED = "Cyan"; MISSING = "Yellow"; SKIPPED = "DarkYellow"; FAILED = "Red" }[$status]
  Write-Host ("[{0,-9}] {1}: {2}" -f $status, $name, $detail) -ForegroundColor $color
}

function Confirm-Step($question) {
  if ($CheckOnly) { return $false }
  if ($Yes) { return $true }
  $answer = Read-Host "$question [y/N]"
  return $answer -match '^(y|yes|c|co)$'
}

function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Get-Cmd($name) { Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1 }

function Get-MajorMinor($text) {
  if ($text -match '(\d+)\.(\d+)') { return @([int]$Matches[1], [int]$Matches[2]) }
  return @(0, 0)
}

function Install-Winget($label, $id) {
  if (-not (Get-Cmd "winget")) {
    Add-Result $label "FAILED" "winget is not available; install $label manually"
    return $false
  }
  if (-not (Confirm-Step "Install $label with winget ($id)?")) {
    Add-Result $label ($(if ($CheckOnly) { "MISSING" } else { "SKIPPED" })) "winget install --id $id -e"
    return $false
  }
  winget install --id $id -e --accept-source-agreements --accept-package-agreements
  Refresh-Path
  return $true
}

function Find-Python {
  foreach ($candidate in @("python", "py", "python3")) {
    $cmd = Get-Cmd $candidate
    if (-not $cmd) { continue }
    if ($cmd.Source -like "*WindowsApps*") { continue }  # Microsoft Store alias, not a real interpreter
    try {
      $ver = & $cmd.Source --version 2>&1 | Out-String
      $mm = Get-MajorMinor $ver
      if ($mm[0] -eq 3 -and $mm[1] -ge 9) { return @{ Path = $cmd.Source; Version = $ver.Trim() } }
    } catch { }
  }
  return $null
}

Write-Host "Spec2Ship setup (Windows)" -ForegroundColor White
Write-Host ""

# 1. Claude Code
$claude = Get-Cmd "claude"
if ($claude) { Add-Result "Claude Code" "OK" ((& claude --version 2>&1 | Out-String).Trim()) }
else { Add-Result "Claude Code" "MISSING" "Install Claude Code first: https://claude.com/claude-code (then re-run this script)" }

# 2. Git / Git Bash
$git = Get-Cmd "git"
if ($git) { Add-Result "Git (Git Bash)" "OK" $(((& git --version) | Out-String).Trim()) }
elseif (Install-Winget "Git (Git Bash)" "Git.Git") { Add-Result "Git (Git Bash)" "INSTALLED" "Git for Windows" }

# 3. Python 3.9+
$py = Find-Python
if ($py) { Add-Result "Python 3.9+" "OK" "$($py.Version) at $($py.Path)" }
elseif (Install-Winget "Python 3.9+" "Python.Python.3.12") {
  $py = Find-Python
  if ($py) { Add-Result "Python 3.9+" "INSTALLED" $py.Version } else { Add-Result "Python 3.9+" "FAILED" "installed but not on PATH yet; open a new terminal" }
}

# 4. Node.js 20+
$node = Get-Cmd "node"
$nodeOk = $false
if ($node) {
  $nv = (& node --version).Trim()
  $nodeOk = (Get-MajorMinor $nv)[0] -ge 20
  if ($nodeOk) { Add-Result "Node.js 20+" "OK" $nv } else { Add-Result "Node.js 20+" "MISSING" "found $nv, need 20+" }
}
if (-not $nodeOk -and (Install-Winget "Node.js 20+" "OpenJS.NodeJS.LTS")) {
  if (Get-Cmd "node") { Add-Result "Node.js 20+" "INSTALLED" (& node --version).Trim() }
}

# 5. pypdf (optional)
if ($py) {
  & $py.Path -c "import pypdf" 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Add-Result "pypdf (optional)" "OK" "installed" }
  elseif (Confirm-Step "Install pypdf for better PDF extraction (python -m pip install --user pypdf)?") {
    & $py.Path -m pip install --user pypdf
    Add-Result "pypdf (optional)" ($(if ($LASTEXITCODE -eq 0) { "INSTALLED" } else { "FAILED" })) "python -m pip install --user pypdf"
  } else { Add-Result "pypdf (optional)" "SKIPPED" "python -m pip install --user pypdf" }
}

# 6. Figma Desktop (optional)
if (-not $SkipFigma) {
  $figmaExe = Join-Path $env:LOCALAPPDATA "Figma\Figma.exe"
  if (Test-Path $figmaExe) { Add-Result "Figma Desktop (optional)" "OK" $figmaExe }
  elseif (Install-Winget "Figma Desktop (optional)" "Figma.Figma") { Add-Result "Figma Desktop (optional)" "INSTALLED" "Figma Desktop" }
}

# 7. Plugins
if (Get-Cmd "claude") {
  $plugins = (& claude plugin list 2>&1 | Out-String)
  if ($plugins -match "claude-code-harness") { Add-Result "claude-code-harness plugin" "OK" "installed" }
  elseif (Confirm-Step "Install the claude-code-harness plugin?") {
    & claude plugin marketplace add $HarnessMarketplace
    & claude plugin install "claude-code-harness@claude-code-harness-marketplace"
    Add-Result "claude-code-harness plugin" ($(if ($LASTEXITCODE -eq 0) { "INSTALLED" } else { "FAILED" })) "claude-code-harness@claude-code-harness-marketplace"
  } else { Add-Result "claude-code-harness plugin" ($(if ($CheckOnly) { "MISSING" } else { "SKIPPED" })) "/plugin install claude-code-harness@claude-code-harness-marketplace" }

  if ($plugins -match "spec2ship@") { Add-Result "Spec2Ship plugin" "OK" "installed (update: claude plugin update spec2ship@spec2ship-marketplace)" }
  elseif (Confirm-Step "Install the Spec2Ship plugin?") {
    & claude plugin marketplace add $Marketplace
    & claude plugin install "spec2ship@spec2ship-marketplace"
    Add-Result "Spec2Ship plugin" ($(if ($LASTEXITCODE -eq 0) { "INSTALLED" } else { "FAILED" })) "spec2ship@spec2ship-marketplace"
  } else { Add-Result "Spec2Ship plugin" ($(if ($CheckOnly) { "MISSING" } else { "SKIPPED" })) "/plugin install spec2ship@spec2ship-marketplace" }
}

Write-Host ""
$todo = @($results | Where-Object { $_.Status -in @("MISSING", "SKIPPED", "FAILED") -and $_.Item -notlike "*(optional)*" })
if ($todo.Count -eq 0) {
  Write-Host "Ready. Restart Claude Code, then run /spec2ship:spec2ship-setup inside your project." -ForegroundColor Green
} else {
  Write-Host "Still missing:" -ForegroundColor Yellow
  $todo | ForEach-Object { Write-Host "  - $($_.Item): $($_.Detail)" }
}
Write-Host ""
Write-Host "Figma (once per machine, manual): Figma Desktop > Plugins > Development > Import plugin from manifest >"
Write-Host "  <Spec2Ship plugin folder>\vendor\figma-bridge\plugin\manifest.json"
Write-Host "  (/spec2ship:spec2ship-setup prints the exact path), then run 'Spec2Ship Figma Bridge (read-only)' in your design file."
if ($todo.Count -gt 0) { exit 1 }
