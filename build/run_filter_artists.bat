@echo off
setlocal EnableDelayedExpansion
rem Soundlore: stream the MusicBrainz artist dump and keep the artists with genre votes.
rem Double-click this file. Output: sources\musicbrainz\artist_genres_extract.jsonl.gz
pushd "%~dp0.."
if errorlevel 1 (echo Could not open the project folder: %~dp0.. & pause & exit /b 1)
echo Project folder: %CD%
if not exist "sources\musicbrainz\artist.tar.xz" (echo Dump not found: sources\musicbrainz\artist.tar.xz & pause & exit /b 1)

rem Find a working Python 3 (py launcher, python on PATH, or the usual install folders)
set "PY="
for %%c in ("py -3" "python" "python3") do (
  if not defined PY (
    %%~c -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >nul 2>nul && set "PY=%%~c"
  )
)
if not defined PY (
  for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "%USERPROFILE%\anaconda3" "%USERPROFILE%\miniconda3" "%LOCALAPPDATA%\anaconda3" "%LOCALAPPDATA%\miniconda3") do (
    if not defined PY if exist "%%~d\python.exe" set "PY="%%~d\python.exe""
  )
)
if not defined PY (
  echo.
  echo Python 3 was not found on this computer.
  echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^)
  echo or run in a terminal:  winget install Python.Python.3.12
  echo Then double-click this file again.
  pause & exit /b 1
)
echo Using Python: !PY!
echo Soundlore - filtering MusicBrainz artists (10-30 minutes)...
echo.
!PY! build\filter_artists.py
echo.
echo Finished. You can close this window.
pause
