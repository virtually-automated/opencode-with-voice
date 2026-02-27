#!/usr/bin/env python3
"""
Voice input client for opencode.
Records audio on hotkey press, transcribes in chunks for faster perceived response.
"""

import io
import sys
import wave
import threading
import time
import argparse
import queue
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
from pynput import keyboard
import pyautogui

DEFAULT_MODEL = "guillaumekln/faster-whisper-tiny.en"

AVAILABLE_MODELS = {
    "tiny": "guillaumekln/faster-whisper-tiny.en",
    "tiny-multi": "guillaumekln/faster-whisper-tiny",
    "base": "guillaumekln/faster-whisper-base.en",
    "base-multi": "guillaumekln/faster-whisper-base",
    "small": "guillaumekln/faster-whisper-small.en",
    "small-multi": "guillaumekln/faster-whisper-small",
    "medium": "guillaumekln/faster-whisper-medium.en",
    "medium-multi": "guillaumekln/faster-whisper-medium",
}

CONFIG = {
    "whisper_url": "http://localhost:8000",
    "model": DEFAULT_MODEL,
    "auto_submit": True,
    "sample_rate": 16000,
    "channels": 1,
    "chunk_interval": 1.5,
    "min_chunk_duration": 0.5,
}


def audio_to_wav_bytes(audio_data, sample_rate=16000):
    """Convert numpy audio array to WAV bytes."""
    audio_int16 = (audio_data * 32767).astype(np.int16)
    
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    buffer.seek(0)
    return buffer


def transcribe_audio(audio_data):
    """Send audio to Whisper API and return transcription."""
    wav_buffer = audio_to_wav_bytes(audio_data, CONFIG["sample_rate"])
    
    files = {
        'file': ('audio.wav', wav_buffer, 'audio/wav')
    }
    data = {
        'model': CONFIG["model"],
        'response_format': 'text'
    }
    
    try:
        response = requests.post(
            f"{CONFIG['whisper_url']}/v1/audio/transcriptions",
            files=files,
            data=data,
            timeout=30
        )
        response.raise_for_status()
        return response.text.strip()
    except requests.exceptions.ConnectionError:
        print("[Error: Cannot connect to Whisper API. Is the container running?]")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[Error: {e}]")
        return None


class VoiceRecorder:
    def __init__(self):
        self.is_recording = False
        self.audio_data = []
        self.stream = None
        self.recording_lock = threading.Lock()
        self.chunk_queue = queue.Queue()
        self.transcription = ""
        self.transcription_lock = threading.Lock()
        self.last_chunk_time = 0
        self.chunk_start_time = 0
        self.processor_thread = None
        self.stop_processor = threading.Event()
        
    def start_recording(self):
        with self.recording_lock:
            if self.is_recording:
                return
            self.is_recording = True
            self.audio_data = []
            self.transcription = ""
            self.last_chunk_time = time.time()
            self.chunk_start_time = time.time()
            self.stop_processor.clear()
            print("[Recording... Release Alt to stop]")
            
            self.processor_thread = threading.Thread(target=self._process_chunks, daemon=True)
            self.processor_thread.start()
            
            self.stream = sd.InputStream(
                samplerate=CONFIG["sample_rate"],
                channels=CONFIG["channels"],
                dtype=np.float32,
                callback=self._audio_callback
            )
            self.stream.start()
    
    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.audio_data.append(indata.copy())
            
            now = time.time()
            if now - self.last_chunk_time >= CONFIG["chunk_interval"]:
                self.last_chunk_time = now
                chunk_audio = np.concatenate(self.audio_data, axis=0)
                duration = len(chunk_audio) / CONFIG["sample_rate"]
                if duration >= CONFIG["min_chunk_duration"]:
                    self.chunk_queue.put(chunk_audio.copy())
    
    def _process_chunks(self):
        while not self.stop_processor.is_set() or not self.chunk_queue.empty():
            try:
                chunk = self.chunk_queue.get(timeout=0.1)
                if self.stop_processor.is_set():
                    break
                text = transcribe_audio(chunk)
                if text and not self.stop_processor.is_set():
                    with self.transcription_lock:
                        self.transcription = text
                    print(f"\r[Live: {text}]  ", end="", flush=True)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"\n[Chunk error: {e}]")
    
    def stop_recording(self):
        with self.recording_lock:
            if not self.is_recording:
                return None
            self.is_recording = False
            self.stop_processor.set()
            
            while not self.chunk_queue.empty():
                try:
                    self.chunk_queue.get_nowait()
                except queue.Empty:
                    break
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            if not self.audio_data:
                return None
            
            audio = np.concatenate(self.audio_data, axis=0)
            if self.processor_thread:
                self.processor_thread.join(timeout=2.0)
            
            return audio
    
    def get_live_transcription(self):
        with self.transcription_lock:
            return self.transcription
    
    def is_active(self):
        with self.recording_lock:
            return self.is_recording


def inject_text(text):
    """Type text into the active window and optionally press Enter."""
    if not text:
        return
    
    print(f"\r\033[K[Final: {text}]")
    pyautogui.write(text, interval=0.01)
    
    if CONFIG["auto_submit"]:
        pyautogui.press('enter')


