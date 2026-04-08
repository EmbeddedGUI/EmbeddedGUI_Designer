@ECHO OFF
set SPHINXBUILD=python -m sphinx
set SOURCEDIR=source
set BUILDDIR=build

if "%1"=="" goto help

%SPHINXBUILD% -b %1 "%SOURCEDIR%" "%BUILDDIR%/%1"
goto end

:help
echo Usage: make.bat html
echo.
echo Example:
echo   make.bat html

:end
