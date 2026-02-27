@echo off
setlocal enabledelayedexpansion

echo ========================================
echo  Whisper STT GPU Setup for Podman
echo ========================================
echo.

REM Check if podman is available
where podman >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Podman not found. Please install Podman first.
    exit /b 1
)

REM Check if nvidia-smi works on Windows host
echo [1/5] Checking NVIDIA GPU on host...
nvidia-smi --query-gpu=name --format=csv,noheader >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] nvidia-smi not found or no GPU detected.
    echo         Please install NVIDIA drivers first.
    exit /b 1
)
for /f "tokens=*" %%i in ('nvidia-smi --query-gpu=name --format=csv,noheader 2^>nul') do echo     Found: %%i
echo     OK
echo.

REM Check if Podman machine is running
echo [2/5] Checking Podman machine...
for /f "tokens=2" %%i in ('podman machine list --format "{{.Running}}" 2^>nul') do set RUNNING=%%i
if not "%RUNNING%"=="true" (
    echo     Starting Podman machine...
    podman machine start
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to start Podman machine.
        exit /b 1
    )
)
echo     OK
echo.

REM Check if CDI is already configured
echo [3/5] Checking CDI configuration...
podman machine ssh "test -f /etc/cdi/nvidia.yaml" 2>nul
if %errorlevel% equ 0 (
    echo     CDI already configured.
    goto :start_container
)

echo     CDI not configured. Setting up...
echo.

REM Install NVIDIA Container Toolkit
echo [4/5] Installing NVIDIA Container Toolkit...
podman machine ssh "sudo dnf install -y nvidia-container-toolkit" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install nvidia-container-toolkit.
    exit /b 1
)
echo     OK
echo.

REM Generate CDI spec
echo     Generating CDI specification...
podman machine ssh "sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Failed to generate CDI spec.
    exit /b 1
)
echo     OK
echo.

REM Enable CDI in Podman
echo     Enabling CDI in Podman...
podman machine ssh "mkdir -p ~/.config/containers && echo '[engine]
enable_cdi = true' > ~/.config/containers/containers.conf" 2>nul
echo     OK
echo.

REM Restart Podman machine to apply changes
echo     Restarting Podman machine...
podman machine stop 2>nul
timeout /t 2 >nul
podman machine start 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Failed to restart Podman machine.
    exit /b 1
)
timeout /t 5 >nul
echo     OK
echo.

:start_container
REM Start the Whisper container
echo [5/5] Starting Whisper container...
podman stop whisper-stt 2>nul
podman rm whisper-stt 2>nul

podman run -d --name whisper-stt -p 8000:8000 ^
    -v hf-hub-cache:/home/ubuntu/.cache/huggingface/hub ^
    --device nvidia.com/gpu=all ^
    --restart unless-stopped ^
    ghcr.io/speaches-ai/speaches:latest-cuda-12.6.3

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start container.
    exit /b 1
)

echo     OK
echo.

REM Verify GPU is accessible
timeout /t 3 >nul
echo Verifying GPU access in container...
podman exec whisper-stt nvidia-smi --query-gpu=name --format=csv,noheader 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] GPU not detected in container. Transcription will use CPU.
) else (
    echo     GPU successfully configured!
)

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo API running at: http://localhost:8000
echo.
echo To start voice input:
echo   python voice_client.py
echo.
pause
