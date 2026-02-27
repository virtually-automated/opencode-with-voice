@echo off
echo Stopping Whisper STT Container...
podman compose -f whisper-podman.yml down
echo Container stopped.
pause
