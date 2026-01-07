# Setup Windows Task Scheduler for TaskManager Backups
# This script creates a scheduled task that runs the backup daily at 2 AM

param(
    [string]$ProjectPath = (Split-Path -Parent $PSScriptRoot),
    [string]$TaskName = "TaskManager-DailyBackup",
    [string]$RunTime = "02:00"
)

# Requires administrator privileges
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "This script requires administrator privileges. Please run as administrator." -ForegroundColor Red
    exit 1
}

# Paths
$BackupScript = Join-Path $ProjectPath "scripts\daily_backup.ps1"

# Check if backup script exists
if (!(Test-Path $BackupScript)) {
    Write-Host "Backup script not found: $BackupScript" -ForegroundColor Red
    exit 1
}

try {
    # Create scheduled task action
    $Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-ExecutionPolicy Bypass -File `"$BackupScript`""
    
    # Create trigger for daily execution at specified time
    $Trigger = New-ScheduledTaskTrigger -Daily -At $RunTime
    
    # Create task settings
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false
    
    # Create task principal (run with highest privileges)
    $Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    
    # Create the task
    $Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Daily backup for TaskManager database"
    
    # Register the task
    Register-ScheduledTask -TaskName $TaskName -InputObject $Task -Force
    
    Write-Host "Successfully created scheduled task: $TaskName" -ForegroundColor Green
    Write-Host "The task will run daily at $RunTime" -ForegroundColor Green
    Write-Host "Backup script location: $BackupScript" -ForegroundColor Green
    
    # Show task details
    Write-Host "`nTask Details:" -ForegroundColor Yellow
    Get-ScheduledTask -TaskName $TaskName | Format-Table -Property TaskName, State, NextRunTime
    
    # Test the task
    $TestRun = Read-Host "`nWould you like to test the backup now? (y/n)"
    if ($TestRun -eq "y" -or $TestRun -eq "Y") {
        Write-Host "Starting test backup..." -ForegroundColor Yellow
        Start-ScheduledTask -TaskName $TaskName
        Start-Sleep -Seconds 3
        
        # Check task status
        $TaskInfo = Get-ScheduledTask -TaskName $TaskName
        Write-Host "Task Status: $($TaskInfo.State)" -ForegroundColor Cyan
    }
    
} catch {
    Write-Host "Failed to create scheduled task: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`nBackup system setup completed successfully!" -ForegroundColor Green
Write-Host "Backups will be stored in: $(Join-Path $ProjectPath 'backups')" -ForegroundColor Green