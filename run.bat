cd /d "%~dp0"
start powershell -NoExit -Command "Set-Location -LiteralPath '%~dp0'; ..\venv\Scripts\python.exe -m uvicorn web.server:app --reload"