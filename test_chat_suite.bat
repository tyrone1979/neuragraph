@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
set PYTHONPATH=%CD%

echo Running chat feature regression suite...
py -3 tests\test_chat_feature_suite.py
set EXIT_CODE=%ERRORLEVEL%
if not %EXIT_CODE%==0 goto done
echo Running report regression suite...
py -3 tests\test_report_regression_suite.py
set EXIT_CODE=%ERRORLEVEL%
if not %EXIT_CODE%==0 goto done
echo.
if %EXIT_CODE%==0 (
  echo Chat regression suite passed.
) else (
  echo Chat regression suite failed with exit code %EXIT_CODE%.
)
:done
pause
