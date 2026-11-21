@echo off
REM Bam dup: bat Docker (may chu web) -> mo app FaceID Studio.
REM Dong app thi may chu Docker tu tat theo. Du lieu van giu nguyen.
setlocal
cd /d "%~dp0"
title FaceID Studio

docker info >nul 2>&1
if not errorlevel 1 goto docker_san_sang
echo Dang mo Docker Desktop, cho khoang 1 phut...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
set /a DEM=0
:cho_docker
timeout /t 3 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 goto docker_san_sang
set /a DEM+=1
if %DEM% geq 60 goto docker_loi
goto cho_docker
:docker_loi
echo [LOI] Doi 3 phut ma Docker van chua chay. Mo Docker Desktop bang tay roi chay lai file nay.
pause
exit /b 1

:docker_san_sang
echo Bat may chu Docker...
pushd deploy
docker compose up -d
popd

echo Mo app FaceID Studio... (dong app thi may chu Docker tu tat)
python desktop_app.py

echo Tat may chu Docker...
pushd deploy
docker compose stop
popd
endlocal
