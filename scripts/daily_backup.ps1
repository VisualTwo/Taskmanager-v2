# TaskManager Daily Backup Script (PowerShell)
# This script should be scheduled to run daily via Windows Task Scheduler

param(
    [string]$ProjectPath = (Split-Path -Parent $PSScriptRoot),
    [string]$BackupType = "scheduled"
)

# Set paths
$VenvPath = Join-Path $ProjectPath ".venv\Scripts\python.exe"
$BackupScript = Join-Path $ProjectPath "scripts\backup_manager.py"
$DbPath = Join-Path $ProjectPath "taskman.db"
$BackupDir = Join-Path $ProjectPath "backups"

# Ensure backup directory exists
if (!(Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

# Change to project directory
Set-Location $ProjectPath

try {
    # Run the backup
    Write-Host "[$(Get-Date)] Starting scheduled backup..."
    
    $process = Start-Process -FilePath $VenvPath -ArgumentList @(
        $BackupScript,
        "--db", $DbPath,
        "--backup-dir", $BackupDir,
        "--action", "backup",
        "--type", $BackupType
    ) -Wait -PassThru -NoNewWindow -RedirectStandardOutput "$BackupDir\backup_output.log" -RedirectStandardError "$BackupDir\backup_error.log"
    
    if ($process.ExitCode -eq 0) {
        Write-Host "[$(Get-Date)] Backup completed successfully"
        $logEntry = "[$(Get-Date)] Backup completed successfully"
    } else {
        Write-Host "[$(Get-Date)] Backup failed with exit code $($process.ExitCode)"
        $logEntry = "[$(Get-Date)] Backup failed with exit code $($process.ExitCode)"
    }
    
    # Log to file
    $logEntry | Add-Content -Path (Join-Path $BackupDir "backup_schedule.log")
    
} catch {
    $errorMessage = "[$(Get-Date)] Backup script failed: $($_.Exception.Message)"
    Write-Host $errorMessage
    $errorMessage | Add-Content -Path (Join-Path $BackupDir "backup_schedule.log")
    exit 1
}

# Optional: Clean up old log files (keep last 30 days)
$LogFiles = Get-ChildItem -Path $BackupDir -Filter "backup_*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) }
$LogFiles | Remove-Item -Force

Write-Host "[$(Get-Date)] Backup script completed"