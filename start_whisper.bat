@echo off
echo Starting Whisper STT Container (CPU-only)...
echo.
echo For GPU acceleration, run setup_gpu.bat instead.
echo.

REM Check if podman is available
where podman >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: podman not found. Please install podman first.
    pause
    exit /b 1
)

podman stop whisper-stt 2>nul
podman rm whisper-stt 2>nul

podman run -d --name whisper-stt -p 8000:8000 ^
    -v hf-hub-cache:/home/ubuntu/.cache/huggingface/hub ^
    --restart unless-stopped ^
    ghcr.io/speaches-ai/speaches:latest-cuda-12.6.3

if %errorlevel% neq 0 (
    echo.
    echo Error: Failed to start container.
    pause
    exit /b 1
)

echo.
echo Whisper STT container started successfully.
echo API available at: http://localhost:8000
echo.
pause
