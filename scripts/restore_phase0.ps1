param(
    [Parameter(Mandatory=$true)][string]$BackupFile,
    [Parameter(Mandatory=$true)][string]$RestoreDatabaseName,
    [Parameter(Mandatory=$true)][string]$DatabaseUser,
    [string]$DatabaseHost = "localhost",
    [string]$DatabasePort = "5432"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $BackupFile)) {
    throw "Backup file does not exist: $BackupFile"
}

createdb --host $DatabaseHost --port $DatabasePort --username $DatabaseUser $RestoreDatabaseName
pg_restore --clean --if-exists --no-owner --no-acl --host $DatabaseHost --port $DatabasePort --username $DatabaseUser --dbname $RestoreDatabaseName $BackupFile

Write-Host "Restored $BackupFile into database $RestoreDatabaseName"
