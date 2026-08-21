@echo off
setlocal
if not exist .venv\Scripts\python.exe (
  py -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
pause
