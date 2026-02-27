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

### 3. Run the Voice Client

```bash
python voice_client.py
```

## Usage

1. Start opencode in a terminal
2. Run `python voice_client.py`
3. Switch to the opencode window
4. **Hold Alt** to record
5. Speak your command
6. **Release** to stop and transcribe
7. Text appears in opencode + auto-presses Enter
8. Press **ESC** to exit the client

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
