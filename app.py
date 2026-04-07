import os
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
from tkinter import (
    Tk,
    Label,
    Button,
    Scale,
    HORIZONTAL,
    filedialog,
    StringVar,
    Entry,
    OptionMenu,
    TclError,
    Canvas,
    Frame,
    Scrollbar,
    Toplevel,
)
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
import soundfile as sf
try:
    from mutagen.id3 import APIC, ID3
    from mutagen.mp3 import MP3

    MUTAGEN_AVAILABLE = True
except Exception:
    APIC = None
    ID3 = None
    MP3 = None
    MUTAGEN_AVAILABLE = False

VERSION_PATH = Path(__file__).resolve().with_name("VERSION")

SESSION_MODE_ALIASES = {
    "Tek Klasor": "Tek Klasör",
    "Tek Klasör": "Tek Klasör",
    "Tarihli Oturum": "Tarihli Oturum",
    "Isimli Oturum": "İsimli Oturum",
    "İsimli Oturum": "İsimli Oturum",
}
MP3_QUALITY_ALIASES = {
    "Yuksek VBR": "Yüksek VBR",
    "Yüksek VBR": "Yüksek VBR",
    "320 kbps": "320 kbps",
    "192 kbps": "192 kbps",
    "128 kbps": "128 kbps",
}
WAV_EXPORT_MODE_ALIASES = {
    "Sadece Vocal WAV": "Sadece Vokal WAV",
    "Sadece Vokal WAV": "Sadece Vokal WAV",
    "Mix + Vocal WAV": "Mix + Vokal WAV",
    "Mix + Vokal WAV": "Mix + Vokal WAV",
    "Sadece WAV (Mix + Vocal)": "Sadece WAV (Mix + Vokal)",
    "Sadece WAV (Mix + Vokal)": "Sadece WAV (Mix + Vokal)",
    "Tum WAV Dosyalari": "Tüm WAV Dosyaları",
    "Tüm WAV Dosyaları": "Tüm WAV Dosyaları",
}
LIMITER_ALIASES = {
    "Acik": "Açık",
    "Açık": "Açık",
    "Kapali": "Kapalı",
    "Kapalı": "Kapalı",
}

LEGACY_QUICK_TAKE_PATTERN = re.compile(r"^quick_take_\d{3}(?:_(?:mix|vocal))?\.(?:mp3|wav)$", re.IGNORECASE)
TIMESTAMPED_QUICK_TAKE_PATTERN = re.compile(r"^quick_take_\d{8}_\d{6}(?:_(?:mix|vocal))?\.(?:mp3|wav)$", re.IGNORECASE)


def normalize_choice(value: str, aliases: dict[str, str], default: str) -> str:
    return aliases.get(str(value or "").strip(), default)


def user_app_data_dir() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "GuitarAmpRecorder"
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "GuitarAmpRecorder"
    return home / ".guitar_amp_recorder"


def user_app_data_path(filename: str) -> Path:
    return user_app_data_dir() / filename


GUI_PRESET_PATH = user_app_data_path("gui_saved_preset.json")
LAST_SESSION_PATH = user_app_data_path("last_session.json")


def read_app_version() -> str:
    try:
        version = VERSION_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.1.0-dev"
    return version or "0.1.0-dev"


def latest_audio_file_in_dir(output_dir: Path) -> Optional[Path]:
    if not output_dir.exists():
        return None
    audio_files = [path for path in output_dir.iterdir() if path.is_file() and path.suffix.lower() in {".mp3", ".wav"}]
    if not audio_files:
        return None
    return max(audio_files, key=lambda path: path.stat().st_mtime)


def visible_recent_output_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() in {".mp3", ".wav"}:
        return True
    return path.name in {
        "session_summary.json",
        "take_notes.txt",
        "export_recovery_note.txt",
        "preparation_summary.txt",
        "session_brief.txt",
    }


def recent_output_file_label(path: Path) -> str:
    if path.suffix.lower() in {".mp3", ".wav"}:
        return "Ses"
    return {
        "session_summary.json": "Oturum özeti",
        "take_notes.txt": "Take notu",
        "export_recovery_note.txt": "Kurtarma notu",
        "preparation_summary.txt": "Hazırlık özeti",
        "session_brief.txt": "Kısa rapor",
    }.get(path.name, "Çıktı")


def recent_output_matches_filter(path: Path, filter_value: str) -> bool:
    normalized = str(filter_value or "Tümü").strip() or "Tümü"
    if normalized == "Sadece Ses":
        return path.suffix.lower() in {".mp3", ".wav"}
    if normalized == "Sadece Belgeler":
        return path.suffix.lower() not in {".mp3", ".wav"}
    return True


