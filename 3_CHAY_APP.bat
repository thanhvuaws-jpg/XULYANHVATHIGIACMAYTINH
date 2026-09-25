@echo off
chcp 65001 >nul
title FaceID - Ung dung may tinh
cd /d "%~dp0"

REM Doc cong tu deploy\.env - mot nguon su that duy nhat. Viet cung cong o day
REM nua thi doi cong se phai sua nhieu cho va chac chan se bo sot mot cho.
set "WEB_PORT="
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%~dp0deploy\.env") do (
    if /i "%%a"=="WEB_PORT" set "WEB_PORT=%%b"
)
if not defined WEB_PORT set "WEB_PORT=8090"
set "FACEID_WEB=http://localhost:%WEB_PORT%"

REM Cho ung dung biet dia chi may chu, de tab Kiosk khoi phai go tay.
set "FACEID_API_URL=%FACEID_WEB%"
REM Chu Viet co dau khong bi loi trong cua so lenh.
set PYTHONIOENCODING=utf-8

echo.
echo  ============================================================
echo    FaceID Studio - ung dung may tinh
echo  ============================================================
echo.

REM May chu khong bat buoc phai chay, nhung tab Kiosk can no de ghi so.
curl -s -m 3 %FACEID_WEB%/api/system/health >nul 2>&1
if not errorlevel 1 goto MAY_CHU_OK

echo  [!] May chu chua chay.
echo      Ung dung van mo duoc, nhung tab "Kiosk diem danh" se khong ghi so duoc.
echo.
choice /c YN /n /m "  Bat may chu truoc? [Y/N] "
if errorlevel 2 goto CHAY_APP
call "%~dp01_BAT_DOCKER.bat"
goto CHAY_APP

:MAY_CHU_OK
echo  [OK] May chu dang chay tai %FACEID_WEB%

:CHAY_APP
echo.
echo  Dang nap mo hinh nhan dien... ^(mat khoang 3-5 giay^)
echo  Cua so ung dung se hien ra. DUNG dong cua so den nay.
echo.

python desktop_app.py
set _ma=%errorlevel%

echo.
if "%_ma%"=="0" goto DONG_BINH_THUONG

echo  [X] Ung dung thoat voi ma loi %_ma%. Xem thong bao ben tren.
echo.
echo      Hay kiem tra:
echo        - Camera co bi ung dung khac chiem khong ^(Zoom, Teams, Camera...^)
echo        - Chay:  python -m pip install -r requirements.txt
echo.
pause
exit /b %_ma%

:DONG_BINH_THUONG
echo  Da dong ung dung.
timeout /t 2 /nobreak >nul
