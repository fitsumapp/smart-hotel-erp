param(
    [Parameter(Mandatory=$true)][string]$DatabaseName,
    [Parameter(Mandatory=$true)][string]$DatabaseUser,
    [string]$DatabaseHost = "localhost",
    [string]$DatabasePort = "5432",
    [string]$OutputDir = ".\backups",
    [string]$MediaDir = ".\media"
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$resolvedOutput = New-Item -ItemType Directory -Force -Path $OutputDir
$dbBackup = Join-Path $resolvedOutput.FullName "$DatabaseName`_$timestamp.dump"
$mediaBackup = Join-Path $resolvedOutput.FullName "media_$timestamp.zip"

pg_dump --format=custom --no-owner --no-acl --host $DatabaseHost --port $DatabasePort --username $DatabaseUser --file $dbBackup $DatabaseName

if (Test-Path -LiteralPath $MediaDir) {
    Compress-Archive -Path (Join-Path $MediaDir "*") -DestinationPath $mediaBackup -Force
}

Write-Host "Database backup: $dbBackup"
if (Test-Path -LiteralPath $mediaBackup) {
    Write-Host "Media backup: $mediaBackup"
}
