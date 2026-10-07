"""Audio decoding and metadata via the ffmpeg/ffprobe binaries.

We call ffmpeg directly instead of going through PyAV: faster-whisper 1.2.1
crashes with PyAV 19 ("unexpected keyword argument 'metadata_errors'"), and
shelling out to ffmpeg reads any format a phone recorder produces anyway.
"""
import json
import re
import subprocess
from pathlib import Path

import numpy as np

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".ogg", ".opus", ".aac", ".flac", ".amr", ".3gp", ".webm"}


def load_audio(path: Path, sr: int = 16000) -> np.ndarray:
    """Decode any audio file to mono float32 at `sr` Hz."""
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
         "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def probe(path: Path) -> dict:
    """Return duration (s) and lower-cased container tags."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, check=True, text=True).stdout
    fmt = json.loads(out).get("format", {})
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    return {"duration": float(fmt.get("duration") or 0.0), "tags": tags}


_ISO6709 = re.compile(r"^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)")


def location_from_tags(tags: dict):
    """iPhone Voice Memos (and some Android recorders) store an ISO 6709 string
    like '+53.3712-001.8165+260.000/'. Return (lat, lon) or None."""
    for key in ("com.apple.quicktime.location.iso6709", "location", "location-eng"):
        val = tags.get(key)
        if val:
            m = _ISO6709.match(val.strip())
            if m:
                return float(m.group(1)), float(m.group(2))
    return None


def find_memos(folder: Path):
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTS and p.is_file())