class HotkeyListener:
    def __init__(self, recorder):
        self.recorder = recorder
        self.listener = None
        self.alt_count = 0
        self.is_processing = False
        self.last_stop_time = 0
    
    def _is_alt(self, key):
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return True
        try:
            if hasattr(key, 'vk') and key.vk in (164, 165):
                return True
        except:
            pass
        return False
    
    def on_press(self, key):
        if self._is_alt(key):
            if self.alt_count == 0:
                self.alt_count = 1
        
        if self.alt_count > 0:
            if not self.recorder.is_active() and not self.is_processing:
                if time.time() - self.last_stop_time > 0.3:
                    self.recorder.start_recording()
    
    def on_release(self, key):
        if self._is_alt(key):
            self.alt_count = 0
        
        if self.alt_count == 0:
            if self.recorder.is_active():
                self.last_stop_time = time.time()
                audio = self.recorder.stop_recording()
                if audio is not None:
                    self.is_processing = True
                    threading.Thread(
                        target=self._process_audio,
                        args=(audio,),
                        daemon=True
                    ).start()
        
        if key == keyboard.Key.esc:
            print("\n[Exiting...]")
            return False
    
    def _process_audio(self, audio):
        try:
            print("\r\033[K[Processing final...]", end="", flush=True)
            text = transcribe_audio(audio)
            if text:
                inject_text(text)
        except Exception as e:
            print(f"\n[Error during transcription: {e}]")
        finally:
            self.is_processing = False
            print("\n[Ready]")
    
    def start(self):
        print("Voice Input Client for OpenCode")
        print("================================")
        print("Hotkey: Hold Alt to record")
        print("Press ESC to exit")
        print()
        
        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )
        self.listener.start()
        self.listener.join()


def check_whisper_api():
    """Check if Whisper API is reachable."""
    try:
        response = requests.get(f"{CONFIG['whisper_url']}/health", timeout=5)
        return True
    except:
        try:
            response = requests.get(f"{CONFIG['whisper_url']}/v1/models", timeout=5)
            return True
        except:
            return False


def ensure_model_downloaded():
    """Check if model is downloaded, download if not."""
    try:
        response = requests.get(f"{CONFIG['whisper_url']}/v1/models", timeout=5)
        models = response.json().get("data", [])
        model_ids = [m.get("id") for m in models]
        
        if CONFIG["model"] not in model_ids:
            print(f"[Downloading model: {CONFIG['model']}...]")
            dl_response = requests.post(
                f"{CONFIG['whisper_url']}/v1/models/{CONFIG['model']}",
                timeout=300
            )
            if dl_response.status_code == 200:
                print(f"[Model downloaded successfully]")
            else:
                print(f"[Warning: Could not download model: {dl_response.text}]")
    except Exception as e:
        print(f"[Warning: Could not check/download model: {e}]")


def list_available_models():
    """List available model shortcuts and their full IDs."""
    print("Available models:")
    print()
    for shortcut, model_id in AVAILABLE_MODELS.items():
        suffix = " (default)" if model_id == DEFAULT_MODEL else ""
        print(f"  --model {shortcut:12} -> {model_id}{suffix}")
    print()
    print("Or use a full model ID from the registry:")
    print("  --model Systran/faster-whisper-large-v3")
    print()


def main():
    parser = argparse.ArgumentParser(description="Voice input client for opencode")
    parser.add_argument(
        "--model", "-m",
        default="tiny",
        help="Model to use (shortcut or full ID). Shortcuts: tiny, base, small, medium (+ -multi for multilingual)"
    )
    parser.add_argument(
        "--list-models", "-l",
        action="store_true",
        help="List available model shortcuts"
    )
    parser.add_argument(
        "--no-submit",
        action="store_true",
        help="Don't auto-press Enter after transcription"
    )
    parser.add_argument(
        "--chunk-interval",
        type=float,
        default=1.5,
        help="Interval in seconds between chunk transcriptions (default: 1.5)"
    )
    
    args = parser.parse_args()
    
    if args.list_models:
        list_available_models()
        return
    
    if args.model in AVAILABLE_MODELS:
        CONFIG["model"] = AVAILABLE_MODELS[args.model]
    else:
        CONFIG["model"] = args.model
    
    if args.no_submit:
        CONFIG["auto_submit"] = False
    
    if args.chunk_interval:
        CONFIG["chunk_interval"] = args.chunk_interval
    
    print(f"Using model: {CONFIG['model']}")
    print(f"Chunk interval: {CONFIG['chunk_interval']}s")
    print()
    
    print("Checking Whisper API connection...")
    if not check_whisper_api():
        print(f"[Warning: Cannot reach Whisper API at {CONFIG['whisper_url']}]")
        print("[Make sure the container is running: podman-compose -f whisper-podman.yml up -d]")
        print()
    else:
        ensure_model_downloaded()
    
    recorder = VoiceRecorder()
    listener = HotkeyListener(recorder)
    listener.start()


if __name__ == "__main__":
    main()
