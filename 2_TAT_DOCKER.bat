@echo off
chcp 65001 >nul
title FaceID - Tat may chu
cd /d "%~dp0"

echo.
echo  ============================================================
echo    TAT MAY CHU FaceID
echo  ============================================================
echo.
echo    [1] Tat thoi          - GIU nguoi da dang ky va so diem danh
echo    [2] Tat va xoa sach   - XOA HET du lieu, ve trang thai ban dau
echo    [3] Thoi, khong tat
echo.

choice /c 123 /n /m "  Chon [1/2/3]: "
if errorlevel 3 goto HUY
if errorlevel 2 goto XOA_SACH
if errorlevel 1 goto TAT_THOI

:TAT_THOI
echo.
echo  Dang tat...
docker compose -f deploy\compose.yml down
echo.
echo  Da tat. Du lieu van con nguyen - bat lai bang 1_BAT_DOCKER.bat
goto XONG

:XOA_SACH
echo.
echo  ############################################################
echo   CANH BAO: se xoa VINH VIEN toan bo
echo     - nguoi da dang ky va vector khuon mat
echo     - so diem danh
echo     - anh dang ky da luu
echo   Khong the hoan tac.
echo  ############################################################
echo.
choice /c YN /n /m "  Chac chan xoa sach? [Y/N] "
if errorlevel 2 goto HUY
echo.
echo  Dang tat va xoa du lieu...
docker compose -f deploy\compose.yml down -v
echo.
echo  Da xoa sach. Lan bat sau se tao lai tai khoan admin/admin123.
goto XONG

:HUY
echo.
echo  Da huy - khong thay doi gi.

:XONG
echo.
pause
