@echo off
setlocal EnableDelayedExpansion
rem Soundlore: artists from Wikidata (genres and sitelinks), then the MusicBrainz dump again
rem to keep those artists too. Double-click this file. Needs internet (query.wikidata.org).
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
echo.
echo Step 1 of 2 - Wikidata artists with a MusicBrainz ID (a few minutes)...
!PY! build\fetch_wikidata_artists.py
if errorlevel 1 (echo. & echo The Wikidata step failed. Send a screenshot of this window. & pause & exit /b 1)
echo.
echo Step 2 of 2 - MusicBrainz artist dump, keeping the Wikidata artists too (about 3 minutes)...
!PY! build\filter_artists.py --also sources\wikidata\artist_mbids.txt
echo.
echo Finished. You can close this window.
pause
