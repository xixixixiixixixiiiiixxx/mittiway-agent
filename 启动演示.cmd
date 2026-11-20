@echo off
where python >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0app.py" --port 8765
) else (
  where py >nul 2>nul && py "%~dp0app.py" --port 8765 || echo 未找到 Python，请先安装 Python 3.10+ 并加入 PATH。
)
pause
