import os
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
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
)
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
import soundfile as sf

GUI_PRESET_PATH = Path(__file__).resolve().with_name(".gui_saved_preset.json")
LAST_SESSION_PATH = Path(__file__).resolve().with_name(".last_session.json")
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


def normalize_choice(value: str, aliases: dict[str, str], default: str) -> str:
    return aliases.get(str(value or "").strip(), default)


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


def next_take_name(prefix: str = "quick_take") -> str:
    return next_take_name_for_dir(Path.home() / "Desktop", prefix)


def next_take_name_for_dir(directory: Path, prefix: str = "quick_take") -> str:
    for i in range(1, 10000):
        name = f"{prefix}_{i:03d}"
        if not take_name_conflicts(directory, name):
            return name
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"


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


def no_device_help_text() -> str:
    return (
        "Ses aygıtı bulunamadı. macOS'ta Sistem Ayarları > Gizlilik ve Güvenlik > Mikrofon bölümünden "
        "Terminal veya GuitarAmpRecorder için izin verin. Harici mikrofon/ses kartı kullanıyorsanız yeniden takıp programı tekrar açın."
    )


def builtin_preset_store() -> dict:
    return {
        "selected": "Temiz Gitar",
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
    merged = {"selected": str(store.get("selected", "Temiz Gitar") or "Temiz Gitar"), "presets": {}}
    builtin = builtin_preset_store()
    builtin_names = set(builtin["presets"].keys())
    user_presets = {
        name: preset
        for name, preset in store.get("presets", {}).items()
        if name not in builtin_names
    }
    merged["presets"].update(builtin["presets"])
    merged["presets"].update(user_presets)
    if merged["selected"] not in merged["presets"]:
        merged["selected"] = builtin["selected"]
    return merged


class GuitarAmpRecorderApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Gitar Amfi Kaydedici")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(720, max(560, screen_w - 120))
        height = min(880, max(640, screen_h - 140))
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(560, 640)
        self.root.configure(bg="#101418")
        self.app_version = read_app_version()

        self.backing_file: Optional[Path] = None

        self.status_text = StringVar(value="Hazır")
        self.operation_state_text = StringVar(value="Durum: hazır")
        self.compact_status_text = StringVar(value="Kısa özet hazırlanıyor...")
        self.recent_output_summary_text = StringVar(value="Son çıktı özeti hazırlanıyor...")
        self.recent_output_subtitle_text = StringVar(value="Son çıktı bölümü hazırlanıyor...")
        self.device_summary_text = StringVar(value="Aygıt taraması bekleniyor...")
        self.setup_hint_text = StringVar(value="Mikrofon kurulumu burada gösterilecek.")
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
        self.readiness_text = StringVar(value="Hazırlık durumu hesaplanıyor...")
        self.readiness_subtitle_text = StringVar(value="Hazırlık özeti hazırlanıyor...")
        self.next_step_subtitle_text = StringVar(value="Sonraki adım özeti hazırlanıyor...")
        self.action_guidance_text = StringVar(value="İşlem önerisi hazırlanıyor...")
        self.action_subtitle_text = StringVar(value="İşlem akışı hazırlanıyor...")
        self.preflight_warning_text = StringVar(value="Ön kontrol hazırlanıyor...")
        self.preflight_subtitle_text = StringVar(value="Ön kontrol özeti hazırlanıyor...")
        self.prep_summary_text = StringVar(value="Kayıt planı hazırlanıyor...")
        self.prep_subtitle_text = StringVar(value="Kayıt planı özeti hazırlanıyor...")
        self.next_step_text = StringVar(value="Hazırlık kontrol ediliyor...")
        self.option_summary_text = StringVar(value="Seçenek açıklamaları hazırlanıyor...")
        self.option_subtitle_text = StringVar(value="Seçenek özeti hazırlanıyor...")
        self.source_subtitle_text = StringVar(value="Kayıt kaynağı hazırlanıyor...")
        self.output_subtitle_text = StringVar(value="Çıktı hedefi hazırlanıyor...")
        self.tone_subtitle_text = StringVar(value="Ton özeti hazırlanıyor...")
        self.mix_subtitle_text = StringVar(value="Mix özeti hazırlanıyor...")
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
        self.last_output_dir: Optional[Path] = None
        self.last_export_path: Optional[Path] = None
        self.last_summary_path: Optional[Path] = None
        self.last_take_notes_path: Optional[Path] = None
        self.last_recovery_note_path: Optional[Path] = None
        self.last_preparation_summary_path: Optional[Path] = None
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
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind_all(sequence, self._on_mousewheel, add="+")

        hero = self.create_section(padx=14, pady=(14, 10), bg="#182028", border="#293543")
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
            wraplength=620,
        ).pack(anchor="w", padx=14, pady=(0, 14))
        Label(
            hero,
            text=f"Sürüm {self.app_version} | Kayıt, dışa aktarım ve oturum takibi",
            bg="#182028",
            fg="#9fb0c2",
            justify="left",
            wraplength=620,
        ).pack(anchor="w", padx=14, pady=(0, 10))
        self.compact_status_label = Label(
            hero,
            textvariable=self.compact_status_text,
            bg="#0f1720",
            fg="#d7eefb",
            justify="left",
            wraplength=620,
            padx=10,
            pady=8,
        )
        self.compact_status_label.pack(fill="x", padx=14, pady=(0, 10))
        self.operation_state_label = Label(
            hero,
            textvariable=self.operation_state_text,
            bg="#182028",
            fg="#9fb0c2",
            justify="left",
            wraplength=620,
            padx=10,
            pady=6,
        )
        self.operation_state_label.pack(anchor="w", padx=14, pady=(0, 10))
        Button(hero, text="Hakkında", command=self.show_about, bg="#34495e", fg="white").pack(anchor="w", padx=14, pady=(0, 14))

        next_step_box = self.create_section(title="Sonraki Adım", subtitlevariable=self.next_step_subtitle_text)
        self.next_step_label = Label(
            next_step_box,
            textvariable=self.next_step_text,
            **self.summary_card_style("#1c2a1f", "#d8f3dc"),
        )
        self.next_step_label.pack(fill="x", padx=14, pady=(10, 10))

        readiness_box = self.create_section(title="Hazırlık Durumu", subtitlevariable=self.readiness_subtitle_text)
        self.readiness_label = Label(
            readiness_box,
            textvariable=self.readiness_text,
            **self.summary_card_style("#1b2029", "#dce6ef"),
        )
        self.readiness_label.pack(fill="x", padx=14, pady=(10, 10))

        preflight_box = self.create_section(title="Kayıt Öncesi Uyarı", subtitlevariable=self.preflight_subtitle_text)
        self.preflight_warning_label = Label(
            preflight_box,
            textvariable=self.preflight_warning_text,
            **self.summary_card_style("#2a1c1c", "#f6e7cb"),
        )
        self.preflight_warning_label.pack(fill="x", padx=14, pady=(10, 10))

        setup = self.create_section(title="Mikrofon Kurulumu", subtitlevariable=self.setup_hint_text)
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
            wraplength=620,
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
            wraplength=620,
            padx=10,
            pady=8,
        )
        self.selected_route_label.pack(fill="x", padx=14, pady=(0, 10))

        device_form = Frame(setup, bg="#151b22")
        device_form.pack(fill="x", padx=14, pady=(0, 8))
        Label(device_form, text="Mikrofonu Listeden Seç", bg="#151b22", fg="#dce6ef").grid(row=0, column=0, sticky="w")
        self.input_device_menu = OptionMenu(device_form, self.input_device_choice, *self.input_device_options)
        self.input_device_menu.configure(width=24, bg="#24303c", fg="white", highlightthickness=0)
        self.input_device_menu.grid(row=1, column=0, sticky="w", pady=(2, 8))
        Label(device_form, text="Çıkışı Listeden Seç", bg="#151b22", fg="#dce6ef").grid(row=0, column=1, sticky="w", padx=(18, 0))
        self.output_device_menu = OptionMenu(device_form, self.output_device_choice, *self.output_device_options)
        self.output_device_menu.configure(width=24, bg="#24303c", fg="white", highlightthickness=0)
        self.output_device_menu.grid(row=1, column=1, sticky="w", padx=(18, 0), pady=(2, 8))
        Label(device_form, text="Mikrofon Aygıt Kimliği", bg="#151b22", fg="#dce6ef").grid(row=2, column=0, sticky="w")
        Entry(device_form, textvariable=self.input_device_id, width=12).grid(row=3, column=0, sticky="w", pady=(2, 8))
        Label(device_form, text="Çıkış Aygıt Kimliği", bg="#151b22", fg="#dce6ef").grid(row=2, column=1, sticky="w", padx=(18, 0))
        Entry(device_form, textvariable=self.output_device_id, width=12).grid(row=3, column=1, sticky="w", padx=(18, 0), pady=(2, 8))
        Label(
            device_form,
            text="Önce listeden seçin. Gerekirse kimlik alanlarını manuel kullanın.",
            bg="#151b22",
            fg="#9fb0c2",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 4))

        button_row = Frame(setup, bg="#151b22")
        button_row.pack(fill="x", padx=14, pady=(0, 12))
        Button(button_row, text="Mikrofonları Yeniden Tara", command=self.inspect_devices, bg="#34495e", fg="white").pack(side="left")
        Button(button_row, text="Önerilen Aygıtları Doldur", command=self.fill_recommended_devices, bg="#1f6feb", fg="white").pack(
            side="left", padx=(8, 0)
        )
        Button(button_row, text="Temiz MacBook Preset", command=self.apply_clean_macbook_preset, bg="#2d7d46", fg="white").pack(
            side="left", padx=(8, 0)
        )
        Button(button_row, text="Harici Mikrofon Preset", command=self.apply_external_mic_preset, bg="#8e44ad", fg="white").pack(
            side="left", padx=(8, 0)
        )
        Button(button_row, text="Varsayılana Dön", command=self.clear_device_selection, bg="#5d6d7e", fg="white").pack(side="left", padx=(8, 0))

        preset_row = Frame(setup, bg="#151b22")
        preset_row.pack(fill="x", padx=14, pady=(0, 12))
        Label(preset_row, text="Preset Adı", bg="#151b22", fg="#dce6ef").grid(row=0, column=0, sticky="w")
        Entry(preset_row, textvariable=self.preset_name, width=18).grid(row=1, column=0, sticky="w", pady=(2, 8))
        Label(preset_row, text="Kayıtlı Presetler", bg="#151b22", fg="#dce6ef").grid(row=0, column=1, sticky="w", padx=(18, 0))
        self.preset_menu = OptionMenu(preset_row, self.preset_name, *self.preset_names)
        self.preset_menu.configure(width=20, bg="#24303c", fg="white", highlightthickness=0)
        self.preset_menu.grid(row=1, column=1, sticky="w", padx=(18, 0), pady=(2, 8))
        Button(preset_row, text="Preset Kaydet", command=self.save_current_preset, bg="#16a085", fg="white").grid(row=1, column=2, sticky="w", padx=(18, 0))
        Button(preset_row, text="Preset Yükle", command=self.load_saved_preset, bg="#2980b9", fg="white").grid(row=1, column=3, sticky="w", padx=(8, 0))
        Button(preset_row, text="Preset Sil", command=self.delete_selected_preset, bg="#c0392b", fg="white").grid(row=1, column=4, sticky="w", padx=(8, 0))
        Button(preset_row, text="Son Oturumu Yükle", command=self.reload_last_session, bg="#6c5ce7", fg="white").grid(row=1, column=5, sticky="w", padx=(8, 0))

        Label(setup, text="Canlı Mikrofon Seviyesi", bg="#151b22", fg="#f4f7fb", font=("Helvetica", 12, "bold")).pack(
            anchor="w", padx=14, pady=(0, 4)
        )
        self.meter_canvas = Canvas(setup, width=620, height=24, bg="#0f141a", highlightthickness=0)
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
        Button(meter_buttons, text="Meter Başlat", command=self.start_input_meter, bg="#2d7d46", fg="white").pack(side="left")
        Button(meter_buttons, text="Meter Durdur", command=self.stop_input_meter, bg="#7f8c8d", fg="white").pack(side="left", padx=(8, 0))
        Button(meter_buttons, text="İzleme Aç", command=self.start_live_monitor, bg="#16a085", fg="white").pack(side="left", padx=(8, 0))
        Button(meter_buttons, text="İzleme Kapat", command=self.stop_live_monitor, bg="#8e44ad", fg="white").pack(side="left", padx=(8, 0))
        Label(setup, textvariable=self.monitor_status_text, bg="#151b22", fg="#9fb0c2", justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        media = self.create_section(title="Kayıt Kaynağı", subtitlevariable=self.source_subtitle_text)
        Label(media, text="Arka Plan Müzik", bg="#151b22", fg="#f4f7fb", font=("Helvetica", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        self.backing_label = Label(media, text="Dosya seçilmedi", fg="#9aa7b5", bg="#151b22")
        self.backing_label.pack(anchor="w", padx=14)
        media_buttons = Frame(media, bg="#151b22")
        media_buttons.pack(anchor="w", padx=14, pady=10)
        Button(media_buttons, text="Müzik Dosyası Seç", command=self.select_backing, bg="#2d7d46", fg="white").pack(side="left")
        Button(media_buttons, text="Sadece Mikrofon Modu", command=self.clear_backing_selection, bg="#5d6d7e", fg="white").pack(side="left", padx=(8, 0))

        export = self.create_section(title="Çıktı", subtitlevariable=self.output_subtitle_text)
        Label(export, text="Çıkış Klasörü", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(12, 2))
        Entry(export, textvariable=self.output_dir, width=48).pack(anchor="w", padx=14)
        Button(export, text="Klasör Seç", command=self.select_output_dir, bg="#34495e", fg="white").pack(anchor="w", padx=14, pady=(8, 10))
        Label(export, text="Oturum Modu", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(8, 2))
        session_mode_menu = OptionMenu(export, self.session_mode, "Tek Klasör", "Tarihli Oturum", "İsimli Oturum")
        session_mode_menu.pack(anchor="w", padx=14)
        Label(export, text="Oturum Adı", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(8, 2))
        Entry(export, textvariable=self.session_name, width=32).pack(anchor="w", padx=14)
        Label(export, text="Çıkış Dosya Adı (MP3)", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(12, 2))
        Entry(export, textvariable=self.output_name, width=48).pack(anchor="w", padx=14)
        Label(export, text="MP3 Kalitesi", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        mp3_quality_menu = OptionMenu(export, self.mp3_quality, "Yüksek VBR", "320 kbps", "192 kbps", "128 kbps")
        mp3_quality_menu.pack(anchor="w", padx=14)
        Label(export, text="WAV Çıkışı", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        wav_export_menu = OptionMenu(export, self.wav_export_mode, "Sadece Vokal WAV", "Mix + Vokal WAV", "Sadece WAV (Mix + Vokal)")
        wav_export_menu.pack(anchor="w", padx=14)
        Label(export, text="Sadece Mikrofon Süresi (sn)", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        Entry(export, textvariable=self.mic_record_seconds, width=12).pack(anchor="w", padx=14)
        Label(export, text="Kayıt Sınırı (saat)", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        limit_menu = OptionMenu(export, self.record_limit_hours, "1", "2")
        limit_menu.pack(anchor="w", padx=14, pady=(0, 12))

        prep_box = self.create_section(title="Kayıt Planı", subtitlevariable=self.prep_subtitle_text)
        self.prep_summary_label = Label(
            prep_box,
            textvariable=self.prep_summary_text,
            **self.summary_card_style("#11202d", "#d7eefb"),
        )
        self.prep_summary_label.pack(fill="x", padx=14, pady=(10, 10))
        prep_buttons = Frame(prep_box, bg="#151b22")
        prep_buttons.pack(anchor="w", padx=14, pady=(0, 12))
        Button(prep_buttons, text="Hazırlığı Kopyala", command=self.copy_current_preparation_to_clipboard, bg="#34495e", fg="white").pack(side="left")
        Button(prep_buttons, text="Hazırlığı Dosyaya Yaz", command=self.export_current_preparation_file, bg="#2d7d46", fg="white").pack(
            side="left", padx=(8, 0)
        )
        Button(prep_buttons, text="Hazırlık Dosyasını Aç", command=self.open_preparation_summary_in_finder, bg="#1f6feb", fg="white").pack(
            side="left", padx=(8, 0)
        )

        option_box = self.create_section(title="Seçenek Özeti", subtitlevariable=self.option_subtitle_text)
        self.option_summary_label = Label(
            option_box,
            textvariable=self.option_summary_text,
            **self.summary_card_style("#2a2014", "#f6e7cb"),
        )
        self.option_summary_label.pack(fill="x", padx=14, pady=(10, 10))

        tone = self.create_section(title="Ton Ayarları", subtitlevariable=self.tone_subtitle_text)
        self.gain = self.make_slider(tone, "Kazanç (dB)", -12, 24, 6)
        self.boost = self.make_slider(tone, "Güçlendirme (dB)", 0, 18, 6)
        self.high_pass_hz = self.make_slider(tone, "High-Pass (Hz)", 0, 240, 70)
        self.bass = self.make_slider(tone, "Bas (dB)", -12, 12, 3)
        self.presence = self.make_slider(tone, "Presence (dB)", -12, 12, 2)
        self.treble = self.make_slider(tone, "Tiz (dB)", -12, 12, 2)
        self.distortion = self.make_slider(tone, "Distorsiyon (%)", 0, 100, 25)

        mix = self.create_section(title="Mix ve Temizlik", subtitlevariable=self.mix_subtitle_text)
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

        actions = self.create_section(title="İşlem", subtitlevariable=self.action_subtitle_text)
        self.action_guidance_label = Label(
            actions,
            textvariable=self.action_guidance_text,
            **self.summary_card_style("#1b2230", "#dfe9f5"),
        )
        self.action_guidance_label.pack(fill="x", padx=14, pady=(10, 6))
        self.start_test_button = Button(actions, text="Mikrofon/Ses Kartı Testi (5 sn)", command=self.start_test_thread, bg="#1f6feb", fg="white")
        self.start_test_button.pack(
            fill="x", padx=14, pady=(0, 6)
        )
        self.start_quick_record_button = Button(actions, text="Hızlı Kayıt (Sadece Mikrofon)", command=self.start_quick_record_thread, bg="#8e44ad", fg="white")
        self.start_quick_record_button.pack(
            fill="x", padx=14, pady=(0, 6)
        )
        self.start_recording_button = Button(actions, text="Tam Kayıt (Mikrofon)", command=self.start_recording_thread, bg="#27ae60", fg="white")
        self.start_recording_button.pack(
            fill="x", padx=14, pady=(0, 6)
        )
        self.stop_recording_button = Button(actions, text="Kaydı Durdur ve Kaydet", command=self.request_stop_recording, bg="#c0392b", fg="white", state="disabled")
        self.stop_recording_button.pack(fill="x", padx=14, pady=(0, 14))

        progress_box = self.create_section(title="Kayıt Durumu", subtitlevariable=self.progress_subtitle_text)
        self.progress_label = Label(
            progress_box,
            textvariable=self.record_progress_text,
            bg="#151b22",
            fg="#dce6ef",
            wraplength=640,
            justify="left",
        )
        self.progress_label.pack(anchor="w", padx=14, pady=(12, 14))

        recent_box = self.create_section(title="Son Çıktılar", subtitlevariable=self.recent_output_subtitle_text)
        self.recent_output_summary_label = Label(
            recent_box,
            textvariable=self.recent_output_summary_text,
            **self.summary_card_style("#1b2029", "#dce6ef"),
        )
        self.recent_output_summary_label.pack(fill="x", padx=14, pady=(10, 8))
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
        self.open_last_export_button.pack(side="left")
        self.play_last_export_button = Button(
            recent_buttons,
            text="Son Kaydı Oynat",
            command=self.start_last_export_playback_thread,
            bg="#16a085",
            fg="white",
            state="disabled",
        )
        self.play_last_export_button.pack(side="left", padx=(8, 0))
        self.open_last_summary_button = Button(
            recent_buttons,
            text="Oturum Özetini Aç",
            command=self.open_last_session_summary_in_finder,
            bg="#6c5ce7",
            fg="white",
            state="disabled",
        )
        self.open_last_summary_button.pack(side="left", padx=(8, 0))
        self.open_last_take_notes_button = Button(
            recent_buttons,
            text="Take Notunu Aç",
            command=self.open_last_take_notes_in_finder,
            bg="#9b59b6",
            fg="white",
            state="disabled",
        )
        self.open_last_take_notes_button.pack(side="left", padx=(8, 0))
        self.open_last_output_dir_button = Button(
            recent_buttons,
            text="Son Oturum Klasörünü Aç",
            command=self.open_output_dir_in_finder,
            bg="#34495e",
            fg="white",
            state="disabled",
        )
        self.open_last_output_dir_button.pack(side="left", padx=(8, 0))
        self.open_last_preparation_button = Button(
            recent_buttons,
            text="Hazırlık Dosyasını Aç",
            command=self.open_preparation_summary_in_finder,
            bg="#1f6feb",
            fg="white",
            state="disabled",
        )
        self.open_last_preparation_button.pack(side="left", padx=(8, 0))
        Button(recent_buttons, text="Listeyi Yenile", command=self.refresh_recent_exports, bg="#2d7d46", fg="white").pack(side="left", padx=(8, 0))
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
        self.copy_last_export_path_button.pack(side="left")
        self.copy_last_summary_button = Button(
            recent_copy_buttons,
            text="Özet İçeriğini Kopyala",
            command=self.copy_last_session_summary_to_clipboard,
            bg="#8e44ad",
            fg="white",
            state="disabled",
        )
        self.copy_last_summary_button.pack(side="left", padx=(8, 0))
        self.copy_last_summary_path_button = Button(
            recent_copy_buttons,
            text="Özet Yolunu Kopyala",
            command=self.copy_last_session_summary_path_to_clipboard,
            bg="#6c5ce7",
            fg="white",
            state="disabled",
        )
        self.copy_last_summary_path_button.pack(side="left", padx=(8, 0))
        self.copy_last_brief_button = Button(
            recent_copy_buttons,
            text="Kısa Rapor Kopyala",
            command=self.copy_last_session_brief_to_clipboard,
            bg="#2d7d46",
            fg="white",
            state="disabled",
        )
        self.copy_last_brief_button.pack(side="left", padx=(8, 0))
        self.export_last_brief_button = Button(
            recent_copy_buttons,
            text="Raporu Dosyaya Yaz",
            command=self.export_last_session_brief_file,
            bg="#f39c12",
            fg="white",
            state="disabled",
        )
        self.export_last_brief_button.pack(side="left", padx=(8, 0))
        self.copy_last_recovery_note_button = Button(
            recent_copy_buttons,
            text="Kurtarma Notunu Kopyala",
            command=self.copy_last_recovery_note_to_clipboard,
            bg="#c0392b",
            fg="white",
            state="disabled",
        )
        self.copy_last_recovery_note_button.pack(side="left", padx=(8, 0))
        self.recent_exports_label = Label(
            recent_box,
            textvariable=self.recent_exports_text,
            bg="#151b22",
            fg="#dce6ef",
            wraplength=640,
            justify="left",
        )
        self.recent_exports_label.pack(anchor="w", padx=14, pady=(0, 14))

        status_box = self.create_section(title="Durum")
        self.status_label = Label(
            status_box,
            textvariable=self.status_text,
            bg="#151b22",
            fg="#dce6ef",
            wraplength=640,
            justify="left",
        )
        self.status_label.pack(anchor="w", padx=14, pady=(12, 14))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.input_device_choice.trace_add("write", self.on_input_choice_changed)
        self.output_device_choice.trace_add("write", self.on_output_choice_changed)
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
        self.update_action_button_copy()
        self.update_progress_subtitle()
        self.update_output_subtitle()
        self.update_tone_subtitle()
        self.update_mix_subtitle()
        self.update_option_explanation_summary()
        self.update_recent_output_summary()

    def create_section(
        self,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        subtitlevariable: Optional[StringVar] = None,
        padx: int = 12,
        pady: tuple[int, int] = (0, 10),
        bg: str = "#151b22",
        border: str = "#24303c",
    ) -> Frame:
        section = Frame(self.content, bg=bg, highlightbackground=border, highlightthickness=1)
        section.pack(fill="x", padx=padx, pady=pady)
        if title:
            Label(section, text=title, bg=bg, fg="#f4f7fb", font=("Helvetica", 14, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
        if subtitle is not None:
            Label(section, text=subtitle, bg=bg, fg="#9fb0c2", justify="left", wraplength=620).pack(anchor="w", padx=14, pady=(0, 10))
        elif subtitlevariable is not None:
            Label(section, textvariable=subtitlevariable, bg=bg, fg="#9fb0c2", justify="left", wraplength=620).pack(
                anchor="w", padx=14, pady=(0, 10)
            )
        return section

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
        self.update_output_subtitle()
        self.update_tone_subtitle()
        self.update_mix_subtitle()
        self.update_option_explanation_summary()

    def session_mode_value(self) -> str:
        return normalize_choice(self.session_mode.get(), SESSION_MODE_ALIASES, "Tek Klasör")

    def mp3_quality_value(self) -> str:
        return normalize_choice(self.mp3_quality.get(), MP3_QUALITY_ALIASES, "Yüksek VBR")

    def wav_export_mode_value(self) -> str:
        return normalize_choice(self.wav_export_mode.get(), WAV_EXPORT_MODE_ALIASES, "Sadece Vokal WAV")

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
        if self.should_export_mp3():
            labels.append(f"MP3 ({self.mp3_quality_value()})")
        if self.should_export_mix_wav():
            labels.append("Mix WAV")
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
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            parts.append("Kurtarma: var")
        return " | ".join(parts)

    def update_compact_status_summary(self) -> None:
        try:
            self.compact_status_text.set(self.build_compact_status_text())
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
        if generated_files:
            parts.append(f"Dosya sayısı: {len(generated_files)}")
        parts.append(f"Klasör: {output_dir}")
        return " | ".join(parts)

    def build_ready_recording_progress_text(self, output_dir: Path) -> str:
        parts = ["Hazır", "Dosyalar hazır", f"Klasör: {output_dir}"]
        if self.last_export_path is not None and self.last_export_path.exists():
            parts.append(f"Son kayıt: {recent_audio_status_text(self.last_export_path)}")
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
            lines.append(f"Kurtarma: {self.last_recovery_note_path.name} hazır")
        return "\n".join(lines)

    def update_recording_prep_summary(self) -> None:
        try:
            self.update_recording_prep_subtitle()
            self.prep_summary_text.set(self.build_recording_prep_text())
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
        return subtitle

    def update_recording_prep_subtitle(self) -> None:
        try:
            self.prep_subtitle_text.set(self.build_recording_prep_subtitle_text())
        except Exception:
            pass

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

    def current_preparation_summary_path(self) -> Path:
        if self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists():
            return self.last_preparation_summary_path
        return self.resolve_output_dir() / "preparation_summary.txt"

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
        if not base_dir:
            return "Önce bir klasör seçin. MP3 ve WAV dosyaları seçtiğiniz yere yazılacak."
        mode = self.session_mode_value()
        if mode == "İsimli Oturum":
            session_name = self.session_name.get().strip() or "session"
            return f"Dosyalar {base_dir} içinde {session_name} klasörüne yazılacak."
        if mode == "Tarihli Oturum":
            return f"Dosyalar {base_dir} içinde tarihli bir klasöre yazılacak."
        return f"Dosyalar doğrudan {base_dir} klasörüne yazılacak."

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
            return "Son çıktı alma denemesi hata verdi. Kurtarma notunu inceleyin, sonra ayarları değiştirip kaydı yeniden başlatın."
        if self.backing_file is None:
            return "Mikrofon modu hazır. Test kaydı alın, sonra doğrudan kaydı başlatın."
        if not output_ready:
            return "Backing seçili. Çıkışı kontrol edin, kısa test yapın, sonra tam kayda geçin."
        return "Backing ve cihazlar hazır. Test kaydı iyi ise tam kaydı başlatabilirsiniz."

    def update_next_step_summary(self) -> None:
        try:
            self.update_next_step_subtitle()
            self.next_step_text.set(self.build_next_step_text())
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
            return "Yeniden denemeden önce kurtarma notu kontrol edilmeli."
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
            return "Hazırlık tamamlanmadan önce kurtarma notunu kontrol edin."
        missing_items = self.missing_readiness_items()
        if missing_items:
            return f"Eksik seçimler: {', '.join(missing_items)}"
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
            label = getattr(self, "readiness_label", None)
            if label is not None:
                label.configure(**self.build_readiness_palette())
        except Exception:
            pass

    def build_preflight_warning_text(self) -> str:
        if not self.output_dir.get().strip():
            return "Ön uyarı: kayıt klasörü seçilmedi."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            return f"Ön uyarı: son çıktı için kurtarma notu var ({self.last_recovery_note_path.name})."
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
            if text.startswith("Hazır:"):
                self.preflight_warning_label.configure(bg="#1f2b22", fg="#d8f3dc")
            else:
                self.preflight_warning_label.configure(bg="#2a1c1c", fg="#f6e7cb")
        except Exception:
            pass

    def build_preflight_subtitle_text(self) -> str:
        if not self.output_dir.get().strip():
            return "Önce kayıt klasörünü seçin."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            return "Son hatayı incelemeden yeni kayıt başlatmayın."
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
            return "Önerilen sıra: Önce kurtarma notunu inceleyin. Ardından kısa test yapın, sonra tam kaydı yeniden başlatın."
        if self.backing_file is None:
            if not output_name:
                return "Önerilen sıra: Çıkışı seçin. Ardından 5 saniyelik test yapın. Sorunsuzsa Hızlı Kayıt ile hızlıca kayıt alın."
            return "Önerilen sıra: Önce 5 saniyelik test yapın. Ses temizse Hızlı Kayıt hızlı yol, tam kayıt ise kontrollü yol olarak hazır."
        if not output_name:
            return "Önerilen sıra: Backing hazır. Önce çıkışı seçin, sonra 5 saniyelik test yapın. Son adımda tam kaydı başlatın."
        return "Önerilen sıra: 5 saniyelik test ile dengeyi kontrol edin. Kısa deneme istiyorsanız Hızlı Kayıt, final take için tam kayıt kullanın."

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
            self.start_quick_record_button.configure(text=self.build_quick_record_button_text())
            self.start_recording_button.configure(text=self.build_main_record_button_text())
        except Exception:
            pass

    def explain_mp3_quality(self) -> str:
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
        parts.append("MP3 açık" if mp3_enabled else "MP3 kapalı")
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

    def on_slider_settings_changed(self, _value: str = "") -> None:
        self.update_tone_subtitle()
        self.update_mix_subtitle()
        self.update_option_explanation_summary()

    def build_recent_output_summary_text(self) -> str:
        if self.recording_active:
            return "Canlı kayıt sürüyor. Son çıktı işlemleri kayıt bitince yeniden açılacak."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                return f"Kurtarma notu hazır. Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}. Önce notu kopyalayın, sonra son kaydı veya klasörü açın."
            return "Kurtarma notu hazır. Önce notu kopyalayın, sonra klasörü açın."
        if self.last_export_path is not None and self.last_export_path.exists():
            ready_items = [f"son kayıt {recent_audio_status_text(self.last_export_path)}"]
            if self.last_summary_path is not None and self.last_summary_path.exists():
                ready_items.append("özet")
            if self.last_take_notes_path is not None and self.last_take_notes_path.exists():
                ready_items.append("take notu")
            if self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists():
                ready_items.append("hazırlık dosyası")
            return f"Hazır: {', '.join(ready_items)}. Önce son kaydı açın veya oynatın."
        if self.last_summary_path is not None and self.last_summary_path.exists():
            if self.last_take_notes_path is not None and self.last_take_notes_path.exists():
                return "Hazır: özet ve take notu. Önce özeti açın, sonra kısa raporu kopyalayın."
            return "Hazır: oturum özeti. Önce özeti açın veya kısa raporu kopyalayın."
        if self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists():
            return "Hazır: hazırlık dosyası. Önce dosyayı açın veya klasörü açın."
        if self.last_take_notes_path is not None and self.last_take_notes_path.exists():
            return "Hazır: take notu. Önce take notunu açın veya klasörü açın."
        if self.current_recent_exports_dir().exists():
            return "Son oturum klasörü hazır. Önce klasörü açın veya listeyi yenileyin."
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
        if self.recording_active:
            return "Kayıt sürerken eski çıktı işlemleri geçici olarak kapalıdır."
        if self.last_recovery_note_path is not None and self.last_recovery_note_path.exists():
            if self.last_export_path is not None and self.last_export_path.exists():
                return f"Sorun yaşandıysa önce kurtarma notunu inceleyin. Son iyi kayıt: {recent_audio_status_text(self.last_export_path)}."
            return "Sorun yaşandıysa önce kurtarma notunu inceleyin."
        if self.last_export_path is not None and self.last_export_path.exists():
            return f"Son kayıt hazır: {recent_audio_status_text(self.last_export_path)}. Dosyayı açabilir, oynatabilir veya yolları kopyalayabilirsiniz."
        if self.last_summary_path is not None and self.last_summary_path.exists():
            return "Özet hazır. Oturum bilgisini açabilir veya kopyalayabilirsiniz."
        if self.last_preparation_summary_path is not None and self.last_preparation_summary_path.exists():
            return "Hazırlık dosyası hazır. Dosyayı açabilir veya oturum klasörüne geçebilirsiniz."
        if self.last_take_notes_path is not None and self.last_take_notes_path.exists():
            return "Take notu hazır. Notu açabilir veya oturum klasörüne geçebilirsiniz."
        return "İlk test veya kayıttan sonra son dosyalar burada görünür."

    def update_recent_output_subtitle(self) -> None:
        try:
            self.recent_output_subtitle_text.set(self.build_recent_output_subtitle_text())
        except Exception:
            pass

    def update_recent_output_summary(self) -> None:
        try:
            self.update_recent_output_subtitle()
            self.recent_output_summary_text.set(self.build_recent_output_summary_text())
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
            "wraplength": 620,
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
            length=620,
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

    def _on_canvas_configure(self, event) -> None:
        try:
            self.canvas.itemconfigure(self.canvas_window, width=event.width)
            self.status_label.configure(wraplength=max(320, event.width - 36))
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

        self.gain.set(4)
        self.boost.set(2)
        self.high_pass_hz.set(80)
        self.bass.set(2)
        self.presence.set(1)
        self.treble.set(1)
        self.distortion.set(0)
        self.backing_level.set(100)
        self.vocal_level.set(85)
        self.noise_reduction.set(10)
        self.speed_ratio.set(100)
        self.output_gain.set(0)

        self.restart_input_meter()
        self.set_status("Temiz MacBook preset uygulandı. Test edip kayda geçebilirsiniz.")

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
            return merge_builtin_presets({"selected": selected, "presets": raw["presets"]})
        if isinstance(raw, dict):
            return merge_builtin_presets({"selected": "Varsayilan", "presets": {"Varsayilan": raw}})
        return self.default_preset_store()

    def write_preset_store_data(self, store: dict) -> None:
        GUI_PRESET_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    def refresh_preset_menu(self, selected_name: Optional[str] = None) -> None:
        store = self.load_preset_store_data()
        names = sorted(store.get("presets", {}).keys()) or ["Temiz Gitar"]
        self.preset_names = names
        menu = self.preset_menu["menu"]
        menu.delete(0, "end")
        for name in self.preset_names:
            menu.add_command(label=name, command=lambda value=name: self.preset_name.set(value))
        target = selected_name or self.preset_name.get() or store.get("selected", "Temiz Gitar")
        if target not in self.preset_names:
            target = self.preset_names[0]
        self.preset_name.set(target)

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

    def current_recent_exports_dir(self) -> Path:
        if self.last_output_dir is not None and self.last_output_dir.exists():
            return self.last_output_dir
        return self.resolve_output_dir()

    def refresh_recent_exports(self) -> None:
        output_dir = self.current_recent_exports_dir()
        if not output_dir.exists():
            self.recent_exports_text.set(f"Klasör bulunamadı: {output_dir}")
            self.update_recent_output_summary()
            return
        recent_files = sorted(
            [path for path in output_dir.iterdir() if visible_recent_output_file(path)],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:8]
        if not recent_files:
            self.recent_exports_text.set("Henüz çıktı yok.")
            self.update_recent_output_summary()
            return
        lines = [recent_output_file_line(path) for path in recent_files]
        latest_audio = latest_audio_file_in_dir(output_dir)
        if latest_audio is not None:
            self.recent_exports_text.set(f"{recent_audio_highlight_line(latest_audio)}\n\n" + "\n".join(lines))
        else:
            self.recent_exports_text.set("\n".join(lines))
        self.update_recent_output_summary()

    def copy_text_to_clipboard(self, content: str, success_message: str, failure_prefix: str) -> None:
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.root.update()
            self.set_status(success_message)
        except Exception as exc:
            self.set_status(f"{failure_prefix}: {exc}")

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

    def open_last_export_in_finder(self) -> None:
        if self.last_export_path is None or not self.last_export_path.exists():
            self.set_status(self.missing_item_status("Son kayıt"))
            return
        try:
            subprocess.run(["open", "-R", str(self.last_export_path)], check=False)
            self.set_status(f"Son kayıt Finder'da seçildi: {recent_audio_status_text(self.last_export_path)}")
        except Exception as exc:
            self.set_status(f"Finder açılamadı: {exc}")

    def start_last_export_playback_thread(self) -> None:
        if self.last_export_path is None or not self.last_export_path.exists():
            self.set_status(self.missing_item_status("Son kayıt"))
            return
        worker = threading.Thread(target=self.play_last_export_audio, daemon=True)
        worker.start()

    def play_last_export_audio(self) -> None:
        if self.last_export_path is None or not self.last_export_path.exists():
            self.set_status(self.missing_item_status("Son kayıt"))
            return
        try:
            audio, sample_rate = sf.read(self.last_export_path, dtype="float32")
            try:
                _, output_idx = self.selected_device_pair()
            except ValueError:
                output_idx = None
            self.set_status(f"Son kayıt çalınıyor: {self.last_export_path.name}")
            sd.play(audio, samplerate=sample_rate, device=output_idx)
            sd.wait()
            self.set_status(f"Son kayıt oynatıldı: {recent_audio_status_text(self.last_export_path)}")
        except Exception as exc:
            self.set_status(f"Son kayıt oynatılamadı: {exc}")

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
            summary_dir = self.last_summary_path.parent
            brief_path = summary_dir / "session_brief.txt"
            brief_path.write_text(self.build_session_brief_text(summary), encoding="utf-8")
            self.set_status(f"Kısa rapor yazıldı: {brief_path}")
        except Exception as exc:
            self.set_status(f"Kısa rapor yazılamadı: {exc}")

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

    def inspect_devices(self, initial: bool = False) -> None:
        if not initial and self.block_changes_during_recording("cihaz listesi"):
            return
        inputs = list_input_devices()
        outputs = list_output_devices()
        input_count = len(inputs)
        output_count = len(outputs)
        self.refresh_device_menus(inputs, outputs)
        self.device_summary_text.set(self.build_device_summary())
        if input_count == 0:
            self.setup_hint_text.set(
                "1. Sistem Ayarları > Gizlilik ve Güvenlik > Mikrofon içinde izin verin. 2. Harici kart takılıysa çıkarıp yeniden takın. 3. Sonra 'Mikrofonları Yeniden Tara'ya basın."
            )
            self.set_status(no_device_help_text())
            return
        if self.input_device_id.get().strip() or self.output_device_id.get().strip():
            self.setup_hint_text.set(
                "Özel aygıt kimliği kullanıyorsunuz. Test başarısız olursa 'Varsayılana Dön' ile boş bırakıp tekrar deneyin."
            )
        else:
            self.setup_hint_text.set(
                "En güvenli kurulum: aygıt kimliklerini boş bırakın. Sorun olursa 'Önerilen Aygıtları Doldur' ile ilk uygun giriş/çıkışı seçin."
            )
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
        gain_db, boost_db, high_pass_hz, bass_db, presence_db, treble_db, distortion = self.current_amp_settings()
        processed = apply_amp_chain(
            voice=mono,
            sample_rate=44100,
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
        processed = reduce_background_noise(processed, 44100, noise_strength, gate_threshold)
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
            self.meter_stream = sd.InputStream(
                samplerate=44100,
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
            self.monitor_stream = sd.Stream(
                samplerate=44100,
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
        start_state = "disabled" if recording_active else "normal"
        stop_state = "normal" if recording_active else "disabled"
        quick_state = "disabled" if recording_active or self.backing_file is not None else "normal"
        self.start_test_button.configure(state=start_state)
        self.start_quick_record_button.configure(state=quick_state)
        self.start_recording_button.configure(state=start_state)
        self.stop_recording_button.configure(state=stop_state)

    def set_recent_output_button_states(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.open_last_export_button.configure(state=state)
        self.play_last_export_button.configure(state=state)
        self.copy_last_export_path_button.configure(state=state)
        self.open_last_summary_button.configure(state=state)
        self.copy_last_summary_button.configure(state=state)
        self.copy_last_summary_path_button.configure(state=state)
        self.copy_last_brief_button.configure(state=state)
        self.export_last_brief_button.configure(state=state)
        self.open_last_take_notes_button.configure(state=state)
        self.copy_last_recovery_note_button.configure(state=state)
        self.open_last_output_dir_button.configure(state=state)
        self.open_last_preparation_button.configure(state=state)

    def begin_recording_progress(self, mode: str, total_seconds: float) -> None:
        self.recording_active = True
        self.recording_started_at = time.time()
        self.recording_target_seconds = max(0.0, float(total_seconds))
        self.recording_mode = mode
        self.stop_recording_requested = False
        try:
            self.set_recording_action_button_states(recording_active=True)
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
        self.update_action_button_copy()
        self.set_status("Arka plan müziği temizlendi. Sadece mikrofon moduna geçildi.")

    def selected_device_pair(self) -> Tuple[Optional[int], Optional[int]]:
        input_text = self.input_device_id.get().strip()
        output_text = self.output_device_id.get().strip()
        input_idx = int(input_text) if input_text else None
        output_idx = int(output_text) if output_text else None
        return input_idx, output_idx

    def start_test_thread(self) -> None:
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
            sr = 44100
            seconds = 5
            frames = sr * seconds
            gain_db, boost_db, high_pass_hz, bass_db, presence_db, treble_db, distortion = settings

            self.set_status("Test kaydı başlıyor (5 sn). Mikrofona konuşun/çalın...")
            recorded = sd.rec(
                frames=frames,
                samplerate=sr,
                channels=1,
                dtype="float32",
                device=input_idx,
            )
            sd.wait()
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
        self.stop_live_monitor()
        if self.backing_file is not None:
            self.set_status("Hızlı Kayıt sadece mikrofon modunda kullanılabilir. Arka planı temizleyin veya tam kaydı başlatın.")
            return
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
        base_name = reserve_take_name_for_dir(output_dir, "quick_take")
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
            target_sr = 44100
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
                recorded = sd.rec(frames=frames, samplerate=sr, channels=1, dtype="float32", device=input_idx)

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
            ffmpeg_bin = shutil.which("ffmpeg")

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
