$ErrorActionPreference = "Stop"

$nodeBin = "C:\Users\sasir\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
$pnpmCmd = "C:\Users\sasir\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd"

if (-not (Test-Path (Join-Path $nodeBin "node.exe"))) {
    throw "Bundled Node.js was not found at $nodeBin"
}
if (-not (Test-Path $pnpmCmd)) {
    throw "Bundled pnpm was not found at $pnpmCmd"
}

$env:PATH = "$nodeBin;$env:PATH"
& $pnpmCmd --dir $PSScriptRoot run dev
if ($LASTEXITCODE -ne 0) {
    throw "Dashboard development server exited with code $LASTEXITCODE"
}
