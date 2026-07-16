[CmdletBinding()]
param(
    [string]$Version = "1.0.0",
    [string]$OutputDirectory = "artifacts"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$PackagingRoot = Join-Path $Root "packaging\windows"
$DistRoot = Join-Path $PackagingRoot "dist"
$WorkRoot = Join-Path $PackagingRoot "build"
$ArtifactRoot = [System.IO.Path]::GetFullPath((Join-Path $Root $OutputDirectory))
$StageName = "Keivotos-V$Version-windows-x64"
$StageRoot = Join-Path $ArtifactRoot $StageName

function Compress-PortableArchive {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    for ($Attempt = 1; $Attempt -le 10; $Attempt++) {
        try {
            Compress-Archive -LiteralPath $Source -DestinationPath $Destination -CompressionLevel Optimal -ErrorAction Stop
            return
        }
        catch {
            if ($Attempt -eq 10) { throw }
            # Native executable and antivirus handles can linger briefly after
            # the verification commands complete on Windows.
            Start-Sleep -Milliseconds 500
        }
    }
}

foreach ($Path in @($DistRoot, $WorkRoot, $StageRoot)) {
    $ResolvedParent = [System.IO.Path]::GetFullPath((Split-Path -Parent $Path))
    if (-not $ResolvedParent.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a path outside the repository: $Path"
    }
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

Push-Location $Root
try {
    uv sync --locked --python 3.11 --group build
    Push-Location (Join-Path $Root "frontend")
    try {
        npm.cmd ci
        npm.cmd run check
        npm.cmd run build
    }
    finally {
        Pop-Location
    }

    .\.venv\Scripts\python.exe .\scripts\release\generate_brand_assets.py
    .\.venv\Scripts\pyinstaller.exe --noconfirm --clean `
        --distpath $DistRoot --workpath $WorkRoot `
        .\packaging\windows\Keivotos.spec
    .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --console `
        --name gallery-dl --distpath $DistRoot --workpath (Join-Path $WorkRoot "gallery-dl") `
        .\packaging\windows\gallery_dl_entry.py

    New-Item -ItemType Directory -Path $ArtifactRoot -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $DistRoot "Keivotos") -Destination $StageRoot -Recurse
    Copy-Item -LiteralPath (Join-Path $DistRoot "gallery-dl.exe") -Destination (Join-Path $StageRoot "gallery-dl.exe")
    $FfmpegPath = (& .\.venv\Scripts\python.exe -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())").Trim()
    Copy-Item -LiteralPath $FfmpegPath -Destination (Join-Path $StageRoot "ffmpeg.exe")
    foreach ($File in @("README.md", "LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "SECURITY.md")) {
        Copy-Item -LiteralPath (Join-Path $Root $File) -Destination (Join-Path $StageRoot $File)
    }
    New-Item -ItemType Directory -Path (Join-Path $StageRoot "docs") -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $Root "docs\user") -Destination (Join-Path $StageRoot "docs\user") -Recurse
    .\.venv\Scripts\python.exe .\scripts\release\collect_licenses.py (Join-Path $StageRoot "licenses")
    $FfmpegLicenseDirectory = Join-Path $StageRoot "licenses\FFmpeg-7.1"
    New-Item -ItemType Directory -Path $FfmpegLicenseDirectory -Force | Out-Null
    & $FfmpegPath -L | Set-Content -LiteralPath (Join-Path $FfmpegLicenseDirectory "LICENSE.txt") -Encoding utf8
    Copy-Item -LiteralPath (Join-Path $Root "packaging\windows\FFMPEG_SOURCE.md") -Destination $FfmpegLicenseDirectory

    & (Join-Path $StageRoot "Keivotos.exe") --version
    & (Join-Path $StageRoot "Keivotos.exe") --portable-check
    & (Join-Path $StageRoot "gallery-dl.exe") --version
    & (Join-Path $StageRoot "ffmpeg.exe") -version

    $ZipPath = Join-Path $ArtifactRoot "$StageName.zip"
    if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
    Compress-PortableArchive -Source $StageRoot -Destination $ZipPath
    $Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath
    "$($Hash.Hash.ToLowerInvariant())  $($Hash.Path | Split-Path -Leaf)" | Set-Content -LiteralPath "$ZipPath.sha256" -Encoding utf8
    Write-Host "Portable archive: $ZipPath"
}
finally {
    Pop-Location
}
