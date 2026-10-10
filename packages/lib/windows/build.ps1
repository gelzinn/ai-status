$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
Push-Location $repoRoot
try {
    python -m PyInstaller --noconfirm --clean packages/lib/windows/ai-status.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
    python packages/lib/windows/licenses.py dist/ai-status/THIRD_PARTY_LICENSES.txt
    if ($LASTEXITCODE -ne 0) { throw "License collection failed" }
    $version = (Get-Content packages/lib/VERSION -Raw).Trim()
    $compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($compiler) {
        & $compiler.Source "/DAppVersion=$version" packages/lib/windows/installer.iss
    } else {
        $compilerPath = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6/ISCC.exe"
        if (!(Test-Path $compilerPath)) { throw "Install Inno Setup 6 to build the installer" }
        & $compilerPath "/DAppVersion=$version" packages/lib/windows/installer.iss
    }
    if ($LASTEXITCODE -ne 0) { throw "Installer build failed" }
    Compress-Archive -Path dist/ai-status -DestinationPath "dist/ai-status-$version-windows-x64.zip" -Force
} finally {
    Pop-Location
}
