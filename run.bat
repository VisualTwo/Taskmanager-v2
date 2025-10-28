cd /d "%~dp0"
start ..\venv\Scripts\python.exe -m uvicorn web.server:app --reload