@echo off
echo ==========================================
echo SENTINEL-Z Phase 2: Brain Training
echo ==========================================

REM Use absolute path to ensure we use the venv Python
set PYTHON_EXE=c:\SENTINEL\venv\Scripts\python.exe

echo [1/2] Starting Self-Supervised Training (Encoder)...
echo This will take approximately 40 minutes on GPU.
"%PYTHON_EXE%" backend\training\train_encoder.py
if %errorlevel% neq 0 (
    echo Error during training!
    pause
    exit /b %errorlevel%
)

echo.
echo [2/2] Generating Embeddings...
"%PYTHON_EXE%" backend\training\generate_embeddings.py
if %errorlevel% neq 0 (
    echo Error during embedding generation!
    pause
    exit /b %errorlevel%
)

echo.
echo ==========================================
echo Phase 2 Complete! Embeddings saved.
echo ==========================================
pause
