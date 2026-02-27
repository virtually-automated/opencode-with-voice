# Voice Input for OpenCode

Speech-to-text system for controlling opencode via voice commands

## Features

- **Simulated Streaming**: Live transcription feedback during recording via chunked audio processing
- **GPU Acceleration**: Fast transcription with CUDA support (~0.1s for tiny model)
- **Hotkey Recording**: Hold Alt to record, release to transcribe
- **Auto-submit**: Automatically presses Enter after transcription

## Requirements

- Podman (or Docker)
- Python 3.9+
- NVIDIA GPU with CUDA drivers (optional, ~10x faster)

## Quickstart

### 1. Setup and Start Whisper API

**With GPU acceleration (recommended):**

```bash
setup_gpu.bat
```

This script automatically:
- Checks for NVIDIA GPU
- Installs NVIDIA Container Toolkit in Podman VM
- Configures CDI for GPU passthrough
- Starts the Whisper container with GPU support

**CPU-only:**

```bash
start_whisper.bat
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Batch Files Overview

This repository includes three batch (.bat) files to help manage the Whisper container:

| File | Description |
|------|-------------|
| `start_whisper.bat` | Starts the Whisper STT container using CPU only. Use this if you don't have an NVIDIA GPU or want to avoid GPU setup. Slower transcription but works on any system. |
| `setup_gpu.bat` | Automated GPU setup and startup script. Checks for NVIDIA GPU, installs NVIDIA Container Toolkit in the Podman VM, configures CDI for GPU passthrough, and starts the Whisper container with GPU acceleration. This is the recommended option for users with NVIDIA GPUs. |
| `stop_whisper.bat` | Stops and removes the running Whisper container. Uses `podman compose` to bring down the container defined in `whisper-podman.yml`. |

### 3. Run the Voice Client

```bash
python voice_client.py
```

## Usage

1. Start opencode in a terminal
2. Run `python voice_client.py`
3. **Click on the opencode window** to ensure it has focus (this is important - the voice client sends keyboard input to the active window)
4. **Hold Alt** to record
5. Speak your command
6. **Release Alt** to stop recording and transcribe
7. The transcribed text appears in opencode and Enter is automatically pressed to submit
8. Press **ESC** to exit the voice client

> **Important**: After starting the voice client with `python voice_client.py`, you must click on the opencode window to give it focus. When you release Alt after recording, the transcribed text will be typed into whichever window has focus. If you don't focus the opencode window, the text will be sent to the wrong application.

## Performance

| Setup | Transcription Time |
|-------|-------------------|
| CPU only | 5-15s |
| GPU (tiny.en) | ~0.1s |
| GPU (small.en) | ~0.2s |

## Configuration

### Command Line Options

```bash
python voice_client.py --model small     # Use small model
python voice_client.py --model medium    # Use medium model  
python voice_client.py --model small-multi  # Multilingual
python voice_client.py --list-models     # Show all models
python voice_client.py --no-submit       # Don't auto-press Enter
python voice_client.py --chunk-interval 1.0  # Chunk interval in seconds (default: 1.5)
```

### Model Shortcuts

| Shortcut | Model | Speed | Accuracy |
|----------|-------|-------|----------|
| `tiny` | faster-whisper-tiny.en | Fastest | Good |
| `base` | faster-whisper-base.en | Fast | Better |
| `small` | faster-whisper-small.en | Medium | Very Good |
| `medium` | faster-whisper-medium.en | Slower | Best |
| `*-multi` | Multilingual variants | Same | Multilingual |

## Stopping

Run the batch file to stop the container:

```bash
stop_whisper.bat
```

Or manually:
```bash
podman stop whisper-stt && podman rm whisper-stt
```

## Troubleshooting

### GPU not detected

Verify GPU is visible in container:
```bash
podman exec whisper-stt nvidia-smi
```

If this fails, re-run `setup_gpu.bat` or check CDI configuration:
```bash
podman machine ssh "cat /etc/cdi/nvidia.yaml"
```

### Model not found

The first run automatically downloads the model. To download manually:
```bash
curl -X POST "http://localhost:8000/v1/models/guillaumekln/faster-whisper-tiny.en"
```

## Manual GPU Setup (Linux/macOS)

If not using the Windows batch script:

```bash
# Install NVIDIA Container Toolkit
podman machine ssh "sudo dnf install -y nvidia-container-toolkit"

# Generate CDI specification
podman machine ssh "sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml"

# Enable CDI in Podman
podman machine ssh "mkdir -p ~/.config/containers && echo '[engine]
enable_cdi = true' > ~/.config/containers/containers.conf"

# Restart Podman machine
podman machine stop && podman machine start

# Start container with GPU
podman run -d --name whisper-stt -p 8000:8000 \
  -v hf-hub-cache:/home/ubuntu/.cache/huggingface/hub \
  --device nvidia.com/gpu=all \
  ghcr.io/speaches-ai/speaches:latest-cuda-12.6.3
```
