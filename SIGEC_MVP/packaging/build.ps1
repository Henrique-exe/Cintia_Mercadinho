#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$ISCCPath,
    [string]$Wheelhouse = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT' -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'Execute em PowerShell NATIVO x64 no Windows x64. Linux, WSL e ARM não são alvos deste build.'
}
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
$ISCCPath = (Resolve-Path -LiteralPath $ISCCPath).Path
# A versão exata é verificada pelo preprocessor em installer.iss.
function Invoke-Checked {
    param([string]$File, [string[]]$Arguments)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Comando falhou ($LASTEXITCODE): $File" }
}
$OldPythonPath = $env:PYTHONPATH
$OldPythonHome = $env:PYTHONHOME
Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = ''
    $env:PYTHONHOME = ''
    Invoke-Checked $PythonExe @('-I', 'packaging\check_build.py')
    $BuildRoot = Join-Path $ProjectRoot 'build'
    New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null
    $BuildEnv = Join-Path $BuildRoot ('venv-' + [guid]::NewGuid().ToString('N'))
    Invoke-Checked $PythonExe @('-I', '-m', 'venv', $BuildEnv)
    $BuildPython = Join-Path $BuildEnv 'Scripts\python.exe'
    $PipArgs = @('-I', '-m', 'pip', '--isolated', 'install', '--require-hashes', '--only-binary=:all:', '-r', 'packaging\requirements-windows.lock')
    if ($Wheelhouse) {
        $Wheelhouse = (Resolve-Path -LiteralPath $Wheelhouse).Path
        $PipArgs += @('--no-index', '--find-links', $Wheelhouse)
    } else {
        $PipArgs += @('--index-url', 'https://pypi.org/simple')
    }
    Invoke-Checked $BuildPython $PipArgs
    Invoke-Checked $BuildPython @('-I', '-m', 'pip', 'check')
    Invoke-Checked $BuildPython @('-m', 'unittest', 'discover', '-s', 'tests', '-v')
    Invoke-Checked $BuildPython @('packaging\prepare_payload.py')
    Invoke-Checked $BuildPython @('-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', 'dist', '--workpath', 'build\pyinstaller', 'packaging\SIGEC.spec')
    $FrozenExe = Join-Path $ProjectRoot 'dist\SIGEC\SIGEC.exe'
    $Smoke = Start-Process -FilePath $FrozenExe -ArgumentList @('--self-test', '--no-dialog') -Wait -PassThru
    if ($Smoke.ExitCode -ne 0) { throw 'Self-test do executável empacotado falhou.' }
    Invoke-Checked $BuildPython @('packaging\prepare_payload.py', '--manifest')
    Invoke-Checked $ISCCPath @('/Qp', 'packaging\installer.iss')
    $Installer = Join-Path $ProjectRoot 'release\Instalar SIGEC.exe'
    if (-not (Test-Path -LiteralPath $Installer)) { throw 'Instalador não encontrado.' }
    $Version = (Get-Content -LiteralPath 'VERSION' -Raw).Trim()
    $Sha = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Sha  Instalar SIGEC.exe" | Set-Content -LiteralPath 'release\SHA256SUMS.txt' -Encoding ASCII
    $Info = [ordered]@{
        appVersion = $Version
        installerSha256 = $Sha
        target = 'Windows 10/11 x64 (aceitação manual pendente)'
        python = '3.14.10 x64'
        pyinstaller = '6.16.0'
        innoSetup = '6.7.4'
        builtAtUtc = [DateTime]::UtcNow.ToString('o')
        buildOs = [Environment]::OSVersion.VersionString
        originalZipSha256 = 'b17db37ee8677a338838391f30a9095bcb40fe9a747d5a4a8108a0d056b2bf02'
        lockSha256 = (Get-FileHash 'packaging\requirements-windows.lock' -Algorithm SHA256).Hash.ToLowerInvariant()
        manualWindowsValidation = 'PENDENTE'
    }
    $Info | ConvertTo-Json | Set-Content -LiteralPath 'release\BUILD-INFO.json' -Encoding UTF8
    Copy-Item -LiteralPath 'build\payload.json' -Destination 'release\payload.json'
    & $BuildPython -I -m pip freeze --all | Set-Content -LiteralPath 'release\dependencies.txt' -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao registrar dependências.' }
    Write-Host "Gerado: $Installer"
    Write-Host "Versão: $Version; SHA-256: $Sha"
    Write-Host 'Build concluído. Validação manual do instalador e do PC da cliente ainda pendente.'
} finally {
    Pop-Location
    $env:PYTHONPATH = $OldPythonPath
    $env:PYTHONHOME = $OldPythonHome
}
