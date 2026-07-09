@echo off
cd /d "C:\Users\alexp\Downloads\neural-network-system-trader-"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 .\cosmo\runner.py
) else (
  python .\cosmo\runner.py
)
pause
