#!/usr/bin/env python3
"""












































































































































































```for backup in backups/**/*.db; do python scripts/backup_manager.py --action verify --backup-file "$backup"; done# Alle Backups auf Integrität prüfen```bash### Backup-Integrität4. Task mit Administrator-Rechten ausführen3. Pfade in den Scripts verifizieren2. PowerShell Execution Policy prüfen: `Get-ExecutionPolicy`1. Task Scheduler Status prüfen### Scheduled Task läuft nicht4. Log-Dateien auf Fehlerdetails prüfen3. Verfügbaren Speicherplatz prüfen2. Berechtigung des Backup-Verzeichnisses prüfen1. Prüfen ob Datenbank gesperrt ist### Backup schlägt fehl## Fehlerbehebung- Zusätzliche Backup-Typen hinzufügen- Backup-Verzeichnisse anpassen- Aufbewahrungszeiten ändernDie Backup-Parameter können in `scripts/backup_manager.py` angepasst werden:## Konfiguration```python scripts/backup_manager.py --action restore --backup-file "backups/daily/taskman_daily_20261207_020000.db" --target "taskman_restored.db"# Backup an anderer Stelle wiederherstellen```bash### 3. Externe Wiederherstellung```python scripts/backup_manager.py --action restore --backup-file "backups/monthly/taskman_monthly_20261101_020000.db"# Gewünschtes Backup wiederherstellenpython scripts/backup_manager.py --action list# Verfügbare Backups anzeigen```bash### 2. Wiederherstellung zu einem bestimmten Zeitpunkt```python scripts/backup_manager.py --action restore --backup-file "backups/daily/[neuestes_backup].db"```bash### 1. Schnelle Wiederherstellung (letztes tägliches Backup)## Wiederherstellung nach Datenverlust```Get-Content "backups/backup_schedule.log" -Tail 10# Letzte Log-Einträge anzeigenGet-ScheduledTask -TaskName "TaskManager-DailyBackup"# Backup-Status überprüfen```bash### Monitoring- `backups/backup_error.log`: Fehler-Output des letzten Laufs- `backups/backup_output.log`: Standard-Output des letzten Laufs- `backups/backup_schedule.log`: Scheduler-Aktivitäten- `backups/backup.log`: Detaillierte Backup-Operationen### Log-Dateien## Monitoring und Logs- Integritätsprüfung vor Restore- Rollback-Möglichkeit bei fehlgeschlagener Wiederherstellung- Automatisches Backup der aktuellen Datenbank vor Restore### 3. Sichere Wiederherstellung- Automatische Verifikation vor Wiederherstellung- Datenbankvalidierung beim Restore- SHA-256 Checksummen für alle Backups### 2. Integritätsprüfung- Transaktionssichere Sicherung- Konsistente Backups auch bei laufender Anwendung- Behandelt WAL-Dateien korrektVerwendet SQLite's integrierte Backup-Funktion statt einfacher Dateikopie:### 1. SQLite Backup API## Sicherheitsfeatures- `.json` Datei: Metadaten (Zeitstempel, Checksumme, etc.)- `.db` Datei: Die eigentliche DatenbankJedes Backup besteht aus:```└── backup_schedule.log  # Scheduler-Protokoll├── backup.log      # Backup-Protokoll├── yearly/         # Jährliche Backups (unbegrenzt)├── monthly/        # Monatliche Backups (12 Monate)├── weekly/         # Wöchentliche Backups (12 Wochen)├── daily/          # Tägliche Backups (30 Tage)backups/```## Backup-Struktur```python scripts/backup_manager.py --action restore --backup-file "backups/daily/taskman_daily_20261207_020000.db"# Datenbank wiederherstellenpython scripts/backup_manager.py --action verify --backup-file "backups/daily/taskman_daily_20261207_020000.db"# Backup-Integrität prüfenpython scripts/backup_manager.py --action cleanup# Alte Backups bereinigenpython scripts/backup_manager.py --action list# Alle Backups auflisten```bash### Backup-Verwaltung```python scripts/backup_manager.py --action backup --type scheduled# Scheduled Backup (entscheidet automatisch basierend auf Datum)python scripts/backup_manager.py --action backup --type weekly# Wöchentliches Backup erstellen  python scripts/backup_manager.py --action backup --type daily# Tägliches Backup erstellen```bash### Manuelle BackupsNach der Installation läuft das Backup-System automatisch täglich um 2:00 Uhr.### Automatische Backups## Verwendung   - Argumente: `-ExecutionPolicy Bypass -File "D:\Skripts\taskmanagerv2\scripts\daily_backup.ps1"`   - Programm: `PowerShell.exe`5. Aktion: "Programm starten"4. Trigger: "Täglich" um 02:00 Uhr3. Name: "TaskManager-DailyBackup"2. "Einfache Aufgabe erstellen..."1. Task Scheduler öffnen#### Windows Task Scheduler Setup:### 2. Manuelle Installation```.\scripts\setup_backup_scheduler.ps1# Als Administrator ausführen```powershell### 1. Automatische Installation (empfohlen)## Installation und Setup| Jährlich | 1. Januar | Unbegrenzt | Langzeitarchivierung || Monatlich | 1. des Monats | 12 Monate | Langfristige Wiederherstellung || Wöchentlich | Jeden Sonntag | 12 Wochen | Mittelfristige Wiederherstellung || Täglich | Jeden Tag | 30 Tage | Kurzfristige Wiederherstellung ||-----|------------|--------------|-------|| Typ | Häufigkeit | Aufbewahrung | Zweck |## Backup-Strategie- **Sichere Backup-Methode**: Nutzt SQLite's Backup-API (kein einfaches Dateikopieren)- **Windows Task Scheduler Integration**: Automatische tägliche Ausführung- **Integritätsprüfung**: Checksummen und Datenbankvalidierung- **Intelligente Retention**: Automatische Bereinigung alter Backups- **Mehrstufige Backup-Strategie**: Täglich, wöchentlich, monatlich, jährlich## FunktionenEin umfassendes Backup-System für die TaskManager SQLite-Datenbank mit intelligenter Retention-Policy.Backup Manager für TaskManager Datenbank
Implementiert eine robuste Backup-Strategie mit verschiedenen Retention-Policies.
"""

