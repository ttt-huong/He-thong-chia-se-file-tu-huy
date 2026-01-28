# Script cài đặt tự động cho Distributed File Sharing System
# Chạy: ..\setup.ps1 trong PowerShell

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SETUP FILESHARE SYSTEM - Windows     " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Kiểm tra venv tồn tại
if (-Not (Test-Path ".\.venv")) {
    Write-Host "[1/4] Tạo virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✅ venv tạo thành công" -ForegroundColor Green
}
else {
    Write-Host "[1/4] venv đã tồn tại, bỏ qua" -ForegroundColor Green
}

Write-Host ""

# Activate venv
Write-Host "[2/4] Kích hoạt venv..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
Write-Host "✅ venv kích hoạt" -ForegroundColor Green

Write-Host ""

# Nâng cấp pip
Write-Host "[3/4] Nâng cấp pip, setuptools, wheel..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel -q
Write-Host "✅ Pip cập nhật" -ForegroundColor Green

Write-Host ""

# Cài requirements
Write-Host "[4/4] Cài dependencies từ requirements.txt..." -ForegroundColor Yellow
python -m pip install -r .\requirements.txt
Write-Host "✅ Dependencies cài xong" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ✅ SETUP HOÀN TẤT                    " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 Tiếp theo:" -ForegroundColor Cyan
Write-Host "  1. Bật Docker services:" -ForegroundColor White
Write-Host "     docker compose up -d postgres redis rabbitmq" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Chạy Gateway:" -ForegroundColor White
Write-Host "     python src/gateway/app.py" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Chạy Worker (terminal khác):" -ForegroundColor White
Write-Host "     python src/worker/worker.py" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Mở frontend:" -ForegroundColor White
Write-Host "     http://localhost:5000" -ForegroundColor Gray
Write-Host ""
