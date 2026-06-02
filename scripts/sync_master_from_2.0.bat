@echo off
setlocal
cd /d "%~dp0.."

echo Fetching origin...
git fetch origin
if errorlevel 1 exit /b 1

for /f %%b in ('git rev-parse --abbrev-ref HEAD') do set START_BRANCH=%%b

echo Syncing master to origin/2.0...
git checkout master
if errorlevel 1 exit /b 1

git merge --ff-only origin/2.0
if errorlevel 1 (
    echo ERROR: master has diverged from 2.0. Resolve manually or reset master to origin/2.0.
    git checkout %START_BRANCH%
    exit /b 1
)

git push origin master
if errorlevel 1 (
    git checkout %START_BRANCH%
    exit /b 1
)

git checkout %START_BRANCH%
if errorlevel 1 exit /b 1

echo master is now synced to 2.0 (%START_BRANCH% restored).
exit /b 0