def filtered_recent_output_files(output_dir: Path, filter_value: str) -> list[Path]:
    if not output_dir.exists():
        return []
    return sorted(
        [
            path
            for path in output_dir.iterdir()
            if visible_recent_output_file(path) and recent_output_matches_filter(path, filter_value)
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def all_recent_output_files(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    return sorted(
        [path for path in output_dir.iterdir() if visible_recent_output_file(path)],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def recent_output_file_line(path: Path) -> str:
    timestamp = time.strftime("%d.%m %H:%M", time.localtime(path.stat().st_mtime))
    return f"- {recent_output_file_label(path)} [{timestamp}]: {path.name}"


def recent_audio_duration_text(path: Path) -> str:
    try:
        info = sf.info(str(path))
    except Exception:
        return ""
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    if duration <= 0:
        return ""
    return format_seconds_short(duration)


def recent_audio_hint_text(path: Path) -> str:
    audio_type = path.suffix.lower().removeprefix(".").upper() or "SES"
    parts = [audio_type]
    duration = recent_audio_duration_text(path)
    if duration:
        parts.append(duration)
    output_dir_name = path.parent.name or str(path.parent)
    if output_dir_name:
        parts.append(output_dir_name)
    return " | ".join(parts)


def recent_audio_status_text(path: Path) -> str:
    return f"{path.name} ({recent_audio_hint_text(path)})"


def recent_audio_highlight_line(path: Path) -> str:
    timestamp = time.strftime("%d.%m %H:%M", time.localtime(path.stat().st_mtime))
    return f"Son kayıt [{timestamp} | {recent_audio_hint_text(path)}]: {path.name}"


def legacy_quick_take_file(path: Path) -> bool:
    return path.is_file() and LEGACY_QUICK_TAKE_PATTERN.match(path.name) is not None


def timestamped_quick_take_file(path: Path) -> bool:
    return path.is_file() and TIMESTAMPED_QUICK_TAKE_PATTERN.match(path.name) is not None


def device_test_output_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".wav" and path.name.endswith("_device_test.wav")


def cleanup_candidate_output_files(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    files = [path for path in output_dir.iterdir() if path.is_file()]
    has_timestamped_quick_take = any(timestamped_quick_take_file(path) for path in files)
    legacy_quick_takes = [path for path in files if has_timestamped_quick_take and legacy_quick_take_file(path)]
    device_tests = sorted(
        [path for path in files if device_test_output_file(path)],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    stale_device_tests = device_tests[1:]
    return sorted(legacy_quick_takes + stale_device_tests, key=lambda path: path.stat().st_mtime, reverse=True)


def archive_ready_export_base_name(path: Optional[Path]) -> str:
    if path is None:
        return "session"
    stem = path.stem
    for suffix in ("_mix", "_vocal", "_device_test"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem or "session"


def session_archive_dir(output_dir: Path, export_path: Optional[Path]) -> Path:
    base_name = archive_ready_export_base_name(export_path)
    archive_root = output_dir / "_arsiv"
    target = archive_root / base_name
    if not target.exists():
        return target
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return archive_root / f"{base_name}_{timestamp}"


def generated_files_from_summary_path(summary_path: Optional[Path]) -> list[Path]:
    if summary_path is None or not summary_path.exists():
        return []
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    generated_files = data.get("generated_files", [])
    if not isinstance(generated_files, list):
        return []
    resolved = []
    for value in generated_files:
        try:
            path = Path(str(value))
        except Exception:
            continue
        if path.exists():
            resolved.append(path)
    return resolved


def format_seconds_short(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def describe_clip_warning(input_peak: float = 0.0, processed_peak: float = 0.0, mix_peak: float = 0.0) -> str:
    warnings = []
    if input_peak >= 0.98:
        warnings.append("Giris clipping riski")
    if processed_peak >= 0.98:
        warnings.append("Islenmis sinyal sinira dayandi")
    if mix_peak >= 0.98:
        warnings.append("Mix sinira dayandi")
    return " | ".join(warnings) if warnings else "Clip riski yok"


def take_lock_dir(directory: Path) -> Path:
    return directory / ".take_locks"


def take_lock_path(directory: Path, name: str) -> Path:
    return take_lock_dir(directory) / f"{name}.lock"


def take_name_conflicts(directory: Path, name: str) -> bool:
    candidates = [
        directory / f"{name}.mp3",
        directory / f"{name}_mix.wav",
        directory / f"{name}_vocal.wav",
        directory / f"{name}_device_test.wav",
        take_lock_path(directory, name),
    ]
    return any(path.exists() for path in candidates)


def reserve_take_name_for_dir(directory: Path, prefix: str = "quick_take") -> str:
    directory.mkdir(parents=True, exist_ok=True)
    take_lock_dir(directory).mkdir(parents=True, exist_ok=True)
    for i in range(1, 10000):
        name = f"{prefix}_{i:03d}"
        if take_name_conflicts(directory, name):
            continue
        lock_path = take_lock_path(directory, name)
        try:
            with lock_path.open("x", encoding="utf-8") as handle:
                handle.write("")
            return name
        except Exception:
            continue
    fallback = f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"
    with take_lock_path(directory, fallback).open("w", encoding="utf-8") as handle:
        handle.write("")
    return fallback


def release_take_name_lock(directory: Path, name: str) -> None:
    lock_path = take_lock_path(directory, name)
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass


def build_export_recovery_note(output_dir: Path, base_name: str, exc: Exception) -> str:
    return "\n".join(
        [
            "Kurtarma Notu",
            f"Tarih: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Klasör: {output_dir}",
            f"Take: {base_name}",
            f"Hata: {exc}",
            "Hedef Dosyalar:",
            f"- {base_name}.mp3",
            f"- {base_name}_mix.wav",
            f"- {base_name}_vocal.wav",
            "Not: Gecici dosyalar temizlenmis olabilir; take_notes.txt ve session_summary.json olusmadiysa kaydi yeniden deneyin.",
        ]
    )


def write_export_recovery_note(output_dir: Path, base_name: str, exc: Exception) -> Optional[Path]:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        note_path = output_dir / "export_recovery_note.txt"
        note_path.write_text(build_export_recovery_note(output_dir, base_name, exc), encoding="utf-8")
        return note_path
    except Exception:
        return None


def db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def one_pole_lowpass(signal: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    if cutoff_hz <= 0:
        return np.zeros_like(signal)
    alpha = np.exp(-2.0 * np.pi * cutoff_hz / sample_rate)
    out = np.zeros_like(signal)
    out[0] = (1.0 - alpha) * signal[0]
    for i in range(1, len(signal)):
        out[i] = (1.0 - alpha) * signal[i] + alpha * out[i - 1]
    return out


def one_pole_highpass(signal: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    if cutoff_hz <= 0:
        return signal.astype(np.float32)
    low = one_pole_lowpass(signal, sample_rate, cutoff_hz)
    return (signal - low).astype(np.float32)


def apply_amp_chain(
    voice: np.ndarray,
    sample_rate: int,
    gain_db: float,
    boost_db: float,
    bass_db: float,
    treble_db: float,
    distortion: float,
    high_pass_hz: float = 0.0,
    presence_db: float = 0.0,
) -> np.ndarray:
    x = voice.astype(np.float32)

    if high_pass_hz > 0:
        x = one_pole_highpass(x, sample_rate, high_pass_hz)

    x = x * db_to_linear(gain_db + boost_db)

    low = one_pole_lowpass(x, sample_rate, 220.0)
    high_base = one_pole_lowpass(x, sample_rate, 2800.0)
    high = x - high_base
    presence_base = one_pole_lowpass(x, sample_rate, 1200.0)
    presence_top = one_pole_lowpass(x, sample_rate, 3600.0)
    presence_band = presence_top - presence_base

    bass_mix = (db_to_linear(bass_db) - 1.0)
    treble_mix = (db_to_linear(treble_db) - 1.0)
    x = x + low * bass_mix + high * treble_mix
    x = x + presence_band * (db_to_linear(presence_db) - 1.0)

    drive = 1.0 + (distortion / 100.0) * 24.0
    x = np.tanh(x * drive) / np.tanh(drive)

    return np.clip(x, -1.0, 1.0)


def ensure_stereo(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=1)
    if audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1)
    return audio[:, :2]


def resample_linear(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return audio
    ratio = dst_sr / src_sr
    src_len = len(audio)
    dst_len = max(1, int(src_len * ratio))
    src_x = np.linspace(0.0, 1.0, src_len)
    dst_x = np.linspace(0.0, 1.0, dst_len)

    if audio.ndim == 1:
        return np.interp(dst_x, src_x, audio).astype(np.float32)

    channels = []
    for ch in range(audio.shape[1]):
        channels.append(np.interp(dst_x, src_x, audio[:, ch]))
    return np.stack(channels, axis=1).astype(np.float32)


def change_speed(audio: np.ndarray, speed_ratio: float) -> np.ndarray:
    if speed_ratio <= 0 or abs(speed_ratio - 1.0) < 1e-6:
        return audio

    src_len = len(audio)
    if src_len <= 1:
        return audio

    dst_len = max(1, int(src_len / speed_ratio))
    src_x = np.linspace(0.0, 1.0, src_len)
    dst_x = np.linspace(0.0, 1.0, dst_len)

    if audio.ndim == 1:
        return np.interp(dst_x, src_x, audio).astype(np.float32)

    channels = [np.interp(dst_x, src_x, audio[:, ch]) for ch in range(audio.shape[1])]
    return np.stack(channels, axis=1).astype(np.float32)


def apply_output_gain(audio: np.ndarray, gain_db: float) -> np.ndarray:
    if abs(gain_db) < 1e-6:
        return audio
    return np.clip(audio * db_to_linear(gain_db), -1.0, 1.0).astype(np.float32)


def reduce_background_noise(signal: np.ndarray, sample_rate: int, strength: float, gate_threshold_pct: float = 25.0) -> np.ndarray:
    if strength <= 0 or len(signal) == 0:
        return signal

    # İlk 0.5 saniyeyi referans alıp basit bir gürültü kapısı uygular.
    ref_frames = max(1, int(sample_rate * 0.5))
    noise_ref = signal[:ref_frames]
    noise_floor = float(np.median(np.abs(noise_ref)))
    threshold = noise_floor * (1.0 + (gate_threshold_pct / 100.0) * 8.0)
    attenuation = max(0.05, 1.0 - strength * 0.9)

    out = signal.copy()
    mask = np.abs(out) < threshold
    out[mask] *= attenuation
    return out.astype(np.float32)


def apply_compressor(signal: np.ndarray, threshold_db: float, ratio: float, makeup_db: float) -> np.ndarray:
    if len(signal) == 0:
        return signal
    x = signal.astype(np.float32).copy()
    eps = 1e-6
    magnitude = np.abs(x)
    above = magnitude > eps
    db = np.zeros_like(magnitude)
    db[above] = 20.0 * np.log10(magnitude[above])
    over_db = np.maximum(db - threshold_db, 0.0)
    compressed_db = threshold_db + over_db / max(ratio, 1.0)
    gain_reduction_db = compressed_db - db
    gain = np.ones_like(magnitude)
    gain[above] = 10 ** (gain_reduction_db[above] / 20.0)
    x *= gain
    if abs(makeup_db) > 1e-6:
        x *= db_to_linear(makeup_db)
    return np.clip(x, -1.0, 1.0).astype(np.float32)


def apply_limiter(signal: np.ndarray, ceiling: float = 0.98) -> np.ndarray:
    if len(signal) == 0:
        return signal
    return np.clip(signal, -ceiling, ceiling).astype(np.float32)


def record_input_stream(
    sample_rate: int,
    frames: int,
    channels: int = 1,
    device: Optional[int] = None,
    blocksize: int = 1024,
) -> np.ndarray:
    if frames <= 0:
        return np.zeros((0, channels), dtype=np.float32)

    chunks: list[np.ndarray] = []
    captured_frames = 0
    finished = threading.Event()
    wait_timeout = max(1.0, frames / max(sample_rate, 1) + 1.0)

    def callback(indata, _frames, _time_info, _status) -> None:
        nonlocal captured_frames
        if indata is None or len(indata) == 0:
            return
        remaining = frames - captured_frames
        if remaining <= 0:
            finished.set()
            raise sd.CallbackStop()
        chunk = np.array(indata[:remaining], dtype=np.float32, copy=True)
        chunks.append(chunk)
        captured_frames += len(chunk)
        if captured_frames >= frames:
            finished.set()
            raise sd.CallbackStop()

    with sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        blocksize=blocksize,
        device=device,
        callback=callback,
    ):
        finished.wait(wait_timeout)

    recorded = np.concatenate(chunks, axis=0) if chunks else np.zeros((0, channels), dtype=np.float32)
    if len(recorded) < frames:
        pad_shape = ((0, frames - len(recorded)), (0, 0))
        recorded = np.pad(recorded, pad_shape, mode="constant")
    return recorded[:frames].astype(np.float32)


def next_take_name(prefix: str = "quick_take") -> str:
    return next_take_name_for_dir(Path.home() / "Desktop", prefix)


def next_take_name_for_dir(directory: Path, prefix: str = "quick_take") -> str:
    for i in range(1, 10000):
        name = f"{prefix}_{i:03d}"
        if not take_name_conflicts(directory, name):
            return name
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"


def next_timestamped_take_name_for_dir(directory: Path, prefix: str = "quick_take") -> str:
    base = f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"
    if not (directory / f"{base}.mp3").exists() and not (directory / f"{base}_mix.wav").exists():
        return base
    for suffix in range(2, 100):
        candidate = f"{base}_{suffix:02d}"
        if not (directory / f"{candidate}.mp3").exists() and not (directory / f"{candidate}_mix.wav").exists():
            return candidate
    return next_take_name_for_dir(directory, prefix)


def format_mm_ss(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def configure_tcl_tk_environment() -> None:
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    roots = []
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        roots.extend(
            [
                executable.parent,
                executable.parent.parent,
                executable.parent.parent / "Resources",
                executable.parent.parent / "Resources" / "lib",
            ]
        )
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass)
            roots.extend([base, base / "tcl", base / "lib"])

    for root in roots:
        if not root.exists():
            continue
        candidates = [root, root / "tcl", root / "lib", root / "Resources", root / "Resources" / "lib"]
        for parent in candidates:
            if not parent.exists():
                continue
            tcl_dirs = sorted(parent.glob("tcl8.*"))
            tk_dirs = sorted(parent.glob("tk8.*"))
            if tcl_dirs and tk_dirs:
                os.environ.setdefault("TCL_LIBRARY", str(tcl_dirs[0]))
                os.environ.setdefault("TK_LIBRARY", str(tk_dirs[0]))
                return


def ffmpeg_binary_candidates() -> list[Path]:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        candidates.extend(
            [
                executable.parent / "ffmpeg",
                executable.parent / "bin" / "ffmpeg",
                executable.parent.parent / "Resources" / "ffmpeg",
                executable.parent.parent / "Resources" / "bin" / "ffmpeg",
            ]
        )
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass)
            candidates.extend(
                [
                    base / "ffmpeg",
                    base / "bin" / "ffmpeg",
                ]
            )
    candidates.extend(
        [
            Path("/opt/homebrew/bin/ffmpeg"),
            Path("/usr/local/bin/ffmpeg"),
            Path("/usr/bin/ffmpeg"),
        ]
    )
    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique_candidates.append(candidate)
    return unique_candidates


def resolve_ffmpeg_binary() -> Optional[str]:
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    for candidate in ffmpeg_binary_candidates():
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def safe_query_devices() -> list:
    try:
        return list(sd.query_devices())
    except Exception:
        return []


def describe_device_state() -> tuple[int, int]:
    devices = safe_query_devices()
    input_count = sum(1 for dev in devices if int(dev.get("max_input_channels", 0)) > 0)
    output_count = sum(1 for dev in devices if int(dev.get("max_output_channels", 0)) > 0)
    return input_count, output_count


def list_input_devices() -> list[tuple[int, str]]:
    devices = safe_query_devices()
    return [
        (idx, str(dev.get("name", "Bilinmeyen Aygıt")))
        for idx, dev in enumerate(devices)
        if int(dev.get("max_input_channels", 0)) > 0
    ]


def list_output_devices() -> list[tuple[int, str]]:
    devices = safe_query_devices()
    return [
        (idx, str(dev.get("name", "Bilinmeyen Aygıt")))
        for idx, dev in enumerate(devices)
        if int(dev.get("max_output_channels", 0)) > 0
    ]


def device_default_samplerate(device_idx: Optional[int], kind: str = "input") -> int:
    try:
        if device_idx is None:
            info = sd.query_devices(kind=kind)
        else:
            info = sd.query_devices(device=device_idx, kind=kind)
        samplerate = int(float(info.get("default_samplerate", 44100)))
        return samplerate if samplerate > 0 else 44100
    except Exception:
        return 44100


def no_device_help_text() -> str:
    return (
        "Ses aygıtı bulunamadı. macOS'ta Sistem Ayarları > Gizlilik ve Güvenlik > Mikrofon bölümünden "
        "Terminal veya GuitarAmpRecorder için izin verin. Harici mikrofon/ses kartı kullanıyorsanız yeniden takıp programı tekrar açın."
    )


def builtin_preset_store() -> dict:
    return {
        "selected": "Temiz Gitar",
        "favorites": [],
        "presets": {
            "Temiz Konusma": {
                "input_device_choice": "Varsayılan macOS girişi",
                "output_device_choice": "Varsayılan macOS çıkışı",
                "input_device_id": "",
                "output_device_id": "",
                "output_name": "",
                "output_dir": str(Path.home() / "Desktop"),
                "session_mode": "Tek Klasör",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yüksek VBR",
                "wav_export_mode": "Sadece Vokal WAV",
                "record_limit_hours": "1",
                "mic_record_seconds": "60",
                "gain": 4,
                "boost": 1,
                "high_pass_hz": 90,
                "bass": 1,
                "presence": 1,
                "treble": 1,
                "distortion": 0,
                "backing_level": 100,
                "vocal_level": 85,
                "noise_reduction": 10,
                "noise_gate_threshold": 8,
                "monitor_level": 100,
                "compressor_amount": 10,
                "compressor_threshold": -20,
                "compressor_makeup": 1,
                "limiter_enabled": "Açık",
                "speed_ratio": 100,
                "output_gain": -4,
            },
            "Ultra Temiz Tani": {
                "input_device_choice": "Varsayılan macOS girişi",
                "output_device_choice": "Varsayılan macOS çıkışı",
                "input_device_id": "",
                "output_device_id": "",
                "output_name": "",
                "output_dir": str(Path.home() / "Desktop"),
                "session_mode": "Tek Klasör",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yüksek VBR",
                "wav_export_mode": "Sadece Vokal WAV",
                "record_limit_hours": "1",
                "mic_record_seconds": "60",
                "gain": 2,
                "boost": 0,
                "high_pass_hz": 0,
                "bass": 0,
                "presence": 0,
                "treble": 0,
                "distortion": 0,
                "backing_level": 100,
                "vocal_level": 85,
                "noise_reduction": 0,
                "noise_gate_threshold": 0,
                "monitor_level": 100,
                "compressor_amount": 0,
                "compressor_threshold": -12,
                "compressor_makeup": 0,
                "limiter_enabled": "Açık",
                "speed_ratio": 100,
                "output_gain": -6,
            },
            "Temiz Gitar": {
                "input_device_choice": "Varsayılan macOS girişi",
                "output_device_choice": "Varsayılan macOS çıkışı",
                "input_device_id": "",
                "output_device_id": "",
                "output_name": "",
                "output_dir": str(Path.home() / "Desktop"),
                "session_mode": "Tek Klasör",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yüksek VBR",
                "wav_export_mode": "Sadece Vokal WAV",
                "record_limit_hours": "1",
                "mic_record_seconds": "60",
                "gain": 2,
                "boost": 0,
                "high_pass_hz": 60,
                "bass": 0,
                "presence": 0,
                "treble": 0,
                "distortion": 0,
                "backing_level": 100,
                "vocal_level": 85,
                "noise_reduction": 0,
                "noise_gate_threshold": 0,
                "monitor_level": 100,
                "compressor_amount": 0,
                "compressor_threshold": -12,
                "compressor_makeup": 0,
                "limiter_enabled": "Açık",
                "speed_ratio": 100,
                "output_gain": -6,
            },
            "Temiz Gitar Dengeli": {
                "input_device_choice": "Varsayılan macOS girişi",
                "output_device_choice": "Varsayılan macOS çıkışı",
                "input_device_id": "",
                "output_device_id": "",
                "output_name": "",
                "output_dir": str(Path.home() / "Desktop"),
                "session_mode": "Tek Klasör",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yüksek VBR",
                "wav_export_mode": "Sadece Vokal WAV",
                "record_limit_hours": "1",
                "mic_record_seconds": "60",
                "gain": 2,
                "boost": 0,
                "high_pass_hz": 60,
                "bass": 0,
                "presence": 0,
                "treble": 0,
                "distortion": 0,
                "backing_level": 100,
                "vocal_level": 85,
                "noise_reduction": 0,
                "noise_gate_threshold": 0,
                "monitor_level": 100,
                "compressor_amount": 0,
                "compressor_threshold": -12,
                "compressor_makeup": 0,
                "limiter_enabled": "Açık",
                "speed_ratio": 100,
                "output_gain": -6,
            },
            "MacBook Mikrofon Hizli Kayit": {
                "input_device_choice": "Varsayılan macOS girişi",
                "output_device_choice": "Varsayılan macOS çıkışı",
                "input_device_id": "",
                "output_device_id": "",
                "output_name": "",
                "output_dir": str(Path.home() / "Desktop"),
                "session_mode": "Tek Klasor",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yuksek VBR",
                "wav_export_mode": "Sadece Vocal WAV",
                "record_limit_hours": "1",
                "mic_record_seconds": "60",
                "gain": 8,
                "boost": 0,
                "high_pass_hz": 70,
                "bass": 0,
                "presence": 1,
                "treble": 1,
                "distortion": 0,
                "backing_level": 100,
                "vocal_level": 100,
                "noise_reduction": 0,
                "noise_gate_threshold": 0,
                "monitor_level": 100,
                "compressor_amount": 0,
                "compressor_threshold": -18,
                "compressor_makeup": 0,
                "limiter_enabled": "Acik",
                "speed_ratio": 100,
                "output_gain": 3,
            },
            "Guclu Performans": {
                "input_device_choice": "Varsayılan macOS girişi",
                "output_device_choice": "Varsayılan macOS çıkışı",
                "input_device_id": "",
                "output_device_id": "",
                "output_name": "",
                "output_dir": str(Path.home() / "Desktop"),
                "session_mode": "Tek Klasör",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yüksek VBR",
                "wav_export_mode": "Mix + Vokal WAV",
                "record_limit_hours": "1",
                "mic_record_seconds": "60",
                "gain": 5,
                "boost": 3,
                "high_pass_hz": 80,
                "bass": 2,
                "presence": 3,
                "treble": 3,
                "distortion": 8,
                "backing_level": 100,
                "vocal_level": 85,
                "noise_reduction": 10,
                "noise_gate_threshold": 10,
                "monitor_level": 100,
                "compressor_amount": 30,
                "compressor_threshold": -18,
                "compressor_makeup": 2,
                "limiter_enabled": "Açık",
                "speed_ratio": 100,
                "output_gain": -5,
            },
        },
    }


def merge_builtin_presets(store: dict) -> dict:
    merged = {
        "selected": str(store.get("selected", "Temiz Gitar") or "Temiz Gitar"),
        "favorites": [],
        "presets": {},
    }
    builtin = builtin_preset_store()
    builtin_names = set(builtin["presets"].keys())
    user_presets = {
        name: preset
        for name, preset in store.get("presets", {}).items()
        if name not in builtin_names
    }
    merged["presets"].update(builtin["presets"])
    merged["presets"].update(user_presets)
    raw_favorites = store.get("favorites", [])
    if isinstance(raw_favorites, list):
        merged["favorites"] = sorted(
            {
                str(name)
                for name in raw_favorites
                if isinstance(name, str) and str(name) in merged["presets"]
            }
        )
    if merged["selected"] not in merged["presets"]:
        merged["selected"] = builtin["selected"]
    return merged


class GuitarAmpRecorderApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Gitar Amfi Kaydedici")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1560, max(1280, screen_w - 60))
        height = min(980, max(760, screen_h - 90))
        x = max(18, (screen_w - width) // 2)
        y = max(20, (screen_h - height) // 2 - 12)
        self.initial_window_width = width
        self.initial_window_height = height
        self.initial_window_x = x
        self.initial_window_y = y
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(1180, 720)
        self.root.configure(bg="#101418")
        self.desktop_two_column = width >= 1180
        self.max_dashboard_width = min(1480, max(1240, width - 36))
        self.hero_wraplength = max(820, min(1280, width - 160))
        if self.desktop_two_column:
            self.section_wraplength = max(460, min(620, ((width - 110) // 2) - 70))
            self.control_length = max(460, min(620, ((width - 110) // 2) - 88))
        else:
            self.section_wraplength = max(620, min(920, width - 110))
            self.control_length = max(620, min(880, width - 140))
        self.content_wraplength = self.section_wraplength
        self.app_version = read_app_version()

        self.backing_file: Optional[Path] = None

        self.status_text = StringVar(value="Hazır")
        self.operation_state_text = StringVar(value="Durum: hazır")
        self.compact_status_text = StringVar(value="Kısa özet hazırlanıyor...")
        self.hero_summary_text = StringVar(value="Üst özet hazırlanıyor...")
        self.hero_status_card_text = StringVar(value="Kayıt özeti hazırlanıyor...")
        self.workspace_tab = StringVar(value="Kayıt")
        self.workspace_hint_text = StringVar(value="Ana kayıt akışı burada gösterilecek.")
        self.recent_output_summary_text = StringVar(value="Son çıktı özeti hazırlanıyor...")
        self.hero_output_card_text = StringVar(value="Son çıktı özeti hazırlanıyor...")
        self.recent_output_subtitle_text = StringVar(value="Son çıktı bölümü hazırlanıyor...")
        self.recent_output_filter = StringVar(value="Tümü")
        self.recent_output_meta_text = StringVar(value="Çıktı ayrıntısı hazırlanıyor...")
        self.device_summary_text = StringVar(value="Aygıt taraması bekleniyor...")
        self.setup_hint_text = StringVar(value="Mikrofon kurulumu burada gösterilecek.")
        self.setup_status_text = StringVar(value="Kurulum özeti hazırlanıyor...")
        self.hero_setup_card_text = StringVar(value="Kurulum özeti hazırlanıyor...")
        self.setup_next_text = StringVar(value="Sıradaki kurulum adımı hazırlanıyor...")
        self.merge_subtitle_text = StringVar(value="Ses ve müzik birleştirme özeti hazırlanıyor...")
        self.merge_summary_text = StringVar(value="Birleştirme kanalı burada gösterilecek.")
        self.meter_text = StringVar(value="Mikrofon seviyesi bekleniyor...")
        self.clip_text = StringVar(value="Seviye: güvenli")
        self.safety_text = StringVar(value="Durum: seviye analizi bekleniyor")
        self.selected_route_text = StringVar(value="Aktif giriş: Varsayılan macOS girişi | Aktif çıkış: Varsayılan macOS çıkışı")
        self.output_name = StringVar(value=f"guitar_mix_{time.strftime('%Y%m%d_%H%M%S')}")
        self.output_dir = StringVar(value=str(Path.home() / "Desktop"))
        self.session_mode = StringVar(value="Tek Klasör")
        self.session_name = StringVar(value=time.strftime("session_%Y%m%d"))
        self.mp3_quality = StringVar(value="Yüksek VBR")
        self.wav_export_mode = StringVar(value="Sadece Vokal WAV")
        self.preset_name = StringVar(value="Temiz Gitar")
        self.preset_note = StringVar(value="")
        self.preset_filter = StringVar(value="")
        self.preset_favorites_only = StringVar(value="kapali")
        self.preset_filter_meta_text = StringVar(value="Preset filtresi kapalı.")
        self.preset_scope_text = StringVar(value="Yerleşik preset seçili.")
        self.preset_favorite_text = StringVar(value="Favori: hayır")
        self.preset_favorite_meta_text = StringVar(value="Favori preset yok.")
        self.preset_favorite_quick_text = StringVar(value="Hızlı favori önerisi hazırlanıyor...")
        self.preset_favorite_button_text = StringVar(value="Favoriye Ekle")
        self.preset_favorites_filter_button_text = StringVar(value="Sadece Favoriler")
        self.preset_summary_text = StringVar(value="Preset özeti hazırlanıyor...")
        self.preset_note_meta_text = StringVar(value="0 karakter")
        self.share_title = StringVar(value="")
        self.share_description = StringVar(value="")
        self.share_image_path = StringVar(value="")
        self.share_meta_text = StringVar(value="Paylaşım özeti hazırlanıyor...")
        self.share_status_text = StringVar(value="Durum: paylaşım hazırlanıyor...")
        self.share_detail_text = StringVar(value="Detay: paylaşım bilgisi hazırlanıyor...")
        self.share_quickstart_text = StringVar(value="Hızlı durum: paylaşım hazırlanıyor...")
        self.share_quick_audio_text = StringVar(value="Ses bekliyor")
        self.share_quick_cover_text = StringVar(value="Kapak bekliyor")
        self.share_quick_package_text = StringVar(value="Paket yok")
        self.share_quick_zip_text = StringVar(value="ZIP yok")
        self.share_ready_text = StringVar(value="Hazırlık sürüyor")
        self.share_next_step_text = StringVar(value="Öneri: Son kaydı seçip paylaşım akışını başlatın.")
        self.share_next_step_button_text = StringVar(value="Sonraki Adımı Uygula")
        self.limiter_enabled = StringVar(value="Açık")
        self.record_progress_text = StringVar(value="Kayıt durumu: beklemede")
        self.progress_subtitle_text = StringVar(value="Kayıt durumu hazırlanıyor...")
        self.input_device_id = StringVar(value="")
        self.output_device_id = StringVar(value="")
        self.input_device_choice = StringVar(value="Varsayılan macOS girişi")
        self.output_device_choice = StringVar(value="Varsayılan macOS çıkışı")
        self.record_limit_hours = StringVar(value="1")
        self.mic_record_seconds = StringVar(value="60")
        self.monitor_status_text = StringVar(value="Canlı monitor kapalı")
        self.quick_control_text = StringVar(value="Hızlı kontrol özeti hazırlanıyor...")
        self.readiness_text = StringVar(value="Hazırlık durumu hesaplanıyor...")
        self.readiness_subtitle_text = StringVar(value="Hazırlık özeti hazırlanıyor...")
        self.next_step_subtitle_text = StringVar(value="Sonraki adım özeti hazırlanıyor...")
        self.action_guidance_text = StringVar(value="İşlem önerisi hazırlanıyor...")
        self.action_subtitle_text = StringVar(value="İşlem akışı hazırlanıyor...")
        self.preflight_warning_text = StringVar(value="Ön kontrol hazırlanıyor...")
        self.preflight_subtitle_text = StringVar(value="Ön kontrol özeti hazırlanıyor...")
        self.prep_summary_text = StringVar(value="Kayıt planı hazırlanıyor...")
        self.prep_subtitle_text = StringVar(value="Kayıt planı özeti hazırlanıyor...")
        self.prep_status_text = StringVar(value="Hazırlık durumu hazırlanıyor...")
        self.prep_meta_text = StringVar(value="Hazırlık dosyası bilgisi hazırlanıyor...")
        self.next_step_text = StringVar(value="Hazırlık kontrol ediliyor...")
        self.option_summary_text = StringVar(value="Seçenek açıklamaları hazırlanıyor...")
        self.option_subtitle_text = StringVar(value="Seçenek özeti hazırlanıyor...")
        self.source_subtitle_text = StringVar(value="Kayıt kaynağı hazırlanıyor...")
        self.mp3_quality_label_text = StringVar(value="MP3 Kalitesi")
        self.output_name_label_text = StringVar(value="Çıkış Dosya Adı")
        self.output_subtitle_text = StringVar(value="Çıktı hedefi hazırlanıyor...")
        self.tone_subtitle_text = StringVar(value="Ton özeti hazırlanıyor...")
        self.mix_subtitle_text = StringVar(value="Mix özeti hazırlanıyor...")
        self.advanced_audio_button_text = StringVar(value="Ton ve Mix Ayarlarını Göster")
        self.meter_level = 0.0
        self.meter_peak_level = 0.0
        self.last_input_peak = 0.0
        self.meter_peak_hold_until = 0.0
        self.meter_clipping_until = 0.0
        self.meter_stream: Optional[sd.InputStream] = None
        self.monitor_stream: Optional[sd.Stream] = None
        self.meter_error_message = ""
        self.recording_active = False
        self.recording_started_at = 0.0
        self.recording_target_seconds = 0.0
        self.recording_mode = ""
        self.stop_recording_requested = False
        self.current_input_device_count = 0
        self.current_output_device_count = 0
        self.last_output_dir: Optional[Path] = None
        self.last_export_path: Optional[Path] = None
        self.last_summary_path: Optional[Path] = None
        self.last_take_notes_path: Optional[Path] = None
        self.last_recovery_note_path: Optional[Path] = None
        self.last_preparation_summary_path: Optional[Path] = None
        self.last_share_package_dir: Optional[Path] = None
        self.share_window = None
        self.recent_exports_text = StringVar(value="Henüz çıktı yok.")
        self.preset_names = ["Temiz Gitar"]
        self.input_device_options = ["Varsayılan macOS girişi"]
        self.output_device_options = ["Varsayılan macOS çıkışı"]

        # Ekranı aşan pencerelerde alttaki butonlar kaybolmasın diye ana içeriği kaydırılabilir tut.
        self.canvas = Canvas(root, highlightthickness=0, bg="#101418")
        self.scrollbar = Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.content = Frame(self.canvas, bg="#101418")
        self.content.bind("<Configure>", self._on_content_configure)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas_window = self.canvas.create_window((width / 2, 0), window=self.content, anchor="n")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.root.after(120, self.ensure_desktop_geometry)

        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind_all(sequence, self._on_mousewheel, add="+")

        hero = self.create_section(padx=18, pady=(18, 12), bg="#182028", border="#293543")
        Label(
            hero,
            text="Gitar Amfi Kaydedici",
            bg="#182028",
            fg="#f4f7fb",
            font=("Helvetica", 18, "bold"),
        ).pack(anchor="w", padx=14, pady=(14, 4))
        Label(
            hero,
            text="Önce testi alın, sonra kaydı başlatın. Aygıt kimliği bilmiyorsanız boş bırakın.",
            bg="#182028",
            fg="#c7d2de",
            justify="left",
            wraplength=self.hero_wraplength,
        ).pack(anchor="w", padx=14, pady=(0, 14))
        Label(
            hero,
            text=f"Sürüm {self.app_version} | Kayıt, dışa aktarım ve oturum takibi",
            bg="#182028",
            fg="#9fb0c2",
            justify="left",
            wraplength=self.hero_wraplength,
        ).pack(anchor="w", padx=14, pady=(0, 8))
        Label(
            hero,
            text="Hazır Akış  Tara -> Test -> Kaydet -> Dışa Aktar",
            bg="#233142",
            fg="#d7eefb",
            font=("Helvetica", 10, "bold"),
            padx=10,
            pady=4,
        ).pack(anchor="w", padx=14, pady=(0, 8))
        hero_toolbar = Frame(hero, bg="#16212b", highlightbackground="#2a3644", highlightthickness=1)
        hero_toolbar.pack(fill="x", padx=14, pady=(0, 10))
        hero_actions = Frame(hero_toolbar, bg="#16212b")
        hero_actions.pack(side="left", padx=10, pady=8)
        self.hero_scan_button = self.create_click_chip(hero_actions, "Aygıtları Tara", self.inspect_devices, role="primary")
        self.hero_scan_button.pack(side="left")
        self.hero_fill_button = self.create_click_chip(hero_actions, "Önerilenleri Doldur", self.fill_recommended_devices, role="success")
        self.hero_fill_button.pack(side="left", padx=(8, 0))
        self.hero_test_button = self.create_click_chip(hero_actions, "5 sn Test", self.start_test_thread, role="secondary")
        self.hero_test_button.pack(side="left", padx=(8, 0))
        self.hero_backing_button = self.create_click_chip(hero_actions, "Müzik Seç", self.select_backing, role="accent")
        self.hero_backing_button.pack(side="left", padx=(8, 0))
        self.about_button = self.create_click_chip(hero_actions, "Hakkında", self.show_about, role="secondary")
        self.about_button.pack(side="left", padx=(8, 0))
        self.operation_state_label = Label(
            hero_toolbar,
            textvariable=self.operation_state_text,
            bg="#203041",
            fg="#d7eefb",
            justify="left",
            wraplength=self.hero_wraplength,
            padx=10,
            pady=6,
            highlightbackground="#2f81f7",
            highlightthickness=1,
        )
        self.operation_state_label.pack(side="right", padx=10, pady=8)

        self.hero_summary_label = Label(
            self.content,
            textvariable=self.hero_summary_text,
            bg="#16212b",
            fg="#dfe9f5",
            justify="left",
            anchor="w",
            wraplength=self.section_wraplength,
            padx=14,
            pady=8,
            highlightbackground="#2a3644",
            highlightthickness=1,
        )
        self.hero_summary_label.pack(fill="x", padx=18, pady=(0, 8))

        self.workspace_navbar = Frame(self.content, bg="#141c25", highlightbackground="#2a3644", highlightthickness=1)
        self.workspace_navbar.pack(fill="x", padx=18, pady=(0, 6))
        Label(
            self.workspace_navbar,
            text="Bölümler",
            bg="#141c25",
            fg="#9fb0c2",
            font=("Helvetica", 9, "bold"),
        ).pack(anchor="w", padx=12, pady=(8, 4))
        self.workspace_tabs = Frame(self.workspace_navbar, bg="#141c25")
        self.workspace_tabs.pack(fill="x", padx=10, pady=(0, 4))
        self.record_tab_button = Label(self.workspace_tabs, text="Kayıt")
        self.setup_tab_button = Label(self.workspace_tabs, text="Kurulum")
        self.music_tab_button = Label(self.workspace_tabs, text="Müzik")
        self.merge_tab_button = Label(self.workspace_tabs, text="Birleştirme")
        self.settings_tab_button = Label(self.workspace_tabs, text="Ayarlar")
        self.audio_tab_button = Label(self.workspace_tabs, text="Ses Düzenleme")
        self.outputs_tab_button = Label(self.workspace_tabs, text="Son Çıktılar")
        for label, tab_name in (
            (self.record_tab_button, "Kayıt"),
            (self.setup_tab_button, "Kurulum"),
            (self.music_tab_button, "Müzik"),
            (self.merge_tab_button, "Birleştirme"),
            (self.settings_tab_button, "Ayarlar"),
            (self.audio_tab_button, "Ses Düzenleme"),
            (self.outputs_tab_button, "Son Çıktılar"),
        ):
            label.bind("<Button-1>", lambda _event, target=tab_name: self.set_workspace_tab(target))
            self.apply_nav_chip_style(label, active=(tab_name == "Kayıt"))
        self.layout_button_flow(
            self.workspace_tabs,
            [
                self.record_tab_button,
                self.setup_tab_button,
                self.music_tab_button,
                self.merge_tab_button,
                self.settings_tab_button,
                self.audio_tab_button,
                self.outputs_tab_button,
            ],
            columns=7,
        )
        self.workspace_hint_label = Label(
            self.workspace_navbar,
            textvariable=self.workspace_hint_text,
            bg="#141c25",
            fg="#9fb0c2",
            justify="left",
            anchor="w",
            font=("Helvetica", 10),
            wraplength=self.section_wraplength,
        )
        self.workspace_hint_label.pack(fill="x", padx=12, pady=(0, 8))

        self.workspace_body = Frame(self.content, bg="#101418")
        self.workspace_body.pack(fill="x", padx=18, pady=(0, 12))

        self.record_tab = Frame(self.workspace_body, bg="#101418")
        self.setup_tab = Frame(self.workspace_body, bg="#101418")
        self.music_tab = Frame(self.workspace_body, bg="#101418")
        self.merge_tab = Frame(self.workspace_body, bg="#101418")
        self.settings_tab = Frame(self.workspace_body, bg="#101418")
        self.audio_tab = Frame(self.workspace_body, bg="#101418")
        self.outputs_tab = Frame(self.workspace_body, bg="#101418")

        self.record_columns = Frame(self.record_tab, bg="#101418")
        self.record_columns.pack(fill="x")
        self.record_left_column = Frame(self.record_columns, bg="#101418")
        self.record_left_column.pack(fill="x")

        self.setup_column = Frame(self.setup_tab, bg="#101418")
        self.setup_column.pack(fill="x")

        self.music_column = Frame(self.music_tab, bg="#101418")
        self.music_column.pack(fill="x")

        self.merge_column = Frame(self.merge_tab, bg="#101418")
        self.merge_column.pack(fill="x")

        self.settings_column = Frame(self.settings_tab, bg="#101418")
        self.settings_column.pack(fill="x")

        self.audio_column = Frame(self.audio_tab, bg="#101418")
        self.audio_column.pack(fill="x")

        self.outputs_column = Frame(self.outputs_tab, bg="#101418")
        self.outputs_column.pack(fill="x")

        focus_box = self.create_section(parent=self.record_left_column, title="Hızlı Kontrol", subtitle="Tek kartta kayıt öncesi genel durum.")
        self.quick_control_label = Label(
            focus_box,
            textvariable=self.quick_control_text,
            **self.summary_card_style("#1b2029", "#dce6ef"),
            anchor="w",
        )
        self.quick_control_label.pack(fill="x", padx=14, pady=(10, 12))

        setup = self.create_section(parent=self.setup_column, title="Mikrofon Kurulumu", subtitlevariable=self.setup_hint_text)
        self.setup_status_label = Label(
            setup,
            textvariable=self.setup_status_text,
            **self.summary_card_style("#11202d", "#d7eefb"),
        )
        self.setup_status_label.pack(fill="x", padx=14, pady=(12, 0))
        self.setup_next_label = Label(
            setup,
            textvariable=self.setup_next_text,
            **self.summary_card_style("#1e252d", "#e4edf5"),
        )
        self.setup_next_label.pack(fill="x", padx=14, pady=(10, 0))
        Label(
            setup,
            text="1. Tara   2. Seç   3. Test Et",
            bg="#151b22",
            fg="#7dd3fc",
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 0))
        Label(
            setup,
            text="Bulunan Aygıtlar",
            bg="#151b22",
            fg="#f4f7fb",
            font=("Helvetica", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(12, 4))
        self.device_summary_label = Label(
            setup,
            textvariable=self.device_summary_text,
            bg="#0f141a",
            fg="#dce6ef",
            justify="left",
            wraplength=self.section_wraplength,
            padx=10,
            pady=10,
        )
        self.device_summary_label.pack(fill="x", padx=14, pady=(0, 10))

        self.selected_route_label = Label(
            setup,
            textvariable=self.selected_route_text,
            bg="#11202d",
            fg="#d7eefb",
            justify="left",
            wraplength=self.section_wraplength,
            padx=10,
            pady=8,
        )
        self.selected_route_label.pack(fill="x", padx=14, pady=(0, 10))

        device_form = Frame(setup, bg="#151b22")
        device_form.pack(fill="x", padx=14, pady=(0, 8))
        device_form.grid_columnconfigure(0, weight=1)
        device_form.grid_columnconfigure(1, weight=1)
        Label(device_form, text="Mikrofonu Listeden Seç", bg="#151b22", fg="#dce6ef").grid(row=0, column=0, sticky="w")
        self.input_device_menu = OptionMenu(device_form, self.input_device_choice, *self.input_device_options)
        self.input_device_menu.configure(width=24, bg="#24303c", fg="white", highlightthickness=0)
        self.input_device_menu.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        Label(device_form, text="Çıkışı Listeden Seç", bg="#151b22", fg="#dce6ef").grid(row=0, column=1, sticky="w", padx=(18, 0))
        self.output_device_menu = OptionMenu(device_form, self.output_device_choice, *self.output_device_options)
        self.output_device_menu.configure(width=24, bg="#24303c", fg="white", highlightthickness=0)
        self.output_device_menu.grid(row=1, column=1, sticky="ew", padx=(18, 0), pady=(2, 8))
        Label(device_form, text="Mikrofon Aygıt Kimliği", bg="#151b22", fg="#dce6ef").grid(row=2, column=0, sticky="w")
        Entry(device_form, textvariable=self.input_device_id, width=12).grid(row=3, column=0, sticky="ew", pady=(2, 8))
        Label(device_form, text="Çıkış Aygıt Kimliği", bg="#151b22", fg="#dce6ef").grid(row=2, column=1, sticky="w", padx=(18, 0))
        Entry(device_form, textvariable=self.output_device_id, width=12).grid(row=3, column=1, sticky="ew", padx=(18, 0), pady=(2, 8))
        Label(
            device_form,
            text="Önce listeden seçin. Gerekirse kimlik alanlarını manuel kullanın.",
            bg="#151b22",
            fg="#9fb0c2",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 4))

        button_row = Frame(setup, bg="#151b22")
        button_row.pack(fill="x", padx=14, pady=(0, 12))
        self.scan_devices_button = Button(button_row, text="Mikrofonları Yeniden Tara", command=self.inspect_devices, bg="#34495e", fg="white")
        self.fill_devices_button = Button(
            button_row, text="Önerilen Aygıtları Doldur", command=self.fill_recommended_devices, bg="#1f6feb", fg="white"
        )
        self.clean_macbook_button = Button(
            button_row, text="Temiz MacBook Preset", command=self.apply_clean_macbook_preset, bg="#2d7d46", fg="white"
        )
        self.external_mic_button = Button(
            button_row, text="Harici Mikrofon Preset", command=self.apply_external_mic_preset, bg="#8e44ad", fg="white"
        )
        self.reset_devices_button = Button(button_row, text="Varsayılana Dön", command=self.clear_device_selection, bg="#5d6d7e", fg="white")
        self.apply_button_style(self.scan_devices_button, role="secondary")
        self.apply_button_style(self.fill_devices_button, role="primary")
        self.apply_button_style(self.clean_macbook_button, role="success")
        self.apply_button_style(self.external_mic_button, role="accent")
        self.apply_button_style(self.reset_devices_button, role="secondary")
        self.layout_button_flow(
            button_row,
            [
                self.scan_devices_button,
                self.fill_devices_button,
                self.clean_macbook_button,
                self.external_mic_button,
                self.reset_devices_button,
            ],
            columns=3,
        )

        preset_row = Frame(setup, bg="#151b22")
        preset_row.pack(fill="x", padx=14, pady=(0, 12))
        preset_row.grid_columnconfigure(0, weight=1)
        preset_row.grid_columnconfigure(1, weight=1)
        Label(preset_row, text="Preset Adı", bg="#151b22", fg="#dce6ef").grid(row=0, column=0, sticky="w")
        Entry(preset_row, textvariable=self.preset_name, width=18).grid(row=1, column=0, sticky="ew", pady=(2, 8))
        Label(preset_row, text="Kayıtlı Presetler", bg="#151b22", fg="#dce6ef").grid(row=0, column=1, sticky="w", padx=(18, 0))
        self.preset_menu = OptionMenu(preset_row, self.preset_name, *self.preset_names)
        self.preset_menu.configure(width=20, bg="#24303c", fg="white", highlightthickness=0)
        self.preset_menu.grid(row=1, column=1, sticky="ew", padx=(18, 0), pady=(2, 8))
        self.save_preset_button = Button(preset_row, text="Preset Kaydet", command=self.save_current_preset, bg="#16a085", fg="white")
        self.save_preset_button.grid(row=1, column=2, sticky="w", padx=(18, 0))
        self.apply_button_style(self.save_preset_button, role="success")
        self.load_preset_button = Button(preset_row, text="Preset Yükle", command=self.load_saved_preset, bg="#2980b9", fg="white")
        self.load_preset_button.grid(row=1, column=3, sticky="w", padx=(8, 0))
        self.apply_button_style(self.load_preset_button, role="primary")
        self.duplicate_preset_button = Button(
            preset_row,
            text="Preset Çoğalt",
            command=self.duplicate_selected_preset,
            bg="#8e44ad",
            fg="white",
        )
        self.duplicate_preset_button.grid(row=1, column=4, sticky="w", padx=(8, 0))
        self.apply_button_style(self.duplicate_preset_button, role="accent")
        self.favorite_preset_button = Button(
            preset_row,
            textvariable=self.preset_favorite_button_text,
            command=self.toggle_selected_preset_favorite,
            bg="#d4a017",
            fg="white",
        )
        self.favorite_preset_button.grid(row=1, column=5, sticky="w", padx=(8, 0))
        self.apply_button_style(self.favorite_preset_button, role="warning")
        self.export_preset_button = Button(
            preset_row,
            text="Preset JSON Yaz",
            command=self.export_selected_preset_json,
            bg="#5b6ee1",
            fg="white",
        )
        self.export_preset_button.grid(row=1, column=6, sticky="w", padx=(8, 0))
        self.apply_button_style(self.export_preset_button, role="accent")
        self.export_favorites_button = Button(
            preset_row,
            text="Favori JSON Yaz",
            command=self.export_favorite_presets_json,
            bg="#7c5cff",
            fg="white",
        )
        self.export_favorites_button.grid(row=1, column=7, sticky="w", padx=(8, 0))
        self.apply_button_style(self.export_favorites_button, role="accent")
        self.copy_favorites_button = Button(
            preset_row,
            text="Favorileri Kopyala",
            command=self.copy_favorite_presets_to_clipboard,
            bg="#5d6d7e",
            fg="white",
        )
        self.copy_favorites_button.grid(row=1, column=8, sticky="w", padx=(8, 0))
        self.apply_button_style(self.copy_favorites_button, role="secondary")
        self.import_favorites_button = Button(
            preset_row,
            text="Favori JSON Aç",
            command=self.import_favorite_presets_json,
            bg="#6c63ff",
            fg="white",
        )
        self.import_favorites_button.grid(row=1, column=9, sticky="w", padx=(8, 0))
        self.apply_button_style(self.import_favorites_button, role="primary")
        self.import_preset_button = Button(
            preset_row,
            text="Preset JSON Aç",
            command=self.import_preset_json,
            bg="#4b7bec",
            fg="white",
        )
        self.import_preset_button.grid(row=1, column=10, sticky="w", padx=(8, 0))
        self.apply_button_style(self.import_preset_button, role="primary")
        self.delete_preset_button = Button(preset_row, text="Preset Sil", command=self.delete_selected_preset, bg="#c0392b", fg="white")
        self.delete_preset_button.grid(row=1, column=11, sticky="w", padx=(8, 0))
        self.apply_button_style(self.delete_preset_button, role="danger")
        self.reload_session_button = Button(preset_row, text="Son Oturumu Yükle", command=self.reload_last_session, bg="#6c5ce7", fg="white")
        self.reload_session_button.grid(row=1, column=12, sticky="w", padx=(8, 0))
        self.apply_button_style(self.reload_session_button, role="accent")
        Label(preset_row, text="Preset Filtresi", bg="#151b22", fg="#dce6ef").grid(row=2, column=0, sticky="w", pady=(0, 0))
        Entry(preset_row, textvariable=self.preset_filter, width=18).grid(row=3, column=0, sticky="ew", pady=(2, 0))
        self.apply_preset_filter_button = Button(
            preset_row,
            text="Filtreyi Uygula",
            command=self.apply_preset_filter,
            bg="#34495e",
            fg="white",
        )
        self.apply_preset_filter_button.grid(row=3, column=1, sticky="w", padx=(18, 0))
        self.apply_button_style(self.apply_preset_filter_button, role="secondary")
        self.clear_preset_filter_button = Button(
            preset_row,
            text="Filtreyi Temizle",
            command=self.clear_preset_filter,
            bg="#5d6d7e",
            fg="white",
        )
        self.clear_preset_filter_button.grid(row=3, column=2, sticky="w", padx=(8, 0))
        self.apply_button_style(self.clear_preset_filter_button, role="secondary")
        self.toggle_preset_favorites_filter_button = Button(
            preset_row,
            textvariable=self.preset_favorites_filter_button_text,
            command=self.toggle_preset_favorites_filter,
            bg="#d4a017",
            fg="white",
        )
        self.toggle_preset_favorites_filter_button.grid(row=3, column=3, sticky="w", padx=(8, 0))
        self.apply_button_style(self.toggle_preset_favorites_filter_button, role="warning")
        Label(preset_row, textvariable=self.preset_filter_meta_text, bg="#151b22", fg="#9fb0c2", justify="left").grid(
            row=4, column=0, columnspan=9, sticky="w", pady=(6, 0)
        )
        Label(preset_row, text="Preset Notu", bg="#151b22", fg="#dce6ef").grid(row=5, column=0, sticky="w", pady=(4, 0))
        Entry(preset_row, textvariable=self.preset_note, width=24).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        Label(preset_row, textvariable=self.preset_note_meta_text, bg="#151b22", fg="#9fb0c2", justify="left").grid(
            row=7, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )
        self.preset_note_speech_button = Button(
            preset_row,
            text="Konuşma",
            command=lambda: self.apply_preset_note_template("Konuşma için net preset"),
            bg="#34495e",
            fg="white",
        )
        self.preset_note_speech_button.grid(row=6, column=2, sticky="w", padx=(8, 0))
        self.apply_button_style(self.preset_note_speech_button, role="secondary")
        self.preset_note_live_button = Button(
            preset_row,
            text="Canlı",
            command=lambda: self.apply_preset_note_template("Canlı performans için hazır"),
            bg="#16a085",
            fg="white",
        )
        self.preset_note_live_button.grid(row=6, column=3, sticky="w", padx=(8, 0))
        self.apply_button_style(self.preset_note_live_button, role="success")
        self.preset_note_night_button = Button(
            preset_row,
            text="Gece",
            command=lambda: self.apply_preset_note_template("Gece sessiz kayıt için uygun"),
            bg="#5d6d7e",
            fg="white",
        )
        self.preset_note_night_button.grid(row=6, column=4, sticky="w", padx=(8, 0))
        self.apply_button_style(self.preset_note_night_button, role="secondary")
        self.preset_note_clean_button = Button(
            preset_row,
            text="Temiz Gitar",
            command=lambda: self.apply_preset_note_template("Temiz gitar tonu için dengeli"),
            bg="#2d7d46",
            fg="white",
        )
        self.preset_note_clean_button.grid(row=6, column=5, sticky="w", padx=(8, 0))
        self.apply_button_style(self.preset_note_clean_button, role="success")
        self.clear_preset_note_button = Button(
            preset_row,
            text="Notu Temizle",
            command=self.clear_preset_note,
            bg="#7f8c8d",
            fg="white",
        )
        self.clear_preset_note_button.grid(row=6, column=6, sticky="w", padx=(8, 0))
        self.apply_button_style(self.clear_preset_note_button, role="secondary")
        self.copy_quick_favorites_button = Button(
            preset_row,
            text="Favori Özetini Kopyala",
            command=self.copy_quick_favorites_to_clipboard,
            bg="#6c5ce7",
            fg="white",
        )
        self.copy_quick_favorites_button.grid(row=6, column=7, sticky="w", padx=(8, 0))
        self.apply_button_style(self.copy_quick_favorites_button, role="accent")
        self.export_quick_favorites_button = Button(
            preset_row,
            text="Favori Özetini Yaz",
            command=self.export_quick_favorites_summary,
            bg="#2d7d46",
            fg="white",
        )
        self.export_quick_favorites_button.grid(row=6, column=8, sticky="w", padx=(8, 0))
        self.apply_button_style(self.export_quick_favorites_button, role="success")
        self.export_quick_favorites_markdown_button = Button(
            preset_row,
            text="Favori Özeti MD",
            command=self.export_quick_favorites_markdown,
            bg="#34495e",
            fg="white",
        )
        self.export_quick_favorites_markdown_button.grid(row=6, column=9, sticky="w", padx=(8, 0))
        self.apply_button_style(self.export_quick_favorites_markdown_button, role="secondary")
        self.open_quick_favorites_button = Button(
            preset_row,
            text="Favori Özetini Aç",
            command=self.open_quick_favorites_summary_in_finder,
            bg="#1f6feb",
            fg="white",
        )
        self.open_quick_favorites_button.grid(row=6, column=10, sticky="w", padx=(8, 0))
        self.apply_button_style(self.open_quick_favorites_button, role="primary")
        Label(preset_row, textvariable=self.preset_scope_text, bg="#151b22", fg="#9fb0c2", justify="left").grid(
            row=8, column=0, columnspan=10, sticky="w", pady=(4, 0)
        )
        Label(preset_row, textvariable=self.preset_favorite_text, bg="#151b22", fg="#9fb0c2", justify="left").grid(
            row=9, column=0, columnspan=10, sticky="w", pady=(4, 0)
        )
        Label(preset_row, textvariable=self.preset_favorite_meta_text, bg="#151b22", fg="#9fb0c2", justify="left").grid(
            row=10, column=0, columnspan=10, sticky="w", pady=(4, 0)
        )
        Label(preset_row, textvariable=self.preset_favorite_quick_text, bg="#151b22", fg="#9fb0c2", justify="left").grid(
            row=11, column=0, columnspan=10, sticky="w", pady=(4, 0)
        )
        Label(preset_row, textvariable=self.preset_summary_text, bg="#151b22", fg="#9fb0c2", justify="left").grid(
            row=12, column=0, columnspan=10, sticky="w", pady=(4, 0)
        )

        Label(setup, text="Canlı Mikrofon Seviyesi", bg="#151b22", fg="#f4f7fb", font=("Helvetica", 12, "bold")).pack(
            anchor="w", padx=14, pady=(0, 4)
        )
        self.meter_canvas = Canvas(setup, width=self.control_length, height=24, bg="#0f141a", highlightthickness=0)
        self.meter_canvas.pack(fill="x", padx=14, pady=(0, 6))
        self.meter_fill = self.meter_canvas.create_rectangle(0, 0, 0, 24, fill="#27ae60", width=0)
        self.meter_peak_marker = self.meter_canvas.create_rectangle(0, 0, 0, 24, fill="#f4f7fb", width=0)
        self.meter_label = Label(setup, textvariable=self.meter_text, bg="#151b22", fg="#9fb0c2", justify="left")
        self.meter_label.pack(anchor="w", padx=14, pady=(0, 8))
        self.clip_label = Label(setup, textvariable=self.clip_text, bg="#151b22", fg="#7ee787", justify="left")
        self.clip_label.pack(anchor="w", padx=14, pady=(0, 8))
        self.safety_label = Label(setup, textvariable=self.safety_text, bg="#151b22", fg="#9fb0c2", justify="left")
        self.safety_label.pack(anchor="w", padx=14, pady=(0, 8))

        meter_buttons = Frame(setup, bg="#151b22")
        meter_buttons.pack(fill="x", padx=14, pady=(0, 12))
        self.start_meter_button = Button(meter_buttons, text="Meter Başlat", command=self.start_input_meter, bg="#2d7d46", fg="white")
        self.apply_button_style(self.start_meter_button, role="success")
        self.stop_meter_button = Button(meter_buttons, text="Meter Durdur", command=self.stop_input_meter, bg="#7f8c8d", fg="white")
        self.apply_button_style(self.stop_meter_button, role="secondary")
        self.open_monitor_button = Button(meter_buttons, text="İzleme Aç", command=self.start_live_monitor, bg="#16a085", fg="white")
        self.apply_button_style(self.open_monitor_button, role="success")
        self.close_monitor_button = Button(meter_buttons, text="İzleme Kapat", command=self.stop_live_monitor, bg="#8e44ad", fg="white")
        self.apply_button_style(self.close_monitor_button, role="accent")
        self.layout_button_flow(
            meter_buttons,
            [
                self.start_meter_button,
                self.stop_meter_button,
                self.open_monitor_button,
                self.close_monitor_button,
            ],
            columns=2,
        )
        Label(setup, textvariable=self.monitor_status_text, bg="#151b22", fg="#9fb0c2", justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        media = self.create_section(parent=self.music_column, title="Kayıt Kaynağı", subtitlevariable=self.source_subtitle_text)
        Label(media, text="Arka Plan Müzik", bg="#151b22", fg="#f4f7fb", font=("Helvetica", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        self.backing_label = Label(media, text="Dosya seçilmedi", fg="#9aa7b5", bg="#151b22")
        self.backing_label.pack(anchor="w", padx=14)
        media_buttons = Frame(media, bg="#151b22")
        media_buttons.pack(fill="x", padx=14, pady=10)
        self.select_backing_button = Button(media_buttons, text="Müzik Dosyası Seç", command=self.select_backing, bg="#2d7d46", fg="white")
        self.apply_button_style(self.select_backing_button, role="success")
        self.clear_backing_button = Button(media_buttons, text="Sadece Mikrofon Modu", command=self.clear_backing_selection, bg="#5d6d7e", fg="white")
        self.apply_button_style(self.clear_backing_button, role="secondary")
        self.layout_button_flow(
            media_buttons,
            [
                self.select_backing_button,
                self.clear_backing_button,
            ],
            columns=2,
        )

        merge_box = self.create_section(parent=self.merge_column, title="Birleştirme Kanalı", subtitlevariable=self.merge_subtitle_text)
        self.merge_summary_label = Label(
            merge_box,
            textvariable=self.merge_summary_text,
            **self.summary_card_style("#1e252d", "#e4edf5"),
        )
        self.merge_summary_label.pack(fill="x", padx=14, pady=(10, 10))

        export = self.create_section(parent=self.settings_column, title="Çıktı", subtitlevariable=self.output_subtitle_text)
        Label(export, text="Çıkış Klasörü", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(12, 2))
        Entry(export, textvariable=self.output_dir, width=48).pack(fill="x", padx=14)
        self.select_output_dir_button = Button(export, text="Klasör Seç", command=self.select_output_dir, bg="#34495e", fg="white")
        self.select_output_dir_button.pack(anchor="w", padx=14, pady=(8, 10))
        self.apply_button_style(self.select_output_dir_button, role="secondary")
        Label(export, text="Oturum Modu", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(8, 2))
        session_mode_menu = OptionMenu(export, self.session_mode, "Tek Klasör", "Tarihli Oturum", "İsimli Oturum")
        session_mode_menu.pack(anchor="w", padx=14)
        Label(export, text="Oturum Adı", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(8, 2))
        Entry(export, textvariable=self.session_name, width=32).pack(fill="x", padx=14)
        Label(export, textvariable=self.output_name_label_text, bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(12, 2))
        Entry(export, textvariable=self.output_name, width=48).pack(fill="x", padx=14)
        Label(export, textvariable=self.mp3_quality_label_text, bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        self.mp3_quality_menu = OptionMenu(export, self.mp3_quality, "Yüksek VBR", "320 kbps", "192 kbps", "128 kbps")
        self.mp3_quality_menu.pack(anchor="w", padx=14)
        Label(export, text="WAV Çıkışı", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        wav_export_menu = OptionMenu(export, self.wav_export_mode, "Sadece Vokal WAV", "Mix + Vokal WAV", "Sadece WAV (Mix + Vokal)")
        wav_export_menu.pack(anchor="w", padx=14)
        Label(export, text="Sadece Mikrofon Süresi (sn)", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        Entry(export, textvariable=self.mic_record_seconds, width=12).pack(anchor="w", padx=14)
        Label(export, text="Kayıt Sınırı (saat)", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        limit_menu = OptionMenu(export, self.record_limit_hours, "1", "2")
        limit_menu.pack(anchor="w", padx=14, pady=(0, 12))

        prep_box = self.create_section(parent=self.settings_column, title="Kayıt Planı", subtitlevariable=self.prep_subtitle_text)
        self.prep_summary_label = Label(
            prep_box,
            textvariable=self.prep_summary_text,
            **self.summary_card_style("#11202d", "#d7eefb"),
        )
        self.prep_summary_label.pack(fill="x", padx=14, pady=(10, 10))
        self.prep_status_label = Label(
            prep_box,
            textvariable=self.prep_status_text,
            bg="#1b2430",
            fg="#d7eefb",
            anchor="w",
            padx=10,
            pady=6,
        )
        self.prep_status_label.pack(fill="x", padx=14, pady=(0, 10))
        self.prep_meta_label = Label(
            prep_box,
            textvariable=self.prep_meta_text,
            bg="#151b22",
            fg="#9fb0c2",
            justify="left",
            anchor="w",
            wraplength=460,
        )
        self.prep_meta_label.pack(fill="x", padx=14, pady=(0, 10))
        prep_buttons = Frame(prep_box, bg="#151b22")
        prep_buttons.pack(fill="x", padx=14, pady=(0, 12))
        self.copy_preparation_button = Button(prep_buttons, text="Hazırlığı Kopyala", command=self.copy_current_preparation_to_clipboard, bg="#34495e", fg="white")
        self.apply_button_style(self.copy_preparation_button, role="secondary")
        self.export_preparation_button = Button(prep_buttons, text="Hazırlığı Dosyaya Yaz", command=self.export_current_preparation_file, bg="#2d7d46", fg="white")
        self.apply_button_style(self.export_preparation_button, role="success")
        self.open_preparation_button = Button(prep_buttons, text="Hazırlık Dosyasını Aç", command=self.open_preparation_summary_in_finder, bg="#1f6feb", fg="white")
        self.apply_button_style(self.open_preparation_button, role="primary")
        self.copy_preparation_path_button = Button(
            prep_buttons,
            text="Hazırlık Yolunu Kopyala",
            command=self.copy_preparation_summary_path_to_clipboard,
            bg="#6c5ce7",
            fg="white",
        )
        self.apply_button_style(self.copy_preparation_path_button, role="accent")
        self.reset_preparation_button = Button(
            prep_buttons,
            text="Hazırlığı Sıfırla",
            command=self.reset_preparation_state,
            bg="#5d6d7e",
            fg="white",
        )
        self.apply_button_style(self.reset_preparation_button, role="secondary")
        self.layout_button_flow(
            prep_buttons,
            [
                self.copy_preparation_button,
                self.export_preparation_button,
                self.open_preparation_button,
                self.copy_preparation_path_button,
                self.reset_preparation_button,
            ],
            columns=2,
        )

        option_box = self.create_section(parent=self.settings_column, title="Seçenek Özeti", subtitlevariable=self.option_subtitle_text)
        self.option_summary_label = Label(
            option_box,
            textvariable=self.option_summary_text,
            **self.summary_card_style("#2a2014", "#f6e7cb"),
        )
        self.option_summary_label.pack(fill="x", padx=14, pady=(10, 10))

        advanced_audio_box = self.create_section(
            parent=self.audio_column,
            title="Gelişmiş Ses Ayarları",
            subtitle="Gerekirse açın. İlk kullanım için kapalı kalabilir.",
        )
        self.advanced_audio_button = Button(
            advanced_audio_box,
            textvariable=self.advanced_audio_button_text,
            command=self.toggle_advanced_audio_section,
            bg="#34495e",
            fg="white",
        )
        self.advanced_audio_button.pack(anchor="w", padx=14, pady=(10, 10))
        self.apply_button_style(self.advanced_audio_button, role="secondary")
        self.advanced_audio_body = Frame(advanced_audio_box, bg="#151b22")

        tone = self.create_section(parent=self.advanced_audio_body, title="Ton Ayarları", subtitlevariable=self.tone_subtitle_text, pady=(0, 10))
        self.gain = self.make_slider(tone, "Kazanç (dB)", -12, 24, 6)
        self.boost = self.make_slider(tone, "Güçlendirme (dB)", 0, 18, 6)
        self.high_pass_hz = self.make_slider(tone, "High-Pass (Hz)", 0, 240, 70)
        self.bass = self.make_slider(tone, "Bas (dB)", -12, 12, 3)
        self.presence = self.make_slider(tone, "Presence (dB)", -12, 12, 2)
        self.treble = self.make_slider(tone, "Tiz (dB)", -12, 12, 2)
        self.distortion = self.make_slider(tone, "Distorsiyon (%)", 0, 100, 25)

        mix = self.create_section(parent=self.advanced_audio_body, title="Mix ve Temizlik", subtitlevariable=self.mix_subtitle_text, pady=(0, 12))
        self.backing_level = self.make_slider(mix, "Arka Plan Seviye (%)", 0, 200, 100)
        self.vocal_level = self.make_slider(mix, "Vokal Seviye (%)", 0, 200, 85)
        self.noise_reduction = self.make_slider(mix, "Gürültü Azaltma (%)", 0, 100, 25)
        self.noise_gate_threshold = self.make_slider(mix, "Noise Gate Eşigi (%)", 0, 100, 25)
        self.monitor_level = self.make_slider(mix, "Canlı İzleme Seviyesi (%)", 0, 200, 100)
        self.compressor_amount = self.make_slider(mix, "Kompresör Miktarı (%)", 0, 100, 35)
        self.compressor_threshold = self.make_slider(mix, "Kompresör Eşiği (dB)", -36, -6, -18)
        self.compressor_makeup = self.make_slider(mix, "Makeup Gain (dB)", 0, 18, 4)
        Label(mix, text="Limiter", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(6, 2))
        limiter_menu = OptionMenu(mix, self.limiter_enabled, "Açık", "Kapalı")
        limiter_menu.pack(anchor="w", padx=14)
        self.speed_ratio = self.make_slider(mix, "Hız (%)", 50, 150, 100)
        self.output_gain = self.make_slider(mix, "Çıkış Kazancı (dB)", -12, 12, 0)
        self.advanced_audio_expanded = False
        self.set_advanced_audio_expanded(False)

        actions = self.create_section(parent=self.record_left_column, title="İşlem", subtitlevariable=self.action_subtitle_text)
        self.action_guidance_label = Label(
            actions,
            textvariable=self.action_guidance_text,
            **self.summary_card_style("#1b2230", "#dfe9f5"),
            anchor="w",
        )
        self.action_guidance_label.pack(fill="x", padx=14, pady=(10, 6))
        action_buttons = Frame(actions, bg="#151b22")
        action_buttons.pack(fill="x", padx=14, pady=(0, 14))
        action_buttons.grid_columnconfigure(0, weight=1)
        action_buttons.grid_columnconfigure(1, weight=1)
        self.start_test_button = self.create_click_chip(
            action_buttons,
            "Mikrofon/Ses Kartı Testi (5 sn)",
            self.start_test_thread,
            role="primary",
            compact=False,
        )
        self.start_test_button.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.start_quick_record_button = self.create_click_chip(
            action_buttons,
            "Hızlı Kayıt (Sadece Mikrofon)",
            self.start_quick_record_thread,
            role="accent",
            compact=False,
        )
        self.start_quick_record_button.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 6))
        self.start_recording_button = self.create_click_chip(
            action_buttons,
            "Tam Kayıt (Mikrofon)",
            self.start_recording_thread,
            role="success",
            compact=False,
        )
        self.start_recording_button.grid(row=1, column=0, sticky="ew")
        self.start_test_button._chip_enabled = False
        self.start_quick_record_button._chip_enabled = False
        self.start_recording_button._chip_enabled = False
        self.apply_click_chip_style(self.start_test_button, role="primary", enabled=False, compact=False)
        self.apply_click_chip_style(self.start_quick_record_button, role="accent", enabled=False, compact=False)
        self.apply_click_chip_style(self.start_recording_button, role="success", enabled=False, compact=False)
        self.stop_recording_button = self.create_click_chip(
            action_buttons,
            "Kaydı Durdur ve Kaydet",
            self.request_stop_recording,
            role="danger",
            compact=False,
        )
        self.stop_recording_button.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        self.stop_recording_button._chip_enabled = False
        self.apply_click_chip_style(self.stop_recording_button, role="danger", enabled=False, compact=False)

        progress_box = self.create_section(parent=self.record_left_column, title="Kayıt Durumu", subtitlevariable=self.progress_subtitle_text)
        self.status_label = Label(
            progress_box,
            textvariable=self.status_text,
            **self.summary_card_style("#1b2029", "#dce6ef"),
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=14, pady=(10, 8))
        self.progress_label = Label(
            progress_box,
            textvariable=self.record_progress_text,
            bg="#151b22",
            fg="#dce6ef",
            anchor="w",
            wraplength=self.section_wraplength,
            justify="left",
            padx=10,
            pady=6,
        )
        self.progress_label.pack(fill="x", padx=14, pady=(0, 10))

        recent_box = self.create_section(parent=self.outputs_column, title="Son Çıktılar", subtitlevariable=self.recent_output_subtitle_text)
        self.recent_output_summary_label = Label(
            recent_box,
            textvariable=self.recent_output_summary_text,
            **self.summary_card_style("#1b2029", "#dce6ef"),
            anchor="w",
        )
        self.recent_output_summary_label.pack(fill="x", padx=14, pady=(10, 8))
        self.recent_output_meta_label = Label(
            recent_box,
            textvariable=self.recent_output_meta_text,
            bg="#151b22",
            fg="#9fb0c2",
            anchor="w",
            justify="left",
            wraplength=self.section_wraplength,
            padx=2,
            pady=0,
        )
        self.recent_output_meta_label.pack(fill="x", padx=14, pady=(0, 8))
        recent_filter_row = Frame(recent_box, bg="#151b22")
        recent_filter_row.pack(fill="x", padx=14, pady=(0, 8))
        Label(recent_filter_row, text="Çıktı Filtresi", bg="#151b22", fg="#dce6ef").grid(row=0, column=0, sticky="w")
        self.recent_output_filter_menu = OptionMenu(recent_filter_row, self.recent_output_filter, "Tümü", "Sadece Ses", "Sadece Belgeler")
        self.recent_output_filter_menu.configure(width=18, bg="#24303c", fg="white", highlightthickness=0)
        self.recent_output_filter_menu.grid(row=1, column=0, sticky="w", pady=(2, 0))
        recent_buttons = Frame(recent_box, bg="#151b22")
        recent_buttons.pack(fill="x", padx=14, pady=(0, 8))
        self.open_last_export_button = Button(
            recent_buttons,
            text="Son Dosyayı Seçili Göster",
            command=self.open_last_export_in_finder,
            bg="#1f6feb",
            fg="white",
            state="disabled",
        )
        self.play_last_export_button = Button(
            recent_buttons,
            text="Son Kaydı Oynat",
            command=self.start_last_export_playback_thread,
            bg="#16a085",
            fg="white",
            state="disabled",
        )
        self.play_visible_recent_audio_button = Button(
            recent_buttons,
            text="Görünen Sesi Oynat",
            command=self.start_visible_recent_audio_playback_thread,
            bg="#1abc9c",
            fg="white",
            state="disabled",
        )
        self.open_visible_recent_output_button = Button(
            recent_buttons,
            text="Görünen Dosyayı Göster",
            command=self.open_visible_recent_output_in_finder,
            bg="#2f81f7",
            fg="white",
            state="disabled",
        )
        self.copy_visible_recent_output_path_button = Button(
            recent_buttons,
            text="Görünen Yolu Kopyala",
            command=self.copy_visible_recent_output_path_to_clipboard,
            bg="#5b6ee1",
            fg="white",
            state="disabled",
        )
        self.open_last_summary_button = Button(
            recent_buttons,
            text="Oturum Özetini Aç",
            command=self.open_last_session_summary_in_finder,
            bg="#6c5ce7",
            fg="white",
            state="disabled",
        )
        self.open_last_take_notes_button = Button(
            recent_buttons,
            text="Take Notunu Aç",
            command=self.open_last_take_notes_in_finder,
            bg="#9b59b6",
            fg="white",
            state="disabled",
        )
        self.open_last_output_dir_button = Button(
            recent_buttons,
            text="Son Oturum Klasörünü Aç",
            command=self.open_output_dir_in_finder,
            bg="#34495e",
            fg="white",
            state="disabled",
        )
        self.open_share_window_button = Button(
            recent_buttons,
            text="Paylaşım Penceresi",
            command=self.open_share_window,
            bg="#e67e22",
            fg="white",
            state="normal",
        )
        self.open_last_preparation_button = Button(
            recent_buttons,
            text="Hazırlık Dosyasını Aç",
            command=self.open_preparation_summary_in_finder,
            bg="#1f6feb",
            fg="white",
            state="disabled",
        )
        self.archive_last_session_button = Button(
            recent_buttons,
            text="Son Oturumu Arşivle",
            command=self.archive_last_session_outputs,
            bg="#546e7a",
            fg="white",
            state="disabled",
        )
        self.reset_session_state_button = Button(
            recent_buttons,
            text="Temiz Başlangıç",
            command=self.reset_session_state,
            bg="#5d6d7e",
            fg="white",
            state="disabled",
        )
        self.cleanup_old_trials_button = Button(
            recent_buttons,
            text="Eski Denemeleri Temizle",
            command=self.clean_old_trial_outputs,
            bg="#8e5a2b",
            fg="white",
            state="disabled",
        )
        self.refresh_recent_button = Button(recent_buttons, text="Listeyi Yenile", command=self.refresh_recent_exports, bg="#2d7d46", fg="white")
        self.layout_button_flow(
            recent_buttons,
            [
                self.open_last_export_button,
                self.play_last_export_button,
                self.play_visible_recent_audio_button,
                self.open_visible_recent_output_button,
                self.copy_visible_recent_output_path_button,
                self.open_last_summary_button,
                self.open_last_take_notes_button,
                self.open_last_output_dir_button,
                self.open_share_window_button,
                self.open_last_preparation_button,
                self.archive_last_session_button,
                self.reset_session_state_button,
                self.cleanup_old_trials_button,
                self.refresh_recent_button,
            ],
            columns=3,
        )
        for button, role in (
            (self.open_last_export_button, "primary"),
            (self.play_last_export_button, "success"),
            (self.play_visible_recent_audio_button, "success"),
            (self.open_visible_recent_output_button, "primary"),
            (self.copy_visible_recent_output_path_button, "accent"),
            (self.open_last_summary_button, "accent"),
            (self.open_last_take_notes_button, "accent"),
            (self.open_last_output_dir_button, "secondary"),
            (self.open_share_window_button, "warning"),
            (self.open_last_preparation_button, "primary"),
            (self.archive_last_session_button, "secondary"),
            (self.reset_session_state_button, "secondary"),
            (self.cleanup_old_trials_button, "warning"),
            (self.refresh_recent_button, "success"),
        ):
            self.apply_button_style(button, role=role)
        recent_copy_buttons = Frame(recent_box, bg="#151b22")
        recent_copy_buttons.pack(fill="x", padx=14, pady=(0, 8))
        self.copy_last_export_path_button = Button(
            recent_copy_buttons,
            text="Dosya Yolunu Kopyala",
            command=self.copy_last_export_path_to_clipboard,
            bg="#1f6feb",
            fg="white",
            state="disabled",
        )
        self.copy_last_summary_button = Button(
            recent_copy_buttons,
            text="Özet İçeriğini Kopyala",
            command=self.copy_last_session_summary_to_clipboard,
            bg="#8e44ad",
            fg="white",
            state="disabled",
        )
        self.copy_last_summary_path_button = Button(
            recent_copy_buttons,
            text="Özet Yolunu Kopyala",
            command=self.copy_last_session_summary_path_to_clipboard,
            bg="#6c5ce7",
            fg="white",
            state="disabled",
        )
        self.copy_last_brief_button = Button(
            recent_copy_buttons,
            text="Kısa Rapor Kopyala",
            command=self.copy_last_session_brief_to_clipboard,
            bg="#2d7d46",
            fg="white",
            state="disabled",
        )
        self.export_last_brief_button = Button(
            recent_copy_buttons,
            text="Raporu Dosyaya Yaz",
            command=self.export_last_session_brief_file,
            bg="#f39c12",
            fg="white",
            state="disabled",
        )
        self.copy_last_brief_path_button = Button(
            recent_copy_buttons,
            text="Rapor Yolunu Kopyala",
            command=self.copy_last_session_brief_path_to_clipboard,
            bg="#6c5ce7",
            fg="white",
            state="disabled",
        )
        self.open_last_brief_button = Button(
            recent_copy_buttons,
            text="Raporu Aç",
            command=self.open_last_session_brief_in_finder,
            bg="#1f6feb",
            fg="white",
            state="disabled",
        )
        self.copy_last_recovery_note_button = Button(
            recent_copy_buttons,
            text="Kurtarma Notunu Kopyala",
            command=self.copy_last_recovery_note_to_clipboard,
            bg="#c0392b",
            fg="white",
            state="disabled",
        )
        self.copy_recent_outputs_button = Button(
            recent_copy_buttons,
            text="Listeyi Kopyala",
            command=self.copy_recent_outputs_to_clipboard,
            bg="#34495e",
            fg="white",
            state="normal",
        )
        self.layout_button_flow(
            recent_copy_buttons,
            [
                self.copy_last_export_path_button,
                self.copy_last_summary_button,
                self.copy_last_summary_path_button,
                self.copy_last_brief_button,
                self.export_last_brief_button,
                self.copy_last_brief_path_button,
                self.open_last_brief_button,
                self.copy_last_recovery_note_button,
                self.copy_recent_outputs_button,
            ],
            columns=3,
        )
        for button, role in (
            (self.copy_last_export_path_button, "primary"),
            (self.copy_last_summary_button, "accent"),
            (self.copy_last_summary_path_button, "accent"),
            (self.copy_last_brief_button, "success"),
            (self.export_last_brief_button, "success"),
            (self.copy_last_brief_path_button, "accent"),
            (self.open_last_brief_button, "primary"),
            (self.copy_last_recovery_note_button, "danger"),
            (self.copy_recent_outputs_button, "secondary"),
        ):
            self.apply_button_style(button, role=role)
        self.recent_exports_label = Label(
            recent_box,
            textvariable=self.recent_exports_text,
            bg="#151b22",
            fg="#dce6ef",
            wraplength=self.section_wraplength,
            justify="left",
        )
        self.recent_exports_label.pack(anchor="w", padx=14, pady=(0, 14))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.input_device_choice.trace_add("write", self.on_input_choice_changed)
        self.output_device_choice.trace_add("write", self.on_output_choice_changed)
        self.recent_output_filter.trace_add("write", lambda *_args: self.refresh_recent_exports())
        for var in (
            self.output_name,
            self.output_dir,
            self.session_mode,
            self.session_name,
            self.mp3_quality,
            self.wav_export_mode,
            self.mic_record_seconds,
            self.record_limit_hours,
            self.preset_name,
            self.input_device_choice,
            self.output_device_choice,
        ):
            var.trace_add("write", self.on_plan_inputs_changed)
        self.inspect_devices(initial=True)
        self.root.after(80, self.apply_startup_preset)
        self.root.after(120, self.update_meter_ui)
        self.root.after(200, self.update_recording_progress_ui)
        self.root.after(220, self.refresh_recent_exports)
        self.root.after(250, self.start_input_meter)
        self.update_operation_state_summary()
        self.update_compact_status_summary()
        self.update_recording_prep_summary()
        self.update_next_step_summary()
        self.update_readiness_summary()
        self.update_preflight_warning_summary()
        self.update_action_guidance_summary()
        self.update_action_subtitle()
        self.update_source_subtitle()
        self.update_merge_summary()
        self.update_action_button_copy()
        self.update_progress_subtitle()
        self.update_mp3_quality_controls()
        self.update_output_name_label()
        self.update_output_subtitle()
        self.update_tone_subtitle()
        self.update_mix_subtitle()
        self.update_option_explanation_summary()
        self.update_recent_output_summary()
        self.set_workspace_tab("Kayıt")

    def create_section(
        self,
        parent: Optional[Frame] = None,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        subtitlevariable: Optional[StringVar] = None,
        padx: Optional[int] = None,
        pady: tuple[int, int] = (0, 10),
        bg: str = "#151b22",
        border: str = "#24303c",
    ) -> Frame:
        container = parent if parent is not None else self.content
        section = Frame(container, bg=bg, highlightbackground=border, highlightthickness=1)
        section.pack(fill="x", padx=(14 if parent is None else 0) if padx is None else padx, pady=pady)
        Frame(section, bg=border, height=3).pack(fill="x")
        if title:
            Label(section, text=title, bg=bg, fg="#f4f7fb", font=("Helvetica", 15, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
        if subtitle is not None:
            Label(
                section,
                text=subtitle,
                bg=bg,
                fg="#9fb0c2",
                justify="left",
                font=("Helvetica", 11),
                wraplength=getattr(self, "section_wraplength", getattr(self, "content_wraplength", 620)),
            ).pack(anchor="w", padx=14, pady=(0, 10))
        elif subtitlevariable is not None:
            Label(
                section,
                textvariable=subtitlevariable,
                bg=bg,
                fg="#9fb0c2",
                justify="left",
                font=("Helvetica", 11),
                wraplength=getattr(self, "section_wraplength", getattr(self, "content_wraplength", 620)),
            ).pack(
                anchor="w", padx=14, pady=(0, 10)
            )
        return section

    def create_overview_card(
        self,
        parent: Frame,
        column: int,
        title: str,
        textvariable: StringVar,
        bg: str,
        fg: str,
    ) -> Frame:
        card = Frame(parent, bg=bg, highlightbackground="#2a3644", highlightthickness=1)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        Label(card, text=title, bg=bg, fg="#f4f7fb", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        Label(
            card,
            textvariable=textvariable,
            bg=bg,
            fg=fg,
            justify="left",
            wraplength=max(260, self.section_wraplength - 40),
            padx=12,
            pady=8,
        ).pack(fill="x")
        return card

    def compact_home_path(self, value: str) -> str:
        path = Path(value).expanduser()
        try:
            return f"~/{path.relative_to(Path.home())}"
        except Exception:
            return str(path)

    def create_click_chip(
        self,
        parent: Frame,
        text: str,
        command,
        role: str = "secondary",
        compact: bool = True,
    ) -> Label:
        chip = Label(parent, text=text)
        chip._chip_command = command
        chip._chip_role = role
        chip._chip_compact = compact
        chip._chip_enabled = True
        chip.bind("<Button-1>", lambda _event, target=chip: self.on_click_chip(target))
        self.apply_click_chip_style(chip, role=role, enabled=True, compact=compact)
        return chip

    def is_click_chip(self, widget) -> bool:
        return "_chip_command" in getattr(widget, "__dict__", {})

    def on_click_chip(self, chip: Label) -> None:
        if not getattr(chip, "_chip_enabled", True):
            return
        command = getattr(chip, "_chip_command", None)
        if callable(command):
            command()

    def apply_click_chip_style(self, chip: Label, role: str = "secondary", enabled: bool = True, compact: bool = True) -> None:
        palette = self.button_palette(role)
        bg = palette["bg"] if enabled else "#2a313a"
        fg = "white" if enabled else "#8b98a7"
        border = palette["activebackground"] if enabled else "#38414c"
        chip.configure(
            bg=bg,
            fg=fg,
            highlightbackground=border,
            highlightthickness=1,
            bd=0,
            padx=12 if compact else 14,
            pady=7 if compact else 9,
            font=("Helvetica", 10, "bold"),
            cursor="hand2" if enabled else "arrow",
        )
        chip._chip_enabled = enabled
        chip._chip_role = role
        chip._chip_compact = compact

    def set_click_widget_state(self, widget, state: str, role: Optional[str] = None) -> None:
        if self.is_click_chip(widget):
            self.apply_click_chip_style(
                widget,
                role=role or getattr(widget, "_chip_role", "secondary"),
                enabled=(state != "disabled"),
                compact=getattr(widget, "_chip_compact", True),
            )
        else:
            widget.configure(state=state)

    def set_click_widget_text(self, widget, text: str) -> None:
        if self.is_click_chip(widget):
            widget.configure(text=text)
        else:
            widget.configure(text=text)

    def set_workspace_tab(self, name: str) -> None:
        self.workspace_tab.set(name)
        tabs = {
            "Kayıt": self.record_tab,
            "Kurulum": self.setup_tab,
            "Müzik": self.music_tab,
            "Birleştirme": self.merge_tab,
            "Ayarlar": self.settings_tab,
            "Ses Düzenleme": self.audio_tab,
            "Son Çıktılar": self.outputs_tab,
        }
        for tab_name, frame in tabs.items():
            if tab_name == name:
                frame.pack(fill="x")
            else:
                frame.pack_forget()
        for label, tab_name in (
            (self.record_tab_button, "Kayıt"),
            (self.setup_tab_button, "Kurulum"),
            (self.music_tab_button, "Müzik"),
            (self.merge_tab_button, "Birleştirme"),
            (self.settings_tab_button, "Ayarlar"),
            (self.audio_tab_button, "Ses Düzenleme"),
            (self.outputs_tab_button, "Son Çıktılar"),
        ):
            self.apply_nav_chip_style(label, active=(tab_name == name))
        self.workspace_hint_text.set(self.build_workspace_hint_text(name))
        if name == "Ses Düzenleme":
            self.set_advanced_audio_expanded(True)

    def set_advanced_audio_expanded(self, expanded: bool) -> None:
        self.advanced_audio_expanded = expanded
        if expanded:
            self.advanced_audio_button_text.set("Ton ve Mix Ayarlarını Gizle")
            self.advanced_audio_body.pack(fill="x", padx=14, pady=(0, 12))
        else:
            self.advanced_audio_button_text.set("Ton ve Mix Ayarlarını Göster")
            self.advanced_audio_body.pack_forget()

    def toggle_advanced_audio_section(self) -> None:
        self.set_advanced_audio_expanded(not getattr(self, "advanced_audio_expanded", False))

    def button_palette(self, role: str) -> dict[str, str]:
        palettes = {
            "primary": {"bg": "#1f6feb", "activebackground": "#2f81f7"},
            "success": {"bg": "#238636", "activebackground": "#2ea043"},
            "secondary": {"bg": "#34495e", "activebackground": "#415a72"},
            "accent": {"bg": "#8e44ad", "activebackground": "#9b59b6"},
            "warning": {"bg": "#8e5a2b", "activebackground": "#a86b34"},
            "danger": {"bg": "#c0392b", "activebackground": "#d84a3b"},
        }
        return palettes.get(role, palettes["secondary"])

    def apply_button_style(self, button: Button, role: str = "secondary", compact: bool = True) -> None:
        palette = self.button_palette(role)
        button.configure(
            bg=palette["bg"],
            fg="white",
            activebackground=palette["activebackground"],
            activeforeground="white",
            bd=0,
            highlightthickness=0,
            padx=12 if compact else 14,
            pady=7 if compact else 9,
            font=("Helvetica", 10, "bold"),
            cursor="hand2",
        )

    def apply_nav_chip_style(self, label: Label, active: bool = False) -> None:
        bg = "#2b6df2" if active else "#1a2430"
        fg = "#ffffff" if active else "#c7d2de"
        border = "#7fb0ff" if active else "#2a3644"
        label.configure(
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            highlightbackground=border,
            highlightthickness=1,
            bd=0,
            padx=10,
            pady=6,
            font=("Helvetica", 10, "bold"),
            cursor="hand2",
        )

    def layout_button_flow(self, parent: Frame, buttons: list[Button], columns: int = 3) -> None:
        for index, button in enumerate(buttons):
            row = index // columns
            column = index % columns
            parent.grid_columnconfigure(column, weight=1)
            button.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0), pady=(0, 8))

    def on_plan_inputs_changed(self, *_args) -> None:
        self.update_operation_state_summary()
        self.update_compact_status_summary()
        self.update_recording_prep_summary()
        self.update_next_step_summary()
        self.update_readiness_summary()
        self.update_preflight_warning_summary()
        self.update_action_guidance_summary()
        self.update_action_subtitle()
        self.update_source_subtitle()
        self.update_action_button_copy()
        self.update_progress_subtitle()
        self.update_mp3_quality_controls()
        self.update_output_name_label()
        self.update_output_subtitle()
        self.update_tone_subtitle()
        self.update_mix_subtitle()
        self.update_merge_summary()
        self.update_option_explanation_summary()
        self.update_setup_hint_summary()

    def session_mode_value(self) -> str:
        return normalize_choice(self.session_mode.get(), SESSION_MODE_ALIASES, "Tek Klasör")

    def mp3_quality_value(self) -> str:
        return normalize_choice(self.mp3_quality.get(), MP3_QUALITY_ALIASES, "Yüksek VBR")

    def wav_export_mode_value(self) -> str:
        return normalize_choice(self.wav_export_mode.get(), WAV_EXPORT_MODE_ALIASES, "Sadece Vokal WAV")

    def mp3_dependency_missing(self) -> bool:
        return self.should_export_mp3() and shutil.which("ffmpeg") is None

    def limiter_enabled_value(self) -> str:
        return normalize_choice(self.limiter_enabled.get(), LIMITER_ALIASES, "Açık")

    def plan_take_name_hint(self) -> str:
        name = self.output_name.get().strip()
        if name:
            return name
        return "otomatik take adı"

    def plan_session_hint(self) -> str:
        mode = self.session_mode_value()
        if mode == "İsimli Oturum":
            return f"İsimli Oturum ({self.session_name.get().strip() or 'session'})"
        if mode == "Tarihli Oturum":
            return "Tarihli Oturum"
        return "Tek Klasör"

    def planned_output_labels(self) -> list[str]:
        labels = []
        mp3_enabled = self.should_export_mp3()
        mp3_missing = self.mp3_dependency_missing()
        if mp3_enabled and not mp3_missing:
            labels.append(f"MP3 ({self.mp3_quality_value()})")
        if self.should_export_mix_wav() or mp3_missing:
            labels.append("Mix WAV (MP3 yerine)" if mp3_enabled and mp3_missing else "Mix WAV")
        labels.append("Vokal WAV")
        labels.append("session_summary.json")
        labels.append("take_notes.txt")
        return labels

    def build_compact_status_text(self) -> str:
        source_text = f"{self.backing_file.name} + mikrofon" if self.backing_file is not None else "Sadece mikrofon"
        take_text = self.output_name.get().strip() or "otomatik"
        output_dir_value = self.output_dir.get().strip()
        target_text = str(self.resolve_output_dir()) if output_dir_value else "klasör seçilmedi"
        parts = [
            f"Preset: {self.preset_name.get()}",
            f"Kaynak: {source_text}",
            f"Oturum: {self.plan_session_hint()}",
            f"Take: {take_text}",
            f"Hedef: {target_text}",
        ]
        preset_note = self.current_preset_note()
        if preset_note:
            parts.append(f"Preset Notu: {preset_note}")
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                parts.append(f"Kurtarma: var | Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}")
            else:
                parts.append("Kurtarma: var")
        return " | ".join(parts)

    def update_compact_status_summary(self) -> None:
        try:
            self.compact_status_text.set(self.build_compact_status_text())
            self.update_hero_overview_cards()
        except Exception:
            pass

    def build_hero_status_card_text(self) -> str:
        preset = self.preset_name.get().strip() or "Varsayılan"
        source = "Müzik + mikrofon" if self.backing_file is not None else "Sadece mikrofon"
        target = self.compact_home_path(str(self.resolve_output_dir())) if self.output_dir.get().strip() else "Klasör seçilmedi"
        return f"{preset}\n{source} | {self.plan_session_hint()}\nHedef: {target}"

    def build_hero_setup_card_text(self) -> str:
        parts = [
            "Giriş hazır" if self.current_input_device_count > 0 else "Giriş yok",
            "Çıkış hazır" if self.current_output_device_count > 0 else "Çıkış yok",
        ]
        if self.should_export_mp3():
            parts.append("ffmpeg hazır" if not self.mp3_dependency_missing() else "ffmpeg eksik")
        else:
            parts.append("MP3 kapalı")
        parts.append("Klasör hazır" if self.output_dir.get().strip() else "Klasör seçilmedi")
        return " | ".join(parts[:2]) + "\n" + " | ".join(parts[2:])

    def build_hero_output_card_text(self) -> str:
        if self.recording_active:
            return "Kayıt sürüyor\nSon çıktı işlemleri kayıt bitince açılacak."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                return f"Kurtarma notu var\nSon iyi kayıt: {recent_audio_hint_text(self.last_export_path)}"
            return "Kurtarma notu var\nÖnce notu inceleyin."
        if self.last_export_path is not None and self.last_export_path.exists():
            return f"Son kayıt hazır\n{recent_audio_status_text(self.last_export_path)}"
        if self.last_summary_path is not None and self.last_summary_path.exists():
            return "Oturum özeti hazır\nKlasörü açabilir veya listeyi yenileyebilirsiniz."
        return "Henüz çıktı yok\nİlk testten sonra burada görünecek."

    def build_hero_preparation_card_text(self) -> str:
        if not self.output_dir.get().strip():
            return "Plan bekliyor\nÖnce kayıt klasörünü seçin."
        prep_path = self.current_preparation_summary_path()
        if prep_path.exists():
            return f"Hazırlık dosyası hazır\n{prep_path.name}"
        return f"Kayıt planı hazır\n{len(self.planned_output_labels())} çıktı planlandı."

    def build_hero_summary_text(self) -> str:
        status = self.build_hero_status_card_text().replace("\n", " | ")
        setup = self.build_hero_setup_card_text().replace("\n", " | ")
        preparation = self.build_hero_preparation_card_text().replace("\n", " | ")
        output = self.build_hero_output_card_text().replace("\n", " | ")
        return f"Canlı Durum: {status}    •    Kurulum: {setup}    •    Hazırlık: {preparation}    •    Son Çıktı: {output}"

    def build_workspace_hint_text(self, name: str) -> str:
        hints = {
            "Kayıt": "Test, hızlı kayıt ve tam kayıt bu alanda.",
            "Kurulum": "Giriş, çıkış, preset ve cihaz seçimi burada.",
            "Müzik": "Arka plan müziği seçimi ve kaynak akışı burada.",
            "Birleştirme": "İki ses kanalı dengesini ve birleştirme özetini burada görün.",
            "Ayarlar": "Çıktı klasörü, oturum ve format ayarları burada.",
            "Ses Düzenleme": "Ton, mix ve gelişmiş ses düzenleme burada.",
            "Son Çıktılar": "Son kayıt, özet, not ve dışa aktarımlar burada.",
        }
        return hints.get(name, "")

    def update_hero_overview_cards(self) -> None:
        try:
            self.hero_status_card_text.set(self.build_hero_status_card_text())
            self.hero_setup_card_text.set(self.build_hero_setup_card_text())
            self.hero_output_card_text.set(self.build_hero_output_card_text())
            self.hero_summary_text.set(self.build_hero_summary_text())
        except Exception:
            pass

    def build_operation_state_text(self) -> str:
        if self.recording_active:
            if self.stop_recording_requested:
                return "Durum: kayıt durduruluyor"
            return f"Durum: kayıt sürüyor ({self.recording_mode})"
        if self.monitor_stream is not None:
            return "Durum: canlı monitor açık"
        if self.meter_stream is not None:
            return "Durum: mikrofon seviyesi izleniyor"
        return "Durum: hazır"

    def build_operation_state_palette(self) -> dict[str, str]:
        if self.recording_active:
            if self.stop_recording_requested:
                return {"bg": "#3a2316", "fg": "#ffd7a8"}
            return {"bg": "#1f3527", "fg": "#d8f3dc"}
        if self.monitor_stream is not None:
            return {"bg": "#33261a", "fg": "#ffe0a8"}
        if self.meter_stream is not None:
            return {"bg": "#10283a", "fg": "#d7eefb"}
        return {"bg": "#182028", "fg": "#9fb0c2"}

    def update_operation_state_summary(self) -> None:
        try:
            self.operation_state_text.set(self.build_operation_state_text())
            label = getattr(self, "operation_state_label", None)
            if label is not None:
                label.configure(**self.build_operation_state_palette())
        except Exception:
            pass

    def build_completion_status_text(self, label: str, output_dir: Path, primary_path: Optional[Path], generated_files: list[Path]) -> str:
        parts = [f"{label} hazır"]
        if primary_path is not None:
            parts.append(f"Ana dosya: {recent_audio_status_text(primary_path)}")
            if self.mp3_dependency_missing():
                parts.append("Not: MP3 yerine WAV kullanıldı")
        if generated_files:
            parts.append(f"Dosya sayısı: {len(generated_files)}")
        parts.append(f"Klasör: {output_dir}")
        return " | ".join(parts)

    def build_ready_recording_progress_text(self, output_dir: Path) -> str:
        parts = ["Hazır", "Dosyalar hazır", f"Klasör: {output_dir}"]
        if self.last_export_path is not None and self.last_export_path.exists():
            parts.append(f"Son kayıt: {recent_audio_status_text(self.last_export_path)}")
            if self.mp3_dependency_missing():
                parts.append("MP3 yerine WAV kullanıldı")
        return " | ".join(parts)

    def build_recording_prep_text(self) -> str:
        output_dir = self.resolve_output_dir()
        source_text = (
            f"Arka plan + mikrofon ({self.backing_file.name})"
            if self.backing_file is not None
            else f"Sadece mikrofon ({self.mic_record_seconds.get().strip() or '60'} sn)"
        )
        lines = [
            f"Preset/Oturum: {self.preset_name.get()} | {self.plan_session_hint()}",
            f"Kaynak: {source_text}",
            f"Take/Hedef: {self.plan_take_name_hint()} | {output_dir}",
            f"Dosyalar: {', '.join(self.planned_output_labels())}",
            f"Cihazlar: {self.input_device_choice.get()} -> {self.output_device_choice.get()}",
        ]
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                lines.append(f"Kurtarma: {self.last_recovery_note_path.name} hazır | Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}")
            else:
                lines.append(f"Kurtarma: {self.last_recovery_note_path.name} hazır")
        return "\n".join(lines)

    def update_recording_prep_summary(self) -> None:
        try:
            self.update_recording_prep_subtitle()
            self.prep_summary_text.set(self.build_recording_prep_text())
            self.prep_status_text.set(self.build_recording_prep_status_text())
            self.prep_meta_text.set(self.build_recording_prep_meta_text())
            label = getattr(self, "prep_status_label", None)
            if label is not None:
                label.configure(**self.build_recording_prep_status_palette())
        except Exception:
            pass

    def build_recording_prep_subtitle_text(self) -> str:
        if not self.output_dir.get().strip():
            return "Planı netleştirmek için önce kayıt klasörünü seçin."
        output_dir = self.resolve_output_dir()
        file_count = len(self.planned_output_labels())
        subtitle = f"{file_count} çıktı hazırlanacak. Hedef: {output_dir}"
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            subtitle += " | kurtarma notu var"
            if self.last_export_path is not None and self.last_export_path.exists():
                subtitle += f" | son iyi kayıt: {recent_audio_status_text(self.last_export_path)}"
        return subtitle

    def update_recording_prep_subtitle(self) -> None:
        try:
            self.prep_subtitle_text.set(self.build_recording_prep_subtitle_text())
        except Exception:
            pass

    def build_recording_prep_status_text(self) -> str:
        if not self.output_dir.get().strip():
            return "Hazırlık durumu: kayıt klasörü bekleniyor"
        prep_path = self.current_preparation_summary_path()
        if prep_path.exists():
            return "Hazırlık durumu: dosya hazır"
        return "Hazırlık durumu: dosya henüz yazılmadı"

    def build_recording_prep_status_palette(self) -> dict[str, str]:
        if not self.output_dir.get().strip():
            return {"bg": "#3a2316", "fg": "#ffd7a8"}
        prep_path = self.current_preparation_summary_path()
        if prep_path.exists():
            return {"bg": "#1f3527", "fg": "#d8f3dc"}
        return {"bg": "#10283a", "fg": "#d7eefb"}

    def build_recording_prep_meta_text(self) -> str:
        if not self.output_dir.get().strip():
            return "Hazırlık dosyası: kayıt klasörü seçilmedi"
        prep_path = self.current_preparation_summary_path()
        if not prep_path.exists():
            return f"Hazırlık dosyası: henüz yazılmadı | Hedef: {prep_path.name}"
        updated = time.strftime("%d.%m %H:%M", time.localtime(prep_path.stat().st_mtime))
        return (
            f"Hazırlık dosyası: {prep_path.name} | "
            f"Klasör: {prep_path.parent.name} | "
            f"Son güncelleme: {updated}"
        )

    def build_current_preparation_brief_text(self) -> str:
        sections = [
            "Hazırlık Özeti",
            self.build_compact_status_text(),
            "",
            f"Sonraki Adım: {self.build_next_step_subtitle_text()}",
            self.build_next_step_text(),
            "",
            f"Hazırlık: {self.build_readiness_subtitle_text()}",
            self.build_readiness_text(),
            "",
            f"Kayıt Planı: {self.build_recording_prep_subtitle_text()}",
            self.build_recording_prep_text(),
            "",
            f"Seçenekler: {self.build_option_subtitle_text()}",
            self.build_option_explanation_text(),
            "",
            f"Ton: {self.build_tone_subtitle_text()}",
            f"Mix: {self.build_mix_subtitle_text()}",
        ]
        return "\n".join(sections)

    def copy_current_preparation_to_clipboard(self) -> None:
        self.copy_text_to_clipboard(
            self.build_current_preparation_brief_text(),
            "Hazırlık özeti panoya alındı",
            "Hazırlık özeti kopyalanamadı",
        )

    def export_current_preparation_file(self) -> None:
        if not self.output_dir.get().strip():
            self.set_status("Hazırlık özeti için önce kayıt klasörünü seçin.")
            return
        try:
            output_dir = self.resolve_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            prep_path = output_dir / "preparation_summary.txt"
            prep_path.write_text(self.build_current_preparation_brief_text(), encoding="utf-8")
            self.last_output_dir = output_dir
            self.last_preparation_summary_path = prep_path
            self.write_last_session_state(output_dir, self.last_summary_path)
            self.update_recent_output_summary()
            if not self.recording_active:
                self.open_last_output_dir_button.configure(state="normal")
                self.open_last_preparation_button.configure(state="normal")
            self.set_status(f"Hazırlık özeti yazıldı: {prep_path}")
        except Exception as exc:
            self.set_status(f"Hazırlık özeti yazılamadı: {exc}")

    def reset_preparation_state(self) -> None:
        if self.block_changes_during_recording("hazırlık durumu"):
            return
        self.last_preparation_summary_path = None
        if self.current_recent_exports_dir().exists():
            self.write_last_session_state(self.current_recent_exports_dir(), self.last_summary_path)
        self.update_recording_prep_summary()
        self.update_recording_prep_subtitle()
        self.update_recent_output_summary()
        try:
            self.open_preparation_button.configure(state="disabled")
            self.open_last_preparation_button.configure(state="disabled")
        except Exception:
            pass
        self.set_status("Hazırlık durumu sıfırlandı. Yeni plan için özet temizlendi.")

    def current_preparation_summary_path(self) -> Path:
        if self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists():
            return self.last_preparation_summary_path
        return self.resolve_output_dir() / "preparation_summary.txt"

    def copy_preparation_summary_path_to_clipboard(self) -> None:
        prep_path = self.current_preparation_summary_path()
        if not prep_path.exists():
            self.set_status(self.missing_item_status("Hazırlık dosyası"))
            return
        self.copy_text_to_clipboard(
            str(prep_path),
            self.copied_item_status("Hazırlık yolu", prep_path.name),
            "Hazırlık yolu kopyalanamadı",
        )

    def open_preparation_summary_in_finder(self) -> None:
        prep_path = self.current_preparation_summary_path()
        if not prep_path.exists():
            self.set_status("Hazırlık dosyası yok.")
            return
        try:
            subprocess.run(["open", "-R", str(prep_path)], check=False)
            self.set_status(self.finder_selected_status("Hazırlık dosyası", prep_path.name))
        except Exception as exc:
            self.set_status(f"Hazırlık dosyası açılamadı: {exc}")

    def build_output_subtitle_text(self) -> str:
        base_dir = self.output_dir.get().strip()
        mp3_enabled = self.should_export_mp3()
        if not base_dir:
            if self.mp3_dependency_missing():
                return "Önce bir klasör seçin. Bu tur MP3 yerine WAV dosyaları seçtiğiniz yere yazılacak."
            if not mp3_enabled:
                return "Önce bir klasör seçin. Bu tur yalnız WAV dosyaları seçtiğiniz yere yazılacak."
            return "Önce bir klasör seçin. MP3 ve WAV dosyaları seçtiğiniz yere yazılacak."
        mode = self.session_mode_value()
        if mode == "İsimli Oturum":
            session_name = self.session_name.get().strip() or "session"
            subtitle = f"Dosyalar {base_dir} içinde {session_name} klasörüne yazılacak."
        elif mode == "Tarihli Oturum":
            subtitle = f"Dosyalar {base_dir} içinde tarihli bir klasöre yazılacak."
        else:
            subtitle = f"Dosyalar doğrudan {base_dir} klasörüne yazılacak."
        if self.mp3_dependency_missing():
            subtitle += " MP3 yerine Mix WAV yazılacak."
        elif not mp3_enabled:
            subtitle += " Yalnız WAV yazılacak."
        return subtitle

    def build_output_name_label_text(self) -> str:
        if self.mp3_dependency_missing():
            return "Çıkış Dosya Adı (WAV fallback)"
        if self.should_export_mp3():
            return "Çıkış Dosya Adı (MP3)"
        return "Çıkış Dosya Adı (WAV)"

    def build_mp3_quality_label_text(self) -> str:
        if self.mp3_dependency_missing():
            return "MP3 Kalitesi (ffmpeg eksik)"
        if not self.should_export_mp3():
            return "MP3 Kalitesi (kapalı)"
        return "MP3 Kalitesi"

    def update_mp3_quality_controls(self) -> None:
        try:
            self.mp3_quality_label_text.set(self.build_mp3_quality_label_text())
            menu = getattr(self, "mp3_quality_menu", None)
            if menu is not None:
                menu.configure(state="normal" if self.should_export_mp3() and not self.mp3_dependency_missing() else "disabled")
        except Exception:
            pass

    def update_output_name_label(self) -> None:
        try:
            self.output_name_label_text.set(self.build_output_name_label_text())
        except Exception:
            pass

    def update_output_subtitle(self) -> None:
        try:
            self.output_subtitle_text.set(self.build_output_subtitle_text())
        except Exception:
            pass

    def build_source_subtitle_text(self) -> str:
        if self.backing_file is not None:
            return f"Arka plan etkin: {self.backing_file.name}. Bu modda tam kayıt kullanılacak."
        return "Şu an sadece mikrofon etkin. İsterseniz arka plan ekleyebilir veya hızlı kayda geçebilirsiniz."

    def update_source_subtitle(self) -> None:
        try:
            self.source_subtitle_text.set(self.build_source_subtitle_text())
        except Exception:
            pass

    def build_next_step_text(self) -> str:
        input_ready = bool(self.input_device_choice.get().strip())
        output_ready = bool(self.output_device_choice.get().strip())
        if not input_ready:
            return "1. Mikrofonları yeniden tara. 2. Bir giriş seç. 3. Test kaydı al."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                return f"Son çıktı alma denemesi hata verdi. Kurtarma notunu inceleyin. Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}. Sonra ayarları değiştirip kaydı yeniden başlatın."
            return "Son çıktı alma denemesi hata verdi. Kurtarma notunu inceleyin, sonra ayarları değiştirip kaydı yeniden başlatın."
        if self.mp3_dependency_missing():
            return "MP3 için ffmpeg eksik. ffmpeg kurun veya bu tur WAV ile devam edip önce kısa test alın."
        if self.backing_file is None:
            return "Mikrofon modu hazır. Test kaydı alın, sonra doğrudan kaydı başlatın."
        if not output_ready:
            return "Backing seçili. Çıkışı kontrol edin, kısa test yapın, sonra tam kayda geçin."
        return "Backing ve cihazlar hazır. Test kaydı iyi ise tam kaydı başlatabilirsiniz."

    def build_quick_control_text(self) -> str:
        next_step = self.build_next_step_text()
        readiness = self.build_readiness_text().replace("\n", " | ")
        warning = self.build_preflight_warning_text()
        return "\n".join(
            [
                f"Sıradaki: {next_step}",
                f"Hazırlık: {readiness}",
                f"Uyarı: {warning}",
            ]
        )

    def build_quick_control_palette(self) -> dict[str, str]:
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            return {"bg": "#2c2418", "fg": "#ffe7b3"}
        if not self.output_dir.get().strip() or self.last_input_peak >= 0.985 or self.last_input_peak < 0.05:
            return {"bg": "#2a1c1c", "fg": "#f6e7cb"}
        if self.missing_readiness_items():
            return {"bg": "#2c2418", "fg": "#ffe7b3"}
        return {"bg": "#1f2b22", "fg": "#d8f3dc"}

    def update_quick_control_summary(self) -> None:
        try:
            self.quick_control_text.set(self.build_quick_control_text())
            label = getattr(self, "quick_control_label", None)
            if label is not None:
                label.configure(**self.build_quick_control_palette())
        except Exception:
            pass

    def update_next_step_summary(self) -> None:
        try:
            self.update_next_step_subtitle()
            self.next_step_text.set(self.build_next_step_text())
            self.update_quick_control_summary()
        except Exception:
            pass

    def build_next_step_subtitle_text(self) -> str:
        input_ready = bool(self.input_device_choice.get().strip())
        output_ready = bool(self.output_device_choice.get().strip())
        if self.recording_active:
            if self.stop_recording_requested:
                return "Kayıt duruyor. İşlem tamamlanana kadar bekleyin."
            return "Kayıt aktif. Sıradaki adım durdurma olacak."
        if not input_ready:
            return "Önce mikrofon seçimi tamamlanmalı."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                return f"Yeniden denemeden önce kurtarma notu kontrol edilmeli. Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}."
            return "Yeniden denemeden önce kurtarma notu kontrol edilmeli."
        if self.mp3_dependency_missing():
            return "MP3 için ffmpeg eksik; kayıt WAV olarak devam edecek."
        if self.backing_file is None:
            return "Sadece mikrofon akışı hazır."
        if not output_ready:
            return "Arka plan seçili, çıkış seçimi bekleniyor."
        return "Arka planlı kayıt akışı hazır."

    def update_next_step_subtitle(self) -> None:
        try:
            self.next_step_subtitle_text.set(self.build_next_step_subtitle_text())
        except Exception:
            pass

    def missing_readiness_items(self) -> list[str]:
        missing: list[str] = []
        if not self.input_device_choice.get().strip():
            missing.append("giriş")
        if not self.output_device_choice.get().strip():
            missing.append("çıkış")
        if not self.output_dir.get().strip():
            missing.append("klasör")
        return missing

    def build_readiness_text(self) -> str:
        take_name = self.output_name.get().strip()
        missing_items = self.missing_readiness_items()
        source_line = (
            f"Kaynak: Arka plan + mikrofon ({self.backing_file.name})"
            if self.backing_file is not None
            else f"Kaynak: Sadece mikrofon ({self.mic_record_seconds.get().strip() or '60'} sn)"
        )
        take_line = f"Take adı: {take_name}" if take_name else "Take adı: otomatik oluşturulacak"
        if missing_items:
            lines = [
                "Genel durum: Eksik seçimler var",
                f"Eksikler: {', '.join(missing_items)}",
                source_line,
                take_line,
            ]
        else:
            lines = [
                "Genel durum: Kayda hazır",
                "Hazır olanlar: giriş, çıkış, klasör, kaynak",
                source_line,
                take_line,
            ]
        if self.mp3_dependency_missing():
            lines.append("MP3 durumu: ffmpeg eksik, çıktı WAV olarak kalacak")
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            lines.append(f"Kurtarma: {self.last_recovery_note_path.name} incelenebilir")
        return "\n".join(lines)

    def build_readiness_palette(self) -> dict[str, str]:
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            return {"bg": "#2c2418", "fg": "#ffe7b3"}
        if self.missing_readiness_items():
            return {"bg": "#2c2418", "fg": "#ffe7b3"}
        return {"bg": "#1f2b22", "fg": "#d8f3dc"}

    def build_readiness_subtitle_text(self) -> str:
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                return f"Hazırlık tamamlanmadan önce kurtarma notunu kontrol edin. Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}."
            return "Hazırlık tamamlanmadan önce kurtarma notunu kontrol edin."
        missing_items = self.missing_readiness_items()
        if missing_items:
            return f"Eksik seçimler: {', '.join(missing_items)}"
        if self.mp3_dependency_missing():
            return "Temel hazırlık tamam. MP3 için ffmpeg eksik."
        return "Giriş, çıkış, klasör ve kaynak hazır görünüyor."

    def update_readiness_subtitle(self) -> None:
        try:
            self.readiness_subtitle_text.set(self.build_readiness_subtitle_text())
        except Exception:
            pass

    def update_readiness_summary(self) -> None:
        try:
            self.update_readiness_subtitle()
            self.readiness_text.set(self.build_readiness_text())
            legacy_label = getattr(self, "readiness_label", None)
            if legacy_label is not None:
                legacy_label.configure(**self.build_readiness_palette())
            self.update_quick_control_summary()
        except Exception:
            pass

    def build_preflight_warning_text(self) -> str:
        if not self.output_dir.get().strip():
            return "Ön uyarı: kayıt klasörü seçilmedi."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                return f"Ön uyarı: son çıktı için kurtarma notu var ({self.last_recovery_note_path.name}). Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}."
            return f"Ön uyarı: son çıktı için kurtarma notu var ({self.last_recovery_note_path.name})."
        if self.mp3_dependency_missing():
            return "Ön uyarı: MP3 açık ama ffmpeg yok, kayıt WAV olarak kalacak."
        if self.last_input_peak >= 0.985:
            return "Ön uyarı: giriş çok yüksek, gain düşürmeden kayda başlamayın."
        if self.last_input_peak < 0.01:
            return "Ön uyarı: giriş çok zayıf, önce kısa test yapın."
        if self.last_input_peak < 0.05:
            return "Ön uyarı: giriş düşük, gerekirse gain artırın."
        return "Hazır: seviye uygun görünüyor, kısa testten sonra kayda geçebilirsiniz."

    def update_preflight_warning_summary(self) -> None:
        try:
            text = self.build_preflight_warning_text()
            self.preflight_warning_text.set(text)
            self.update_preflight_subtitle()
            legacy_label = getattr(self, "preflight_warning_label", None)
            if legacy_label is not None:
                if text.startswith("Hazır:"):
                    legacy_label.configure(bg="#1f2b22", fg="#d8f3dc")
                else:
                    legacy_label.configure(bg="#2a1c1c", fg="#f6e7cb")
            self.update_quick_control_summary()
        except Exception:
            pass

    def build_preflight_subtitle_text(self) -> str:
        if not self.output_dir.get().strip():
            return "Önce kayıt klasörünü seçin."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                return f"Son hatayı incelemeden yeni kayıt başlatmayın. Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}."
            return "Son hatayı incelemeden yeni kayıt başlatmayın."
        if self.mp3_dependency_missing():
            return "MP3 için ffmpeg kurulmalı veya WAV ile devam edilmeli."
        if self.last_input_peak >= 0.985:
            return "Giriş seviyesi fazla yüksek."
        if self.last_input_peak < 0.01:
            return "Giriş seviyesi neredeyse yok."
        if self.last_input_peak < 0.05:
            return "Giriş seviyesi düşük."
        return "Ön kontrol temiz görünüyor."

    def update_preflight_subtitle(self) -> None:
        try:
            self.preflight_subtitle_text.set(self.build_preflight_subtitle_text())
        except Exception:
            pass

    def build_action_guidance_text(self) -> str:
        input_name = self.input_device_choice.get().strip()
        output_name = self.output_device_choice.get().strip()
        if self.recording_active:
            if self.stop_recording_requested:
                return "Önerilen sıra: Durdurma istendi. Kayıt bölümü hazırlanırken yeni işlem başlatmayın."
            return "Önerilen sıra: Kayıt sürüyor. Şu anda yalnız durdur butonunu kullanın."
        if not input_name:
            return "Önerilen sıra: 1. Mikrofonları tara. 2. Girişi seç. 3. Sonra 5 saniyelik testi çalıştır."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                return f"Önerilen sıra: Önce kurtarma notunu inceleyin. Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}. Ardından kısa test yapın, sonra tam kaydı yeniden başlatın."
            return "Önerilen sıra: Önce kurtarma notunu inceleyin. Ardından kısa test yapın, sonra tam kaydı yeniden başlatın."
        if self.backing_file is None:
            if not output_name:
                return "Önerilen sıra: Çıkışı seçin. Ardından 5 saniyelik test yapın. Sorunsuzsa Hızlı Kayıt ile hızlıca kayıt alın."
            return "Önerilen sıra: Önce 5 saniyelik test yapın. Ses temizse Hızlı Kayıt hızlı yol, tam kayıt ise kontrollü yol olarak hazır."
        if not output_name:
            return "Önerilen sıra: Backing hazır. Önce çıkışı seçin, sonra 5 saniyelik test yapın. Son adımda tam kaydı başlatın."
        return "Önerilen sıra: 5 saniyelik test ile dengeyi kontrol edin. Denge doğruysa tam kaydı başlatın."

    def update_action_guidance_summary(self) -> None:
        try:
            self.action_guidance_text.set(self.build_action_guidance_text())
        except Exception:
            pass

    def build_action_subtitle_text(self) -> str:
        if self.recording_active:
            if self.stop_recording_requested:
                return "Kayıt durduruluyor. Yeni işlem başlatmayın."
            return "Kayıt sürüyor. Bu bölüm geçici olarak kilitli."
        if self.backing_file is not None:
            return "Önce test yapın, sonra tam kayda geçin. Hızlı kayıt bu modda kapalıdır."
        return "Önce test yapın, sonra hızlı kayıt veya tam kayıt seçin."

    def update_action_subtitle(self) -> None:
        try:
            self.action_subtitle_text.set(self.build_action_subtitle_text())
        except Exception:
            pass

    def build_progress_subtitle_text(self) -> str:
        if self.recording_active:
            if self.stop_recording_requested:
                return "Kayıt durduruluyor. Elde edilen bölüm hazırlanıyor."
            return "Kayıt sürerken geçen ve kalan süre burada yenilenir."
        return "Kayıt başlamadığında son durum burada görünür."

    def update_progress_subtitle(self) -> None:
        try:
            self.progress_subtitle_text.set(self.build_progress_subtitle_text())
        except Exception:
            pass

    def build_quick_record_button_text(self) -> str:
        if self.backing_file is not None:
            return "Hızlı Kayıt (Sadece Mikrofon Modunda)"
        return "Hızlı Kayıt (Sadece Mikrofon)"

    def build_main_record_button_text(self) -> str:
        if self.backing_file is not None:
            return "Tam Kayıt (Arka Plan + Mikrofon)"
        return "Tam Kayıt (Mikrofon)"

    def update_action_button_copy(self) -> None:
        try:
            self.set_click_widget_text(self.start_quick_record_button, self.build_quick_record_button_text())
            self.set_click_widget_text(self.start_recording_button, self.build_main_record_button_text())
        except Exception:
            pass

    def explain_mp3_quality(self) -> str:
        if self.mp3_dependency_missing():
            return "MP3: ffmpeg eksik, bu tur WAV yedeğiyle devam edilecek"
        quality = self.mp3_quality_value()
        if quality == "320 kbps":
            return "MP3: en yüksek sabit kalite"
        if quality == "192 kbps":
            return "MP3: kalite ve boyut dengeli"
        if quality == "128 kbps":
            return "MP3: daha küçük dosya, daha düşük kalite"
        return "MP3: yüksek kalite VBR"

    def explain_wav_export_mode(self) -> str:
        mode = self.wav_export_mode_value()
        if mode == "Mix + Vokal WAV":
            return "WAV: mix + vokal ayrı yazılacak"
        if mode == "Sadece WAV (Mix + Vokal)":
            return "WAV: sadece mix + vokal yazılacak"
        if mode == "Tüm WAV Dosyaları":
            return "WAV: tüm WAV dosyaları yazılacak"
        return "WAV: sadece işlenmiş vokal yazılacak"

    def explain_monitor_behavior(self) -> str:
        level = int(self.monitor_level.get())
        if level == 0:
            return "İzleme: kapalı"
        if level < 100:
            return f"İzleme: düşük (%{level})"
        if level > 100:
            return f"İzleme: yüksek (%{level})"
        return "İzleme: normal"

    def explain_speed_behavior(self) -> str:
        speed = int(self.speed_ratio.get())
        if speed == 100:
            return "Hız: normal"
        if speed < 100:
            return f"Hız: daha yavaş (%{speed})"
        return f"Hız: daha hızlı (%{speed})"

    def build_option_explanation_text(self) -> str:
        limiter_text = "Limiter: açık, tepeler sınırlanacak" if self.limiter_enabled_value() == "Açık" else "Limiter: kapalı, tepeler serbest kalacak"
        lines = [
            self.explain_mp3_quality(),
            self.explain_wav_export_mode(),
            self.explain_monitor_behavior(),
            self.explain_speed_behavior(),
            limiter_text,
        ]
        return "\n".join(lines)

    def update_option_explanation_summary(self) -> None:
        try:
            self.update_option_subtitle()
            self.option_summary_text.set(self.build_option_explanation_text())
        except Exception:
            pass

    def build_option_subtitle_text(self) -> str:
        wav_mode = self.wav_export_mode_value()
        mp3_enabled = self.should_export_mp3()
        limiter_enabled = self.limiter_enabled_value() == "Açık"
        parts = []
        if mp3_enabled:
            parts.append("MP3 açık (ffmpeg eksik)" if self.mp3_dependency_missing() else "MP3 açık")
        else:
            parts.append("MP3 kapalı")
        if wav_mode == "Mix + Vokal WAV":
            parts.append("mix + vokal WAV")
        elif wav_mode == "Sadece WAV (Mix + Vokal)":
            parts.append("yalnız WAV çıkışı")
        elif wav_mode == "Tüm WAV Dosyaları":
            parts.append("tüm WAV dosyaları")
        else:
            parts.append("yalnız vokal WAV")
        parts.append("limiter açık" if limiter_enabled else "limiter kapalı")
        return " | ".join(parts)

    def update_option_subtitle(self) -> None:
        try:
            self.option_subtitle_text.set(self.build_option_subtitle_text())
        except Exception:
            pass

    def build_tone_subtitle_text(self) -> str:
        gain = int(self.gain.get())
        boost = int(self.boost.get())
        distortion = int(self.distortion.get())
        high_pass = int(self.high_pass_hz.get())
        if distortion >= 60:
            drive_text = "yüksek drive"
        elif distortion >= 25:
            drive_text = "orta drive"
        else:
            drive_text = "temiz/sakin drive"
        return f"Kazanç {gain} dB | boost {boost} dB | {drive_text} | high-pass {high_pass} Hz"

    def update_tone_subtitle(self) -> None:
        try:
            self.tone_subtitle_text.set(self.build_tone_subtitle_text())
        except Exception:
            pass

    def build_mix_subtitle_text(self) -> str:
        backing = int(self.backing_level.get())
        vocal = int(self.vocal_level.get())
        noise = int(self.noise_reduction.get())
        monitor = int(self.monitor_level.get())
        compressor = int(self.compressor_amount.get())
        limiter = "açık" if self.limiter_enabled_value() == "Açık" else "kapalı"
        return (
            f"Arka plan %{backing} | vokal %{vocal} | gürültü azaltma %{noise} | "
            f"izleme %{monitor} | kompresör %{compressor} | limiter {limiter}"
        )

    def update_mix_subtitle(self) -> None:
        try:
            self.mix_subtitle_text.set(self.build_mix_subtitle_text())
        except Exception:
            pass

    def planned_audio_output_labels(self) -> list[str]:
        return [label for label in self.planned_output_labels() if label.endswith("WAV") or label.startswith("MP3")]

    def build_merge_subtitle_text(self) -> str:
        if self.backing_file is None:
            return "Arka plan eklerseniz ses ve müzik dengesi burada özetlenir."
        if self.current_input_device_count <= 0:
            return "Birleştirme için önce mikrofonu görünür hale getirip yeniden tarayın."
        if self.current_output_device_count <= 0:
            return "Birleştirme için önce çıkışı görünür hale getirip yeniden tarayın."
        if not self.output_dir.get().strip():
            return "Birleştirme için önce kayıt klasörünü seçin."
        if self.mp3_dependency_missing():
            return "Arka planlı kayıt hazır. MP3 yerine Mix WAV yazılacak."
        return "Arka planlı kayıt hazır. Önce test yapın, sonra tam kayda geçin."

    def build_merge_summary_text(self) -> str:
        if self.backing_file is None:
            return "\n".join(
                [
                    "Kanal: kapalı",
                    "Durum: yalnız mikrofon kaydı",
                "Hızlı Kayıt: açık",
                ]
            )
        backing = int(self.backing_level.get())
        vocal = int(self.vocal_level.get())
        monitor = int(self.monitor_level.get())
        speed = int(self.speed_ratio.get())
        outputs = ", ".join(self.planned_audio_output_labels())
        missing_bits = []
        if self.current_input_device_count <= 0:
            missing_bits.append("mikrofon")
        if self.current_output_device_count <= 0:
            missing_bits.append("çıkış")
        if not self.output_dir.get().strip():
            missing_bits.append("klasör")
        return "\n".join(
            [
                "Kanal: arka plan + mikrofon",
                f"Dosya: {self.backing_file.name}",
                f"Denge: müzik %{backing} | vokal %{vocal}",
                f"İzleme / hız: %{monitor} | %{speed}",
                f"Çıktı: {outputs}",
                f"Eksik: {', '.join(missing_bits)}" if missing_bits else "Durum: birleştirme hazır",
                "Akış: önce test, sonra tam kayıt",
            ]
        )

    def build_merge_palette(self) -> dict[str, str]:
        if self.backing_file is None:
            return {"bg": "#1e252d", "fg": "#e4edf5"}
        if self.current_input_device_count <= 0 or self.current_output_device_count <= 0 or not self.output_dir.get().strip():
            return {"bg": "#2c2418", "fg": "#ffe7b3"}
        if self.mp3_dependency_missing():
            return {"bg": "#33261a", "fg": "#ffe0a8"}
        return {"bg": "#1f2b22", "fg": "#d8f3dc"}

    def update_merge_summary(self) -> None:
        try:
            self.merge_subtitle_text.set(self.build_merge_subtitle_text())
            self.merge_summary_text.set(self.build_merge_summary_text())
            label = getattr(self, "merge_summary_label", None)
            if label is not None:
                label.configure(**self.build_merge_palette())
        except Exception:
            pass

    def on_slider_settings_changed(self, _value: str = "") -> None:
        self.update_tone_subtitle()
        self.update_mix_subtitle()
        self.update_merge_summary()
        self.update_option_explanation_summary()

    def build_recent_output_summary_text(self) -> str:
        filter_detail = self.current_recent_output_filter_detail()
        if self.recording_active:
            return "Canlı kayıt sürüyor. Son çıktı işlemleri kayıt bitince yeniden açılacak."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                text = f"Kurtarma notu hazır. Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}. Önce notu kopyalayın, sonra son kaydı veya klasörü açın."
                return f"{text} Görünüm: {filter_detail}." if filter_detail else text
            text = "Kurtarma notu hazır. Önce notu kopyalayın, sonra klasörü açın."
            return f"{text} Görünüm: {filter_detail}." if filter_detail else text
        if self.last_export_path is not None and self.last_export_path.exists():
            ready_items = [f"son kayıt {recent_audio_status_text(self.last_export_path)}"]
            if self.last_summary_path is not None and self.last_summary_path.exists():
                ready_items.append("özet")
            if self.last_take_notes_path is not None and self.last_take_notes_path.exists():
                ready_items.append("take notu")
            if self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists():
                ready_items.append("hazırlık dosyası")
            text = f"Hazır: {', '.join(ready_items)}. Önce son kaydı açın veya oynatın."
            return f"{text} Görünüm: {filter_detail}." if filter_detail else text
        if self.last_summary_path is not None and self.last_summary_path.exists():
            if self.last_take_notes_path is not None and self.last_take_notes_path.exists():
                text = "Hazır: özet ve take notu. Önce özeti açın, sonra kısa raporu kopyalayın."
                return f"{text} Görünüm: {filter_detail}." if filter_detail else text
            text = "Hazır: oturum özeti. Önce özeti açın veya kısa raporu kopyalayın."
            return f"{text} Görünüm: {filter_detail}." if filter_detail else text
        if self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists():
            text = "Hazır: hazırlık dosyası. Önce dosyayı açın veya klasörü açın."
            return f"{text} Görünüm: {filter_detail}." if filter_detail else text
        if self.last_take_notes_path is not None and self.last_take_notes_path.exists():
            text = "Hazır: take notu. Önce take notunu açın veya klasörü açın."
            return f"{text} Görünüm: {filter_detail}." if filter_detail else text
        if self.current_recent_exports_dir().exists():
            text = "Son oturum klasörü hazır. Önce klasörü açın veya listeyi yenileyin."
            return f"{text} Görünüm: {filter_detail}." if filter_detail else text
        return "Henüz son çıktı yok. İlk test veya kayıttan sonra bu bölüm dolacak."

    def build_recent_output_summary_palette(self) -> dict[str, str]:
        if self.recording_active:
            return {"bg": "#10283a", "fg": "#d7eefb"}
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            return {"bg": "#2c2418", "fg": "#ffe7b3"}
        if (
            (self.last_export_path is not None and self.last_export_path.exists())
            or (self.last_summary_path is not None and self.last_summary_path.exists())
            or (self.last_take_notes_path is not None and self.last_take_notes_path.exists())
            or (self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists())
        ):
            return {"bg": "#1f2b22", "fg": "#d8f3dc"}
        return {"bg": "#1b2029", "fg": "#dce6ef"}

    def build_recent_output_subtitle_text(self) -> str:
        filter_detail = self.current_recent_output_filter_detail()
        if self.recording_active:
            return "Kayıt sürerken eski çıktı işlemleri geçici olarak kapalıdır."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                text = f"Sorun yaşandıysa önce kurtarma notunu inceleyin. Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}."
                return f"{text} Gösterim: {filter_detail}." if filter_detail else text
            text = "Sorun yaşandıysa önce kurtarma notunu inceleyin."
            return f"{text} Gösterim: {filter_detail}." if filter_detail else text
        if self.last_export_path is not None and self.last_export_path.exists():
            text = f"Son kayıt hazır: {recent_audio_status_text(self.last_export_path)}. Dosyayı açabilir, oynatabilir veya yolları kopyalayabilirsiniz."
            return f"{text} Gösterim: {filter_detail}." if filter_detail else text
        if self.last_summary_path is not None and self.last_summary_path.exists():
            text = "Özet hazır. Oturum bilgisini açabilir veya kopyalayabilirsiniz."
            return f"{text} Gösterim: {filter_detail}." if filter_detail else text
        if self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists():
            text = "Hazırlık dosyası hazır. Dosyayı açabilir veya oturum klasörüne geçebilirsiniz."
            return f"{text} Gösterim: {filter_detail}." if filter_detail else text
        if self.last_take_notes_path is not None and self.last_take_notes_path.exists():
            text = "Take notu hazır. Notu açabilir veya oturum klasörüne geçebilirsiniz."
            return f"{text} Gösterim: {filter_detail}." if filter_detail else text
        text = "İlk test veya kayıttan sonra son dosyalar burada görünür."
        return f"{text} Gösterim: {filter_detail}." if filter_detail else text

    def build_recent_output_meta_text(self) -> str:
        output_dir = self.current_recent_exports_dir()
        if not output_dir.exists():
            return f"Klasör: {output_dir} | durum: bulunamadı"
        all_files = all_recent_output_files(output_dir)
        filtered_files = filtered_recent_output_files(output_dir, self.recent_output_filter.get())
        if not all_files:
            return f"Klasör: {output_dir.name} | çıktı yok"
        latest_timestamp = time.strftime("%d.%m %H:%M", time.localtime(all_files[0].stat().st_mtime))
        return (
            f"Klasör: {output_dir.name} | "
            f"Görünen: {len(filtered_files)} / Toplam: {len(all_files)} | "
            f"Son güncelleme: {latest_timestamp}"
        )

    def current_recent_output_filter_detail(self) -> str:
        output_dir = self.current_recent_exports_dir()
        if not output_dir.exists():
            return ""
        filter_value = self.recent_output_filter.get()
        count = len(filtered_recent_output_files(output_dir, filter_value))
        if filter_value == "Tümü":
            return f"{count} öğe"
        return f"{filter_value} | {count} öğe"

    def update_recent_output_subtitle(self) -> None:
        try:
            self.recent_output_subtitle_text.set(self.build_recent_output_subtitle_text())
        except Exception:
            pass

    def update_recent_output_summary(self) -> None:
        try:
            self.update_recent_output_subtitle()
        except Exception:
            pass
        try:
            self.recent_output_summary_text.set(self.build_recent_output_summary_text())
        except Exception:
            pass
        try:
            self.recent_output_meta_text.set(self.build_recent_output_meta_text())
        except Exception:
            pass
        try:
            self.update_hero_overview_cards()
        except Exception:
            pass
        try:
            label = getattr(self, "recent_output_summary_label", None)
            if label is not None:
                label.configure(**self.build_recent_output_summary_palette())
        except Exception:
            pass

    def summary_card_style(self, bg: str, fg: str) -> dict[str, object]:
        return {
            "bg": bg,
            "fg": fg,
            "justify": "left",
            "wraplength": getattr(self, "section_wraplength", getattr(self, "content_wraplength", 620)),
            "padx": 9,
            "pady": 7,
        }

    def make_slider(self, parent: Frame, label: str, min_v: int, max_v: int, default: int) -> Scale:
        Label(parent, text=label, bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14)
        slider = Scale(
            parent,
            from_=min_v,
            to=max_v,
            orient=HORIZONTAL,
            length=getattr(self, "control_length", 620),
            resolution=1,
            bg="#151b22",
            fg="#dce6ef",
            command=self.on_slider_settings_changed,
        )
        slider.set(default)
        slider.pack(anchor="w", padx=14, pady=(0, 8))
        return slider

    def _on_content_configure(self, _event=None) -> None:
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except TclError:
            pass

    def ensure_desktop_geometry(self) -> None:
        try:
            current_w = self.root.winfo_width()
            current_h = self.root.winfo_height()
            if current_w < self.initial_window_width - 40 or current_h < self.initial_window_height - 40:
                self.root.geometry(
                    f"{self.initial_window_width}x{self.initial_window_height}+{self.initial_window_x}+{self.initial_window_y}"
                )
        except TclError:
            pass

    def _on_canvas_configure(self, event) -> None:
        try:
            available_width = max(960, event.width - 32)
            dashboard_width = min(getattr(self, "max_dashboard_width", available_width), available_width)
            self.canvas.coords(self.canvas_window, event.width / 2, 0)
            self.canvas.itemconfigure(self.canvas_window, width=dashboard_width)
            self.status_label.configure(wraplength=getattr(self, "section_wraplength", max(320, event.width - 36)))
        except TclError:
            pass

    def _on_mousewheel(self, event) -> None:
        try:
            if hasattr(event, "delta") and event.delta:
                step = -1 if event.delta > 0 else 1
            elif getattr(event, "num", None) == 4:
                step = -1
            elif getattr(event, "num", None) == 5:
                step = 1
            else:
                return
            self.canvas.yview_scroll(step, "units")
        except TclError:
            pass

    def set_status(self, text: str) -> None:
        def update() -> None:
            self.status_text.set(text)
            self.root.update_idletasks()

        if threading.current_thread() is threading.main_thread():
            try:
                update()
            except TclError:
                pass
            return

        try:
            self.root.after(0, update)
        except TclError:
            pass

    def missing_item_status(self, label: str) -> str:
        return f"{label} yok."

    def copied_item_status(self, label: str, filename: str) -> str:
        return f"{label} panoya alındı: {filename}"

    def finder_selected_status(self, label: str, filename: str) -> str:
        return f"{label} Finder'da seçildi: {filename}"

    def block_changes_during_recording(self, action_label: str) -> bool:
        if not getattr(self, "recording_active", False):
            return False
        self.set_status(f"Kayıt sürerken {action_label} değiştirilemez. Önce kaydı durdurun.")
        return True

    def show_about(self) -> None:
        self.set_status(
            f"Gitar Amfi Kaydedici {self.app_version} | Canlı izleme, kompresör/limiter, oturum klasörleri, oturum özeti ve son oturum geri yükleme desteklenir."
        )

    def clear_device_selection(self) -> None:
        if self.block_changes_during_recording("cihaz ayarları"):
            return
        self.input_device_choice.set("Varsayılan macOS girişi")
        self.output_device_choice.set("Varsayılan macOS çıkışı")
        self.input_device_id.set("")
        self.output_device_id.set("")
        self.restart_input_meter()
        self.set_status("Aygıt kimlikleri temizlendi. Varsayılan mikrofon ve çıkış kullanılacak.")

    def apply_clean_macbook_preset(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        input_options = [item for item in self.input_device_options if "MacBook Air Mikrofonu" in item]
        output_options = [item for item in self.output_device_options if "MacBook Air Hoparlörü" in item]
        self.input_device_choice.set(input_options[0] if input_options else "Varsayılan macOS girişi")
        self.output_device_choice.set(output_options[0] if output_options else "Varsayılan macOS çıkışı")

        self.preset_name.set("MacBook Mikrofon Hizli Kayit")
        self.gain.set(8)
        self.boost.set(0)
        self.high_pass_hz.set(70)
        self.bass.set(0)
        self.presence.set(1)
        self.treble.set(1)
        self.distortion.set(0)
        self.backing_level.set(100)
        self.vocal_level.set(100)
        self.noise_reduction.set(0)
        self.noise_gate_threshold.set(0)
        self.compressor_amount.set(0)
        self.compressor_threshold.set(-18)
        self.compressor_makeup.set(0)
        self.limiter_enabled.set("Acik")
        self.speed_ratio.set(100)
        self.output_gain.set(3)

        self.restart_input_meter()
        self.set_status("MacBook mikrofon hizli kayit preset uygulandi. Meter ile kontrol edip kayda gecebilirsiniz.")

    def apply_external_mic_preset(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        input_options = [item for item in self.input_device_options if "USB PnP Sound Device" in item]
        output_options = [item for item in self.output_device_options if "MacBook Air Hoparlörü" in item]
        self.input_device_choice.set(input_options[0] if input_options else "Varsayılan macOS girişi")
        self.output_device_choice.set(output_options[0] if output_options else "Varsayılan macOS çıkışı")

        self.gain.set(6)
        self.boost.set(4)
        self.high_pass_hz.set(90)
        self.bass.set(3)
        self.presence.set(2)
        self.treble.set(1)
        self.distortion.set(0)
        self.backing_level.set(100)
        self.vocal_level.set(85)
        self.noise_reduction.set(10)
        self.speed_ratio.set(100)
        self.output_gain.set(0)

        self.restart_input_meter()
        self.set_status("Harici mikrofon preset uygulandı. USB PnP girişini test edip kayda geçebilirsiniz.")

    def default_preset_store(self) -> dict:
        return builtin_preset_store()

    def load_preset_store_data(self) -> dict:
        if not GUI_PRESET_PATH.exists():
            return self.default_preset_store()
        try:
            raw = json.loads(GUI_PRESET_PATH.read_text(encoding="utf-8"))
        except Exception:
            return self.default_preset_store()
        if isinstance(raw, dict) and "presets" in raw and isinstance(raw.get("presets"), dict):
            selected = str(raw.get("selected", "Temiz Gitar") or "Temiz Gitar")
            favorites = raw.get("favorites", [])
            return merge_builtin_presets({"selected": selected, "favorites": favorites, "presets": raw["presets"]})
        if isinstance(raw, dict):
            return merge_builtin_presets({"selected": "Varsayilan", "presets": {"Varsayilan": raw}})
        return self.default_preset_store()

    def write_preset_store_data(self, store: dict) -> None:
        GUI_PRESET_PATH.parent.mkdir(parents=True, exist_ok=True)
        normalized = merge_builtin_presets(store)
        GUI_PRESET_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def preset_favorites(self, store: dict) -> set[str]:
        favorites = store.get("favorites", [])
        if not isinstance(favorites, list):
            return set()
        return {
            str(name)
            for name in favorites
            if isinstance(name, str) and str(name) in store.get("presets", {})
        }

    def preset_filter_term(self) -> str:
        return str(self.preset_filter.get() if hasattr(self, "preset_filter") else "").strip().casefold()

    def preset_favorites_only_enabled(self) -> bool:
        if not hasattr(self, "preset_favorites_only"):
            return False
        try:
            return str(self.preset_favorites_only.get()).strip().casefold() == "acik"
        except Exception:
            return False

    def current_preset_note(self) -> str:
        if not hasattr(self, "preset_note"):
            return ""
        try:
            return str(self.preset_note.get()).strip()
        except Exception:
            return ""

    def update_preset_note_meta_text(self) -> None:
        note = self.current_preset_note()
        self.preset_note_meta_text.set(f"{len(note)} karakter")

    def apply_preset_note_template(self, note: str) -> None:
        self.preset_note.set(note)
        self.update_preset_note_meta_text()
        self.set_status(f"Preset notu şablonu uygulandı: {note}")

    def clear_preset_note(self) -> None:
        self.preset_note.set("")
        self.update_preset_note_meta_text()
        self.set_status("Preset notu temizlendi.")

    def filtered_preset_names(self, store: dict, filter_text: Optional[str] = None) -> list[str]:
        names = self.ordered_preset_names(store)
        if self.preset_favorites_only_enabled():
            favorite_names = self.preset_favorites(store)
            names = [name for name in names if name in favorite_names]
        term = (filter_text if filter_text is not None else self.preset_filter_term()).strip().casefold()
        if not term:
            return names
        return [name for name in names if term in name.casefold()]

    def ordered_preset_names(self, store: dict) -> list[str]:
        names = sorted(store.get("presets", {}).keys()) or ["Temiz Gitar"]
        favorite_names = self.preset_favorites(store)
        if not favorite_names:
            return names
        favorites = [name for name in names if name in favorite_names]
        others = [name for name in names if name not in favorite_names]
        return favorites + others

    def display_preset_name(self, preset_name: str, store: dict) -> str:
        if preset_name in self.preset_favorites(store):
            return f"★ {preset_name}"
        return preset_name

    def update_preset_filter_meta(self, total_count: int, matched_count: int, filter_text: str) -> None:
        favorite_count = len(self.preset_favorites(self.load_preset_store_data()))
        favorite_suffix = f" | Favori: {favorite_count}" if favorite_count else " | Favori: 0"
        favorites_prefix = "Favoriler açık. " if self.preset_favorites_only_enabled() else ""
        if not filter_text:
            if self.preset_favorites_only_enabled():
                self.preset_filter_meta_text.set(
                    f"{favorites_prefix}Gösterilen favori presetler: {matched_count}/{total_count}{favorite_suffix}"
                )
            else:
                self.preset_filter_meta_text.set(f"{favorites_prefix}Tüm presetler gösteriliyor: {total_count}{favorite_suffix}")
            return
        if matched_count:
            self.preset_filter_meta_text.set(
                f'{favorites_prefix}Filtre "{filter_text}" için eşleşme: {matched_count}/{total_count}{favorite_suffix}'
            )
            return
        fallback_text = "Favori listesi gösteriliyor." if self.preset_favorites_only_enabled() else "Tam liste gösteriliyor."
        self.preset_filter_meta_text.set(
            f'{favorites_prefix}Filtre "{filter_text}" için eşleşme yok. {fallback_text}{favorite_suffix}'
        )

    def update_preset_scope_text(self, selected_name: str) -> None:
        builtin_names = set(builtin_preset_store().get("presets", {}).keys())
        if selected_name in builtin_names:
            self.preset_scope_text.set(f"Yerleşik preset seçili: {selected_name}")
            return
        self.preset_scope_text.set(f"Kullanıcı preset seçili: {selected_name}")

    def update_preset_favorite_text(self, selected_name: str, store: dict) -> None:
        favorites = sorted(self.preset_favorites(store))
        is_favorite = selected_name in favorites
        self.preset_favorite_text.set(f"Favori: {'evet' if is_favorite else 'hayır'}")
        if not favorites:
            self.preset_favorite_meta_text.set("Favori preset yok.")
            self.preset_favorite_quick_text.set("Hızlı favori yok.")
        else:
            preview = ", ".join(favorites[:3])
            extra = "" if len(favorites) <= 3 else f" +{len(favorites) - 3}"
            self.preset_favorite_meta_text.set(f"{len(favorites)} favori: {preview}{extra}")
            quick_parts = []
            presets = store.get("presets", {})
            for name in favorites[:2]:
                note = ""
                preset = presets.get(name, {})
                if isinstance(preset, dict):
                    note = str(preset.get("preset_note", "")).strip()
                quick_parts.append(f"{name} ({note})" if note else name)
            self.preset_favorite_quick_text.set(f"Hızlı favoriler: {' | '.join(quick_parts)}")
        self.preset_favorite_button_text.set("Favoriden Çıkar" if is_favorite else "Favoriye Ekle")
        self.preset_favorites_filter_button_text.set("Tüm Presetler" if self.preset_favorites_only_enabled() else "Sadece Favoriler")

    def update_preset_summary_text(self, selected_name: str, store: dict) -> None:
        preset = store.get("presets", {}).get(selected_name, {})
        if not isinstance(preset, dict):
            self.preset_summary_text.set(f"Preset özeti hazırlanamadı: {selected_name}")
            return
        gain = preset.get("gain", "-")
        vocal = preset.get("vocal_level", "-")
        output_gain = preset.get("output_gain", "-")
        note = str(preset.get("preset_note", "")).strip()
        summary = f"Gain: {gain} | Vokal: {vocal}% | Çıkış Kazancı: {output_gain} dB"
        if note:
            summary = f"{summary} | Not: {note}"
        self.preset_summary_text.set(summary)

    def on_preset_selected(self, selected_name: str) -> None:
        self.preset_name.set(selected_name)
        store = self.load_preset_store_data()
        preset = store.get("presets", {}).get(selected_name, {})
        self.preset_note.set(str(preset.get("preset_note", "")).strip() if isinstance(preset, dict) else "")
        self.update_preset_note_meta_text()
        self.update_preset_scope_text(selected_name)
        self.update_preset_favorite_text(selected_name, store)
        self.update_preset_summary_text(selected_name, store)

    def refresh_preset_menu(self, selected_name: Optional[str] = None) -> None:
        store = self.load_preset_store_data()
        all_names = self.ordered_preset_names(store)
        filtered_names = self.filtered_preset_names(store)
        names = filtered_names or all_names
        self.preset_names = names
        menu = self.preset_menu["menu"]
        menu.delete(0, "end")
        for name in self.preset_names:
            menu.add_command(label=self.display_preset_name(name, store), command=lambda value=name: self.on_preset_selected(value))
        target = selected_name or self.preset_name.get() or store.get("selected", "Temiz Gitar")
        if target not in self.preset_names:
            target = self.preset_names[0]
        self.preset_name.set(target)
        self.update_preset_filter_meta(len(all_names), len(filtered_names), str(self.preset_filter.get()).strip())
        self.update_preset_note_meta_text()
        self.update_preset_scope_text(target)
        self.update_preset_favorite_text(target, store)
        self.update_preset_summary_text(target, store)

    def apply_preset_filter(self) -> None:
        self.refresh_preset_menu()
        term = str(self.preset_filter.get()).strip()
        if term:
            self.set_status(f"Preset filtresi uygulandı: {term}")
        else:
            self.set_status("Preset filtresi kapalı. Tüm presetler gösteriliyor.")

    def clear_preset_filter(self) -> None:
        self.preset_filter.set("")
        self.refresh_preset_menu()
        self.set_status("Preset filtresi temizlendi.")

    def toggle_preset_favorites_filter(self) -> None:
        next_value = "kapali" if self.preset_favorites_only_enabled() else "acik"
        self.preset_favorites_only.set(next_value)
        self.refresh_preset_menu()
        if next_value == "acik":
            self.set_status("Sadece favori presetler gösteriliyor.")
        else:
            self.set_status("Tüm presetler gösteriliyor.")

    def load_preset_store(self, initial: bool = False) -> None:
        store = self.load_preset_store_data()
        self.refresh_preset_menu(store.get("selected", "Temiz Gitar"))
        presets = store.get("presets", {})
        selected = self.preset_name.get()
        if selected in presets:
            self.apply_preset_data(presets[selected])
            if not initial:
                self.set_status(f"Preset yüklendi: {selected}")
        elif initial:
            self.set_status("Hazır. Yeni preset oluşturabilirsiniz.")

    def apply_startup_preset(self) -> None:
        store = self.load_preset_store_data()
        if store.get("presets"):
            self.load_preset_store(initial=True)
        else:
            self.apply_clean_macbook_preset()
        last_session = self.load_last_session_state()
        if last_session:
            output_dir = str(last_session.get("output_dir", "")).strip()
            if output_dir:
                path = Path(output_dir)
                if normalize_choice(str(last_session.get("session_mode", "")), SESSION_MODE_ALIASES, "Tek Klasör") == "Tek Klasör":
                    self.output_dir.set(str(path))
                elif path.parent.exists():
                    self.output_dir.set(str(path.parent))
                    self.session_name.set(path.name)
            session_mode = str(last_session.get("session_mode", "")).strip()
            if session_mode:
                self.session_mode.set(session_mode)
            self.restore_last_session_paths(last_session)
            self.refresh_recent_exports()
            self.set_status(f"Son oturum hazır: {output_dir}")

    def collect_current_preset(self) -> dict:
        return {
            "input_device_choice": self.input_device_choice.get(),
            "output_device_choice": self.output_device_choice.get(),
            "input_device_id": self.input_device_id.get(),
            "output_device_id": self.output_device_id.get(),
            "output_name": self.output_name.get(),
            "output_dir": self.output_dir.get(),
            "session_mode": self.session_mode_value(),
            "session_name": self.session_name.get(),
            "mp3_quality": self.mp3_quality_value(),
            "wav_export_mode": self.wav_export_mode_value(),
            "preset_note": self.current_preset_note(),
            "record_limit_hours": self.record_limit_hours.get(),
            "mic_record_seconds": self.mic_record_seconds.get(),
            "gain": int(self.gain.get()),
            "boost": int(self.boost.get()),
            "high_pass_hz": int(self.high_pass_hz.get()),
            "bass": int(self.bass.get()),
            "presence": int(self.presence.get()),
            "treble": int(self.treble.get()),
            "distortion": int(self.distortion.get()),
            "backing_level": int(self.backing_level.get()),
            "vocal_level": int(self.vocal_level.get()),
            "noise_reduction": int(self.noise_reduction.get()),
            "noise_gate_threshold": int(self.noise_gate_threshold.get()),
            "monitor_level": int(self.monitor_level.get()),
            "compressor_amount": int(self.compressor_amount.get()),
            "compressor_threshold": int(self.compressor_threshold.get()),
            "compressor_makeup": int(self.compressor_makeup.get()),
            "limiter_enabled": self.limiter_enabled_value(),
            "speed_ratio": int(self.speed_ratio.get()),
            "output_gain": int(self.output_gain.get()),
        }

    def apply_preset_data(self, preset: dict) -> None:
        self.input_device_choice.set(str(preset.get("input_device_choice", "Varsayılan macOS girişi")))
        self.output_device_choice.set(str(preset.get("output_device_choice", "Varsayılan macOS çıkışı")))
        self.input_device_id.set(str(preset.get("input_device_id", "")))
        self.output_device_id.set(str(preset.get("output_device_id", "")))
        self.output_name.set(str(preset.get("output_name", self.output_name.get())))
        self.output_dir.set(str(preset.get("output_dir", self.output_dir.get())))
        self.session_mode.set(normalize_choice(str(preset.get("session_mode", self.session_mode.get())), SESSION_MODE_ALIASES, self.session_mode_value()))
        self.session_name.set(str(preset.get("session_name", self.session_name.get())))
        self.mp3_quality.set(normalize_choice(str(preset.get("mp3_quality", self.mp3_quality.get())), MP3_QUALITY_ALIASES, self.mp3_quality_value()))
        self.wav_export_mode.set(normalize_choice(str(preset.get("wav_export_mode", self.wav_export_mode.get())), WAV_EXPORT_MODE_ALIASES, self.wav_export_mode_value()))
        self.preset_note.set(str(preset.get("preset_note", "")))
        self.update_preset_note_meta_text()
        self.record_limit_hours.set(str(preset.get("record_limit_hours", "1")))
        self.mic_record_seconds.set(str(preset.get("mic_record_seconds", "60")))

        self.gain.set(int(preset.get("gain", 6)))
        self.boost.set(int(preset.get("boost", 6)))
        self.high_pass_hz.set(int(preset.get("high_pass_hz", 70)))
        self.bass.set(int(preset.get("bass", 3)))
        self.presence.set(int(preset.get("presence", 2)))
        self.treble.set(int(preset.get("treble", 2)))
        self.distortion.set(int(preset.get("distortion", 25)))
        self.backing_level.set(int(preset.get("backing_level", 100)))
        self.vocal_level.set(int(preset.get("vocal_level", 85)))
        self.noise_reduction.set(int(preset.get("noise_reduction", 10)))
        self.noise_gate_threshold.set(int(preset.get("noise_gate_threshold", 25)))
        self.monitor_level.set(int(preset.get("monitor_level", 100)))
        self.compressor_amount.set(int(preset.get("compressor_amount", 35)))
        self.compressor_threshold.set(int(preset.get("compressor_threshold", -18)))
        self.compressor_makeup.set(int(preset.get("compressor_makeup", 4)))
        self.limiter_enabled.set(normalize_choice(str(preset.get("limiter_enabled", "Açık")), LIMITER_ALIASES, "Açık"))
        self.speed_ratio.set(int(preset.get("speed_ratio", 100)))
        self.output_gain.set(int(preset.get("output_gain", 0)))

        self.restart_input_meter()

    def save_current_preset(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        try:
            store = self.load_preset_store_data()
            raw_name = self.preset_name.get().strip()
            selected_name = str(store.get("selected", "Temiz Gitar") or "Temiz Gitar")
            if not raw_name and selected_name in set(builtin_preset_store().get("presets", {}).keys()):
                self.set_status("Yeni bir preset adı girin.")
                return
            name = raw_name or selected_name
            if name in set(builtin_preset_store().get("presets", {}).keys()):
                self.set_status(f"Hazır preset üzerine kaydedilemez: {name}")
                return
            store.setdefault("presets", {})[name] = self.collect_current_preset()
            store["selected"] = name
            self.write_preset_store_data(store)
            self.refresh_preset_menu(name)
            self.set_status(f"Preset kaydedildi: {name}")
        except Exception as exc:
            self.set_status(f"Preset kaydetme hatası: {exc}")

    def load_saved_preset(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        try:
            store = self.load_preset_store_data()
            name = self.preset_name.get().strip() or store.get("selected", "Temiz Gitar")
            presets = store.get("presets", {})
            if name not in presets:
                self.set_status(f"Preset bulunamadı: {name}")
                return
            self.apply_preset_data(presets[name])
            store["selected"] = name
            self.write_preset_store_data(store)
            self.refresh_preset_menu(name)
            self.set_status(f"Preset yüklendi: {name}")
        except Exception as exc:
            self.set_status(f"Preset okuma hatası: {exc}")

    def delete_selected_preset(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        try:
            name = self.preset_name.get().strip()
            if not name:
                self.set_status("Silinecek preset seçilmedi.")
                return
            builtin_names = set(builtin_preset_store().get("presets", {}).keys())
            if name in builtin_names:
                self.set_status(f"Hazır preset silinemez: {name}")
                return
            store = self.load_preset_store_data()
            presets = store.get("presets", {})
            if name not in presets:
                self.set_status(f"Preset bulunamadı: {name}")
                return
            previous_selected = str(store.get("selected", "") or "")
            del presets[name]
            store["favorites"] = sorted(fav for fav in self.preset_favorites(store) if fav != name)
            if not presets:
                store = self.default_preset_store()
                self.write_preset_store_data(store)
                self.refresh_preset_menu("Temiz Gitar")
                self.set_status(f"Preset silindi: {name}. Tum kullanici presetleri temizlendi.")
                return
            next_name = previous_selected if previous_selected in presets else sorted(presets.keys())[0]
            store["selected"] = next_name
            self.write_preset_store_data(store)
            self.refresh_preset_menu(next_name)
            self.set_status(f"Preset silindi: {name}")
        except Exception as exc:
            self.set_status(f"Preset silme hatası: {exc}")

    def next_duplicate_preset_name(self, source_name: str, existing_names: set[str]) -> str:
        base_name = f"{source_name} Kopya"
        if base_name not in existing_names:
            return base_name
        index = 2
        while True:
            candidate = f"{source_name} Kopya {index}"
            if candidate not in existing_names:
                return candidate
            index += 1

    def safe_preset_export_name(self, preset_name: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in preset_name).strip()
        cleaned = cleaned.replace(" ", "_")
        return cleaned or "preset"

    def duplicate_selected_preset(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        try:
            store = self.load_preset_store_data()
            source_name = self.preset_name.get().strip() or str(store.get("selected", "Temiz Gitar") or "Temiz Gitar")
            presets = store.get("presets", {})
            if source_name not in presets:
                self.set_status(f"Preset bulunamadı: {source_name}")
                return
            duplicate_name = self.next_duplicate_preset_name(source_name, set(presets.keys()))
            store.setdefault("presets", {})[duplicate_name] = dict(presets[source_name])
            store["selected"] = duplicate_name
            self.write_preset_store_data(store)
            self.refresh_preset_menu(duplicate_name)
            self.set_status(f"Preset çoğaltıldı: {source_name} -> {duplicate_name}")
        except Exception as exc:
            self.set_status(f"Preset çoğaltma hatası: {exc}")

    def toggle_selected_preset_favorite(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        try:
            store = self.load_preset_store_data()
            name = self.preset_name.get().strip() or str(store.get("selected", "Temiz Gitar") or "Temiz Gitar")
            if name not in store.get("presets", {}):
                self.set_status(f"Preset bulunamadı: {name}")
                return
            favorites = self.preset_favorites(store)
            if name in favorites:
                favorites.remove(name)
                action_text = "Favoriden çıkarıldı"
            else:
                favorites.add(name)
                action_text = "Favoriye eklendi"
            store["favorites"] = sorted(favorites)
            store["selected"] = name
            self.write_preset_store_data(store)
            self.refresh_preset_menu(name)
            self.set_status(f"{action_text}: {name}")
        except Exception as exc:
            self.set_status(f"Preset favori güncelleme hatası: {exc}")

    def export_selected_preset_json(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        if not self.output_dir.get().strip():
            self.set_status("Preset JSON için önce kayıt klasörünü seçin.")
            return
        try:
            store = self.load_preset_store_data()
            name = self.preset_name.get().strip() or str(store.get("selected", "Temiz Gitar") or "Temiz Gitar")
            presets = store.get("presets", {})
            if name not in presets:
                self.set_status(f"Preset bulunamadı: {name}")
                return
            output_dir = self.resolve_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            export_name = f"{self.safe_preset_export_name(name)}.preset.json"
            export_path = output_dir / export_name
            export_path.write_text(
                json.dumps({"name": name, "preset": presets[name]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.set_status(f"Preset JSON yazıldı: {export_path}")
        except Exception as exc:
            self.set_status(f"Preset JSON yazılamadı: {exc}")

    def export_favorite_presets_json(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        if not self.output_dir.get().strip():
            self.set_status("Favori preset JSON için önce kayıt klasörünü seçin.")
            return
        try:
            store = self.load_preset_store_data()
            favorites = sorted(self.preset_favorites(store))
            if not favorites:
                self.set_status("Yazdırılacak favori preset yok.")
                return
            presets = store.get("presets", {})
            output_dir = self.resolve_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            export_path = output_dir / "favori_presetler.json"
            payload = {
                "count": len(favorites),
                "favorites": [
                    {"name": name, "preset": presets[name]}
                    for name in favorites
                    if name in presets
                ],
            }
            export_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.set_status(f"Favori preset JSON yazıldı: {export_path}")
        except Exception as exc:
            self.set_status(f"Favori preset JSON yazılamadı: {exc}")

    def copy_favorite_presets_to_clipboard(self) -> None:
        try:
            store = self.load_preset_store_data()
            favorites = sorted(self.preset_favorites(store))
            if not favorites:
                self.set_status("Kopyalanacak favori preset yok.")
                return
            content = "Favori Presetler\n" + "\n".join(f"- {name}" for name in favorites)
            self.copy_text_to_clipboard(
                content,
                "Favori preset listesi panoya alındı",
                "Favori preset listesi kopyalanamadı",
            )
        except Exception as exc:
            self.set_status(f"Favori preset listesi kopyalanamadı: {exc}")

    def copy_quick_favorites_to_clipboard(self) -> None:
        try:
            store = self.load_preset_store_data()
            selected_name = str(self.preset_name.get()).strip() or store.get("selected", "Temiz Gitar")
            self.update_preset_favorite_text(selected_name, store)
            content = str(self.preset_favorite_quick_text.get()).strip()
            if not content or content == "Hızlı favori yok.":
                self.set_status("Kopyalanacak hızlı favori özeti yok.")
                return
            self.copy_text_to_clipboard(
                content,
                "Hızlı favori özeti panoya alındı",
                "Hızlı favori özeti kopyalanamadı",
            )
        except Exception as exc:
            self.set_status(f"Hızlı favori özeti kopyalanamadı: {exc}")

    def export_quick_favorites_summary(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        if not self.output_dir.get().strip():
            self.set_status("Favori özeti için önce kayıt klasörünü seçin.")
            return
        try:
            store = self.load_preset_store_data()
            selected_name = str(self.preset_name.get()).strip() or store.get("selected", "Temiz Gitar")
            self.update_preset_favorite_text(selected_name, store)
            content = str(self.preset_favorite_quick_text.get()).strip()
            if not content or content == "Hızlı favori yok.":
                self.set_status("Yazdırılacak hızlı favori özeti yok.")
                return
            output_dir = self.resolve_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            export_path = output_dir / "favori_ozeti.txt"
            export_path.write_text(content, encoding="utf-8")
            self.set_status(f"Favori özeti yazıldı: {export_path}")
        except Exception as exc:
            self.set_status(f"Favori özeti yazılamadı: {exc}")

    def export_quick_favorites_markdown(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        if not self.output_dir.get().strip():
            self.set_status("Favori Markdown özeti için önce kayıt klasörünü seçin.")
            return
        try:
            store = self.load_preset_store_data()
            selected_name = str(self.preset_name.get()).strip() or store.get("selected", "Temiz Gitar")
            self.update_preset_favorite_text(selected_name, store)
            favorites = sorted(self.preset_favorites(store))
            if not favorites:
                self.set_status("Yazdırılacak favori Markdown özeti yok.")
                return
            presets = store.get("presets", {})
            lines = ["# Favori Presetler", ""]
            for name in favorites:
                note = ""
                preset = presets.get(name, {})
                if isinstance(preset, dict):
                    note = str(preset.get("preset_note", "")).strip()
                lines.append(f"- **{name}**" + (f": {note}" if note else ""))
            output_dir = self.resolve_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            export_path = output_dir / "favori_ozeti.md"
            export_path.write_text("\n".join(lines), encoding="utf-8")
            self.set_status(f"Favori Markdown özeti yazıldı: {export_path}")
        except Exception as exc:
            self.set_status(f"Favori Markdown özeti yazılamadı: {exc}")

    def quick_favorites_summary_path(self) -> Optional[Path]:
        if not self.output_dir.get().strip():
            return None
        output_dir = self.resolve_output_dir()
        markdown_path = output_dir / "favori_ozeti.md"
        text_path = output_dir / "favori_ozeti.txt"
        if markdown_path.exists():
            return markdown_path
        if text_path.exists():
            return text_path
        return None

    def open_quick_favorites_summary_in_finder(self) -> None:
        summary_path = self.quick_favorites_summary_path()
        if summary_path is None or not summary_path.exists():
            self.set_status("Favori özeti dosyası yok.")
            return
        try:
            subprocess.run(["open", "-R", str(summary_path)], check=False)
            self.set_status(self.finder_selected_status("Favori özeti", summary_path.name))
        except Exception as exc:
            self.set_status(f"Favori özeti açılamadı: {exc}")

    def import_favorite_presets_json(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        try:
            file_path = filedialog.askopenfilename(
                title="Favori Preset JSON Aç",
                filetypes=[("JSON", "*.json"), ("Tüm Dosyalar", "*.*")],
            )
            if not file_path:
                self.set_status("Favori preset JSON seçilmedi.")
                return
            source_path = Path(file_path)
            raw = json.loads(source_path.read_text(encoding="utf-8"))
            favorites_payload = raw.get("favorites") if isinstance(raw, dict) else None
            if not isinstance(favorites_payload, list):
                self.set_status(f"Favori preset JSON geçersiz: {source_path.name}")
                return
            store = self.load_preset_store_data()
            presets = store.setdefault("presets", {})
            favorite_names = self.preset_favorites(store)
            imported_names: list[str] = []
            for item in favorites_payload:
                if not isinstance(item, dict) or not isinstance(item.get("preset"), dict):
                    continue
                source_name = str(item.get("name", "")).strip() or "İçe Aktarılan Favori"
                target_name = self.import_selected_preset_name(source_name, set(presets.keys()))
                presets[target_name] = dict(item["preset"])
                favorite_names.add(target_name)
                imported_names.append(target_name)
            if not imported_names:
                self.set_status(f"Favori preset JSON geçersiz: {source_path.name}")
                return
            store["favorites"] = sorted(favorite_names)
            store["selected"] = imported_names[-1]
            self.write_preset_store_data(store)
            self.refresh_preset_menu(imported_names[-1])
            self.set_status(f"{len(imported_names)} favori preset içe aktarıldı.")
        except Exception as exc:
            self.set_status(f"Favori preset JSON okunamadı: {exc}")

    def import_selected_preset_name(self, source_name: str, existing_names: set[str]) -> str:
        if source_name not in existing_names and source_name not in set(builtin_preset_store().get("presets", {}).keys()):
            return source_name
        return self.next_duplicate_preset_name(source_name, existing_names)

    def import_preset_json(self) -> None:
        if self.block_changes_during_recording("preset"):
            return
        try:
            file_path = filedialog.askopenfilename(
                title="Preset JSON Aç",
                filetypes=[("Preset JSON", "*.preset.json"), ("JSON", "*.json"), ("Tüm Dosyalar", "*.*")],
            )
            if not file_path:
                self.set_status("Preset JSON seçilmedi.")
                return
            source_path = Path(file_path)
            raw = json.loads(source_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("preset"), dict):
                source_name = str(raw.get("name", "")).strip() or source_path.stem.replace(".preset", "")
                preset_data = raw["preset"]
            elif isinstance(raw, dict):
                source_name = source_path.stem.replace(".preset", "")
                preset_data = raw
            else:
                self.set_status(f"Preset JSON geçersiz: {source_path.name}")
                return
            store = self.load_preset_store_data()
            target_name = self.import_selected_preset_name(source_name or "İçe Aktarılan Preset", set(store.get("presets", {}).keys()))
            store.setdefault("presets", {})[target_name] = dict(preset_data)
            store["selected"] = target_name
            self.write_preset_store_data(store)
            self.refresh_preset_menu(target_name)
            self.set_status(f"Preset içe aktarıldı: {target_name}")
        except Exception as exc:
            self.set_status(f"Preset JSON okunamadı: {exc}")

    def fill_recommended_devices(self) -> None:
        if self.block_changes_during_recording("cihaz ayarları"):
            return
        inputs = list_input_devices()
        outputs = list_output_devices()
        if inputs:
            self.input_device_id.set(str(inputs[0][0]))
            self.input_device_choice.set(f"{inputs[0][0]} - {inputs[0][1]}")
        if outputs:
            self.output_device_id.set(str(outputs[0][0]))
            self.output_device_choice.set(f"{outputs[0][0]} - {outputs[0][1]}")
        if not inputs:
            self.set_status(no_device_help_text())
            return
        self.restart_input_meter()
        input_text = f"{inputs[0][0]} - {inputs[0][1]}"
        output_text = f"{outputs[0][0]} - {outputs[0][1]}" if outputs else "varsayılan çıkış"
        self.set_status(f"Önerilen aygıtlar dolduruldu. Giriş: {input_text} | Çıkış: {output_text}")

    def select_output_dir(self) -> None:
        if self.block_changes_during_recording("çıkış klasörü"):
            return
        selected_dir = filedialog.askdirectory(title="Çıkış klasörünü seç")
        if not selected_dir:
            return
        self.output_dir.set(selected_dir)
        self.set_status(f"Çıkış klasörü seçildi: {selected_dir}")
        self.refresh_recent_exports()

    def resolve_output_dir(self) -> Path:
        base_dir = Path(self.output_dir.get().strip() or str(Path.home() / "Desktop")).expanduser()
        mode = self.session_mode_value()
        if mode == "Tarihli Oturum":
            return base_dir / time.strftime("%Y-%m-%d_%H-%M-%S")
        if mode == "İsimli Oturum":
            session_name = self.session_name.get().strip() or time.strftime("session_%Y%m%d")
            safe_name = "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in session_name).strip() or "session"
            return base_dir / safe_name
        return base_dir

    def safe_session_name(self) -> str:
        session_name = self.session_name.get().strip() or time.strftime("session_%Y%m%d")
        return "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in session_name).strip() or "session"

    def preview_output_dir(self) -> Path:
        base_dir = Path(self.output_dir.get().strip() or str(Path.home() / "Desktop")).expanduser()
        mode = self.session_mode.get()
        if mode == "Tarihli Oturum":
            return base_dir / "<tarihli-oturum>"
        if mode == "Isimli Oturum":
            return base_dir / self.safe_session_name()
        return base_dir

    def planned_export_summary(self) -> str:
        targets: list[str] = []
        if self.should_export_mp3():
            targets.append(f"MP3 ({self.mp3_quality.get()})")
        if self.should_export_mix_wav():
            targets.append("Mix WAV")
        targets.append("Vocal WAV")
        return " + ".join(targets)

    def planned_source_summary(self) -> str:
        if self.backing_file is not None:
            return f"{self.backing_file.name} + mikrofon"
        return "Sadece mikrofon"

    def planned_duration_summary(self) -> str:
        if self.backing_file is not None:
            return "Backing dosyasi boyunca (ust sinir kayit limiti)"
        try:
            record_seconds = float(self.mic_record_seconds.get().strip())
        except ValueError:
            record_seconds = 60.0
        record_seconds = max(5.0, min(record_seconds, 7200.0))
        limit_hours = self.record_limit_hours.get().strip() or "1"
        return f"{record_seconds:.0f} sn (ust sinir {limit_hours} saat)"

    def planned_readiness_summary(self) -> str:
        if not self.output_dir.get().strip():
            return "Cikis klasoru secilmedi. Once klasoru belirleyin."
        if self.last_input_peak >= 0.985:
            return "Uyari: giris clipping yapiyor. Kayittan once gain dusurun."
        if self.last_input_peak >= 0.05:
            return "Hazir gorunuyor. Once 5 saniyelik test yapip sonra kayda gecin."
        return "Seviye kontrolu bekleniyor. Meter veya 5 saniyelik test ile girisi dogrulayin."

    def build_recording_readiness_summary(self) -> str:
        target_dir = self.preview_output_dir()
        manual_name = self.output_name.get().strip() or f"guitar_mix_{time.strftime('%Y%m%d_%H%M%S')}"
        quick_name = next_timestamped_take_name_for_dir(target_dir, "quick_take")
        lines = [
            "Hazirlik ozeti:",
            f"Preset: {self.preset_name.get()}",
            f"Kaynak: {self.planned_source_summary()}",
            f"Hedef klasor: {target_dir}",
            f"Tam kayit adi: {manual_name}",
            f"Quick kayit adi: {quick_name}",
            f"Ciktilar: {self.planned_export_summary()}",
            f"Sure plani: {self.planned_duration_summary()}",
            f"Durum: {self.planned_readiness_summary()}",
        ]
        preset_note = self.current_preset_note()
        if preset_note:
            lines.insert(2, f"Preset Notu: {preset_note}")
        return "\n".join(lines)

    def refresh_recording_readiness(self, *_args) -> None:
        if self.recording_active:
            return
        self.record_progress_text.set(self.build_recording_readiness_summary())

    def build_session_summary(
        self,
        output_dir: Path,
        generated_files: list[Path],
        event: str,
        recording_stats: Optional[dict] = None,
    ) -> dict:
        return {
            "app_version": self.app_version,
            "event": event,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "output_dir": str(output_dir),
            "preset_name": self.preset_name.get(),
            "preset_note": self.current_preset_note(),
            "session_mode": self.session_mode_value(),
            "session_name": self.session_name.get(),
            "input_device_choice": self.input_device_choice.get(),
            "output_device_choice": self.output_device_choice.get(),
            "input_device_id": self.input_device_id.get(),
            "output_device_id": self.output_device_id.get(),
            "backing_file": str(self.backing_file) if self.backing_file else "",
            "export": {
                "output_name": self.output_name.get(),
                "mp3_quality": self.mp3_quality_value(),
                "wav_export_mode": self.wav_export_mode_value(),
                "record_limit_hours": self.record_limit_hours.get(),
                "mic_record_seconds": self.mic_record_seconds.get(),
            },
            "tone": {
                "gain": int(self.gain.get()),
                "boost": int(self.boost.get()),
                "high_pass_hz": int(self.high_pass_hz.get()),
                "bass": int(self.bass.get()),
                "presence": int(self.presence.get()),
                "treble": int(self.treble.get()),
                "distortion": int(self.distortion.get()),
            },
            "mix": {
                "backing_level": int(self.backing_level.get()),
                "vocal_level": int(self.vocal_level.get()),
                "noise_reduction": int(self.noise_reduction.get()),
                "noise_gate_threshold": int(self.noise_gate_threshold.get()),
                "monitor_level": int(self.monitor_level.get()),
                "compressor_amount": int(self.compressor_amount.get()),
                "compressor_threshold": int(self.compressor_threshold.get()),
                "compressor_makeup": int(self.compressor_makeup.get()),
                "limiter_enabled": self.limiter_enabled_value(),
                "speed_ratio": int(self.speed_ratio.get()),
                "output_gain": int(self.output_gain.get()),
            },
            "generated_files": [str(path) for path in generated_files],
            "artifacts": {
                "session_summary": str(output_dir / "session_summary.json"),
                "take_notes": str(output_dir / "take_notes.txt"),
            },
            "recording": recording_stats or {},
        }

    def write_session_summary(
        self,
        output_dir: Path,
        generated_files: list[Path],
        event: str,
        recording_stats: Optional[dict] = None,
    ) -> Optional[Path]:
        try:
            summary_path = output_dir / "session_summary.json"
            summary = self.build_session_summary(output_dir, generated_files, event, recording_stats)
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return summary_path
        except Exception:
            return None

    def build_take_notes_text(self, summary: dict) -> str:
        recording = summary.get("recording", {})
        generated_files = summary.get("generated_files", [])
        clip_warning = str(
            recording.get(
                "clip_warning",
                describe_clip_warning(
                    float(recording.get("input_peak", 0.0)),
                    float(recording.get("processed_peak", 0.0)),
                    float(recording.get("mix_peak", 0.0)),
                ),
            )
        )
        lines = [
            f"Olay: {summary.get('event', 'bilinmiyor')}",
            f"Tarih: {summary.get('timestamp', 'bilinmiyor')}",
            f"Klasör: {summary.get('output_dir', 'bilinmiyor')}",
            f"Preset: {summary.get('preset_name', 'bilinmiyor') or 'bilinmiyor'}",
            f"Clip Durumu: {clip_warning}",
        ]
        preset_note = str(summary.get("preset_note", "")).strip()
        if preset_note:
            lines.append(f"Preset Notu: {preset_note}")
        if recording.get("mode"):
            lines.append(f"Mod: {recording['mode']}")
        if "duration_seconds" in recording:
            lines.append(f"Sure: {format_seconds_short(float(recording.get('duration_seconds', 0.0)))}")
        if "requested_duration_seconds" in recording:
            lines.append(f"Hedef Sure: {format_seconds_short(float(recording.get('requested_duration_seconds', 0.0)))}")
        if "input_peak" in recording:
            lines.append(f"Giris Peak: {float(recording.get('input_peak', 0.0)):.3f}")
        if "processed_peak" in recording:
            lines.append(f"Islenmis Peak: {float(recording.get('processed_peak', 0.0)):.3f}")
        if "mix_peak" in recording:
            lines.append(f"Mix Peak: {float(recording.get('mix_peak', 0.0)):.3f}")
        if recording.get("stopped_early"):
            lines.append("Durum: erken durduruldu")
        if generated_files:
            lines.append("Dosyalar:")
            lines.extend([f"- {Path(path).name}" for path in generated_files])
        return "\n".join(lines)

    def write_take_notes(self, output_dir: Path, summary: dict) -> Optional[Path]:
        try:
            take_notes_path = output_dir / "take_notes.txt"
            take_notes_path.write_text(self.build_take_notes_text(summary), encoding="utf-8")
            return take_notes_path
        except Exception:
            return None

    def remember_completed_take_name(self, base_name: str) -> None:
        try:
            self.output_name.set(base_name)
        except Exception:
            pass

    def notify_success(self) -> None:
        try:
            self.root.bell()
        except Exception:
            pass

    def restore_previous_success_paths(
        self,
        output_dir: Optional[Path],
        export_path: Optional[Path],
        summary_path: Optional[Path],
        take_notes_path: Optional[Path],
    ) -> None:
        self.last_output_dir = output_dir
        self.last_export_path = export_path
        self.last_summary_path = summary_path
        self.last_take_notes_path = take_notes_path

    def write_last_session_state(self, output_dir: Path, summary_path: Optional[Path] = None) -> None:
        try:
            data = {
                "app_version": self.app_version,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "output_dir": str(output_dir),
                "session_mode": self.session_mode_value(),
                "session_name": self.session_name.get(),
                "preset_name": self.preset_name.get(),
                "last_export_path": str(self.last_export_path) if self.last_export_path else "",
                "take_notes_path": str(self.last_take_notes_path) if self.last_take_notes_path else "",
                "recovery_note_path": str(self.last_recovery_note_path) if self.last_recovery_note_path else "",
                "preparation_summary_path": str(self.last_preparation_summary_path) if self.last_preparation_summary_path else "",
                "summary_path": str(summary_path) if summary_path else "",
            }
            LAST_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
            LAST_SESSION_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_last_session_state(self) -> dict:
        if not LAST_SESSION_PATH.exists():
            return {}
        try:
            data = json.loads(LAST_SESSION_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def restore_last_session_paths(self, data: dict) -> None:
        output_dir = str(data.get("output_dir", "")).strip()
        output_path = Path(output_dir) if output_dir else None
        self.last_output_dir = output_path if output_path is not None and output_path.exists() else None

        export_path = str(data.get("last_export_path", "")).strip()
        if export_path:
            export_file = Path(export_path)
            self.last_export_path = export_file if export_file.exists() else None
        elif self.last_output_dir is not None:
            self.last_export_path = latest_audio_file_in_dir(self.last_output_dir)
        else:
            self.last_export_path = None

        summary_path = str(data.get("summary_path", "")).strip()
        if summary_path:
            path = Path(summary_path)
            self.last_summary_path = path if path.exists() else None
        elif self.last_output_dir is not None:
            fallback_summary_path = self.last_output_dir / "session_summary.json"
            self.last_summary_path = fallback_summary_path if fallback_summary_path.exists() else None
        else:
            self.last_summary_path = None

        take_notes_path = str(data.get("take_notes_path", "")).strip()
        if take_notes_path:
            path = Path(take_notes_path)
            self.last_take_notes_path = path if path.exists() else None
        elif self.last_output_dir is not None:
            fallback_take_notes_path = self.last_output_dir / "take_notes.txt"
            self.last_take_notes_path = fallback_take_notes_path if fallback_take_notes_path.exists() else None
        else:
            self.last_take_notes_path = None

        recovery_note_path = str(data.get("recovery_note_path", "")).strip()
        if recovery_note_path:
            path = Path(recovery_note_path)
            self.last_recovery_note_path = path if path.exists() else None
        elif self.last_output_dir is not None:
            fallback_recovery_note_path = self.last_output_dir / "export_recovery_note.txt"
            self.last_recovery_note_path = fallback_recovery_note_path if fallback_recovery_note_path.exists() else None
        else:
            self.last_recovery_note_path = None

        preparation_summary_path = str(data.get("preparation_summary_path", "")).strip()
        if preparation_summary_path:
            path = Path(preparation_summary_path)
            self.last_preparation_summary_path = path if path.exists() else None
        elif self.last_output_dir is not None:
            fallback_prep_path = self.last_output_dir / "preparation_summary.txt"
            self.last_preparation_summary_path = fallback_prep_path if fallback_prep_path.exists() else None
        else:
            self.last_preparation_summary_path = None

    def reload_last_session(self) -> None:
        if self.block_changes_during_recording("oturum bilgisi"):
            return
        data = self.load_last_session_state()
        if not data:
            self.set_status("Son oturum bilgisi bulunamadi.")
            return
        output_dir = str(data.get("output_dir", "")).strip()
        if output_dir:
            path = Path(output_dir)
            if path.parent.exists():
                if normalize_choice(str(data.get("session_mode", "")), SESSION_MODE_ALIASES, "Tek Klasör") == "Tek Klasör":
                    self.output_dir.set(str(path))
                else:
                    self.output_dir.set(str(path.parent))
                    self.session_name.set(path.name)
        session_mode = str(data.get("session_mode", "")).strip()
        if session_mode:
            self.session_mode.set(session_mode)
        preset_name = str(data.get("preset_name", "")).strip()
        if preset_name:
            self.preset_name.set(preset_name)
            self.load_saved_preset()
        self.restore_last_session_paths(data)
        self.refresh_recent_exports()
        self.update_compact_status_summary()
        self.update_recording_prep_summary()
        self.update_next_step_summary()
        self.update_readiness_summary()
        self.update_preflight_warning_summary()
        self.update_action_guidance_summary()
        self.update_recent_output_summary()
        self.set_status(f"Son oturum yuklendi: {output_dir or 'bilinmiyor'}")

    def session_state_available(self) -> bool:
        return any(
            path is not None
            for path in (
                self.last_output_dir,
                self.last_export_path,
                self.last_summary_path,
                self.last_take_notes_path,
                self.last_recovery_note_path,
                self.last_preparation_summary_path,
            )
        ) or LAST_SESSION_PATH.exists()

    def update_reset_session_state_button_state(self) -> None:
        button = getattr(self, "reset_session_state_button", None)
        if button is None:
            return
        state = "normal" if self.session_state_available() else "disabled"
        button.configure(state=state)

    def clear_last_session_state_file(self) -> None:
        try:
            if LAST_SESSION_PATH.exists():
                LAST_SESSION_PATH.unlink()
        except Exception:
            pass

    def reset_session_state(self) -> None:
        if self.block_changes_during_recording("oturum durumu"):
            return
        self.last_output_dir = None
        self.last_export_path = None
        self.last_summary_path = None
        self.last_take_notes_path = None
        self.last_recovery_note_path = None
        self.last_preparation_summary_path = None
        self.clear_last_session_state_file()
        self.refresh_recent_exports()
        self.update_compact_status_summary()
        self.update_recording_prep_summary()
        self.update_next_step_summary()
        self.update_readiness_summary()
        self.update_preflight_warning_summary()
        self.update_action_guidance_summary()
        self.update_recent_output_summary()
        self.set_status("Oturum durumu sıfırlandı. Yeni kayıt için temiz başlangıç hazır.")

    def current_recent_exports_dir(self) -> Path:
        if self.last_output_dir is not None and self.last_output_dir.exists():
            return self.last_output_dir
        return self.resolve_output_dir()

    def current_filtered_recent_audio_file(self) -> Optional[Path]:
        output_dir = self.current_recent_exports_dir()
        recent_files = filtered_recent_output_files(output_dir, self.recent_output_filter.get())
        for path in recent_files:
            if path.suffix.lower() in {".mp3", ".wav"}:
                return path
        return None

    def current_filtered_recent_output_file(self) -> Optional[Path]:
        output_dir = self.current_recent_exports_dir()
        recent_files = filtered_recent_output_files(output_dir, self.recent_output_filter.get())
        return recent_files[0] if recent_files else None

    def refresh_recent_exports(self) -> None:
        output_dir = self.current_recent_exports_dir()
        if not output_dir.exists():
            self.recent_exports_text.set(f"Klasör bulunamadı: {output_dir}")
            self.update_reset_session_state_button_state()
            self.update_archive_last_session_button_state(output_dir)
            self.update_cleanup_old_trials_button_state(output_dir)
            self.update_recent_output_summary()
            return
        recent_files = filtered_recent_output_files(output_dir, self.recent_output_filter.get())[:8]
        if not recent_files:
            self.recent_exports_text.set(f"{self.recent_output_filter.get()} filtresine uygun çıktı yok.")
            self.update_reset_session_state_button_state()
            self.update_archive_last_session_button_state(output_dir)
            self.update_cleanup_old_trials_button_state(output_dir)
            self.update_recent_output_summary()
            return
        lines = [recent_output_file_line(path) for path in recent_files]
        latest_audio = latest_audio_file_in_dir(output_dir)
        if latest_audio is not None:
            self.recent_exports_text.set(f"{recent_audio_highlight_line(latest_audio)}\n\n" + "\n".join(lines))
        else:
            self.recent_exports_text.set("\n".join(lines))
        self.update_reset_session_state_button_state()
        self.update_archive_last_session_button_state(output_dir)
        self.update_cleanup_old_trials_button_state(output_dir)
        self.update_recent_output_summary()

    def current_session_archive_candidates(self, output_dir: Optional[Path] = None) -> list[Path]:
        target_dir = output_dir or self.current_recent_exports_dir()
        if not target_dir.exists():
            return []
        candidates: list[Path] = []
        candidates.extend(path for path in generated_files_from_summary_path(self.last_summary_path) if path.parent == target_dir)
        for path in (
            self.last_summary_path,
            self.last_take_notes_path,
            self.last_recovery_note_path,
            self.last_preparation_summary_path,
        ):
            if path is not None and path.exists() and path.parent == target_dir:
                candidates.append(path)
        unique_candidates: list[Path] = []
        seen: set[Path] = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            unique_candidates.append(path)
        return unique_candidates

    def update_archive_last_session_button_state(self, output_dir: Optional[Path] = None) -> None:
        button = getattr(self, "archive_last_session_button", None)
        if button is None:
            return
        target_dir = output_dir or self.current_recent_exports_dir()
        state = "normal" if self.current_session_archive_candidates(target_dir) else "disabled"
        button.configure(state=state)

    def archive_last_session_outputs(self) -> None:
        output_dir = self.current_recent_exports_dir()
        if not output_dir.exists():
            self.set_status(f"Klasör bulunamadı: {output_dir}")
            self.update_archive_last_session_button_state(output_dir)
            return
        candidates = self.current_session_archive_candidates(output_dir)
        if not candidates:
            self.set_status("Arşivlenecek son oturum dosyası yok.")
            self.update_archive_last_session_button_state(output_dir)
            return
        archive_dir = session_archive_dir(output_dir, self.last_export_path)
        archive_dir.mkdir(parents=True, exist_ok=True)
        moved_paths: dict[Path, Path] = {}
        moved_count = 0
        for path in candidates:
            destination = archive_dir / path.name
            try:
                shutil.move(str(path), str(destination))
                moved_paths[path] = destination
                moved_count += 1
            except Exception:
                continue
        if moved_count == 0:
            self.set_status("Son oturum arşivlenemedi.")
            self.update_archive_last_session_button_state(output_dir)
            return
        if self.last_export_path in moved_paths:
            self.last_export_path = latest_audio_file_in_dir(output_dir)
        if self.last_summary_path in moved_paths:
            self.last_summary_path = None
        if self.last_take_notes_path in moved_paths:
            self.last_take_notes_path = None
        if self.last_recovery_note_path in moved_paths:
            self.last_recovery_note_path = None
        if self.last_preparation_summary_path in moved_paths:
            self.last_preparation_summary_path = None
        self.write_last_session_state(output_dir, self.last_summary_path)
        self.refresh_recent_exports()
        self.set_status(f"Son oturum arşivlendi: {archive_dir.name} ({moved_count} dosya)")

    def update_cleanup_old_trials_button_state(self, output_dir: Optional[Path] = None) -> None:
        button = getattr(self, "cleanup_old_trials_button", None)
        if button is None:
            return
        target_dir = output_dir or self.current_recent_exports_dir()
        state = "normal" if cleanup_candidate_output_files(target_dir) else "disabled"
        button.configure(state=state)

    def clean_old_trial_outputs(self) -> None:
        output_dir = self.current_recent_exports_dir()
        if not output_dir.exists():
            self.set_status(f"Klasör bulunamadı: {output_dir}")
            self.update_cleanup_old_trials_button_state(output_dir)
            return
        candidates = cleanup_candidate_output_files(output_dir)
        if not candidates:
            self.set_status("Temizlenecek eski deneme yok.")
            self.update_cleanup_old_trials_button_state(output_dir)
            return
        removed_count = 0
        for path in candidates:
            try:
                path.unlink()
                removed_count += 1
            except Exception:
                continue
        self.refresh_recent_exports()
        self.set_status(f"Eski denemeler temizlendi: {removed_count} dosya")

    def copy_text_to_clipboard(self, content: str, success_message: str, failure_prefix: str) -> None:
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.root.update()
            self.set_status(success_message)
        except Exception as exc:
            self.set_status(f"{failure_prefix}: {exc}")

    def copy_recent_outputs_to_clipboard(self) -> None:
        content = str(self.recent_exports_text.get()).strip()
        if not content:
            self.set_status("Kopyalanacak çıktı listesi yok.")
            return
        self.copy_text_to_clipboard(
            content,
            "Son çıktı listesi panoya alındı",
            "Son çıktı listesi kopyalanamadı",
        )

    def open_output_dir_in_finder(self) -> None:
        output_dir = self.current_recent_exports_dir()
        if not output_dir.exists():
            self.set_status(f"Klasör bulunamadı: {output_dir}")
            return
        try:
            subprocess.run(["open", str(output_dir)], check=False)
            self.set_status(f"Klasör açıldı: {output_dir.name}")
        except Exception as exc:
            self.set_status(f"Klasör açılamadı: {exc}")

    def current_share_audio_path(self) -> Optional[Path]:
        if self.last_export_path is not None and self.last_export_path.exists():
            return self.last_export_path
        audio_path = self.current_filtered_recent_audio_file()
        if audio_path is not None and audio_path.exists():
            return audio_path
        return None

    def default_share_title_for_audio(self, audio_path: Path) -> str:
        return audio_path.stem.replace("_", " ").strip() or "Yeni kayıt"

    def default_share_description_for_audio(self, audio_path: Path) -> str:
        parts = [f"Kayıt: {audio_path.stem.replace('_', ' ')}", f"Preset: {self.preset_name.get().strip() or 'Temiz Gitar'}"]
        note = self.current_preset_note()
        if note:
            parts.append(f"Not: {note}")
        return " | ".join(parts)

    def share_template_audio_label(self, audio_path: Optional[Path]) -> str:
        if audio_path is None:
            return "Yeni kayıt"
        return audio_path.stem.replace("_", " ").strip() or "Yeni kayıt"

    def share_template_note_suffix(self) -> str:
        note = self.current_preset_note()
        if not note:
            return ""
        return f" | Not: {note}"

    def share_template_values(self, template_name: str, audio_path: Optional[Path] = None) -> tuple[str, str]:
        source_audio = audio_path or self.current_share_audio_path()
        audio_label = self.share_template_audio_label(source_audio)
        preset_name = self.preset_name.get().strip() or "Temiz Gitar"
        note_suffix = self.share_template_note_suffix()
        normalized = template_name.strip().lower()
        if normalized == "canlı":
            return (
                f"{audio_label} | Canlı Kayıt",
                f"Canlı kayıt paylaşımı | Kayıt: {audio_label} | Preset: {preset_name}{note_suffix}",
            )
        if normalized == "temiz gitar":
            return (
                f"{audio_label} | Temiz Gitar Tonu",
                f"Temiz gitar tonu paylaşımı | Kayıt: {audio_label} | Preset: {preset_name}{note_suffix}",
            )
        if normalized == "konuşma":
            return (
                f"{audio_label} | Konuşma Kaydı",
                f"Konuşma kaydı paylaşımı | Kayıt: {audio_label} | Preset: {preset_name}{note_suffix}",
            )
        if normalized == "tanıtım":
            return (
                f"{audio_label} | Yeni Paylaşım",
                f"Yeni kayıt paylaşımı | Kayıt: {audio_label} | Preset: {preset_name}{note_suffix}",
            )
        return (
            self.default_share_title_for_audio(source_audio) if source_audio is not None else "Yeni kayıt",
            self.default_share_description_for_audio(source_audio) if source_audio is not None else f"Kayıt: {audio_label} | Preset: {preset_name}{note_suffix}",
        )

    def apply_share_template(self, template_name: str) -> None:
        title, description = self.share_template_values(template_name)
        self.share_title.set(title)
        self.share_description.set(description)
        self.set_status(f"Paylaşım şablonu uygulandı: {template_name}")

    def share_hashtag_list(self, audio_path: Optional[Path] = None) -> list[str]:
        source_audio = audio_path or self.current_share_audio_path()
        tags = ["#YouTube", "#Muzik", "#Kayit"]
        preset_name = (self.preset_name.get().strip() or "").lower()
        note = self.current_preset_note().lower()
        audio_label = self.share_template_audio_label(source_audio).lower()
        combined = " ".join(part for part in (preset_name, note, audio_label) if part)
        if "gitar" in combined:
            tags.extend(["#Gitar", "#TemizGitar"])
        if "konuş" in combined or "konus" in combined:
            tags.extend(["#Konusma", "#SesKaydi"])
        if "canlı" in combined or "canli" in combined:
            tags.append("#CanliKayit")
        if "tanıt" in combined or "tanit" in combined:
            tags.append("#YeniVideo")
        unique_tags: list[str] = []
        for tag in tags:
            if tag not in unique_tags:
                unique_tags.append(tag)
        return unique_tags

    def append_share_hashtags(self) -> None:
        hashtags = " ".join(self.share_hashtag_list())
        description = str(self.share_description.get()).strip()
        if hashtags in description:
            self.set_status("Paylaşım hashtagleri zaten açıklamaya eklendi.")
            return
        if description:
            updated = f"{description}\n\n{hashtags}"
        else:
            updated = hashtags
        self.share_description.set(updated)
        self.set_status("Paylaşım hashtagleri eklendi.")

    def clear_share_text(self) -> None:
        self.share_title.set("")
        self.share_description.set("")
        self.set_status("Paylaşım başlık ve açıklaması temizlendi.")

    def share_footer_text(self) -> str:
        preset_name = self.preset_name.get().strip() or "Temiz Gitar"
        note = self.current_preset_note()
        lines = [
            "Dinlediğiniz için teşekkürler.",
            f"Kullanılan preset: {preset_name}",
        ]
        if note:
            lines.append(f"Preset notu: {note}")
        lines.append("Beğendiyseniz paylaşmayı ve kanala destek olmayı unutmayın.")
        return "\n".join(lines)

    def append_share_footer(self) -> None:
        footer = self.share_footer_text()
        description = str(self.share_description.get()).strip()
        if footer in description:
            self.set_status("Paylaşım sonu zaten açıklamaya eklendi.")
            return
        if description:
            updated = f"{description}\n\n{footer}"
        else:
            updated = footer
        self.share_description.set(updated)
        self.set_status("Paylaşım sonu eklendi.")

    def cleaned_share_title(self, raw_title: str) -> str:
        collapsed = " ".join(str(raw_title).replace("\n", " ").replace("\r", " ").split())
        cleaned = collapsed.replace(" | | ", " | ").strip(" |")
        if len(cleaned) > 100:
            cleaned = cleaned[:100].rstrip(" |")
        return cleaned

    def normalize_share_title(self) -> None:
        current_title = str(self.share_title.get())
        cleaned = self.cleaned_share_title(current_title)
        if not cleaned:
            self.set_status("Düzenlenecek paylaşım başlığı yok.")
            return
        self.share_title.set(cleaned)
        self.set_status("Paylaşım başlığı düzenlendi.")

    def concise_share_description(self, audio_path: Optional[Path] = None) -> str:
        source_audio = audio_path or self.current_share_audio_path()
        audio_label = self.share_template_audio_label(source_audio)
        preset_name = self.preset_name.get().strip() or "Temiz Gitar"
        note = self.current_preset_note()
        parts = [f"Kayıt: {audio_label}", f"Preset: {preset_name}"]
        if note:
            parts.append(f"Not: {note}")
        return " | ".join(parts)

    def apply_concise_share_description(self) -> None:
        self.share_description.set(self.concise_share_description())
        self.set_status("Kısa paylaşım açıklaması uygulandı.")

    def share_upload_category(self, audio_path: Optional[Path] = None) -> str:
        source_audio = audio_path or self.current_share_audio_path()
        combined = " ".join(
            part.lower()
            for part in (
                self.share_template_audio_label(source_audio),
                self.preset_name.get().strip(),
                self.current_preset_note(),
                str(self.share_title.get()).strip(),
            )
            if part
        )
        if "konuş" in combined or "konus" in combined:
            return "People & Blogs"
        return "Music"

    def share_upload_note_text(self, audio_path: Optional[Path] = None) -> str:
        category = self.share_upload_category(audio_path)
        lines = [
            "YouTube yükleme notu",
            f"Kategori: {category}",
            "Görünürlük: Herkese Açık",
            "Kitle ayarı: Çocuklar için değil",
            "Kapak: Seçilen görsel hazır",
        ]
        return "\n".join(lines)

    def copy_share_upload_note(self) -> None:
        self.copy_text_to_clipboard(
            self.share_upload_note_text(),
            "YouTube yükleme notu panoya alındı",
            "YouTube yükleme notu kopyalanamadı",
        )

    def copy_share_upload_note_path(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Kopyalanacak YouTube yükleme notu yolu yok.")
            return
        note_path = package_dir / "youtube_yukleme_notu.txt"
        if not note_path.exists():
            self.set_status("Kopyalanacak YouTube yükleme notu yolu yok.")
            return
        self.copy_text_to_clipboard(
            str(note_path),
            "YouTube yükleme notu yolu panoya alındı",
            "YouTube yükleme notu yolu kopyalanamadı",
        )

    def copy_share_title(self) -> None:
        title = str(self.share_title.get()).strip()
        if not title:
            self.set_status("Kopyalanacak paylaşım başlığı yok.")
            return
        self.copy_text_to_clipboard(
            title,
            "Paylaşım başlığı panoya alındı",
            "Paylaşım başlığı kopyalanamadı",
        )

    def copy_share_description(self) -> None:
        description = str(self.share_description.get()).strip()
        if not description:
            self.set_status("Kopyalanacak paylaşım açıklaması yok.")
            return
        self.copy_text_to_clipboard(
            description,
            "Paylaşım açıklaması panoya alındı",
            "Paylaşım açıklaması kopyalanamadı",
        )

    def share_upload_ready_text(self, audio_path: Path) -> str:
        self.ensure_share_defaults(audio_path)
        title = str(self.share_title.get()).strip() or self.default_share_title_for_audio(audio_path)
        description = str(self.share_description.get()).strip() or self.default_share_description_for_audio(audio_path)
        lines = [
            "YouTube hazır yükleme metni",
            "",
            f"Başlık: {title}",
            "",
            "Açıklama:",
            description or "-",
            "",
            self.share_upload_note_text(audio_path),
        ]
        return "\n".join(lines)

    def copy_share_upload_ready_text(self) -> None:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            self.set_status("Hazır yükleme metni için ses dosyası yok.")
            return
        self.copy_text_to_clipboard(
            self.share_upload_ready_text(audio_path),
            "Hazır yükleme metni panoya alındı",
            "Hazır yükleme metni kopyalanamadı",
        )

    def write_share_upload_note(self) -> None:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            self.set_status("Yükleme notu için ses dosyası yok.")
            return
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            package_dir = self.share_package_dir(audio_path)
            package_dir.mkdir(parents=True, exist_ok=True)
        note_path = package_dir / "youtube_yukleme_notu.txt"
        note_path.write_text(self.share_upload_note_text(audio_path), encoding="utf-8")
        self.last_share_package_dir = package_dir
        self.update_share_meta_text()
        self.set_status(f"YouTube yükleme notu yazıldı: {note_path}")

    def open_share_upload_note_in_finder(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("YouTube yükleme notu yok.")
            return
        note_path = package_dir / "youtube_yukleme_notu.txt"
        if not note_path.exists():
            self.set_status("YouTube yükleme notu yok.")
            return
        try:
            subprocess.run(["open", "-R", str(note_path)], check=False)
            self.set_status(f"YouTube yükleme notu açıldı: {note_path.name}")
        except Exception as exc:
            self.set_status(f"YouTube yükleme notu açılamadı: {exc}")

    def copy_share_package_path(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Kopyalanacak paylaşım paketi yok.")
            return
        self.copy_text_to_clipboard(
            str(package_dir),
            "Paylaşım paketi yolu panoya alındı",
            "Paylaşım paketi yolu kopyalanamadı",
        )

    def copy_share_package_name(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Kopyalanacak paylaşım paketi adı yok.")
            return
        self.copy_text_to_clipboard(
            package_dir.name,
            "Paylaşım paketi adı panoya alındı",
            "Paylaşım paketi adı kopyalanamadı",
        )

    def copy_share_package_zip_path(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Kopyalanacak paylaşım paketi ZIP yok.")
            return
        zip_path = self.share_package_zip_path(package_dir)
        if not zip_path.exists():
            self.set_status("Kopyalanacak paylaşım paketi ZIP yok.")
            return
        self.copy_text_to_clipboard(
            str(zip_path),
            "Paylaşım paketi ZIP yolu panoya alındı",
            "Paylaşım paketi ZIP yolu kopyalanamadı",
        )

    def copy_share_package_zip_name(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Kopyalanacak paylaşım paketi ZIP adı yok.")
            return
        zip_path = self.share_package_zip_path(package_dir)
        if not zip_path.exists():
            self.set_status("Kopyalanacak paylaşım paketi ZIP adı yok.")
            return
        self.copy_text_to_clipboard(
            zip_path.name,
            "Paylaşım paketi ZIP adı panoya alındı",
            "Paylaşım paketi ZIP adı kopyalanamadı",
        )

    def copy_share_image_path(self) -> None:
        image_value = str(self.share_image_path.get()).strip()
        if not image_value:
            self.set_status("Kopyalanacak kapak görseli yok.")
            return
        image_path = Path(image_value)
        if not image_path.exists():
            self.set_status(f"Kapak görseli bulunamadı: {image_path}")
            return
        self.copy_text_to_clipboard(
            str(image_path),
            "Kapak görseli yolu panoya alındı",
            "Kapak görseli yolu kopyalanamadı",
        )

    def copy_share_image_name(self) -> None:
        image_value = str(self.share_image_path.get()).strip()
        if not image_value:
            self.set_status("Kopyalanacak kapak görseli adı yok.")
            return
        image_path = Path(image_value)
        if not image_path.exists():
            self.set_status(f"Kapak görseli bulunamadı: {image_path}")
            return
        self.copy_text_to_clipboard(
            image_path.name,
            "Kapak görseli adı panoya alındı",
            "Kapak görseli adı kopyalanamadı",
        )

    def copy_share_audio_name(self) -> None:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            self.set_status("Kopyalanacak ses dosyası adı yok.")
            return
        self.copy_text_to_clipboard(
            audio_path.name,
            "Ses dosyası adı panoya alındı",
            "Ses dosyası adı kopyalanamadı",
        )

    def copy_share_audio_path(self) -> None:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            self.set_status("Kopyalanacak ses dosyası yolu yok.")
            return
        self.copy_text_to_clipboard(
            str(audio_path),
            "Ses dosyası yolu panoya alındı",
            "Ses dosyası yolu kopyalanamadı",
        )

    def copy_share_meta_summary(self) -> None:
        summary = self.share_meta_summary().strip()
        if not summary:
            self.set_status("Kopyalanacak paylaşım özeti yok.")
            return
        self.copy_text_to_clipboard(
            summary,
            "Paylaşım özeti panoya alındı",
            "Paylaşım özeti kopyalanamadı",
        )

    def copy_share_detail_summary(self) -> None:
        summary = self.share_detail_summary().strip()
        if not summary:
            self.set_status("Kopyalanacak paylaşım detayı yok.")
            return
        self.copy_text_to_clipboard(
            summary,
            "Paylaşım detayı panoya alındı",
            "Paylaşım detayı kopyalanamadı",
        )

    def copy_share_upload_checklist(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Kopyalanacak yükleme sırası yok.")
            return
        checklist_path = self.share_upload_checklist_path(package_dir)
        if not checklist_path.exists():
            self.set_status("Kopyalanacak yükleme sırası yok.")
            return
        try:
            content = checklist_path.read_text(encoding="utf-8")
            self.copy_text_to_clipboard(
                content,
                "Yükleme sırası panoya alındı",
                "Yükleme sırası kopyalanamadı",
            )
        except Exception as exc:
            self.set_status(f"Yükleme sırası kopyalanamadı: {exc}")

    def copy_share_note_paths(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Kopyalanacak not yolu yok.")
            return
        note_paths = [
            package_dir / "youtube_yukleme_notu.txt",
            package_dir / "paylasim_paketi.md",
            package_dir / "paylasim_ozeti.txt",
            package_dir / "paylasim_detayi.txt",
            self.share_upload_checklist_path(package_dir),
            package_dir / "paylasim_rehberi.txt",
        ]
        existing_paths = [str(path) for path in note_paths if path.exists()]
        if not existing_paths:
            self.set_status("Kopyalanacak not yolu yok.")
            return
        self.copy_text_to_clipboard(
            "\n".join(existing_paths),
            "Not yolları panoya alındı",
            "Not yolları kopyalanamadı",
        )

    def copy_share_package_markdown(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Kopyalanacak paylaşım paketi markdown yok.")
            return
        package_markdown_path = package_dir / "paylasim_paketi.md"
        if not package_markdown_path.exists():
            self.set_status("Kopyalanacak paylaşım paketi markdown yok.")
            return
        try:
            content = package_markdown_path.read_text(encoding="utf-8")
            self.copy_text_to_clipboard(
                content,
                "Paylaşım paketi markdown panoya alındı",
                "Paylaşım paketi markdown kopyalanamadı",
            )
        except Exception as exc:
            self.set_status(f"Paylaşım paketi markdown kopyalanamadı: {exc}")

    def write_share_meta_summary(self) -> None:
        audio_path = self.current_share_audio_path()
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            if audio_path is None or not audio_path.exists():
                self.set_status("Yazılacak paylaşım özeti için ses dosyası yok.")
                return
            package_dir = self.share_package_dir(audio_path)
            package_dir.mkdir(parents=True, exist_ok=True)
        self.last_share_package_dir = package_dir
        summary = self.share_meta_summary().strip()
        if not summary:
            self.set_status("Yazılacak paylaşım özeti yok.")
            return
        summary_path = package_dir / "paylasim_ozeti.txt"
        summary_path.write_text(summary, encoding="utf-8")
        self.update_share_meta_text()
        self.set_status(f"Paylaşım özeti yazıldı: {summary_path}")

    def write_share_detail_summary_file(self, package_dir: Path) -> Path:
        detail_path = package_dir / "paylasim_detayi.txt"
        previous_content = None
        for _ in range(3):
            current_content = self.share_detail_summary().strip()
            detail_path.write_text(current_content, encoding="utf-8")
            if current_content == previous_content:
                break
            previous_content = current_content
        return detail_path

    def write_share_detail_summary(self) -> None:
        audio_path = self.current_share_audio_path()
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            if audio_path is None or not audio_path.exists():
                self.set_status("Yazılacak paylaşım detayı için ses dosyası yok.")
                return
            package_dir = self.share_package_dir(audio_path)
            package_dir.mkdir(parents=True, exist_ok=True)
        self.last_share_package_dir = package_dir
        summary = self.share_detail_summary().strip()
        if not summary:
            self.set_status("Yazılacak paylaşım detayı yok.")
            return
        detail_path = self.write_share_detail_summary_file(package_dir)
        self.update_share_meta_text()
        self.set_status(f"Paylaşım detayı yazıldı: {detail_path}")

    def open_share_meta_summary_in_finder(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Paylaşım özeti yok.")
            return
        summary_path = package_dir / "paylasim_ozeti.txt"
        if not summary_path.exists():
            self.set_status("Paylaşım özeti yok.")
            return
        try:
            subprocess.run(["open", "-R", str(summary_path)], check=False)
            self.set_status(f"Paylaşım özeti açıldı: {summary_path.name}")
        except Exception as exc:
            self.set_status(f"Paylaşım özeti açılamadı: {exc}")

    def open_share_detail_summary_in_finder(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Paylaşım detayı yok.")
            return
        detail_path = package_dir / "paylasim_detayi.txt"
        if not detail_path.exists():
            self.set_status("Paylaşım detayı yok.")
            return
        try:
            subprocess.run(["open", "-R", str(detail_path)], check=False)
            self.set_status(f"Paylaşım detayı açıldı: {detail_path.name}")
        except Exception as exc:
            self.set_status(f"Paylaşım detayı açılamadı: {exc}")

    def open_share_upload_checklist_in_finder(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Yükleme sırası yok.")
            return
        checklist_path = self.share_upload_checklist_path(package_dir)
        if not checklist_path.exists():
            self.set_status("Yükleme sırası yok.")
            return
        try:
            subprocess.run(["open", "-R", str(checklist_path)], check=False)
            self.set_status(f"Yükleme sırası açıldı: {checklist_path.name}")
        except Exception as exc:
            self.set_status(f"Yükleme sırası açılamadı: {exc}")

    def open_share_package_markdown_in_finder(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Paylaşım paketi markdown yok.")
            return
        package_markdown_path = package_dir / "paylasim_paketi.md"
        if not package_markdown_path.exists():
            self.set_status("Paylaşım paketi markdown yok.")
            return
        try:
            subprocess.run(["open", "-R", str(package_markdown_path)], check=False)
            self.set_status(f"Paylaşım paketi markdown açıldı: {package_markdown_path.name}")
        except Exception as exc:
            self.set_status(f"Paylaşım paketi markdown açılamadı: {exc}")

    def share_meta_summary(self) -> str:
        audio_path = self.current_share_audio_path()
        audio_part = f"Ses: {audio_path.name}" if audio_path is not None and audio_path.exists() else "Ses: hazır değil"
        image_value = str(self.share_image_path.get()).strip()
        image_path = Path(image_value) if image_value else None
        image_part = f"Kapak: {image_path.name}" if image_path is not None and image_path.exists() else "Kapak: seçilmedi"
        package_dir = self.last_share_package_dir
        package_part = f"Paket: {package_dir.name}" if package_dir is not None and package_dir.exists() else "Paket: henüz yok"
        return " | ".join([audio_part, image_part, package_part])

    def share_status_badge_text(self) -> str:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            return "Durum: ses hazır değil"
        image_value = str(self.share_image_path.get()).strip()
        image_path = Path(image_value) if image_value else None
        if image_path is None or not image_path.exists():
            return "Durum: kapak seçilmedi"
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            return "Durum: paket bekliyor"
        if not self.share_package_complete(package_dir):
            return "Durum: paket eksik"
        if self.share_zip_current(package_dir):
            return "Durum: paket ve ZIP hazır"
        zip_path = self.share_package_zip_path(package_dir)
        if zip_path.exists():
            return "Durum: ZIP güncellenmeli"
        return "Durum: paket hazır"

    def share_package_expected_paths(self, package_dir: Path) -> list[Path]:
        expected_paths = [
            package_dir / "youtube_baslik.txt",
            package_dir / "youtube_aciklama.txt",
            package_dir / "paylasim_paketi.md",
            package_dir / "youtube_yukleme_notu.txt",
            package_dir / "paylasim_rehberi.txt",
            package_dir / "paylasim_ozeti.txt",
            package_dir / "paylasim_detayi.txt",
            self.share_upload_checklist_path(package_dir),
        ]
        audio_path = self.current_share_audio_path()
        if audio_path is not None and audio_path.exists():
            expected_paths.append(package_dir / audio_path.name)
        image_value = str(self.share_image_path.get()).strip()
        image_path = Path(image_value) if image_value else None
        if image_path is not None and image_path.exists():
            expected_paths.append(package_dir / f"kapak{image_path.suffix.lower() or '.jpg'}")
        return expected_paths

    def share_package_complete(self, package_dir: Optional[Path]) -> bool:
        if package_dir is None or not package_dir.exists():
            return False
        expected_paths = self.share_package_expected_paths(package_dir)
        return bool(expected_paths) and all(path.exists() for path in expected_paths)

    def share_missing_package_items(self, package_dir: Optional[Path]) -> list[str]:
        if package_dir is None or not package_dir.exists():
            return []
        return [path.name for path in self.share_package_expected_paths(package_dir) if not path.exists()]

    def share_package_latest_mtime(self, package_dir: Optional[Path]) -> float:
        if package_dir is None or not package_dir.exists():
            return 0.0
        candidate_paths = [path for path in self.share_package_expected_paths(package_dir) if path.exists()]
        if not candidate_paths:
            return package_dir.stat().st_mtime
        return max(path.stat().st_mtime for path in candidate_paths)

    def share_zip_current(self, package_dir: Optional[Path]) -> bool:
        if not self.share_package_complete(package_dir):
            return False
        assert package_dir is not None
        zip_path = self.share_package_zip_path(package_dir)
        if not zip_path.exists():
            return False
        return zip_path.stat().st_mtime >= self.share_package_latest_mtime(package_dir)

    def share_quickstart_badges(self) -> list[str]:
        audio_path = self.current_share_audio_path()
        image_value = str(self.share_image_path.get()).strip()
        image_path = Path(image_value) if image_value else None
        package_dir = self.last_share_package_dir
        package_ready = self.share_package_complete(package_dir)
        zip_path = self.share_package_zip_path(package_dir) if package_dir is not None and package_dir.exists() else None
        zip_ready = self.share_zip_current(package_dir)
        return [
            "Ses hazır" if audio_path is not None and audio_path.exists() else "Ses bekliyor",
            "Kapak seçildi" if image_path is not None and image_path.exists() else "Kapak bekliyor",
            "Paket hazır" if package_ready else ("Paket eksik" if package_dir is not None and package_dir.exists() else "Paket yok"),
            "ZIP hazır" if zip_ready else ("ZIP eski" if zip_path is not None and zip_path.exists() else "ZIP yok"),
        ]

    def share_quickstart_badge_text(self) -> str:
        return f"Hızlı durum: {' | '.join(self.share_quickstart_badges())}"

    def share_quickstart_badge_configs(self) -> list[tuple[str, str, str, str]]:
        badges = self.share_quickstart_badges()
        configs: list[tuple[str, str, str, str]] = []
        for key, text in zip(("audio", "cover", "package", "zip"), badges):
            is_ready = "hazır" in text.lower() or "seçildi" in text.lower()
            bg = "#173226" if is_ready else "#3a2616"
            fg = "#d8f3dc" if is_ready else "#f6e7cb"
            configs.append((key, text, bg, fg))
        return configs

    def share_next_step_hint(self) -> str:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            return "Öneri: Önce Son Kaydı Kullan ile paylaşılacak sesi seçin."
        image_value = str(self.share_image_path.get()).strip()
        image_path = Path(image_value) if image_value else None
        if image_path is None or not image_path.exists():
            return "Öneri: Görsel Seç ile kapak görselini ekleyin."
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            return "Öneri: YouTube Paketi Yaz ile paylaşım klasörünü oluşturun."
        if not self.share_package_complete(package_dir):
            return "Öneri: YouTube Paketi Yaz ile eksik paylaşım dosyalarını tamamlayın."
        if not self.share_zip_current(package_dir):
            return "Öneri: Paketi ZIP Yap ile gönderime hazır arşivi çıkarın."
        return "Öneri: YouTube Yükle ile yükleme sayfasını açıp hazır dosyaları kullanın."

    def share_next_step_action(self) -> tuple[str, object]:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            return ("Son Kaydı Kullan", self.use_last_audio_for_share)
        image_value = str(self.share_image_path.get()).strip()
        image_path = Path(image_value) if image_value else None
        if image_path is None or not image_path.exists():
            return ("Görsel Seç", self.select_share_image)
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            return ("YouTube Paketi Yaz", self.export_share_package)
        if not self.share_package_complete(package_dir):
            return ("YouTube Paketi Yaz", self.export_share_package)
        if not self.share_zip_current(package_dir):
            return ("Paketi ZIP Yap", self.export_share_package_zip)
        return ("YouTube Yükle", self.open_youtube_upload_page)

    def apply_share_next_step_action(self) -> None:
        _, action = self.share_next_step_action()
        action()

    def share_ready_badge_config(self) -> tuple[str, str, str]:
        audio_path = self.current_share_audio_path()
        image_value = str(self.share_image_path.get()).strip()
        image_path = Path(image_value) if image_value else None
        package_dir = self.last_share_package_dir
        is_ready = (
            audio_path is not None
            and audio_path.exists()
            and image_path is not None
            and image_path.exists()
            and self.share_package_complete(package_dir)
            and self.share_zip_current(package_dir)
        )
        if is_ready:
            return ("YouTube'a Hazır", "#173226", "#d8f3dc")
        return ("Hazırlık sürüyor", "#3a2616", "#f6e7cb")

    def share_package_size_text(self, package_dir: Optional[Path]) -> str:
        if package_dir is None or not package_dir.exists():
            return "henüz yok"
        if package_dir.is_file():
            total_size = package_dir.stat().st_size
        else:
            total_size = 0
            for path in package_dir.rglob("*"):
                if path.is_file():
                    total_size += path.stat().st_size
        if total_size < 1024:
            return f"{total_size} B"
        if total_size < 1024 * 1024:
            return f"{total_size / 1024:.1f} KB"
        return f"{total_size / (1024 * 1024):.1f} MB"

    def share_package_file_count_text(self, package_dir: Optional[Path]) -> str:
        if package_dir is None or not package_dir.exists():
            return "henüz yok"
        if package_dir.is_file():
            return "1 dosya"
        file_count = sum(1 for path in package_dir.rglob("*") if path.is_file())
        if file_count == 1:
            return "1 dosya"
        return f"{file_count} dosya"

    def share_detail_summary(self) -> str:
        audio_path = self.current_share_audio_path()
        audio_status_part = "Ses durumu: hazir" if audio_path is not None and audio_path.exists() else "Ses durumu: bekleniyor"
        audio_suffix_part = (
            f"Ses türü: {audio_path.suffix.lower().lstrip('.') or 'bilinmiyor'}"
            if audio_path is not None and audio_path.exists()
            else "Ses türü: yok"
        )
        image_value = str(self.share_image_path.get()).strip()
        image_path = Path(image_value) if image_value else None
        image_status_part = "Kapak durumu: hazir" if image_path is not None and image_path.exists() else "Kapak durumu: bekleniyor"
        image_part = f"Kapak dosyası: {image_path.name}" if image_path is not None and image_path.exists() else "Kapak dosyası: yok"
        image_suffix_part = (
            f"Kapak türü: {image_path.suffix.lower().lstrip('.') or 'bilinmiyor'}"
            if image_path is not None and image_path.exists()
            else "Kapak türü: yok"
        )
        package_dir = self.last_share_package_dir
        progress_value = sum(
            (
                1 if audio_path is not None and audio_path.exists() else 0,
                1 if image_path is not None and image_path.exists() else 0,
                1 if self.share_package_complete(package_dir) else 0,
                1 if self.share_zip_current(package_dir) else 0,
            )
        )
        progress_part = f"Ilerleme: {progress_value}/4"
        if package_dir is None or not package_dir.exists():
            package_status_part = "Paket durumu: henüz yok"
        elif self.share_package_complete(package_dir):
            package_status_part = "Paket durumu: hazir"
        else:
            package_status_part = "Paket durumu: eksik"
        if package_dir is None or not package_dir.exists():
            package_part = "Son paket zamanı: henüz yok"
        else:
            package_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(self.share_package_latest_mtime(package_dir)))
            package_part = f"Son paket zamanı: {package_time}"
        size_part = f"Paket boyutu: {self.share_package_size_text(package_dir)}"
        zip_path = self.share_package_zip_path(package_dir) if package_dir is not None and package_dir.exists() else None
        zip_part = f"ZIP boyutu: {self.share_package_size_text(zip_path)}" if zip_path is not None and zip_path.exists() else "ZIP boyutu: henüz yok"
        if zip_path is None or not zip_path.exists():
            zip_status_part = "ZIP durumu: henüz yok"
        elif self.share_zip_current(package_dir):
            zip_status_part = "ZIP durumu: guncel"
        else:
            zip_status_part = "ZIP durumu: eski"
        if zip_path is not None and zip_path.exists():
            zip_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(zip_path.stat().st_mtime))
            zip_time_part = f"Son ZIP zamanı: {zip_time}"
        else:
            zip_time_part = "Son ZIP zamanı: henüz yok"
        count_part = f"Paket içeriği: {self.share_package_file_count_text(package_dir)}"
        missing_items = self.share_missing_package_items(package_dir)
        if missing_items:
            preview = ", ".join(missing_items[:3])
            if len(missing_items) > 3:
                preview = f"{preview} +{len(missing_items) - 3}"
            missing_part = f"Eksik paket öğeleri: {preview}"
        else:
            missing_part = "Eksik paket öğeleri: yok"
        if self.share_ready_badge_config()[0] == "YouTube'a Hazır":
            overall_part = "Hazırlık durumu: hazir"
        else:
            overall_part = "Hazırlık durumu: suruyor"
        next_step_part = f"Sonraki adım: {self.share_next_step_action()[0]}"
        return " | ".join(
            [
                audio_status_part,
                audio_suffix_part,
                image_status_part,
                image_part,
                image_suffix_part,
                progress_part,
                package_status_part,
                package_part,
                size_part,
                zip_part,
                zip_status_part,
                zip_time_part,
                count_part,
                missing_part,
                overall_part,
                next_step_part,
            ]
        )

    def update_share_meta_text(self) -> None:
        if hasattr(self, "share_meta_text"):
            self.share_meta_text.set(self.share_meta_summary())
        if hasattr(self, "share_status_text"):
            self.share_status_text.set(self.share_status_badge_text())
        if hasattr(self, "share_detail_text"):
            self.share_detail_text.set(self.share_detail_summary())
        if hasattr(self, "share_quickstart_text"):
            self.share_quickstart_text.set(self.share_quickstart_badge_text())
        for key, text, bg, fg in self.share_quickstart_badge_configs():
            text_var = getattr(self, f"share_quick_{key}_text", None)
            if text_var is not None:
                text_var.set(text)
            label = getattr(self, f"share_quick_{key}_label", None)
            if label is not None:
                try:
                    label.configure(bg=bg, fg=fg)
                except Exception:
                    pass
        if hasattr(self, "share_next_step_text"):
            self.share_next_step_text.set(self.share_next_step_hint())
        if hasattr(self, "share_next_step_button_text"):
            self.share_next_step_button_text.set(self.share_next_step_action()[0])
        ready_text, ready_bg, ready_fg = self.share_ready_badge_config()
        if hasattr(self, "share_ready_text"):
            self.share_ready_text.set(ready_text)
        ready_label = getattr(self, "share_ready_label", None)
        if ready_label is not None:
            try:
                ready_label.configure(bg=ready_bg, fg=ready_fg)
            except Exception:
                pass

    def ensure_share_defaults(self, audio_path: Optional[Path] = None) -> None:
        source_audio = audio_path or self.current_share_audio_path()
        if source_audio is None:
            self.update_share_meta_text()
            return
        if not str(self.share_title.get()).strip():
            self.share_title.set(self.default_share_title_for_audio(source_audio))
        if not str(self.share_description.get()).strip():
            self.share_description.set(self.default_share_description_for_audio(source_audio))
        self.update_share_meta_text()

    def select_share_image(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Kapak Görseli Seç",
            filetypes=[
                ("Görseller", "*.png *.jpg *.jpeg *.webp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("WEBP", "*.webp"),
                ("Tüm Dosyalar", "*.*"),
            ],
        )
        if not file_path:
            self.set_status("Paylaşım görseli seçilmedi.")
            return
        self.share_image_path.set(file_path)
        self.update_share_meta_text()
        self.set_status(f"Paylaşım görseli seçildi: {Path(file_path).name}")

    def safe_share_export_name(self, text: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in text).strip()
        cleaned = cleaned.replace(" ", "_")
        return cleaned or "paylasim"

    def share_package_dir(self, audio_path: Path) -> Path:
        output_dir = self.resolve_output_dir()
        return output_dir / "_paylasim" / f"{self.safe_share_export_name(audio_path.stem)}_youtube_paketi"

    def share_package_zip_path(self, package_dir: Path) -> Path:
        return package_dir.parent / f"{package_dir.name}.zip"

    def share_upload_checklist_path(self, package_dir: Path) -> Path:
        return package_dir / "youtube_yukleme_sirasi.txt"

    def image_mime_type(self, image_path: Path) -> str:
        suffix = image_path.suffix.lower()
        if suffix == ".png":
            return "image/png"
        if suffix in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if suffix == ".webp":
            return "image/webp"
        return "image/jpeg"

    def embed_cover_art_in_mp3(self, mp3_path: Path, image_path: Path) -> tuple[bool, str]:
        if not MUTAGEN_AVAILABLE or MP3 is None or ID3 is None or APIC is None:
            return False, "Mutagen eksik, kapak yalnızca ayrı görsel dosyası olarak hazır."
        try:
            audio = MP3(mp3_path, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
            for key in list(audio.tags.keys()):
                if str(key).startswith("APIC"):
                    del audio.tags[key]
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime=self.image_mime_type(image_path),
                    type=3,
                    desc="Kapak",
                    data=image_path.read_bytes(),
                )
            )
            audio.save()
            return True, "Kapak görseli mp3 içine eklendi."
        except Exception as exc:
            return False, f"Kapak mp3 içine eklenemedi: {exc}"

    def build_share_package_markdown(self, title: str, description: str, audio_name: str, image_name: str, cover_status: str) -> str:
        lines = [
            "# YouTube Paylaşım Paketi",
            "",
            f"- Başlık: {title}",
            f"- Ses Dosyası: {audio_name}",
            f"- Kapak Görseli: {image_name}",
            f"- MP3 Kapak: {cover_status}",
            "",
            "## Hızlı Kullanım",
            "",
            "1. `youtube_baslik.txt` ve `youtube_aciklama.txt` dosyalarını kopyalayın.",
            f"2. `{audio_name}` dosyasını yükleyin ve `{image_name}` görselini kapak olarak seçin.",
            "3. `youtube_yukleme_notu.txt` ve `paylasim_detayi.txt` ile son kontrolü yapın.",
            "",
            "## Yardımcı Dosyalar",
            "",
            "- `youtube_baslik.txt`: Kopyalanacak başlık",
            "- `youtube_aciklama.txt`: Kopyalanacak açıklama",
            "- `youtube_yukleme_notu.txt`: Kategori ve görünürlük notu",
            "- `paylasim_ozeti.txt`: Kısa paket özeti",
            "- `paylasim_detayi.txt`: Hazırlık durumu ve sonraki adım",
            "- `paylasim_rehberi.txt`: Yükleme öncesi rehber",
            "- `youtube_yukleme_sirasi.txt`: Adım adım yükleme sırası",
            "",
            "## Açıklama",
            "",
            description or "-",
        ]
        return "\n".join(lines)

    def build_share_guide_text(self, audio_path: Path, title: str, description: str) -> str:
        lines = [
            "YouTube paylaşım rehberi",
            "",
            f"Ses dosyası: {audio_path.name}",
            f"Başlık: {title}",
            "Durum özeti: paylasim_detayi.txt",
            "",
            "Açıklama:",
            description or "-",
            "",
            self.share_upload_note_text(audio_path),
        ]
        return "\n".join(lines)

    def build_share_upload_checklist_text(self, audio_name: str, image_name: str) -> str:
        lines = [
            "YouTube yükleme sırası",
            "",
            "1. youtube_baslik.txt dosyasındaki başlığı kontrol edin ve kopyalayın.",
            "2. youtube_aciklama.txt dosyasındaki açıklamayı kontrol edin ve kopyalayın.",
            f"3. Ses dosyasını yükleyin: {audio_name}",
            f"4. Kapak görselini yükleyin: {image_name}",
            "5. youtube_yukleme_notu.txt içindeki kategori ve görünürlük ayarlarını uygulayın.",
            "6. paylasim_rehberi.txt ile son kez metinleri gözden geçirin.",
            "7. paylasim_ozeti.txt üzerinden paket içeriğini hızlıca doğrulayın.",
            "8. paylasim_detayi.txt ile hazırlık durumunu ve sonraki adımı kontrol edin.",
        ]
        return "\n".join(lines)

    def share_guide_text(self, audio_path: Path) -> str:
        self.ensure_share_defaults(audio_path)
        title = str(self.share_title.get()).strip() or self.default_share_title_for_audio(audio_path)
        description = str(self.share_description.get()).strip() or self.default_share_description_for_audio(audio_path)
        return self.build_share_guide_text(audio_path, title, description)

    def copy_share_guide_text(self) -> None:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            self.set_status("Paylaşım rehberi için ses dosyası yok.")
            return
        self.copy_text_to_clipboard(
            self.share_guide_text(audio_path),
            "Paylaşım rehberi panoya alındı",
            "Paylaşım rehberi kopyalanamadı",
        )

    def write_share_guide_file(self) -> None:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            self.set_status("Paylaşım rehberi için ses dosyası yok.")
            return
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            package_dir = self.share_package_dir(audio_path)
            package_dir.mkdir(parents=True, exist_ok=True)
        guide_path = package_dir / "paylasim_rehberi.txt"
        guide_path.write_text(self.share_guide_text(audio_path), encoding="utf-8")
        self.last_share_package_dir = package_dir
        self.update_share_meta_text()
        self.set_status(f"Paylaşım rehberi yazıldı: {guide_path}")

    def open_share_guide_in_finder(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Paylaşım rehberi yok.")
            return
        guide_path = package_dir / "paylasim_rehberi.txt"
        if not guide_path.exists():
            self.set_status("Paylaşım rehberi yok.")
            return
        try:
            subprocess.run(["open", "-R", str(guide_path)], check=False)
            self.set_status(f"Paylaşım rehberi açıldı: {guide_path.name}")
        except Exception as exc:
            self.set_status(f"Paylaşım rehberi açılamadı: {exc}")

    def create_share_package(self) -> Optional[Path]:
        if self.block_changes_during_recording("paylaşım paketi"):
            return None
        try:
            audio_path = self.current_share_audio_path()
            if audio_path is None or not audio_path.exists():
                self.set_status("Paylaşım için ses dosyası yok.")
                return None
            image_value = str(self.share_image_path.get()).strip()
            if not image_value:
                self.set_status("Paylaşım için kapak görseli seçin.")
                return None
            image_path = Path(image_value)
            if not image_path.exists():
                self.set_status(f"Kapak görseli bulunamadı: {image_path}")
                return None
            self.ensure_share_defaults(audio_path)
            title = str(self.share_title.get()).strip() or self.default_share_title_for_audio(audio_path)
            description = str(self.share_description.get()).strip() or self.default_share_description_for_audio(audio_path)
            package_dir = self.share_package_dir(audio_path)
            package_dir.mkdir(parents=True, exist_ok=True)
            audio_target = package_dir / audio_path.name
            shutil.copy2(audio_path, audio_target)
            image_target = package_dir / f"kapak{image_path.suffix.lower() or '.jpg'}"
            shutil.copy2(image_path, image_target)
            cover_status = "MP3 değil, kapak ayrı görsel dosyası olarak hazır."
            if audio_target.suffix.lower() == ".mp3":
                _, cover_status = self.embed_cover_art_in_mp3(audio_target, image_target)
            (package_dir / "youtube_baslik.txt").write_text(title, encoding="utf-8")
            (package_dir / "youtube_aciklama.txt").write_text(description, encoding="utf-8")
            (package_dir / "paylasim_paketi.md").write_text(
                self.build_share_package_markdown(title, description, audio_path.name, image_target.name, cover_status),
                encoding="utf-8",
            )
            self.last_share_package_dir = package_dir
            (package_dir / "youtube_yukleme_notu.txt").write_text(self.share_upload_note_text(audio_path), encoding="utf-8")
            (package_dir / "paylasim_rehberi.txt").write_text(self.share_guide_text(audio_path), encoding="utf-8")
            (package_dir / "paylasim_ozeti.txt").write_text(self.share_meta_summary().strip(), encoding="utf-8")
            self.share_upload_checklist_path(package_dir).write_text(
                self.build_share_upload_checklist_text(audio_target.name, image_target.name),
                encoding="utf-8",
            )
            self.write_share_detail_summary_file(package_dir)
            self.update_share_meta_text()
            return package_dir
        except Exception as exc:
            self.set_status(f"Paylaşım paketi hazırlanamadı: {exc}")
            return None

    def export_share_package(self) -> None:
        package_dir = self.create_share_package()
        if package_dir is not None:
            self.set_status(f"YouTube paylaşım paketi hazır: {package_dir}")

    def open_last_share_package_in_finder(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Paylaşım paketi yok.")
            return
        try:
            subprocess.run(["open", str(package_dir)], check=False)
            self.set_status(f"Paylaşım paketi açıldı: {package_dir.name}")
        except Exception as exc:
            self.set_status(f"Paylaşım paketi açılamadı: {exc}")

    def create_share_package_zip(self, package_dir: Optional[Path] = None) -> Optional[Path]:
        package_dir = package_dir or self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("ZIP yapılacak paylaşım paketi yok.")
            return None
        zip_path = self.share_package_zip_path(package_dir)
        try:
            if zip_path.exists():
                zip_path.unlink()
            shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=package_dir.parent, base_dir=package_dir.name)
            self.update_share_meta_text()
            return zip_path
        except Exception as exc:
            self.set_status(f"Paylaşım paketi ZIP yapılamadı: {exc}")
            return None

    def export_share_package_zip(self) -> None:
        zip_path = self.create_share_package_zip()
        if zip_path is not None:
            self.set_status(f"Paylaşım paketi ZIP hazır: {zip_path}")

    def prepare_share_package_complete(self) -> None:
        package_dir = self.create_share_package()
        if package_dir is None:
            return
        zip_path = self.create_share_package_zip(package_dir)
        if zip_path is None:
            return
        self.set_status(f"Tam paylaşım hazırlığı hazır: {zip_path}")

    def prepare_share_package_complete_and_open(self) -> None:
        package_dir = self.create_share_package()
        if package_dir is None:
            return
        zip_path = self.create_share_package_zip(package_dir)
        if zip_path is None:
            return
        checklist_path = self.share_upload_checklist_path(package_dir)
        try:
            subprocess.run(["open", "-R", str(checklist_path)], check=False)
            self.set_status(f"Tam paylaşım hazırlığı açıldı: {checklist_path.name}")
        except Exception as exc:
            self.set_status(f"Tam paylaşım hazırlığı hazır ama açılamadı: {exc}")

    def open_share_package_zip_in_finder(self) -> None:
        package_dir = self.last_share_package_dir
        if package_dir is None or not package_dir.exists():
            self.set_status("Paylaşım paketi ZIP yok.")
            return
        zip_path = self.share_package_zip_path(package_dir)
        if not zip_path.exists():
            self.set_status("Paylaşım paketi ZIP yok.")
            return
        try:
            subprocess.run(["open", "-R", str(zip_path)], check=False)
            self.set_status(f"Paylaşım paketi ZIP açıldı: {zip_path.name}")
        except Exception as exc:
            self.set_status(f"Paylaşım paketi ZIP açılamadı: {exc}")

    def open_youtube_upload_page(self) -> None:
        try:
            webbrowser.open("https://www.youtube.com/upload")
            self.set_status("YouTube yükleme sayfası açıldı.")
        except Exception as exc:
            self.set_status(f"YouTube yükleme sayfası açılamadı: {exc}")

    def use_last_audio_for_share(self) -> None:
        audio_path = self.current_share_audio_path()
        if audio_path is None or not audio_path.exists():
            self.set_status("Paylaşım için kullanılacak ses dosyası yok.")
            return
        self.ensure_share_defaults(audio_path)
        self.update_share_meta_text()
        self.set_status(f"Paylaşım paketi son kayıtla hazırlandı: {audio_path.name}")

    def open_share_window(self) -> None:
        self.ensure_share_defaults()
        if self.share_window is not None:
            try:
                self.share_window.lift()
                self.share_window.focus_force()
                return
            except Exception:
                self.share_window = None
        try:
            window = Toplevel(self.root)
            self.share_window = window
            window.title("YouTube Paylaşım Paketi")
            window.configure(bg="#101418")
            window.geometry("860x460")

            def close_window() -> None:
                self.share_window = None
                try:
                    window.destroy()
                except Exception:
                    pass

            def build_share_action_row(
                row_index: int,
                label_text: str,
                hint_text: str,
                items: list[tuple[str, object, str, str]],
            ) -> None:
                row_frame = Frame(container, bg="#101418")
                row_frame.grid(row=row_index, column=0, columnspan=4, sticky="w", pady=(0, 8))
                label_frame = Frame(row_frame, bg="#101418")
                label_frame.pack(side="left", anchor="n")
                Label(label_frame, text=label_text, bg="#101418", fg="#dce6ef", width=16, anchor="w").pack(side="top", anchor="w")
                Label(
                    label_frame,
                    text=hint_text,
                    bg="#101418",
                    fg="#7f8c99",
                    width=16,
                    anchor="w",
                    justify="left",
                    wraplength=140,
                    font=("Helvetica", 9),
                ).pack(side="top", anchor="w", pady=(2, 0))
                for text, command, role, bg in items:
                    button = Button(row_frame, text=text, command=command, bg=bg, fg="white")
                    self.apply_button_style(button, role=role)
                    button.pack(side="left", padx=(8, 0), anchor="n")

            window.protocol("WM_DELETE_WINDOW", close_window)
            container = Frame(window, bg="#101418")
            container.pack(fill="both", expand=True, padx=16, pady=16)
            Label(container, text="YouTube Paylaşım Paketi", bg="#101418", fg="#f4f7fb", font=("Helvetica", 15, "bold")).grid(
                row=0, column=0, columnspan=4, sticky="w"
            )
            Label(
                container,
                text="Son mp3 kaydınızı, kapak görseli ve başlık/açıklama ile birlikte paylaşım klasörüne hazırlar.",
                bg="#101418",
                fg="#c7d2de",
                justify="left",
                wraplength=700,
            ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 12))
            self.update_share_meta_text()
            Label(container, textvariable=self.share_meta_text, bg="#101418", fg="#9fb0c2", justify="left", wraplength=700).grid(
                row=2, column=0, columnspan=4, sticky="w", pady=(0, 10)
            )
            Label(container, textvariable=self.share_status_text, bg="#101418", fg="#86efac", justify="left", wraplength=700).grid(
                row=3, column=0, columnspan=4, sticky="w", pady=(0, 8)
            )
            Label(container, textvariable=self.share_detail_text, bg="#101418", fg="#93c5fd", justify="left", wraplength=700).grid(
                row=4, column=0, columnspan=4, sticky="w", pady=(0, 8)
            )
            Label(container, text="Başlık", bg="#101418", fg="#dce6ef").grid(row=5, column=0, sticky="w")
            Entry(container, textvariable=self.share_title, width=48).grid(row=6, column=0, columnspan=4, sticky="ew", pady=(2, 8))
            Label(container, text="Açıklama", bg="#101418", fg="#dce6ef").grid(row=7, column=0, sticky="w")
            Entry(container, textvariable=self.share_description, width=48).grid(row=8, column=0, columnspan=4, sticky="ew", pady=(2, 8))
            build_share_action_row(
                9,
                "Hızlı Başlangıç",
                "En sık kullanılan adımları sırayla öne çıkarır.",
                [
                    ("Son Kaydı Kullan", self.use_last_audio_for_share, "success", "#16a085"),
                    ("Görsel Seç", self.select_share_image, "secondary", "#34495e"),
                    ("Tam Hazırla", self.prepare_share_package_complete, "success", "#1f8f55"),
                    ("Hazırla + Aç", self.prepare_share_package_complete_and_open, "primary", "#1f6feb"),
                    ("YouTube Paketi Yaz", self.export_share_package, "success", "#2d7d46"),
                    ("Paketi Aç", self.open_last_share_package_in_finder, "primary", "#1f6feb"),
                    ("YouTube Yükle", self.open_youtube_upload_page, "danger", "#c0392b"),
                ],
            )
            quick_badge_row = Frame(container, bg="#101418")
            quick_badge_row.grid(row=10, column=0, columnspan=4, sticky="w", pady=(0, 8))
            self.share_quick_audio_label = Label(
                quick_badge_row,
                textvariable=self.share_quick_audio_text,
                bg="#173226",
                fg="#d8f3dc",
                font=("Helvetica", 9, "bold"),
                padx=10,
                pady=5,
            )
            self.share_quick_cover_label = Label(
                quick_badge_row,
                textvariable=self.share_quick_cover_text,
                bg="#3a2616",
                fg="#f6e7cb",
                font=("Helvetica", 9, "bold"),
                padx=10,
                pady=5,
            )
            self.share_quick_package_label = Label(
                quick_badge_row,
                textvariable=self.share_quick_package_text,
                bg="#3a2616",
                fg="#f6e7cb",
                font=("Helvetica", 9, "bold"),
                padx=10,
                pady=5,
            )
            self.share_quick_zip_label = Label(
                quick_badge_row,
                textvariable=self.share_quick_zip_text,
                bg="#3a2616",
                fg="#f6e7cb",
                font=("Helvetica", 9, "bold"),
                padx=10,
                pady=5,
            )
            self.share_quick_audio_label.pack(side="left")
            self.share_quick_cover_label.pack(side="left", padx=(8, 0))
            self.share_quick_package_label.pack(side="left", padx=(8, 0))
            self.share_quick_zip_label.pack(side="left", padx=(8, 0))
            self.share_ready_label = Label(
                container,
                textvariable=self.share_ready_text,
                bg="#3a2616",
                fg="#f6e7cb",
                font=("Helvetica", 10, "bold"),
                padx=10,
                pady=5,
            )
            self.share_ready_label.grid(row=11, column=0, columnspan=4, sticky="w", pady=(0, 8))
            next_step_row = Frame(container, bg="#101418")
            next_step_row.grid(row=12, column=0, columnspan=4, sticky="w", pady=(0, 8))
            Label(next_step_row, textvariable=self.share_next_step_text, bg="#101418", fg="#fbbf24", justify="left", wraplength=560).pack(
                side="left"
            )
            self.share_next_step_button = Button(
                next_step_row,
                textvariable=self.share_next_step_button_text,
                command=self.apply_share_next_step_action,
                bg="#f59e0b",
                fg="white",
            )
            self.apply_button_style(self.share_next_step_button, role="warning")
            self.share_next_step_button.pack(side="left", padx=(12, 0))
            build_share_action_row(
                13,
                "Şablonlar",
                "Hazır ton ve paylaşım tiplerini tek dokunuşla yerleştirir.",
                [
                    ("Canlı", lambda: self.apply_share_template("Canlı"), "success", "#16a085"),
                    ("Temiz Gitar", lambda: self.apply_share_template("Temiz Gitar"), "success", "#2d7d46"),
                    ("Konuşma", lambda: self.apply_share_template("Konuşma"), "secondary", "#34495e"),
                    ("Tanıtım", lambda: self.apply_share_template("Tanıtım"), "primary", "#8e44ad"),
                ],
            )
            build_share_action_row(
                14,
                "Metin Araçları",
                "Başlık ve açıklamayı hızla toparlar, kopyalar ve kısaltır.",
                [
                    ("Hashtag Ekle", self.append_share_hashtags, "warning", "#d97706"),
                    ("Metni Temizle", self.clear_share_text, "secondary", "#4b5563"),
                    ("Son Ekle", self.append_share_footer, "success", "#0f766e"),
                    ("Başlığı Düzenle", self.normalize_share_title, "primary", "#2563eb"),
                    ("Kısa Açıklama", self.apply_concise_share_description, "primary", "#1d4ed8"),
                    ("Başlığı Kopyala", self.copy_share_title, "secondary", "#475569"),
                    ("Açıklamayı Kopyala", self.copy_share_description, "secondary", "#475569"),
                    ("Hazır Metni Kopyala", self.copy_share_upload_ready_text, "secondary", "#475569"),
                ],
            )
            build_share_action_row(
                15,
                "Notlar",
                "Yükleme sırasında gereken not, rehber, özet, detay ve yol kopyalama araçlarını toplar.",
                [
                    ("Notu Kopyala", self.copy_share_upload_note, "primary", "#7c3aed"),
                    ("Notu Yaz", self.write_share_upload_note, "primary", "#6d28d9"),
                    ("Notu Aç", self.open_share_upload_note_in_finder, "primary", "#1f6feb"),
                    ("Not Yolunu Kopyala", self.copy_share_upload_note_path, "secondary", "#475569"),
                    ("Not Yollarını Kopyala", self.copy_share_note_paths, "secondary", "#475569"),
                    ("Paketi MD Kopyala", self.copy_share_package_markdown, "secondary", "#334155"),
                    ("Özeti Kopyala", self.copy_share_meta_summary, "secondary", "#334155"),
                    ("Detayı Kopyala", self.copy_share_detail_summary, "secondary", "#334155"),
                    ("Paketi MD Aç", self.open_share_package_markdown_in_finder, "primary", "#1f6feb"),
                    ("Özeti Yaz", self.write_share_meta_summary, "secondary", "#475569"),
                    ("Detayı Yaz", self.write_share_detail_summary, "secondary", "#475569"),
                    ("Özeti Aç", self.open_share_meta_summary_in_finder, "primary", "#1f6feb"),
                    ("Detayı Aç", self.open_share_detail_summary_in_finder, "primary", "#1f6feb"),
                    ("Sırayı Kopyala", self.copy_share_upload_checklist, "secondary", "#475569"),
                    ("Sırayı Aç", self.open_share_upload_checklist_in_finder, "primary", "#1f6feb"),
                    ("Rehberi Kopyala", self.copy_share_guide_text, "secondary", "#475569"),
                    ("Rehberi Yaz", self.write_share_guide_file, "success", "#0f766e"),
                    ("Rehberi Aç", self.open_share_guide_in_finder, "primary", "#1f6feb"),
                ],
            )
            build_share_action_row(
                16,
                "Dosyalar",
                "Paket, kapak ve ses dosyalarının ad ve yollarını hızlıca verir.",
                [
                    ("Paket Yolunu Kopyala", self.copy_share_package_path, "secondary", "#475569"),
                    ("Paket Adını Kopyala", self.copy_share_package_name, "secondary", "#64748b"),
                    ("Kapak Yolunu Kopyala", self.copy_share_image_path, "secondary", "#64748b"),
                    ("Kapak Adını Kopyala", self.copy_share_image_name, "secondary", "#64748b"),
                    ("Ses Adını Kopyala", self.copy_share_audio_name, "secondary", "#64748b"),
                    ("Ses Yolunu Kopyala", self.copy_share_audio_path, "secondary", "#64748b"),
                ],
            )
            Label(container, text="Kapak Görseli", bg="#101418", fg="#dce6ef").grid(row=17, column=0, sticky="w")
            Entry(container, textvariable=self.share_image_path, width=48).grid(row=18, column=0, columnspan=4, sticky="ew", pady=(2, 8))
            Label(container, text="Paket İşlemleri", bg="#101418", fg="#dce6ef").grid(row=19, column=0, sticky="w", pady=(4, 0))
            button_row = Frame(container, bg="#101418")
            button_row.grid(row=20, column=0, columnspan=4, sticky="w", pady=(4, 0))
            select_button = Button(button_row, text="Görsel Seç", command=self.select_share_image, bg="#34495e", fg="white")
            use_audio_button = Button(button_row, text="Son Kaydı Kullan", command=self.use_last_audio_for_share, bg="#16a085", fg="white")
            prepare_button = Button(button_row, text="Tam Hazırla", command=self.prepare_share_package_complete, bg="#1f8f55", fg="white")
            prepare_open_button = Button(button_row, text="Hazırla + Aç", command=self.prepare_share_package_complete_and_open, bg="#1f6feb", fg="white")
            export_button = Button(button_row, text="YouTube Paketi Yaz", command=self.export_share_package, bg="#2d7d46", fg="white")
            zip_button = Button(button_row, text="Paketi ZIP Yap", command=self.export_share_package_zip, bg="#2563eb", fg="white")
            zip_open_button = Button(button_row, text="ZIP Göster", command=self.open_share_package_zip_in_finder, bg="#475569", fg="white")
            zip_copy_button = Button(button_row, text="ZIP Yolunu Kopyala", command=self.copy_share_package_zip_path, bg="#64748b", fg="white")
            zip_name_button = Button(button_row, text="ZIP Adını Kopyala", command=self.copy_share_package_zip_name, bg="#64748b", fg="white")
            open_button = Button(button_row, text="Paketi Aç", command=self.open_last_share_package_in_finder, bg="#1f6feb", fg="white")
            upload_button = Button(button_row, text="YouTube Yükle", command=self.open_youtube_upload_page, bg="#c0392b", fg="white")
            for button, role in (
                (select_button, "secondary"),
                (use_audio_button, "success"),
                (prepare_button, "success"),
                (prepare_open_button, "primary"),
                (export_button, "success"),
                (zip_button, "primary"),
                (zip_open_button, "secondary"),
                (zip_copy_button, "secondary"),
                (zip_name_button, "secondary"),
                (open_button, "primary"),
                (upload_button, "danger"),
            ):
                self.apply_button_style(button, role=role)
            select_button.pack(side="left")
            use_audio_button.pack(side="left", padx=(8, 0))
            prepare_button.pack(side="left", padx=(8, 0))
            prepare_open_button.pack(side="left", padx=(8, 0))
            export_button.pack(side="left", padx=(8, 0))
            zip_button.pack(side="left", padx=(8, 0))
            zip_open_button.pack(side="left", padx=(8, 0))
            zip_copy_button.pack(side="left", padx=(8, 0))
            zip_name_button.pack(side="left", padx=(8, 0))
            open_button.pack(side="left", padx=(8, 0))
            upload_button.pack(side="left", padx=(8, 0))
            self.update_share_meta_text()
            self.set_status("Paylaşım penceresi açıldı. Kapak görseli seçip YouTube paketini hazırlayabilirsiniz.")
        except Exception as exc:
            self.share_window = None
            self.set_status(f"Paylaşım penceresi açılamadı: {exc}")

    def open_last_export_in_finder(self) -> None:
        if self.last_export_path is None or not self.last_export_path.exists():
            self.set_status(self.missing_item_status("Son kayıt"))
            return
        try:
            subprocess.run(["open", "-R", str(self.last_export_path)], check=False)
            self.set_status(f"Son kayıt Finder'da seçildi: {recent_audio_status_text(self.last_export_path)}")
        except Exception as exc:
            self.set_status(f"Finder açılamadı: {exc}")

    def open_visible_recent_output_in_finder(self) -> None:
        output_path = self.current_filtered_recent_output_file()
        if output_path is None or not output_path.exists():
            self.set_status("Görünen filtrede gösterilecek çıktı yok.")
            return
        try:
            subprocess.run(["open", "-R", str(output_path)], check=False)
            self.set_status(self.finder_selected_status("Görünen çıktı", output_path.name))
        except Exception as exc:
            self.set_status(f"Görünen çıktı açılamadı: {exc}")

    def copy_visible_recent_output_path_to_clipboard(self) -> None:
        output_path = self.current_filtered_recent_output_file()
        if output_path is None or not output_path.exists():
            self.set_status("Görünen filtrede kopyalanacak çıktı yok.")
            return
        self.copy_text_to_clipboard(
            str(output_path),
            self.copied_item_status("Görünen çıktı yolu", output_path.name),
            "Görünen çıktı yolu kopyalanamadı",
        )

    def start_last_export_playback_thread(self) -> None:
        if self.last_export_path is None or not self.last_export_path.exists():
            self.set_status(self.missing_item_status("Son kayıt"))
            return
        worker = threading.Thread(target=self.play_last_export_audio, daemon=True)
        worker.start()

    def start_visible_recent_audio_playback_thread(self) -> None:
        audio_path = self.current_filtered_recent_audio_file()
        if audio_path is None or not audio_path.exists():
            self.set_status("Görünen filtrede oynatılacak ses yok.")
            return
        worker = threading.Thread(target=self.play_audio_file, args=(audio_path, "Görünen ses"), daemon=True)
        worker.start()

    def play_last_export_audio(self) -> None:
        if self.last_export_path is None or not self.last_export_path.exists():
            self.set_status(self.missing_item_status("Son kayıt"))
            return
        self.play_audio_file(self.last_export_path, "Son kayıt")

    def play_audio_file(self, path: Path, label: str) -> None:
        if not path.exists():
            self.set_status(self.missing_item_status(label))
            return
        try:
            audio, sample_rate = sf.read(path, dtype="float32")
            try:
                _, output_idx = self.selected_device_pair()
            except ValueError:
                output_idx = None
            self.set_status(f"{label} çalınıyor: {path.name}")
            sd.play(audio, samplerate=sample_rate, device=output_idx)
            sd.wait()
            self.set_status(f"{label} oynatıldı: {recent_audio_status_text(path)}")
        except Exception as exc:
            self.set_status(f"{label} oynatılamadı: {exc}")

    def open_last_session_summary_in_finder(self) -> None:
        if self.last_summary_path is None or not self.last_summary_path.exists():
            self.set_status(self.missing_item_status("Özet"))
            return
        try:
            subprocess.run(["open", "-R", str(self.last_summary_path)], check=False)
            self.set_status(self.finder_selected_status("Özet", self.last_summary_path.name))
        except Exception as exc:
            self.set_status(f"Özet açılamadı: {exc}")

    def open_last_take_notes_in_finder(self) -> None:
        if self.last_take_notes_path is None or not self.last_take_notes_path.exists():
            self.set_status(self.missing_item_status("Take notu"))
            return
        try:
            subprocess.run(["open", "-R", str(self.last_take_notes_path)], check=False)
            self.set_status(self.finder_selected_status("Take notu", self.last_take_notes_path.name))
        except Exception as exc:
            self.set_status(f"Take notu açılamadı: {exc}")

    def copy_last_session_summary_to_clipboard(self) -> None:
        if self.last_summary_path is None or not self.last_summary_path.exists():
            self.set_status(self.missing_item_status("Özet"))
            return
        try:
            content = self.last_summary_path.read_text(encoding="utf-8")
            self.copy_text_to_clipboard(
                content,
                self.copied_item_status("Özet", self.last_summary_path.name),
                "Özet kopyalanamadı",
            )
        except Exception as exc:
            self.set_status(f"Özet kopyalanamadı: {exc}")

    def copy_last_export_path_to_clipboard(self) -> None:
        if self.last_export_path is None or not self.last_export_path.exists():
            self.set_status(self.missing_item_status("Son kayıt"))
            return
        self.copy_text_to_clipboard(
            str(self.last_export_path),
            self.copied_item_status("Dosya yolu", self.last_export_path.name),
            "Dosya yolu kopyalanamadı",
        )

    def copy_last_session_summary_path_to_clipboard(self) -> None:
        if self.last_summary_path is None or not self.last_summary_path.exists():
            self.set_status(self.missing_item_status("Özet"))
            return
        self.copy_text_to_clipboard(
            str(self.last_summary_path),
            self.copied_item_status("Özet yolu", self.last_summary_path.name),
            "Özet yolu kopyalanamadı",
        )

    def build_session_brief_text(self, summary: dict) -> str:
        generated_files = summary.get("generated_files", [])
        recording = summary.get("recording", {})
        lines = [
            f"Olay: {summary.get('event', 'bilinmiyor')}",
            f"Tarih: {summary.get('timestamp', 'bilinmiyor')}",
            f"Klasör: {summary.get('output_dir', 'bilinmiyor')}",
        ]
        if summary.get("preset_name"):
            lines.append(f"Preset: {summary['preset_name']}")
        preset_note = str(summary.get("preset_note", "")).strip()
        if preset_note:
            lines.append(f"Preset Notu: {preset_note}")
        if recording:
            mode = recording.get("mode", "")
            if mode:
                lines.append(f"Mod: {mode}")
            if "duration_seconds" in recording:
                lines.append(f"Sure: {format_seconds_short(float(recording.get('duration_seconds', 0.0)))}")
            if "requested_duration_seconds" in recording:
                lines.append(f"Hedef Sure: {format_seconds_short(float(recording.get('requested_duration_seconds', 0.0)))}")
            if "input_peak" in recording:
                lines.append(f"Giris Peak: {float(recording.get('input_peak', 0.0)):.3f}")
            if "processed_peak" in recording:
                lines.append(f"Islenmis Peak: {float(recording.get('processed_peak', 0.0)):.3f}")
            if "mix_peak" in recording:
                lines.append(f"Mix Peak: {float(recording.get('mix_peak', 0.0)):.3f}")
            clip_warning = str(
                recording.get(
                    "clip_warning",
                    describe_clip_warning(
                        float(recording.get("input_peak", 0.0)),
                        float(recording.get("processed_peak", 0.0)),
                        float(recording.get("mix_peak", 0.0)),
                    ),
                )
            )
            lines.append(f"Clip Durumu: {clip_warning}")
            if recording.get("stopped_early"):
                lines.append("Durum: erken durduruldu")
        if generated_files:
            lines.append("Dosyalar:")
            lines.extend([f"- {Path(path).name}" for path in generated_files])
        return "\n".join(lines)

    def last_session_brief_path(self) -> Optional[Path]:
        if self.last_summary_path is None or not self.last_summary_path.exists():
            return None
        return self.last_summary_path.parent / "session_brief.txt"

    def copy_last_session_brief_to_clipboard(self) -> None:
        if self.last_summary_path is None or not self.last_summary_path.exists():
            self.set_status(self.missing_item_status("Özet"))
            return
        try:
            summary = json.loads(self.last_summary_path.read_text(encoding="utf-8"))
            if not isinstance(summary, dict):
                raise ValueError("Özet biçimi geçersiz")
            content = self.build_session_brief_text(summary)
            self.copy_text_to_clipboard(
                content,
                self.copied_item_status("Kısa rapor", self.last_summary_path.name),
                "Kısa rapor kopyalanamadı",
            )
        except Exception as exc:
            self.set_status(f"Kısa rapor kopyalanamadı: {exc}")

    def export_last_session_brief_file(self) -> None:
        if self.last_summary_path is None or not self.last_summary_path.exists():
            self.set_status(self.missing_item_status("Özet"))
            return
        try:
            summary = json.loads(self.last_summary_path.read_text(encoding="utf-8"))
            if not isinstance(summary, dict):
                raise ValueError("Özet biçimi geçersiz")
            brief_path = self.last_session_brief_path()
            assert brief_path is not None
            brief_path.write_text(self.build_session_brief_text(summary), encoding="utf-8")
            for button_name in ("copy_last_brief_path_button", "open_last_brief_button"):
                button = getattr(self, button_name, None)
                if button is not None:
                    button.configure(state="normal")
            self.set_status(f"Kısa rapor yazıldı: {brief_path}")
        except Exception as exc:
            self.set_status(f"Kısa rapor yazılamadı: {exc}")

    def copy_last_session_brief_path_to_clipboard(self) -> None:
        brief_path = self.last_session_brief_path()
        if brief_path is None or not brief_path.exists():
            self.set_status(self.missing_item_status("Kısa rapor"))
            return
        self.copy_text_to_clipboard(
            str(brief_path),
            self.copied_item_status("Kısa rapor yolu", brief_path.name),
            "Kısa rapor yolu kopyalanamadı",
        )

    def open_last_session_brief_in_finder(self) -> None:
        brief_path = self.last_session_brief_path()
        if brief_path is None or not brief_path.exists():
            self.set_status(self.missing_item_status("Kısa rapor"))
            return
        try:
            subprocess.run(["open", "-R", str(brief_path)], check=False)
            self.set_status(self.finder_selected_status("Kısa rapor", brief_path.name))
        except Exception as exc:
            self.set_status(f"Kısa rapor açılamadı: {exc}")

    def copy_last_recovery_note_to_clipboard(self) -> None:
        if self.last_recovery_note_path is None or not self.last_recovery_note_path.exists():
            self.set_status(self.missing_item_status("Kurtarma notu"))
            return
        try:
            content = self.last_recovery_note_path.read_text(encoding="utf-8")
            self.copy_text_to_clipboard(
                content,
                self.copied_item_status("Kurtarma notu", self.last_recovery_note_path.name),
                "Kurtarma notu kopyalanamadı",
            )
        except Exception as exc:
            self.set_status(f"Kurtarma notu kopyalanamadı: {exc}")

    def build_device_summary(self) -> str:
        inputs = list_input_devices()
        outputs = list_output_devices()
        input_lines = [f"• {idx}: {name}" for idx, name in inputs[:5]]
        output_lines = [f"• {idx}: {name}" for idx, name in outputs[:5]]
        input_text = "\n".join(input_lines) if input_lines else "• Mikrofon girişi bulunamadı."
        output_text = "\n".join(output_lines) if output_lines else "• Çıkış aygıtı bulunamadı."
        return f"Giriş Aygıtları ({len(inputs)}):\n{input_text}\n\nÇıkış Aygıtları ({len(outputs)}):\n{output_text}"

    def build_setup_status_text(self, input_count: int, output_count: int) -> str:
        parts = []
        parts.append("Giriş hazır" if input_count > 0 else "Giriş yok")
        parts.append("Çıkış hazır" if output_count > 0 else "Çıkış yok")
        if self.should_export_mp3():
            parts.append("ffmpeg hazır" if not self.mp3_dependency_missing() else "ffmpeg eksik")
        else:
            parts.append("MP3 kapalı")
        parts.append("Klasör hazır" if self.output_dir.get().strip() else "Klasör seçilmedi")
        return "Kurulum: " + " | ".join(parts)

    def build_setup_hint_text(self, input_count: int, output_count: int) -> str:
        if input_count == 0:
            return (
                "1. Sistem Ayarları > Gizlilik ve Güvenlik > Mikrofon içinde izin verin. "
                "2. Harici kart takılıysa çıkarıp yeniden takın. "
                "3. Sonra 'Mikrofonları Yeniden Tara'ya basın."
            )
        if self.mp3_dependency_missing():
            return "Kurulum eksiği: MP3 için ffmpeg bulunamadı. Şimdilik WAV ile devam edebilirsiniz veya `brew install ffmpeg` kurun."
        if not self.output_dir.get().strip():
            return "Kurulum tamamlanmak üzere. Son adım olarak kayıt klasörünü seçin."
        if self.input_device_id.get().strip() or self.output_device_id.get().strip():
            return "Özel aygıt kimliği kullanıyorsunuz. Test başarısız olursa 'Varsayılana Dön' ile boş bırakıp tekrar deneyin."
        if output_count == 0:
            return "Çıkış aygıtı görünmüyor. Hoparlör veya kulaklığı kontrol edip sonra tekrar tarayın."
        return "Kurulum hazır görünüyor. En güvenli akış: önce 5 saniyelik test, sonra kayıt."

    def build_setup_next_text(self, input_count: int, output_count: int) -> str:
        if input_count == 0:
            return "Sıradaki adım: mikrofon iznini açıp yeniden tara."
        if output_count == 0:
            return "Sıradaki adım: çıkışı kontrol edip yeniden tara."
        if self.mp3_dependency_missing():
            return "Sıradaki adım: ffmpeg kur veya WAV ile devam et."
        if not self.output_dir.get().strip():
            return "Sıradaki adım: kayıt klasörü seç."
        if self.input_device_id.get().strip() or self.output_device_id.get().strip():
            return "Sıradaki adım: 5 saniyelik test yap ve cihaz seçimini doğrula."
        return "Sıradaki adım: 5 saniyelik test yap."

    def update_setup_hint_summary(self) -> None:
        try:
            self.setup_hint_text.set(self.build_setup_hint_text(self.current_input_device_count, self.current_output_device_count))
            self.setup_status_text.set(self.build_setup_status_text(self.current_input_device_count, self.current_output_device_count))
            self.setup_next_text.set(self.build_setup_next_text(self.current_input_device_count, self.current_output_device_count))
            self.update_hero_overview_cards()
            if hasattr(self, "start_test_button"):
                self.set_recording_action_button_states(recording_active=self.recording_active)
            self.set_hero_action_button_states()
            label = getattr(self, "setup_status_label", None)
            if label is not None:
                ready = (
                    self.current_input_device_count > 0
                    and self.current_output_device_count > 0
                    and bool(self.output_dir.get().strip())
                    and not self.mp3_dependency_missing()
                )
                if ready:
                    label.configure(**self.summary_card_style("#1f2b22", "#d8f3dc"))
                else:
                    label.configure(**self.summary_card_style("#2a1c1c", "#f6e7cb"))
            next_label = getattr(self, "setup_next_label", None)
            if next_label is not None:
                ready = (
                    self.current_input_device_count > 0
                    and self.current_output_device_count > 0
                    and bool(self.output_dir.get().strip())
                    and not self.mp3_dependency_missing()
                )
                if ready:
                    next_label.configure(**self.summary_card_style("#1f2b22", "#d8f3dc"))
                else:
                    next_label.configure(**self.summary_card_style("#1e252d", "#e4edf5"))
        except Exception:
            pass

    def inspect_devices(self, initial: bool = False) -> None:
        if not initial and self.block_changes_during_recording("cihaz listesi"):
            return
        inputs = list_input_devices()
        outputs = list_output_devices()
        input_count = len(inputs)
        output_count = len(outputs)
        self.current_input_device_count = input_count
        self.current_output_device_count = output_count
        self.refresh_device_menus(inputs, outputs)
        self.device_summary_text.set(self.build_device_summary())
        self.update_setup_hint_summary()
        if input_count == 0:
            self.set_status(no_device_help_text())
            return
        self.restart_input_meter()
        if initial:
            self.set_status(f"Hazır. Giriş aygıtı: {input_count} | Çıkış aygıtı: {output_count}")
            return
        self.set_status(f"Ses aygıtları bulundu. Giriş: {input_count} | Çıkış: {output_count}")

    def refresh_device_menus(self, inputs: list[tuple[int, str]], outputs: list[tuple[int, str]]) -> None:
        self.input_device_options = ["Varsayılan macOS girişi"] + [f"{idx} - {name}" for idx, name in inputs]
        self.output_device_options = ["Varsayılan macOS çıkışı"] + [f"{idx} - {name}" for idx, name in outputs]

        input_menu = self.input_device_menu["menu"]
        input_menu.delete(0, "end")
        for option in self.input_device_options:
            input_menu.add_command(label=option, command=lambda value=option: self.input_device_choice.set(value))

        output_menu = self.output_device_menu["menu"]
        output_menu.delete(0, "end")
        for option in self.output_device_options:
            output_menu.add_command(label=option, command=lambda value=option: self.output_device_choice.set(value))

        if self.input_device_choice.get() not in self.input_device_options:
            self.input_device_choice.set("Varsayılan macOS girişi")
        if self.output_device_choice.get() not in self.output_device_options:
            self.output_device_choice.set("Varsayılan macOS çıkışı")
        self.update_selected_route_text()

    def parse_device_choice(self, choice: str) -> Optional[int]:
        head = choice.strip().split(" - ", 1)[0]
        if head.startswith("Varsayılan"):
            return None
        try:
            return int(head)
        except ValueError:
            return None

    def on_input_choice_changed(self, *_args) -> None:
        device_idx = self.parse_device_choice(self.input_device_choice.get())
        self.input_device_id.set("" if device_idx is None else str(device_idx))
        self.update_selected_route_text()

    def on_output_choice_changed(self, *_args) -> None:
        device_idx = self.parse_device_choice(self.output_device_choice.get())
        self.output_device_id.set("" if device_idx is None else str(device_idx))
        self.update_selected_route_text()

    def update_selected_route_text(self) -> None:
        self.selected_route_text.set(
            f"Aktif giriş: {self.input_device_choice.get()} | Aktif çıkış: {self.output_device_choice.get()}"
        )

    def update_level_tracking(self, mono_audio: np.ndarray) -> None:
        if mono_audio is None or len(mono_audio) == 0:
            return
        level = float(np.max(np.abs(mono_audio)))
        self.last_input_peak = level
        self.meter_level = max(level, self.meter_level * 0.65)
        if level >= self.meter_peak_level:
            self.meter_peak_level = level
            self.meter_peak_hold_until = time.time() + 1.2
        if level >= 0.98:
            self.meter_clipping_until = time.time() + 1.5

    def classify_input_level(self, peak_level: float) -> tuple[str, str]:
        if peak_level >= 0.98:
            return ("Kritik: clipping var, kazanci hemen dusurun", "#ff7b72")
        if peak_level >= 0.92:
            return ("Riskli: seviye cok yuksek, biraz dusurun", "#f39c12")
        if peak_level >= 0.18:
            return ("Iyi: giris seviyesi kayit icin uygun", "#7ee787")
        if peak_level >= 0.05:
            return ("Düşük: daha güçlü çalın/söyleyin veya gain artırın", "#d29922")
        return ("Çok düşük: sinyal neredeyse yok", "#8b949e")

    def validate_recording_safety(self) -> tuple[bool, str]:
        if not self.output_dir.get().strip():
            return False, "Kayıt öncesi çıkış klasörü seçin."
        try:
            output_dir = self.resolve_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"Çıkış klasörü hazırlanamadı: {exc}"
        if self.last_input_peak >= 0.985:
            return False, "Giriş clipping yapıyor. Önce kazancı düşürün veya monitor/test ile seviyeyi düzeltin."
        if self.last_input_peak < 0.01:
            return True, "Uyarı: giriş seviyesi çok düşük. Kayıt alınabilir ama ses zayıf olabilir."
        if self.last_input_peak < 0.05:
            return True, "Uyarı: giriş seviyesi düşük. Gerekirse gain artırın."
        return True, ""

    def validate_start_requirements(self, action_label: str) -> tuple[bool, str]:
        if self.current_input_device_count <= 0:
            return False, f"{action_label} başlamadan önce mikrofonu görünür hale getirip yeniden tarayın."
        if self.current_output_device_count <= 0:
            return False, f"{action_label} başlamadan önce çıkışı görünür hale getirip yeniden tarayın."
        if not self.output_dir.get().strip():
            return False, f"{action_label} öncesi çıkış klasörü seçin."
        return True, ""

    def start_actions_ready(self) -> bool:
        return self.current_input_device_count > 0 and self.current_output_device_count > 0 and bool(self.output_dir.get().strip())

    def set_hero_action_button_states(self) -> None:
        recording_active = getattr(self, "recording_active", False)
        setup_ready = self.start_actions_ready()
        scan_state = "disabled" if recording_active else "normal"
        test_state = "disabled" if recording_active or not setup_ready else "normal"
        backing_state = "disabled" if recording_active else "normal"
        for name, state, role in (
            ("hero_scan_button", scan_state, "primary"),
            ("hero_fill_button", scan_state, "success"),
            ("hero_test_button", test_state, "secondary"),
            ("hero_backing_button", backing_state, "accent"),
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                self.set_click_widget_state(widget, state, role=role)

    def meter_callback(self, indata, _frames, _time_info, status) -> None:
        if status:
            self.meter_error_message = f"Meter uyarısı: {status}"
        if indata is None or len(indata) == 0:
            return
        self.update_level_tracking(indata[:, 0])

    def monitor_callback(self, indata, outdata, _frames, _time_info, status) -> None:
        if status:
            self.meter_error_message = f"İzleme uyarısı: {status}"
        if indata is None or len(indata) == 0:
            outdata.fill(0)
            return
        mono = indata[:, 0].copy()
        self.update_level_tracking(mono)
        sample_rate = device_default_samplerate(self.selected_device_pair()[0], "input")
        gain_db, boost_db, high_pass_hz, bass_db, presence_db, treble_db, distortion = self.current_amp_settings()
        processed = apply_amp_chain(
            voice=mono,
            sample_rate=sample_rate,
            gain_db=gain_db,
            boost_db=boost_db,
            high_pass_hz=high_pass_hz,
            bass_db=bass_db,
            presence_db=presence_db,
            treble_db=treble_db,
            distortion=distortion,
        )
        noise_strength = float(self.noise_reduction.get()) / 100.0
        gate_threshold = float(self.noise_gate_threshold.get())
        output_gain_db = float(self.output_gain.get())
        monitor_level = float(self.monitor_level.get()) / 100.0
        processed = reduce_background_noise(processed, sample_rate, noise_strength, gate_threshold)
        processed = self.apply_dynamics(processed)
        processed = apply_output_gain(processed, output_gain_db)
        processed = np.clip(processed * monitor_level, -1.0, 1.0)
        stereo = np.stack([processed, processed], axis=1)
        outdata[:] = stereo

    def update_meter_ui(self) -> None:
        try:
            width = max(1, int(self.meter_canvas.winfo_width()))
            now = time.time()
            level = max(0.0, min(self.meter_level, 1.0))
            if now > self.meter_peak_hold_until:
                self.meter_peak_level *= 0.92
            peak_level = max(level, min(self.meter_peak_level, 1.0))
            self.meter_level *= 0.82
            fill_width = int(width * level)
            peak_x = int(width * peak_level)
            color = "#27ae60"
            if level > 0.7:
                color = "#f39c12"
            if level > 0.9:
                color = "#e74c3c"
            self.meter_canvas.coords(self.meter_fill, 0, 0, fill_width, 24)
            self.meter_canvas.itemconfigure(self.meter_fill, fill=color)
            self.meter_canvas.coords(self.meter_peak_marker, max(0, peak_x - 2), 0, min(width, peak_x), 24)
            if self.meter_error_message:
                self.meter_text.set(self.meter_error_message)
                self.meter_error_message = ""
            elif self.meter_stream is not None or self.monitor_stream is not None:
                self.meter_text.set(f"Giriş: %{int(level * 100)} | Peak: %{int(peak_level * 100)}")
            elif not self.meter_text.get():
                self.meter_text.set("Seviye izleme duruyor.")
            if now < self.meter_clipping_until:
                self.clip_text.set("Uyarı: seviye çok yüksek, gain düşürün")
                self.clip_label.configure(fg="#ff7b72")
            elif peak_level > 0.9:
                self.clip_text.set("Seviye: sınıra yakın")
                self.clip_label.configure(fg="#f39c12")
            else:
                self.clip_text.set("Seviye: güvenli")
                self.clip_label.configure(fg="#7ee787")
            safety_message, safety_color = self.classify_input_level(peak_level)
            self.safety_text.set(f"Durum: {safety_message}")
            self.safety_label.configure(fg=safety_color)
            self.update_preflight_warning_summary()
            self.root.after(120, self.update_meter_ui)
        except TclError:
            pass

    def start_input_meter(self) -> None:
        try:
            input_idx, _ = self.selected_device_pair()
        except ValueError:
            self.meter_text.set("Seviye izleme başlayamadı: aygıt kimliği sayısal olmalı.")
            return
        self.stop_live_monitor()
        self.stop_input_meter()
        input_count, _ = describe_device_state()
        if input_count == 0:
            self.meter_text.set("Seviye izleme başlayamadı: mikrofon girişi bulunamadı.")
            self.update_operation_state_summary()
            return
        try:
            sample_rate = device_default_samplerate(input_idx, "input")
            self.meter_stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=1024,
                device=input_idx,
                callback=self.meter_callback,
            )
            self.meter_stream.start()
            self.meter_text.set("Mikrofon seviyesi izleniyor. Konuşun veya çalın.")
            self.update_operation_state_summary()
        except Exception as exc:
            self.meter_stream = None
            self.meter_text.set(f"Seviye izleme başlayamadı: {exc}")
            self.update_operation_state_summary()

    def start_live_monitor(self) -> None:
        try:
            input_idx, output_idx = self.selected_device_pair()
        except ValueError:
            self.set_status("İzleme açılamadı: aygıt kimliği sayısal olmalı.")
            return
        self.stop_input_meter()
        self.stop_live_monitor()
        input_count, output_count = describe_device_state()
        if input_count == 0 or output_count == 0:
            self.set_status("İzleme açılamadı: giriş veya çıkış aygıtı bulunamadı.")
            return
        try:
            sample_rate = device_default_samplerate(input_idx, "input")
            self.monitor_stream = sd.Stream(
                samplerate=sample_rate,
                blocksize=1024,
                dtype="float32",
                channels=(1, 2),
                device=(input_idx, output_idx),
                callback=self.monitor_callback,
            )
            self.monitor_stream.start()
            self.monitor_status_text.set("Canlı monitor açık. Kulaklık önerilir.")
            self.meter_text.set("Canlı monitor açık. Gecikme için kulaklık önerilir.")
            self.update_operation_state_summary()
        except Exception as exc:
            self.monitor_stream = None
            self.monitor_status_text.set(f"Canlı monitor açılamadı: {exc}")
            self.update_operation_state_summary()

    def stop_live_monitor(self) -> None:
        stream = self.monitor_stream
        self.monitor_stream = None
        if stream is None:
            self.monitor_status_text.set("Canlı monitor kapalı")
            self.update_operation_state_summary()
            return
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
        self.monitor_status_text.set("Canlı monitor kapalı")
        self.update_operation_state_summary()

    def stop_input_meter(self) -> None:
        stream = self.meter_stream
        self.meter_stream = None
        self.meter_level = 0.0
        self.meter_peak_level = 0.0
        self.last_input_peak = 0.0
        self.meter_peak_hold_until = 0.0
        self.meter_clipping_until = 0.0
        if stream is None:
            return
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
        self.meter_text.set("Seviye izleme durdu.")
        self.clip_text.set("Seviye: güvenli")
        self.safety_text.set("Durum: seviye analizi bekleniyor")
        self.update_operation_state_summary()

    def restart_input_meter(self) -> None:
        if self.monitor_stream is not None:
            return
        self.root.after(50, self.start_input_meter)

    def set_recording_action_button_states(self, recording_active: bool) -> None:
        setup_ready = self.start_actions_ready()
        start_state = "disabled" if recording_active or not setup_ready else "normal"
        stop_state = "normal" if recording_active else "disabled"
        quick_state = "disabled" if recording_active or not setup_ready or self.backing_file is not None else "normal"
        self.set_click_widget_state(self.start_test_button, start_state, role="primary")
        self.set_click_widget_state(self.start_quick_record_button, quick_state, role="accent")
        self.set_click_widget_state(self.start_recording_button, start_state, role="success")
        self.set_click_widget_state(self.stop_recording_button, stop_state, role="danger")

    def set_recent_output_button_states(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for name in (
            "open_last_export_button",
            "play_last_export_button",
            "open_visible_recent_output_button",
            "copy_visible_recent_output_path_button",
            "copy_last_export_path_button",
            "open_last_summary_button",
            "copy_last_summary_button",
            "copy_last_summary_path_button",
            "copy_last_brief_button",
            "export_last_brief_button",
            "copy_last_brief_path_button",
            "open_last_brief_button",
            "open_last_take_notes_button",
            "copy_last_recovery_note_button",
            "open_last_output_dir_button",
            "open_last_preparation_button",
            "archive_last_session_button",
            "reset_session_state_button",
            "cleanup_old_trials_button",
        ):
            button = getattr(self, name, None)
            if button is not None:
                button.configure(state=state)

    def begin_recording_progress(self, mode: str, total_seconds: float) -> None:
        self.recording_active = True
        self.recording_started_at = time.time()
        self.recording_target_seconds = max(0.0, float(total_seconds))
        self.recording_mode = mode
        self.stop_recording_requested = False
        try:
            self.set_recording_action_button_states(recording_active=True)
            self.set_hero_action_button_states()
            self.set_recent_output_button_states(enabled=False)
            self.update_action_guidance_summary()
            self.update_action_subtitle()
            self.update_operation_state_summary()
            self.update_progress_subtitle()
            self.update_recent_output_summary()
        except TclError:
            pass

    def finish_recording_progress(self, final_text: str = "Kayıt durumu: beklemede") -> None:
        self.recording_active = False
        self.recording_started_at = 0.0
        self.recording_target_seconds = 0.0
        self.recording_mode = ""
        self.stop_recording_requested = False
        self.record_progress_text.set(final_text)
        try:
            self.set_recording_action_button_states(recording_active=False)
            self.set_hero_action_button_states()
            self.update_action_guidance_summary()
            self.update_action_subtitle()
            self.update_operation_state_summary()
            self.update_progress_subtitle()
            if self.last_export_path is not None and self.last_export_path.exists():
                self.open_last_export_button.configure(state="normal")
                self.play_last_export_button.configure(state="normal")
                self.copy_last_export_path_button.configure(state="normal")
            else:
                self.open_last_export_button.configure(state="disabled")
                self.play_last_export_button.configure(state="disabled")
                self.copy_last_export_path_button.configure(state="disabled")
            if self.last_summary_path is not None and self.last_summary_path.exists():
                self.open_last_summary_button.configure(state="normal")
                self.copy_last_summary_button.configure(state="normal")
                self.copy_last_summary_path_button.configure(state="normal")
                self.copy_last_brief_button.configure(state="normal")
                self.export_last_brief_button.configure(state="normal")
            else:
                self.open_last_summary_button.configure(state="disabled")
                self.copy_last_summary_button.configure(state="disabled")
                self.copy_last_summary_path_button.configure(state="disabled")
                self.copy_last_brief_button.configure(state="disabled")
                self.export_last_brief_button.configure(state="disabled")
            brief_path = self.last_session_brief_path()
            if brief_path is not None and brief_path.exists():
                self.copy_last_brief_path_button.configure(state="normal")
                self.open_last_brief_button.configure(state="normal")
            else:
                self.copy_last_brief_path_button.configure(state="disabled")
                self.open_last_brief_button.configure(state="disabled")
            if self.last_take_notes_path is not None and self.last_take_notes_path.exists():
                self.open_last_take_notes_button.configure(state="normal")
            else:
                self.open_last_take_notes_button.configure(state="disabled")
            if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
                self.copy_last_recovery_note_button.configure(state="normal")
            else:
                self.copy_last_recovery_note_button.configure(state="disabled")
            if self.current_recent_exports_dir().exists():
                self.open_last_output_dir_button.configure(state="normal")
            else:
                self.open_last_output_dir_button.configure(state="disabled")
            if self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists():
                self.open_last_preparation_button.configure(state="normal")
            else:
                self.open_last_preparation_button.configure(state="disabled")
            self.update_reset_session_state_button_state()
            self.update_archive_last_session_button_state()
            self.update_cleanup_old_trials_button_state()
            self.update_recent_output_summary()
        except TclError:
            pass

    def update_recording_progress_ui(self) -> None:
        try:
            if self.recording_active:
                elapsed = max(0.0, time.time() - self.recording_started_at)
                if self.recording_target_seconds > 0:
                    remaining = max(0.0, self.recording_target_seconds - elapsed)
                    self.record_progress_text.set(
                        f"Kayıt sürüyor ({self.recording_mode}) | Geçen: {format_mm_ss(elapsed)} | Kalan: {format_mm_ss(remaining)}"
                    )
                else:
                    self.record_progress_text.set(f"Kayıt sürüyor ({self.recording_mode}) | Geçen: {format_mm_ss(elapsed)}")
            self.root.after(200, self.update_recording_progress_ui)
        except TclError:
            pass

    def request_stop_recording(self) -> None:
        if not self.recording_active:
            self.set_status("Aktif kayıt yok.")
            return
        self.stop_recording_requested = True
        self.set_status("Kayıt durdurma istendi. Elde edilen bölüm kaydedilecek...")
        self.record_progress_text.set("Kayıt durduruluyor, elde edilen bölüm hazırlanıyor...")
        try:
            self.stop_recording_button.configure(state="disabled")
            self.update_action_guidance_summary()
            self.update_action_subtitle()
            self.update_operation_state_summary()
            self.update_progress_subtitle()
        except TclError:
            pass
        try:
            sd.stop()
        except Exception:
            pass

    def on_close(self) -> None:
        try:
            self.write_last_session_state(self.current_recent_exports_dir(), self.last_summary_path)
        except Exception:
            pass
        self.stop_live_monitor()
        self.stop_input_meter()
        self.root.destroy()

    def select_backing(self) -> None:
        if self.block_changes_during_recording("kayıt kaynağı"):
            return
        file_path = filedialog.askopenfilename(
            title="Arka plan müzik seç",
            filetypes=[
                ("Audio Files", "*.wav *.aiff *.aif *.flac"),
                ("WAV", "*.wav"),
                ("AIFF", "*.aiff *.aif"),
                ("FLAC", "*.flac"),
            ],
        )
        if not file_path:
            return
        self.backing_file = Path(file_path)
        self.backing_label.config(text=self.backing_file.name, fg="#2c3e50")
        self.update_compact_status_summary()
        self.update_recording_prep_summary()
        self.update_next_step_summary()
        self.update_readiness_summary()
        self.update_preflight_warning_summary()
        self.update_action_guidance_summary()
        self.update_action_subtitle()
        self.update_source_subtitle()
        self.update_action_button_copy()

    def clear_backing_selection(self) -> None:
        if self.block_changes_during_recording("kayıt kaynağı"):
            return
        self.backing_file = None
        self.backing_label.config(text="Dosya seçilmedi", fg="#9aa7b5")
        self.update_compact_status_summary()
        self.update_recording_prep_summary()
        self.update_next_step_summary()
        self.update_readiness_summary()
        self.update_preflight_warning_summary()
        self.update_action_guidance_summary()
        self.update_action_subtitle()
        self.update_source_subtitle()
        self.update_merge_summary()
        self.update_action_button_copy()
        self.set_status("Arka plan müziği temizlendi. Sadece mikrofon moduna geçildi.")

    def selected_device_pair(self) -> Tuple[Optional[int], Optional[int]]:
        input_idx = self.selected_device_index(self.input_device_choice.get(), self.input_device_id.get())
        output_idx = self.selected_device_index(self.output_device_choice.get(), self.output_device_id.get())
        return input_idx, output_idx

    def selected_device_index(self, choice_text: str, id_text: str) -> Optional[int]:
        parsed_choice = self.parse_device_choice(choice_text)
        if parsed_choice is not None:
            return parsed_choice
        if choice_text.strip().startswith("Varsayılan"):
            return None
        device_text = id_text.strip()
        return int(device_text) if device_text else None

    def start_test_thread(self) -> None:
        ready, message = self.validate_start_requirements("Test")
        if not ready:
            self.set_status(message)
            return
        try:
            input_idx, output_idx = self.selected_device_pair()
        except ValueError:
            self.set_status("Aygıt kimliği alanlarına sadece sayı girin (veya boş bırakın).")
            return
        settings = self.current_amp_settings()
        base_name = self.output_name.get().strip() or "guitar_mix"
        worker = threading.Thread(
            target=self.run_device_test,
            args=(input_idx, output_idx, settings, base_name),
            daemon=True,
        )
        worker.start()

    def current_amp_settings(self) -> Tuple[float, float, float, float, float, float, float]:
        return (
            float(self.gain.get()),
            float(self.boost.get()),
            float(self.high_pass_hz.get()),
            float(self.bass.get()),
            float(self.presence.get()),
            float(self.treble.get()),
            float(self.distortion.get()),
        )

    def should_export_mp3(self) -> bool:
        return self.wav_export_mode_value() not in {"Sadece WAV (Mix + Vokal)", "Tüm WAV Dosyaları"}

    def should_export_mix_wav(self) -> bool:
        return self.wav_export_mode_value() in {"Mix + Vokal WAV", "Sadece WAV (Mix + Vokal)", "Tüm WAV Dosyaları"}

    def ffmpeg_mp3_args(self) -> list[str]:
        quality = self.mp3_quality_value()
        if quality == "320 kbps":
            return ["-codec:a", "libmp3lame", "-b:a", "320k"]
        if quality == "192 kbps":
            return ["-codec:a", "libmp3lame", "-b:a", "192k"]
        if quality == "128 kbps":
            return ["-codec:a", "libmp3lame", "-b:a", "128k"]
        return ["-codec:a", "libmp3lame", "-qscale:a", "2"]

    def apply_dynamics(self, signal: np.ndarray) -> np.ndarray:
        amount = float(self.compressor_amount.get()) / 100.0
        threshold_db = float(self.compressor_threshold.get())
        makeup_db = float(self.compressor_makeup.get())
        ratio = 1.0 + amount * 7.0
        out = signal
        if amount > 0:
            out = apply_compressor(out, threshold_db, ratio, makeup_db)
        if self.limiter_enabled_value() == "Açık":
            out = apply_limiter(out, 0.98)
        return out

    def run_device_test(
        self,
        input_idx: Optional[int],
        output_idx: Optional[int],
        settings: Tuple[float, float, float, float, float, float, float],
        base_name: str,
    ) -> None:
        try:
            self.stop_live_monitor()
            input_count, _ = describe_device_state()
            if input_count == 0:
                self.set_status(no_device_help_text())
                return
            sr = device_default_samplerate(input_idx, "input")
            seconds = 5
            frames = sr * seconds
            gain_db, boost_db, high_pass_hz, bass_db, presence_db, treble_db, distortion = settings

            self.set_status("Test kaydı başlıyor (5 sn). Mikrofona konuşun/çalın...")
            recorded = record_input_stream(sample_rate=sr, frames=frames, channels=1, device=input_idx)
            voice = recorded[:, 0]

            processed = apply_amp_chain(
                voice=voice,
                sample_rate=sr,
                gain_db=gain_db,
                boost_db=boost_db,
                high_pass_hz=high_pass_hz,
                bass_db=bass_db,
                presence_db=presence_db,
                treble_db=treble_db,
                distortion=distortion,
            )
            noise_strength = float(self.noise_reduction.get()) / 100.0
            gate_threshold = float(self.noise_gate_threshold.get())
            output_gain_db = float(self.output_gain.get())
            processed = reduce_background_noise(processed, sr, noise_strength, gate_threshold)
            processed = self.apply_dynamics(processed)
            processed = apply_output_gain(processed, output_gain_db)

            preview = np.stack([processed, processed], axis=1)
            self.set_status("Test çalınıyor...")
            sd.play(preview, samplerate=sr, device=output_idx)
            sd.wait()

            output_dir = self.resolve_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
            test_path = output_dir / f"{base_name}_device_test.wav"
            sf.write(test_path, processed, sr)
            self.last_output_dir = output_dir
            self.last_export_path = test_path
            input_peak = float(np.max(np.abs(voice))) if len(voice) else 0.0
            processed_peak = float(np.max(np.abs(processed))) if len(processed) else 0.0
            recording_stats = {
                "mode": "Mikrofon/Ses Karti Testi",
                "duration_seconds": float(seconds),
                "requested_duration_seconds": float(seconds),
                "input_peak": input_peak,
                "processed_peak": processed_peak,
                "generated_file_count": 1,
                "clip_warning": describe_clip_warning(input_peak, processed_peak, 0.0),
                "stopped_early": False,
            }
            summary = self.build_session_summary(output_dir, [test_path], "device_test", recording_stats)
            summary_path = self.write_session_summary(output_dir, [test_path], "device_test", recording_stats)
            take_notes_path = self.write_take_notes(output_dir, summary)
            self.last_summary_path = summary_path if summary_path is not None and summary_path.exists() else None
            self.last_take_notes_path = take_notes_path if take_notes_path is not None and take_notes_path.exists() else None
            self.last_recovery_note_path = None
            self.write_last_session_state(output_dir, summary_path)
            self.refresh_recent_exports()
            self.remember_completed_take_name(base_name)
            self.notify_success()
            self.update_compact_status_summary()
            self.update_recording_prep_summary()
            self.update_next_step_summary()
            self.update_readiness_summary()
            self.update_preflight_warning_summary()
            self.update_action_guidance_summary()

            self.set_status(self.build_completion_status_text("Test", output_dir, test_path, [test_path]))
        except Exception as exc:
            self.set_status(f"Test hatası: {exc}")

    def start_recording_thread(self) -> None:
        ready, message = self.validate_start_requirements("Kayıt")
        if not ready:
            self.set_status(message)
            return
        self.stop_live_monitor()
        ok, warning = self.validate_recording_safety()
        if not ok:
            self.set_status(warning)
            return
        if warning:
            self.set_status(warning)
        try:
            input_idx, output_idx = self.selected_device_pair()
        except ValueError:
            self.set_status("Aygıt kimliği alanlarına sadece sayı girin (veya boş bırakın).")
            return
        settings = self.current_amp_settings()
        output_dir = self.resolve_output_dir()
        requested_name = self.output_name.get().strip()
        reserved_take_name = None
        if requested_name:
            base_name = requested_name
        else:
            base_name = reserve_take_name_for_dir(output_dir, "take")
            reserved_take_name = base_name
        worker = threading.Thread(
            target=self.record_and_export,
            args=(output_dir, self.backing_file, input_idx, output_idx, settings, base_name, reserved_take_name),
            daemon=True,
        )
        worker.start()

    def start_quick_record_thread(self) -> None:
        if self.backing_file is not None:
            self.set_status("Hızlı Kayıt sadece mikrofon modunda kullanılabilir. Arka planı temizleyin veya tam kaydı başlatın.")
            return
        ready, message = self.validate_start_requirements("Hızlı kayıt")
        if not ready:
            self.set_status(message)
            return
        self.stop_live_monitor()
        ok, warning = self.validate_recording_safety()
        if not ok:
            self.set_status(warning)
            return
        if warning:
            self.set_status(warning)
        try:
            input_idx, output_idx = self.selected_device_pair()
        except ValueError:
            self.set_status("Aygıt kimliği alanlarına sadece sayı girin (veya boş bırakın).")
            return
        settings = self.current_amp_settings()
        output_dir = self.resolve_output_dir()
        base_name = next_timestamped_take_name_for_dir(output_dir, "quick_take")
        worker = threading.Thread(
            target=self.record_and_export,
            args=(output_dir, None, input_idx, output_idx, settings, base_name, base_name),
            daemon=True,
        )
        worker.start()

    def record_and_export(
        self,
        output_dir: Path,
        backing_file: Optional[Path],
        input_idx: Optional[int],
        output_idx: Optional[int],
        settings: Tuple[float, float, float, float, float, float, float],
        base_name: str,
        reserved_take_name: Optional[str] = None,
    ) -> None:
        previous_last_output_dir = self.last_output_dir
        previous_last_export_path = self.last_export_path
        previous_last_summary_path = self.last_summary_path
        previous_last_take_notes_path = self.last_take_notes_path
        previous_last_recovery_note_path = self.last_recovery_note_path
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            target_sr = device_default_samplerate(input_idx, "input")
            sr = target_sr
            input_count, _ = describe_device_state()
            if input_count == 0:
                self.set_status(no_device_help_text())
                self.finish_recording_progress()
                return

            limit_seconds = 7200 if self.record_limit_hours.get() == "2" else 3600
            if backing_file is not None:
                self.set_status("Arka plan müzik yükleniyor...")
                backing, backing_sr = sf.read(backing_file, dtype="float32")
                backing = ensure_stereo(backing)

                if backing_sr != target_sr:
                    self.set_status(f"Örnekleme hızı {backing_sr} -> {target_sr} dönüştürülüyor...")
                    backing = resample_linear(backing, backing_sr, target_sr)

                max_frames = sr * limit_seconds
                if len(backing) > max_frames:
                    self.set_status(f"Kayıt sınırı {limit_seconds // 3600} saat olarak uygulandı, dosya kırpıldı.")
                    backing = backing[:max_frames]

                duration_sec = len(backing) / sr
                requested_duration_seconds = duration_sec
                self.begin_recording_progress("Arka plan + mikrofon", duration_sec)
                self.set_status(
                    f"Kayıt başlıyor ({duration_sec:.1f} sn). Kulaklık önerilir. Arka plan müzik çalarken mikrofona söyleyin/çalın..."
                )
                recorded = sd.playrec(backing, samplerate=sr, channels=1, dtype="float32", device=(input_idx, output_idx))
            else:
                try:
                    record_seconds = float(self.mic_record_seconds.get().strip())
                except ValueError:
                    record_seconds = 60.0
                record_seconds = max(5.0, min(record_seconds, 7200.0))
                capped_seconds = min(record_seconds, float(limit_seconds))
                frames = max(1, int(sr * capped_seconds))
                backing = np.zeros((frames, 2), dtype=np.float32)
                requested_duration_seconds = capped_seconds
                self.begin_recording_progress("Sadece mikrofon", capped_seconds)
                self.set_status(f"Sadece mikrofon kaydı başlıyor ({capped_seconds:.1f} sn).")
                recorded = record_input_stream(sample_rate=sr, frames=frames, channels=1, device=input_idx)

            if backing_file is not None:
                sd.wait()
            stop_requested = self.stop_recording_requested
            if stop_requested:
                elapsed = max(0.0, time.time() - self.recording_started_at)
                captured_frames = min(len(recorded), len(backing), max(1, int(elapsed * sr)))
                recorded = recorded[:captured_frames]
                backing = backing[:captured_frames]
                self.finish_recording_progress("Kayıt durduruldu, elde edilen bölüm işleniyor...")
            else:
                self.finish_recording_progress("Kayıt alındı, işleniyor...")

            if len(recorded) == 0 or len(backing) == 0:
                self.set_status("Kayıt çok erken durduruldu, kaydedilecek ses oluşmadı.")
                self.finish_recording_progress("Kayıt durumu: beklemede")
                return

            voice = recorded[:, 0]
            self.set_status("Amfi efektleri uygulanıyor...")
            gain_db, boost_db, high_pass_hz, bass_db, presence_db, treble_db, distortion = settings
            processed_voice = apply_amp_chain(
                voice=voice,
                sample_rate=sr,
                gain_db=gain_db,
                boost_db=boost_db,
                high_pass_hz=high_pass_hz,
                bass_db=bass_db,
                presence_db=presence_db,
                treble_db=treble_db,
                distortion=distortion,
            )
            noise_strength = float(self.noise_reduction.get()) / 100.0
            gate_threshold = float(self.noise_gate_threshold.get())
            speed_ratio = float(self.speed_ratio.get()) / 100.0
            output_gain_db = float(self.output_gain.get())
            backing_level = float(self.backing_level.get()) / 100.0
            vocal_level = float(self.vocal_level.get()) / 100.0

            processed_voice = reduce_background_noise(processed_voice, sr, noise_strength, gate_threshold)
            processed_voice = self.apply_dynamics(processed_voice)

            if abs(speed_ratio - 1.0) > 1e-6:
                self.set_status(f"Hız ayarı uygulanıyor (%{self.speed_ratio.get()})...")
                backing = change_speed(backing, speed_ratio)
                processed_voice = change_speed(processed_voice, speed_ratio)

            min_len = min(len(backing), len(processed_voice))
            backing = backing[:min_len]
            processed_voice = processed_voice[:min_len]

            mix = backing.copy() * backing_level
            mix[:, 0] += processed_voice * vocal_level
            mix[:, 1] += processed_voice * vocal_level
            mix = apply_output_gain(mix, output_gain_db)
            processed_voice = apply_output_gain(processed_voice, output_gain_db)
            if self.limiter_enabled_value() == "Açık":
                mix = apply_limiter(mix, 0.98)
                processed_voice = apply_limiter(processed_voice, 0.98)

            peak = np.max(np.abs(mix))
            if peak > 0.98:
                mix = mix / peak * 0.98
            mix = np.clip(mix, -1.0, 1.0)

            mp3_path = output_dir / f"{base_name}.mp3"
            mix_wav_path = output_dir / f"{base_name}_mix.wav"
            vocal_wav_path = output_dir / f"{base_name}_vocal.wav"

            self.set_status("Dosyalar hazırlanıyor...")
            ffmpeg_bin = resolve_ffmpeg_binary()

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_wav_path = Path(tmp_wav.name)

            try:
                sf.write(tmp_wav_path, mix, sr)
                if self.should_export_mix_wav():
                    sf.write(mix_wav_path, mix, sr)
                sf.write(vocal_wav_path, processed_voice, sr)

                if self.should_export_mp3() and ffmpeg_bin:
                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(tmp_wav_path),
                        *self.ffmpeg_mp3_args(),
                        str(mp3_path),
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)
                elif self.should_export_mp3():
                    if not self.should_export_mix_wav():
                        sf.write(mix_wav_path, mix, sr)
                if self.should_export_mp3() and ffmpeg_bin and mp3_path.exists():
                    self.last_export_path = mp3_path
                elif self.should_export_mix_wav() and mix_wav_path.exists():
                    self.last_export_path = mix_wav_path
                else:
                    self.last_export_path = vocal_wav_path
                self.last_output_dir = output_dir
                generated_files = [path for path in [mp3_path, mix_wav_path, vocal_wav_path] if path.exists()]
                input_peak = float(np.max(np.abs(voice))) if len(voice) else 0.0
                processed_peak = float(np.max(np.abs(processed_voice))) if len(processed_voice) else 0.0
                mix_peak = float(np.max(np.abs(mix))) if len(mix) else 0.0
                recording_stats = {
                    "mode": "Arka plan + mikrofon" if backing_file is not None else "Sadece mikrofon",
                    "duration_seconds": len(processed_voice) / sr if len(processed_voice) else 0.0,
                    "requested_duration_seconds": requested_duration_seconds,
                    "input_peak": input_peak,
                    "processed_peak": processed_peak,
                    "mix_peak": mix_peak,
                    "generated_file_count": len(generated_files),
                    "clip_warning": describe_clip_warning(input_peak, processed_peak, mix_peak),
                    "stopped_early": bool(stop_requested),
                }
                summary = self.build_session_summary(output_dir, generated_files, "record_export", recording_stats)
                summary_path = self.write_session_summary(output_dir, generated_files, "record_export", recording_stats)
                take_notes_path = self.write_take_notes(output_dir, summary)
                self.last_summary_path = summary_path if summary_path is not None and summary_path.exists() else None
                self.last_take_notes_path = take_notes_path if take_notes_path is not None and take_notes_path.exists() else None
                self.last_recovery_note_path = None
                self.write_last_session_state(output_dir, summary_path)
            finally:
                if tmp_wav_path.exists():
                    tmp_wav_path.unlink()

            self.set_status(self.build_completion_status_text("Kayıt", output_dir, self.last_export_path, generated_files))
            self.refresh_recent_exports()
            self.remember_completed_take_name(base_name)
            self.notify_success()
            self.update_compact_status_summary()
            self.update_recording_prep_summary()
            self.update_next_step_summary()
            self.update_readiness_summary()
            self.update_preflight_warning_summary()
            self.update_action_guidance_summary()
            self.update_action_subtitle()
            self.finish_recording_progress(self.build_ready_recording_progress_text(output_dir))
        except Exception as exc:
            self.restore_previous_success_paths(
                previous_last_output_dir,
                previous_last_export_path,
                previous_last_summary_path,
                previous_last_take_notes_path,
            )
            recovery_note_path = write_export_recovery_note(output_dir, base_name, exc)
            self.last_recovery_note_path = recovery_note_path if recovery_note_path is not None and recovery_note_path.exists() else previous_last_recovery_note_path
            self.finish_recording_progress("Kayıt durumu: hata")
            self.update_compact_status_summary()
            self.update_recording_prep_summary()
            self.update_next_step_summary()
            self.update_readiness_summary()
            self.update_preflight_warning_summary()
            self.update_action_guidance_summary()
            self.update_action_subtitle()
            if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
                self.set_status(f"Hata: {exc} | Kurtarma notu: {self.last_recovery_note_path}")
            else:
                self.set_status(f"Hata: {exc}")
        finally:
            if reserved_take_name:
                release_take_name_lock(output_dir, reserved_take_name)


def main() -> None:
    configure_tcl_tk_environment()
    root = Tk()
    GuitarAmpRecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
