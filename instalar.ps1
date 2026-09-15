# Preparación local para Windows 10/11 x64; la ejecuta el agente instalador.
param(
    [switch]$Consent,
    [string]$Destination = (Join-Path $env:USERPROFILE 'Taller de escritura'),
    [string]$Model = 'opus',
    [string]$ObsidianApp = ''
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
if (-not $Consent) { throw 'Falta la petición de instalar el taller.' }
if (-not [Environment]::Is64BitOperatingSystem) { throw 'Esta entrega requiere Windows de 64 bits.' }
if (Test-Path $Destination) {
    if ((Get-Item $Destination).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'El destino no puede ser un enlace.' }
    if ((Get-ChildItem -Force $Destination | Measure-Object).Count -gt 0 -and -not (Test-Path (Join-Path $Destination '.installer/owned'))) {
        throw 'El destino contiene archivos ajenos. El agente debe elegir otra carpeta.'
    }
}
$Runtime = Join-Path $Destination '.installer'
New-Item -ItemType Directory -Force $Runtime | Out-Null
New-Item -ItemType File -Force (Join-Path $Runtime 'owned') | Out-Null
$Archive = Join-Path $Runtime 'uv.zip'
$UvHash = 'fe0c7815acf4fc45f8a5eff58ed3cf7ae2e15c3cf1dceadbd10c816ec1690cc1'
if (-not (Test-Path $Archive)) {
    Invoke-WebRequest -UseBasicParsing 'https://github.com/astral-sh/uv/releases/download/0.11.7/uv-x86_64-pc-windows-msvc.zip' -OutFile $Archive
}
if ((Get-FileHash $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $UvHash) { throw 'La descarga de uv no coincide con su huella.' }
$UvFolder = Join-Path $Runtime 'uv'
Expand-Archive -Path $Archive -DestinationPath $UvFolder -Force
$Uv = @(Get-ChildItem $UvFolder -Recurse -Filter uv.exe)
if ($Uv.Count -ne 1) { throw 'El paquete de uv no tiene la estructura esperada.' }
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Runtime 'python'
$env:UV_CACHE_DIR = Join-Path $Runtime 'cache'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
& $Uv[0].FullName python install --no-bin 3.13.5
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar Python local.' }
$Python = & $Uv[0].FullName python find --managed-python 3.13.5
if ($LASTEXITCODE -ne 0) { throw 'No se encontró el Python preparado.' }
$InstallerArgs = @((Join-Path $PSScriptRoot 'instalar.py'), '--consent', '--dest', $Destination, '--model', $Model)
if ($ObsidianApp) { $InstallerArgs += @('--obsidian-app', $ObsidianApp) }
& $Python @InstallerArgs
exit $LASTEXITCODE
