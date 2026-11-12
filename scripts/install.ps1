# Spec2Ship one-command installer (Windows PowerShell 5.1+ / PowerShell 7).
#
#   irm https://raw.githubusercontent.com/hthai1523/spec2ship/main/scripts/install.ps1 | iex
#
# Adds the Harness and Spec2Ship marketplaces, then installs both plugins with the `claude` CLI.
# Safe to re-run. Set SPEC2SHIP_SOURCE to install from a local checkout or fork,
# e.g.  $env:SPEC2SHIP_SOURCE = 'D:\src\spec2ship'
$ErrorActionPreference = 'Stop'

$HarnessMarketplaceSource = 'Chachamaru127/claude-code-harness'
$HarnessMarketplace = 'claude-code-harness-marketplace'
$HarnessPlugin = 'harness'   # renamed from "claude-code-harness" upstream
$Spec2ShipSource = if ($env:SPEC2SHIP_SOURCE) { $env:SPEC2SHIP_SOURCE } else { 'hthai1523/spec2ship' }
$Spec2ShipMarketplace = 'spec2ship-marketplace'

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host 'Claude Code CLI ("claude") was not found on PATH. Install it first: https://code.claude.com/docs' -ForegroundColor Red
    exit 1
}

function Invoke-Claude {
    param([string[]]$CliArgs)
    & claude @CliArgs
    if ($LASTEXITCODE -ne 0) { throw "claude $($CliArgs -join ' ') failed (exit $LASTEXITCODE)" }
}

function Add-Marketplace {
    param([string]$Name, [string]$Source)
    $known = (& claude plugin marketplace list 2>$null) -join "`n"
    if ($known -match [regex]::Escape($Name)) {
        Write-Host "[skip] marketplace $Name already added"
        return
    }
    Write-Host "[add ] marketplace $Name  <-  $Source"
    Invoke-Claude @('plugin', 'marketplace', 'add', $Source)
}

try {
    Add-Marketplace $HarnessMarketplace $HarnessMarketplaceSource
    Add-Marketplace $Spec2ShipMarketplace $Spec2ShipSource

    Write-Host "[inst] $HarnessPlugin@$HarnessMarketplace"
    Invoke-Claude @('plugin', 'install', "$HarnessPlugin@$HarnessMarketplace")
    Write-Host "[inst] spec2ship@$Spec2ShipMarketplace"
    Invoke-Claude @('plugin', 'install', "spec2ship@$Spec2ShipMarketplace")
}
catch {
    Write-Host "Install failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host 'Done. Restart Claude Code, then run: /spec2ship:spec2ship-setup' -ForegroundColor Green
Write-Host 'Figma Desktop still needs the figma-mcp-go plugin imported once (see README > Figma setup).'
