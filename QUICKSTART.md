# TaskManager V2 - Schnellstart

## ⚡ Schnellinstallation

### 1. Repository Setup
```bash
cd D:\Skripts\taskmanagerv2
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Server starten
```bash
python -m uvicorn web.server:app --host 127.0.0.1 --port 8001
```

### 3. Browser öffnen
```
http://127.0.0.1:8001
```

## 🔄 Backup-System aktivieren

```powershell
# Als Administrator ausführen
powershell -ExecutionPolicy Bypass -File "scripts/setup_backup_scheduler.ps1"
```

## 🧪 Tests ausführen

```bash
python -m pytest
```

## 📊 Aktueller Status

✅ **Server läuft auf Port 8001**  
✅ **Deutsche Feiertage aktiv**  
✅ **Backup-System bereit**  
✅ **Alle Tests bestanden (69/69)**  
✅ **Dokumentation vollständig**  

## 🔗 Wichtige URLs

- **Dashboard**: http://127.0.0.1:8001
- **Heute**: http://127.0.0.1:8001/?date=07.01.2026
- **API Docs**: http://127.0.0.1:8001/docs

## 📞 Bei Problemen

1. Port bereits belegt → `--port 8002` verwenden
2. Module nicht gefunden → Virtual Environment aktivieren
3. Backup-Fehler → PowerShell als Administrator ausführen

**Happy Task Managing! 🚀**