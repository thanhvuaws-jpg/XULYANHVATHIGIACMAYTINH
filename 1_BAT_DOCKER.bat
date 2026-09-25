@echo off
chcp 65001 >nul
title FaceID - Bat may chu
cd /d "%~dp0"

REM Doc cong tu deploy\.env - mot nguon su that duy nhat. Viet cung cong o day
REM nua thi doi cong se phai sua nhieu cho va chac chan se bo sot mot cho.
set "WEB_PORT="
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%~dp0deploy\.env") do (
    if /i "%%a"=="WEB_PORT" set "WEB_PORT=%%b"
)
if not defined WEB_PORT set "WEB_PORT=8090"
set "FACEID_WEB=http://localhost:%WEB_PORT%"

echo.
echo  ============================================================
echo    BAT MAY CHU FaceID  (backend + web)
echo  ============================================================
echo.

REM Docker Desktop da chay chua?
REM Ghi chu: khong dat nhan :label hay bien %var% ben trong khoi ngoac ( ),
REM vi batch doc ca khoi mot lan va bien se khong cap nhat trong vong lap.
docker info >nul 2>&1
if not errorlevel 1 goto DOCKER_OK

echo  [!] Docker Desktop chua chay. Dang mo ho...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
echo      Cho Docker khoi dong ^(co the mat 30-60 giay^)...
set _dem=0

:CHO_DOCKER
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 goto DOCKER_OK
set /a _dem+=1
if %_dem% lss 24 goto CHO_DOCKER
echo.
echo  [X] Docker khong khoi dong duoc sau 2 phut.
echo      Mo Docker Desktop thu cong roi chay lai file nay.
pause
exit /b 1

:DOCKER_OK
echo  [1/3] Docker da san sang.

REM Lan dau chua co .env thi tao tu mau, kem khoa ky token ngau nhien.
if exist "deploy\.env" goto CO_ENV
echo  [*] Chua co deploy\.env - dang tao tu mau va sinh khoa moi...
copy /y "deploy\.env.example" "deploy\.env" >nul
python -c "import pathlib,secrets; p=pathlib.Path('deploy/.env'); t=p.read_text(encoding='utf-8'); p.write_text(t.replace('FACEID_SECRET_KEY=doi-khoa-nay-di-dung-de-nguyen','FACEID_SECRET_KEY='+secrets.token_urlsafe(48)),encoding='utf-8')"

:CO_ENV
echo  [2/3] Dang khoi dong ^(lan dau se build, mat vai phut^)...
echo.
docker compose -f deploy\compose.yml up -d --build
if not errorlevel 1 goto CHO_ENGINE
echo.
echo  [X] Khoi dong that bai. Xem thong bao loi ben tren.
pause
exit /b 1

:CHO_ENGINE
echo.
echo  [3/3] Cho engine nap mo hinh...
set _n=0

:CHO_HEALTH
timeout /t 3 /nobreak >nul
set _hs=
for /f "delims=" %%s in ('docker inspect -f "{{.State.Health.Status}}" faceid-backend-1 2^>nul') do set _hs=%%s
if "%_hs%"=="healthy" goto SAN_SANG
set /a _n+=1
if %_n% lss 40 goto CHO_HEALTH
echo  [!] Backend lau hon binh thuong. Xem log bang lenh:
echo      docker compose -f deploy\compose.yml logs backend
goto XONG

:SAN_SANG
echo.
echo  ============================================================
echo    MAY CHU DA SAN SANG
echo.
echo      Giao dien web  :  %FACEID_WEB%
echo      Tai lieu API   :  %FACEID_WEB%/docs
echo      Dang nhap      :  admin / admin123
echo  ============================================================
echo.
choice /c YN /n /m "  Mo trinh duyet luon? [Y/N] "
if errorlevel 2 goto XONG
start "" %FACEID_WEB%

:XONG
echo.
echo  Tat may chu: chay file  2_TAT_DOCKER.bat
echo.
pause