import sqlite3
import shutil
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import json
import hashlib


class BackupManager:
    """
    Manages database backups with configurable retention policies.
    
    Backup Strategy:
    - Daily backups: Keep 30 days
    - Weekly backups: Keep 12 weeks  
    - Monthly backups: Keep 12 months
    - Yearly backups: Keep forever
    """
    
    def __init__(self, db_path: str, backup_base_dir: str = "backups"):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_base_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for different backup types
        self.daily_dir = self.backup_dir / "daily"
        self.weekly_dir = self.backup_dir / "weekly" 
        self.monthly_dir = self.backup_dir / "monthly"
        self.yearly_dir = self.backup_dir / "yearly"
        
        for dir_path in [self.daily_dir, self.weekly_dir, self.monthly_dir, self.yearly_dir]:
            dir_path.mkdir(exist_ok=True)
            
        # Setup logging
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup backup-specific logging."""
        logger = logging.getLogger("backup_manager")
        logger.setLevel(logging.INFO)
        
        # Log file
        log_file = self.backup_dir / "backup.log"
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
        
    def create_backup(self, backup_type: str = "daily") -> Optional[str]:
        """
        Create a backup using SQLite's backup API.
        This is safer than file copying as it handles WAL files correctly.
        """
        if not self.db_path.exists():
            self.logger.error(f"Database file not found: {self.db_path}")
            return None
            
        timestamp = datetime.now()
        backup_filename = f"taskman_{backup_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}.db"
        
        # Choose backup directory based on type
        backup_dirs = {
            "daily": self.daily_dir,
            "weekly": self.weekly_dir,
            "monthly": self.monthly_dir,
            "yearly": self.yearly_dir
        }
        backup_path = backup_dirs.get(backup_type, self.daily_dir) / backup_filename
        
        try:
            # Use SQLite backup API for safe backup
            source = sqlite3.connect(str(self.db_path))
            target = sqlite3.connect(str(backup_path))
            
            # Backup database
            source.backup(target)
            
            source.close()
            target.close()
            
            # Create backup metadata
            self._create_backup_metadata(backup_path, backup_type, timestamp)
            
            self.logger.info(f"Created {backup_type} backup: {backup_filename}")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Backup creation failed: {e}")
            # Clean up partial backup
            if backup_path.exists():
                backup_path.unlink()
            return None
            
    def _create_backup_metadata(self, backup_path: Path, backup_type: str, timestamp: datetime):
        """Create metadata file for backup."""
        metadata = {
            "backup_type": backup_type,
            "created_at": timestamp.isoformat(),
            "source_db": str(self.db_path),
            "backup_path": str(backup_path),
            "file_size": backup_path.stat().st_size,
            "checksum": self._calculate_checksum(backup_path)
        }
        
        metadata_path = backup_path.with_suffix('.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of backup file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
        
    def cleanup_old_backups(self):
        """Remove old backups according to retention policy."""
        now = datetime.now()
        
        # Daily backups: keep 30 days
        self._cleanup_backups(self.daily_dir, now - timedelta(days=30))
        
        # Weekly backups: keep 12 weeks (84 days)
        self._cleanup_backups(self.weekly_dir, now - timedelta(days=84))
        
        # Monthly backups: keep 12 months (365 days)
        self._cleanup_backups(self.monthly_dir, now - timedelta(days=365))
        
        # Yearly backups: keep forever (no cleanup)
        
    def _cleanup_backups(self, backup_dir: Path, cutoff_date: datetime):
        """Remove backups older than cutoff_date."""
        for backup_file in backup_dir.glob("*.db"):
            try:
                # Parse timestamp from filename
                parts = backup_file.stem.split('_')
                if len(parts) >= 3:
                    date_str = parts[-2]  # YYYYMMDD
                    time_str = parts[-1]  # HHMMSS
                    backup_datetime = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                    
                    if backup_datetime < cutoff_date:
                        # Remove backup file and metadata
                        backup_file.unlink()
                        metadata_file = backup_file.with_suffix('.json')
                        if metadata_file.exists():
                            metadata_file.unlink()
                        self.logger.info(f"Removed old backup: {backup_file.name}")
                        
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Could not parse backup filename {backup_file.name}: {e}")
                
    def run_scheduled_backup(self):
        """
        Run the appropriate backup based on current date/time.
        This method should be called daily by a scheduler.
        """
        now = datetime.now()
        
        # Always create daily backup
        self.create_backup("daily")
        
        # Weekly backup on Sundays
        if now.weekday() == 6:  # Sunday
            self.create_backup("weekly")
            
        # Monthly backup on 1st of month
        if now.day == 1:
            self.create_backup("monthly")
            
        # Yearly backup on January 1st
        if now.month == 1 and now.day == 1:
            self.create_backup("yearly")
            
        # Clean up old backups
        self.cleanup_old_backups()
        
    def verify_backup(self, backup_path: str) -> bool:
        """Verify backup integrity."""
        backup_file = Path(backup_path)
        metadata_file = backup_file.with_suffix('.json')
        
        if not backup_file.exists() or not metadata_file.exists():
            return False
            
        try:
            # Load metadata
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                
            # Verify checksum
            current_checksum = self._calculate_checksum(backup_file)
            stored_checksum = metadata.get('checksum')
            
            if current_checksum != stored_checksum:
                self.logger.error(f"Backup integrity check failed for {backup_file.name}")
                return False
                
            # Try to open database
            conn = sqlite3.connect(str(backup_file))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            if not tables:
                self.logger.error(f"Backup appears to be empty: {backup_file.name}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Backup verification failed for {backup_file.name}: {e}")
            return False
            
    def restore_backup(self, backup_path: str, target_path: Optional[str] = None) -> bool:
        """Restore database from backup."""
        backup_file = Path(backup_path)
        target_file = Path(target_path) if target_path else self.db_path
        
        if not self.verify_backup(backup_path):
            self.logger.error(f"Cannot restore: backup verification failed")
            return False
            
        try:
            # Create backup of current database before restore
            if target_file.exists():
                current_backup = target_file.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
                shutil.copy2(target_file, current_backup)
                self.logger.info(f"Current database backed up to: {current_backup}")
                
            # Restore from backup
            shutil.copy2(backup_file, target_file)
            self.logger.info(f"Database restored from: {backup_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Restore failed: {e}")
            return False
            
    def list_backups(self) -> dict:
        """List all available backups."""
        backups = {
            "daily": [],
            "weekly": [],
            "monthly": [],
            "yearly": []
        }
        
        for backup_type, backup_dir in [
            ("daily", self.daily_dir),
            ("weekly", self.weekly_dir),
            ("monthly", self.monthly_dir),
            ("yearly", self.yearly_dir)
        ]:
            for backup_file in sorted(backup_dir.glob("*.db")):
                metadata_file = backup_file.with_suffix('.json')
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        backups[backup_type].append({
                            "filename": backup_file.name,
                            "path": str(backup_file),
                            "created_at": metadata.get("created_at"),
                            "file_size": metadata.get("file_size"),
                            "checksum": metadata.get("checksum")
                        })
                    except Exception:
                        # If metadata is corrupted, still list the backup
                        backups[backup_type].append({
                            "filename": backup_file.name,
                            "path": str(backup_file),
                            "created_at": "unknown",
                            "file_size": backup_file.stat().st_size,
                            "checksum": "unknown"
                        })
                        
        return backups


def main():
    """CLI interface for backup manager."""
    import argparse
    
    parser = argparse.ArgumentParser(description="TaskManager Database Backup Manager")
    parser.add_argument("--db", default="taskman.db", help="Database file path")
    parser.add_argument("--backup-dir", default="backups", help="Backup directory")
    parser.add_argument("--action", choices=["backup", "cleanup", "list", "verify", "restore"], 
                       default="backup", help="Action to perform")
    parser.add_argument("--type", choices=["daily", "weekly", "monthly", "yearly", "scheduled"], 
                       default="daily", help="Backup type")
    parser.add_argument("--backup-file", help="Backup file for restore/verify operations")
    parser.add_argument("--target", help="Target file for restore operation")
    
    args = parser.parse_args()
    
    backup_manager = BackupManager(args.db, args.backup_dir)
    
    if args.action == "backup":
        if args.type == "scheduled":
            backup_manager.run_scheduled_backup()
        else:
            backup_manager.create_backup(args.type)
    elif args.action == "cleanup":
        backup_manager.cleanup_old_backups()
    elif args.action == "list":
        backups = backup_manager.list_backups()
        for backup_type, backup_list in backups.items():
            if backup_list:
                print(f"\n{backup_type.upper()} Backups:")
                for backup in backup_list:
                    size_mb = backup['file_size'] / 1024 / 1024 if backup['file_size'] else 0
                    print(f"  {backup['filename']} ({size_mb:.1f}MB) - {backup['created_at']}")
    elif args.action == "verify":
        if args.backup_file:
            result = backup_manager.verify_backup(args.backup_file)
            print(f"Backup verification: {'PASSED' if result else 'FAILED'}")
        else:
            print("--backup-file required for verify operation")
    elif args.action == "restore":
        if args.backup_file:
            result = backup_manager.restore_backup(args.backup_file, args.target)
            print(f"Backup restore: {'SUCCESS' if result else 'FAILED'}")
        else:
            print("--backup-file required for restore operation")


if __name__ == "__main__":
    main()
