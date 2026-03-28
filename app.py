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


def read_app_version() -> str:
    try:
        version = VERSION_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.1.0-dev"
    return version or "0.1.0-dev"


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
        if not (directory / f"{name}.mp3").exists() and not (directory / f"{name}_mix.wav").exists():
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
                "session_mode": "Tek Klasor",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yuksek VBR",
                "wav_export_mode": "Sadece Vocal WAV",
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
                "limiter_enabled": "Acik",
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
                "session_mode": "Tek Klasor",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yuksek VBR",
                "wav_export_mode": "Sadece Vocal WAV",
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
                "limiter_enabled": "Acik",
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
                "session_mode": "Tek Klasor",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yuksek VBR",
                "wav_export_mode": "Sadece Vocal WAV",
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
                "limiter_enabled": "Acik",
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
                "session_mode": "Tek Klasor",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yuksek VBR",
                "wav_export_mode": "Sadece Vocal WAV",
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
                "limiter_enabled": "Acik",
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
                "session_mode": "Tek Klasor",
                "session_name": time.strftime("session_%Y%m%d"),
                "mp3_quality": "Yuksek VBR",
                "wav_export_mode": "Mix + Vocal WAV",
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
                "limiter_enabled": "Acik",
                "speed_ratio": 100,
                "output_gain": -5,
            },
        },
    }


def merge_builtin_presets(store: dict) -> dict:
    merged = {"selected": str(store.get("selected", "Temiz Gitar") or "Temiz Gitar"), "presets": {}}
    builtin = builtin_preset_store()
    merged["presets"].update(builtin["presets"])
    merged["presets"].update(store.get("presets", {}))
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
        self.device_summary_text = StringVar(value="Aygıt taraması bekleniyor...")
        self.setup_hint_text = StringVar(value="Mikrofon kurulumu burada gösterilecek.")
        self.meter_text = StringVar(value="Mikrofon seviyesi bekleniyor...")
        self.clip_text = StringVar(value="Headroom: guvenli")
        self.safety_text = StringVar(value="Guvenlik: seviye analizi bekleniyor")
        self.selected_route_text = StringVar(value="Aktif giriş: Varsayılan macOS girişi | Aktif çıkış: Varsayılan macOS çıkışı")
        self.output_name = StringVar(value=f"guitar_mix_{time.strftime('%Y%m%d_%H%M%S')}")
        self.output_dir = StringVar(value=str(Path.home() / "Desktop"))
        self.session_mode = StringVar(value="Tek Klasor")
        self.session_name = StringVar(value=time.strftime("session_%Y%m%d"))
        self.mp3_quality = StringVar(value="Yuksek VBR")
        self.wav_export_mode = StringVar(value="Sadece Vocal WAV")
        self.preset_name = StringVar(value="Temiz Gitar")
        self.limiter_enabled = StringVar(value="Acik")
        self.record_progress_text = StringVar(value="Kayıt durumu: beklemede")
        self.input_device_id = StringVar(value="")
        self.output_device_id = StringVar(value="")
        self.input_device_choice = StringVar(value="Varsayılan macOS girişi")
        self.output_device_choice = StringVar(value="Varsayılan macOS çıkışı")
        self.record_limit_hours = StringVar(value="1")
        self.mic_record_seconds = StringVar(value="60")
        self.monitor_status_text = StringVar(value="Canli monitor kapali")
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
        self.last_export_path: Optional[Path] = None
        self.last_session_summary_path: Optional[Path] = None
        self.recent_exports_text = StringVar(value="Ses dosyasi yok.")
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
            text="Önce mikrofonu test edin, sonra kaydı alın. Aygıt kimliği bilmiyorsanız alanları boş bırakın.",
            bg="#182028",
            fg="#c7d2de",
            justify="left",
            wraplength=620,
        ).pack(anchor="w", padx=14, pady=(0, 14))
        Label(
            hero,
            text=f"Surum {self.app_version} | Profesyonel kayit, export ve oturum takibi",
            bg="#182028",
            fg="#9fb0c2",
            justify="left",
            wraplength=620,
        ).pack(anchor="w", padx=14, pady=(0, 10))
        Button(hero, text="Hakkinda", command=self.show_about, bg="#34495e", fg="white").pack(anchor="w", padx=14, pady=(0, 14))

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
        Label(preset_row, text="Preset Adi", bg="#151b22", fg="#dce6ef").grid(row=0, column=0, sticky="w")
        Entry(preset_row, textvariable=self.preset_name, width=18).grid(row=1, column=0, sticky="w", pady=(2, 8))
        Label(preset_row, text="Kayitli Presetler", bg="#151b22", fg="#dce6ef").grid(row=0, column=1, sticky="w", padx=(18, 0))
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
        Button(meter_buttons, text="Monitor Ac", command=self.start_live_monitor, bg="#16a085", fg="white").pack(side="left", padx=(8, 0))
        Button(meter_buttons, text="Monitor Kapat", command=self.stop_live_monitor, bg="#8e44ad", fg="white").pack(side="left", padx=(8, 0))
        Label(setup, textvariable=self.monitor_status_text, bg="#151b22", fg="#9fb0c2", justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        media = self.create_section(title="Kayıt Kaynağı", subtitle="Backing track seçebilir veya sadece mikrofon kaydı alabilirsiniz.")
        Label(media, text="Arka Plan Müzik", bg="#151b22", fg="#f4f7fb", font=("Helvetica", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        self.backing_label = Label(media, text="Dosya seçilmedi", fg="#9aa7b5", bg="#151b22")
        self.backing_label.pack(anchor="w", padx=14)
        media_buttons = Frame(media, bg="#151b22")
        media_buttons.pack(anchor="w", padx=14, pady=10)
        Button(media_buttons, text="Müzik Dosyası Seç", command=self.select_backing, bg="#2d7d46", fg="white").pack(side="left")
        Button(media_buttons, text="Müziği Temizle", command=self.clear_backing, bg="#5d6d7e", fg="white").pack(side="left", padx=(8, 0))

        export = self.create_section(title="Çıktı", subtitle="Kayıt klasörünü seçin; MP3 ve WAV dosyaları oraya yazılır.")
        Label(export, text="Çıkış Klasörü", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(12, 2))
        Entry(export, textvariable=self.output_dir, width=48).pack(anchor="w", padx=14)
        Button(export, text="Klasör Seç", command=self.select_output_dir, bg="#34495e", fg="white").pack(anchor="w", padx=14, pady=(8, 10))
        Label(export, text="Oturum Modu", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(8, 2))
        session_mode_menu = OptionMenu(export, self.session_mode, "Tek Klasor", "Tarihli Oturum", "Isimli Oturum")
        session_mode_menu.pack(anchor="w", padx=14)
        Label(export, text="Oturum Adi", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(8, 2))
        Entry(export, textvariable=self.session_name, width=32).pack(anchor="w", padx=14)
        Label(export, text="Çıkış Dosya Adı (MP3)", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(12, 2))
        Entry(export, textvariable=self.output_name, width=48).pack(anchor="w", padx=14)
        Label(export, text="MP3 Kalitesi", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        mp3_quality_menu = OptionMenu(export, self.mp3_quality, "Yuksek VBR", "320 kbps", "192 kbps", "128 kbps")
        mp3_quality_menu.pack(anchor="w", padx=14)
        Label(export, text="WAV Export", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        wav_export_menu = OptionMenu(export, self.wav_export_mode, "Sadece Vocal WAV", "Mix + Vocal WAV", "Sadece WAV (Mix + Vocal)")
        wav_export_menu.pack(anchor="w", padx=14)
        Label(export, text="Sadece Mikrofon Süresi (sn)", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        Entry(export, textvariable=self.mic_record_seconds, width=12).pack(anchor="w", padx=14)
        Label(export, text="Kayıt Sınırı (saat)", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(10, 2))
        limit_menu = OptionMenu(export, self.record_limit_hours, "1", "2")
        limit_menu.pack(anchor="w", padx=14, pady=(0, 12))

        tone = self.create_section(title="Ton Ayarları", subtitle="Amfi karakterini ve distorsiyonu burada ayarlayın.")
        self.gain = self.make_slider(tone, "Kazanç (dB)", -12, 24, 6)
        self.boost = self.make_slider(tone, "Güçlendirme (dB)", 0, 18, 6)
        self.high_pass_hz = self.make_slider(tone, "High-Pass (Hz)", 0, 240, 70)
        self.bass = self.make_slider(tone, "Bas (dB)", -12, 12, 3)
        self.presence = self.make_slider(tone, "Presence (dB)", -12, 12, 2)
        self.treble = self.make_slider(tone, "Tiz (dB)", -12, 12, 2)
        self.distortion = self.make_slider(tone, "Distorsiyon (%)", 0, 100, 25)

        mix = self.create_section(title="Mix ve Temizlik", subtitle="Arka plan/vokal seviyesi ve son çıkış işlemleri.")
        self.backing_level = self.make_slider(mix, "Arka Plan Seviye (%)", 0, 200, 100)
        self.vocal_level = self.make_slider(mix, "Vokal Seviye (%)", 0, 200, 85)
        self.noise_reduction = self.make_slider(mix, "Gürültü Azaltma (%)", 0, 100, 25)
        self.noise_gate_threshold = self.make_slider(mix, "Noise Gate Eşigi (%)", 0, 100, 25)
        self.monitor_level = self.make_slider(mix, "Canli Monitor Seviye (%)", 0, 200, 100)
        self.compressor_amount = self.make_slider(mix, "Kompresor Miktari (%)", 0, 100, 35)
        self.compressor_threshold = self.make_slider(mix, "Kompresor Threshold (dB)", -36, -6, -18)
        self.compressor_makeup = self.make_slider(mix, "Makeup Gain (dB)", 0, 18, 4)
        Label(mix, text="Limiter", bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14, pady=(6, 2))
        limiter_menu = OptionMenu(mix, self.limiter_enabled, "Acik", "Kapali")
        limiter_menu.pack(anchor="w", padx=14)
        self.speed_ratio = self.make_slider(mix, "Hız (%)", 50, 150, 100)
        self.output_gain = self.make_slider(mix, "Çıkış Kazancı (dB)", -12, 12, 0)

        actions = self.create_section(title="İşlem", subtitle="Önce test, sonra quick kayıt veya tam kayıt.")
        Button(actions, text="Mikrofon/Ses Kartı Testi (5 sn)", command=self.start_test_thread, bg="#1f6feb", fg="white").pack(
            fill="x", padx=14, pady=(12, 6)
        )
        Button(actions, text="Quick Kayıt (Preset, Sorusuz)", command=self.start_quick_record_thread, bg="#8e44ad", fg="white").pack(
            fill="x", padx=14, pady=(0, 6)
        )
        Button(actions, text="Kaydı Başlat ve MP3 Çıkar", command=self.start_recording_thread, bg="#27ae60", fg="white").pack(
            fill="x", padx=14, pady=(0, 6)
        )
        self.stop_recording_button = Button(actions, text="Kaydı Durdur ve Kaydet", command=self.request_stop_recording, bg="#c0392b", fg="white", state="disabled")
        self.stop_recording_button.pack(fill="x", padx=14, pady=(0, 14))

        progress_box = self.create_section(title="Kayıt Durumu", subtitle="Kayıt sırasında geçen süre ve kalan süre burada görünür.")
        self.progress_label = Label(
            progress_box,
            textvariable=self.record_progress_text,
            bg="#151b22",
            fg="#dce6ef",
            wraplength=640,
            justify="left",
        )
        self.progress_label.pack(anchor="w", padx=14, pady=(12, 14))

        recent_box = self.create_section(title="Son Ciktilar", subtitle="Son uretilen dosyayi Finder'da acabilir ve son exportlari gorebilirsiniz.")
        recent_buttons = Frame(recent_box, bg="#151b22")
        recent_buttons.pack(fill="x", padx=14, pady=(12, 8))
        self.open_last_export_button = Button(
            recent_buttons,
            text="Son Dosyayi Finder'da Goster",
            command=self.open_last_export_in_finder,
            bg="#1f6feb",
            fg="white",
            state="disabled",
        )
        self.open_last_export_button.pack(side="left")
        self.open_last_summary_button = Button(
            recent_buttons,
            text="Son Oturum Ozetini Ac",
            command=self.open_last_session_summary,
            bg="#6c5ce7",
            fg="white",
            state="disabled",
        )
        self.open_last_summary_button.pack(side="left", padx=(8, 0))
        Button(recent_buttons, text="Klasoru Ac", command=self.open_output_dir_in_finder, bg="#34495e", fg="white").pack(side="left", padx=(8, 0))
        Button(recent_buttons, text="Listeyi Yenile", command=self.refresh_recent_exports_from_action, bg="#2d7d46", fg="white").pack(side="left", padx=(8, 0))
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
        for variable in (
            self.output_name,
            self.output_dir,
            self.session_mode,
            self.session_name,
            self.mp3_quality,
            self.wav_export_mode,
            self.preset_name,
            self.record_limit_hours,
            self.mic_record_seconds,
        ):
            variable.trace_add("write", self.refresh_recording_readiness)
        self.inspect_devices(initial=True)
        self.root.after(80, self.apply_startup_preset)
        self.root.after(120, self.update_meter_ui)
        self.root.after(200, self.update_recording_progress_ui)
        self.root.after(220, self.refresh_recent_exports)
        self.root.after(250, self.start_input_meter)
        self.refresh_recording_readiness()

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

    def make_slider(self, parent: Frame, label: str, min_v: int, max_v: int, default: int) -> Scale:
        Label(parent, text=label, bg="#151b22", fg="#dce6ef").pack(anchor="w", padx=14)
        slider = Scale(parent, from_=min_v, to=max_v, orient=HORIZONTAL, length=620, resolution=1, bg="#151b22", fg="#dce6ef")
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

    def show_about(self) -> None:
        self.set_status(
            f"Gitar Amfi Kaydedici {self.app_version} | Canli monitor, kompresor/limiter, oturum klasorleri, session summary ve son oturum yukleme desteklenir."
        )

    def clear_device_selection(self) -> None:
        self.input_device_choice.set("Varsayılan macOS girişi")
        self.output_device_choice.set("Varsayılan macOS çıkışı")
        self.input_device_id.set("")
        self.output_device_id.set("")
        self.restart_input_meter()
        self.set_status("Aygıt kimlikleri temizlendi. Varsayılan mikrofon ve çıkış kullanılacak.")

    def apply_clean_macbook_preset(self) -> None:
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
            return merge_builtin_presets({"selected": "Temiz Gitar", "presets": {"Varsayilan": raw}})
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
                if last_session.get("session_mode") == "Tek Klasor":
                    self.output_dir.set(str(path))
                elif path.parent.exists():
                    self.output_dir.set(str(path.parent))
                    self.session_name.set(path.name)
            session_mode = str(last_session.get("session_mode", "")).strip()
            if session_mode:
                self.session_mode.set(session_mode)
            self.restore_last_session_summary(last_session)
            self.refresh_recent_exports()
            self.set_status(f"Son oturum hazir: {output_dir}")

    def collect_current_preset(self) -> dict:
        return {
            "input_device_choice": self.input_device_choice.get(),
            "output_device_choice": self.output_device_choice.get(),
            "input_device_id": self.input_device_id.get(),
            "output_device_id": self.output_device_id.get(),
            "output_name": self.output_name.get(),
            "output_dir": self.output_dir.get(),
            "session_mode": self.session_mode.get(),
            "session_name": self.session_name.get(),
            "mp3_quality": self.mp3_quality.get(),
            "wav_export_mode": self.wav_export_mode.get(),
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
            "limiter_enabled": self.limiter_enabled.get(),
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
        self.session_mode.set(str(preset.get("session_mode", self.session_mode.get())))
        self.session_name.set(str(preset.get("session_name", self.session_name.get())))
        self.mp3_quality.set(str(preset.get("mp3_quality", self.mp3_quality.get())))
        self.wav_export_mode.set(str(preset.get("wav_export_mode", self.wav_export_mode.get())))
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
        self.limiter_enabled.set(str(preset.get("limiter_enabled", "Acik")))
        self.speed_ratio.set(int(preset.get("speed_ratio", 100)))
        self.output_gain.set(int(preset.get("output_gain", 0)))

        self.restart_input_meter()

    def save_current_preset(self) -> None:
        try:
            name = self.preset_name.get().strip() or "Temiz Gitar"
            store = self.load_preset_store_data()
            store.setdefault("presets", {})[name] = self.collect_current_preset()
            store["selected"] = name
            self.write_preset_store_data(store)
            self.refresh_preset_menu(name)
            self.set_status(f"Preset kaydedildi: {name}")
        except Exception as exc:
            self.set_status(f"Preset kaydetme hatası: {exc}")

    def load_saved_preset(self) -> None:
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
        try:
            name = self.preset_name.get().strip()
            if not name:
                self.set_status("Silinecek preset secilmedi.")
                return
            store = self.load_preset_store_data()
            presets = store.get("presets", {})
            if name not in presets:
                self.set_status(f"Preset bulunamadi: {name}")
                return
            del presets[name]
            if not presets:
                store = self.default_preset_store()
                self.write_preset_store_data(store)
                self.refresh_preset_menu("Temiz Gitar")
                self.set_status(f"Preset silindi: {name}. Tum kullanici presetleri temizlendi.")
                return
            next_name = sorted(presets.keys())[0]
            store["selected"] = next_name
            self.write_preset_store_data(store)
            self.refresh_preset_menu(next_name)
            self.set_status(f"Preset silindi: {name}")
        except Exception as exc:
            self.set_status(f"Preset silme hatası: {exc}")

    def fill_recommended_devices(self) -> None:
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
        selected_dir = filedialog.askdirectory(title="Çıkış klasörünü seç")
        if not selected_dir:
            return
        self.output_dir.set(selected_dir)
        self.set_status(f"Çıkış klasörü seçildi: {selected_dir}")
        self.refresh_recent_exports()

    def resolve_output_dir(self) -> Path:
        base_dir = Path(self.output_dir.get().strip() or str(Path.home() / "Desktop")).expanduser()
        mode = self.session_mode.get()
        if mode == "Tarihli Oturum":
            return base_dir / time.strftime("%Y-%m-%d_%H-%M-%S")
        if mode == "Isimli Oturum":
            return base_dir / self.safe_session_name()
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
        quick_name = next_take_name_for_dir(target_dir, "quick_take")
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
        return "\n".join(lines)

    def refresh_recording_readiness(self, *_args) -> None:
        if self.recording_active:
            return
        self.record_progress_text.set(self.build_recording_readiness_summary())

    def build_session_summary(self, output_dir: Path, generated_files: list[Path], event: str) -> dict:
        return {
            "app_version": self.app_version,
            "event": event,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "output_dir": str(output_dir),
            "preset_name": self.preset_name.get(),
            "session_mode": self.session_mode.get(),
            "session_name": self.session_name.get(),
            "input_device_choice": self.input_device_choice.get(),
            "output_device_choice": self.output_device_choice.get(),
            "input_device_id": self.input_device_id.get(),
            "output_device_id": self.output_device_id.get(),
            "backing_file": str(self.backing_file) if self.backing_file else "",
            "export": {
                "output_name": self.output_name.get(),
                "mp3_quality": self.mp3_quality.get(),
                "wav_export_mode": self.wav_export_mode.get(),
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
                "limiter_enabled": self.limiter_enabled.get(),
                "speed_ratio": int(self.speed_ratio.get()),
                "output_gain": int(self.output_gain.get()),
            },
            "generated_files": [str(path) for path in generated_files],
        }

    def write_session_summary(self, output_dir: Path, generated_files: list[Path], event: str) -> Optional[Path]:
        try:
            summary_path = output_dir / "session_summary.json"
            summary = self.build_session_summary(output_dir, generated_files, event)
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return summary_path
        except Exception:
            return None

    def write_last_session_state(self, output_dir: Path, summary_path: Optional[Path] = None) -> None:
        try:
            effective_summary_path = summary_path or self.last_session_summary_path
            data = {
                "app_version": self.app_version,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "output_dir": str(output_dir),
                "session_mode": self.session_mode.get(),
                "session_name": self.session_name.get(),
                "preset_name": self.preset_name.get(),
                "summary_path": str(effective_summary_path) if effective_summary_path else "",
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

    def restore_last_session_summary(self, data: dict) -> None:
        summary_text = str(data.get("summary_path", "")).strip()
        summary_path = Path(summary_text) if summary_text else None
        self.last_session_summary_path = summary_path if summary_path and summary_path.exists() else None
        self.restore_last_export_from_summary()
        self.refresh_recent_output_buttons()

    def restore_last_export_from_summary(self) -> None:
        self.last_export_path = None
        summary_path = self.last_session_summary_path
        if summary_path is None or not summary_path.exists():
            return
        try:
            raw = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            return
        generated_files = raw.get("generated_files", [])
        if not isinstance(generated_files, list):
            return
        existing_files = []
        for item in generated_files:
            path = Path(str(item))
            if path.exists():
                existing_files.append(path)
        if existing_files:
            self.last_export_path = existing_files[0]

    def reload_last_session(self) -> None:
        data = self.load_last_session_state()
        if not data:
            self.set_status("Son oturum bilgisi bulunamadi.")
            return
        output_dir = str(data.get("output_dir", "")).strip()
        if output_dir:
            path = Path(output_dir)
            if path.parent.exists():
                if data.get("session_mode") == "Tek Klasor":
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
        self.restore_last_session_summary(data)
        self.refresh_recent_exports()
        self.set_status(f"Son oturum yuklendi: {output_dir or 'bilinmiyor'}")

    def refresh_recent_exports(self) -> None:
        output_dir = self.resolve_output_dir()
        if not output_dir.exists():
            self.last_export_path = None
            self.last_session_summary_path = None
            output_dir_text = self.format_display_path(output_dir)
            self.recent_exports_text.set(
                f"Cikis klasoru bulunamadi: {output_dir_text}\n"
                "Bu cikis klasorune su an ulasilamiyor.\n"
                "'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz."
            )
            self.refresh_recent_output_buttons()
            return
        output_dir_text = self.format_display_path(output_dir)
        self.restore_session_summary_from_output_dir(output_dir)
        summary_line = self.recent_session_summary_line(output_dir)
        all_audio_files = [
            path for path in output_dir.iterdir() if path.is_file() and path.suffix.lower() in {".mp3", ".wav"}
        ]
        recent_files = sorted(
            all_audio_files,
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:6]
        count_line = f"Top {len(all_audio_files)}"
        if len(all_audio_files) > len(recent_files):
            count_line += " | Gr son 6"
        elif len(recent_files) == 1:
            count_line += " | Gr 1"
        elif recent_files:
            count_line += " | Gr tumu"
        else:
            if summary_line:
                count_line += " | Ozet"
        if len(recent_files) > 1:
            count_line += " | Yeni"
        if not recent_files:
            self.last_export_path = None
            lines = [f"Klasor {output_dir_text}"]
            lines.append(count_line)
            if summary_line:
                lines.append("Ses dosyasi yok. Alttaki ozeti acin.")
                lines.append(summary_line)
            else:
                lines.append("Ses dosyasi yok. Yeni kayitlar burada gorunur.")
            self.recent_exports_text.set("\n".join(lines))
            self.refresh_recent_output_buttons()
            return
        current_export = self.last_export_path
        if (
            current_export is None
            or not current_export.exists()
            or current_export.parent != output_dir
            or current_export != recent_files[0]
        ):
            self.last_export_path = recent_files[0]
        lines = [f"Klasor {output_dir_text}"]
        lines.append(count_line)
        for index, path in enumerate(recent_files):
            label = f"- {path.name}"
            if index == 0:
                label += " (Export)"
            lines.append(label)
        hidden_count = max(0, len(all_audio_files) - len(recent_files))
        if hidden_count:
            lines.append(
                f"+{hidden_count}"
            )
        if summary_line:
            lines.append(summary_line)
        self.recent_exports_text.set("\n".join(lines))
        self.refresh_recent_output_buttons()

    def refresh_recent_exports_from_action(self) -> None:
        self.refresh_recent_exports()
        output_dir = self.resolve_output_dir()
        if not output_dir.exists():
            self.set_status(
                f"Guncel. Cikis klasoru bulunamadi: {self.format_display_path(output_dir)}. "
                "'Klasoru Ac' ile yeniden olusturabilir ve Finder'da acabilirsiniz."
            )
            return
        audio_files = [
            path for path in output_dir.iterdir() if path.is_file() and path.suffix.lower() in {".mp3", ".wav"}
        ]
        if not audio_files:
            if self.last_session_summary_path is not None and self.last_session_summary_path.exists():
                self.set_status(
                    "Guncel. "
                    "Ozet acilabilir."
                )
            else:
                self.set_status(
                    "Guncel. "
                    "Yeni kayitlar burada gorunur."
                )
            return
        shown_count = min(len(audio_files), 6)
        if len(audio_files) > shown_count:
            visibility_suffix = " Gr son 6."
        elif shown_count == 1:
            visibility_suffix = " Gr 1."
        else:
            visibility_suffix = " Gr tumu."
        sort_suffix = " Yeni." if shown_count > 1 else ""
        summary_suffix = ""
        if self.last_session_summary_path is not None and self.last_session_summary_path.exists():
            summary_suffix = " Ozet acilabilir."
        self.set_status(
            f"Guncel. {len(audio_files)} ses dosyasi.{visibility_suffix}{sort_suffix}{summary_suffix}"
        )

    def format_display_path(self, path: Path) -> str:
        try:
            home = Path.home().resolve()
            resolved = path.expanduser().resolve()
            if resolved == home:
                return "~"
            if home in resolved.parents:
                return f"~/{resolved.relative_to(home)}"
        except Exception:
            pass
        return str(path)

    def recent_session_summary_line(self, output_dir: Path) -> str:
        summary_path = self.last_session_summary_path
        if summary_path is None or not summary_path.exists():
            candidate = output_dir / "session_summary.json"
            summary_path = candidate if candidate.exists() else None
        if summary_path is None:
            return ""
        return "- session_summary.json (Ozet)"

    def restore_session_summary_from_output_dir(self, output_dir: Path) -> None:
        candidate = output_dir / "session_summary.json"
        current = self.last_session_summary_path
        if current is not None and current.exists() and current == candidate:
            return
        if candidate.exists():
            self.last_session_summary_path = candidate
        else:
            self.last_session_summary_path = None

    def refresh_recent_output_buttons(self) -> None:
        export_button = getattr(self, "open_last_export_button", None)
        summary_button = getattr(self, "open_last_summary_button", None)
        try:
            if export_button is not None:
                export_state = "normal" if self.last_export_path is not None and self.last_export_path.exists() else "disabled"
                export_button.configure(state=export_state)
            if summary_button is not None:
                summary_state = (
                    "normal" if self.last_session_summary_path is not None and self.last_session_summary_path.exists() else "disabled"
                )
                summary_button.configure(state=summary_state)
        except TclError:
            pass

    def refresh_recent_outputs_if_available(self) -> None:
        refresh = getattr(self, "refresh_recent_exports", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass

    def open_output_dir_in_finder(self) -> None:
        output_dir = self.resolve_output_dir()
        try:
            created_now = not output_dir.exists()
            output_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(["open", str(output_dir)], check=False)
            self.refresh_recent_exports()
            prefix = "Klasor hazirlandi ve acildi" if created_now else "Klasor acildi"
            self.set_status(f"{prefix}: {self.format_display_path(output_dir)}")
        except Exception as exc:
            self.set_status(f"Klasor acilamadi: {exc}")

    def open_last_export_in_finder(self) -> None:
        self.refresh_recent_outputs_if_available()
        if self.last_export_path is None or not self.last_export_path.exists():
            self.last_export_path = None
            self.refresh_recent_output_buttons()
            self.set_status("Son export dosyasi bulunamadi; son ciktilar yenilendi.")
            return
        try:
            subprocess.run(["open", "-R", str(self.last_export_path)], check=False)
            self.set_status(f"Son export Finder'da gosteriliyor: {self.last_export_path.name}")
        except Exception as exc:
            self.set_status(f"Finder acilamadi: {exc}")

    def open_last_session_summary(self) -> None:
        self.refresh_recent_outputs_if_available()
        if self.last_session_summary_path is None or not self.last_session_summary_path.exists():
            self.last_session_summary_path = None
            self.refresh_recent_output_buttons()
            self.set_status("Son oturum ozeti bulunamadi; son ciktilar yenilendi.")
            return
        try:
            subprocess.run(["open", str(self.last_session_summary_path)], check=False)
            self.set_status(f"Oturum ozeti aciliyor: {self.last_session_summary_path.name}")
        except Exception as exc:
            self.set_status(f"Ozet acilamadi: {exc}")

    def build_device_summary(self) -> str:
        inputs = list_input_devices()
        outputs = list_output_devices()
        input_lines = [f"• {idx}: {name}" for idx, name in inputs[:5]]
        output_lines = [f"• {idx}: {name}" for idx, name in outputs[:5]]
        input_text = "\n".join(input_lines) if input_lines else "• Mikrofon girişi bulunamadı."
        output_text = "\n".join(output_lines) if output_lines else "• Çıkış aygıtı bulunamadı."
        return f"Giriş Aygıtları ({len(inputs)}):\n{input_text}\n\nÇıkış Aygıtları ({len(outputs)}):\n{output_text}"

    def inspect_devices(self, initial: bool = False) -> None:
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
            return ("Dusuk: daha guclu calin/soyleyin veya gain artirin", "#d29922")
        return ("Cok dusuk: sinyal neredeyse yok", "#8b949e")

    def validate_recording_safety(self) -> tuple[bool, str]:
        if not self.output_dir.get().strip():
            return False, "Kayit oncesi cikis klasoru secin."
        try:
            output_dir = self.resolve_output_dir()
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            return False, f"Cikis klasoru hazirlanamadi: {exc}"
        if self.last_input_peak >= 0.985:
            return False, "Giris clipping yapiyor. Once kazanci dusurun veya monitor/test ile seviyeyi duzeltin."
        if self.last_input_peak < 0.01:
            return True, "Uyari: giris seviyesi cok dusuk. Kayit alinabilir ama ses zayif olabilir."
        if self.last_input_peak < 0.05:
            return True, "Uyari: giris seviyesi dusuk. Gerekirse gain artirin."
        return True, ""

    def meter_callback(self, indata, _frames, _time_info, status) -> None:
        if status:
            self.meter_error_message = f"Meter uyarısı: {status}"
        if indata is None or len(indata) == 0:
            return
        self.update_level_tracking(indata[:, 0])

    def monitor_callback(self, indata, outdata, _frames, _time_info, status) -> None:
        if status:
            self.meter_error_message = f"Monitor uyarısı: {status}"
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
                self.meter_text.set(f"Canlı giriş: %{int(level * 100)} | Peak: %{int(peak_level * 100)}")
            elif not self.meter_text.get():
                self.meter_text.set("Meter duruyor.")
            if now < self.meter_clipping_until:
                self.clip_text.set("UYARI: clipping algilandi, giris kazancini dusurun")
                self.clip_label.configure(fg="#ff7b72")
            elif peak_level > 0.9:
                self.clip_text.set("Headroom: sinira yakin")
                self.clip_label.configure(fg="#f39c12")
            else:
                self.clip_text.set("Headroom: guvenli")
                self.clip_label.configure(fg="#7ee787")
            safety_message, safety_color = self.classify_input_level(peak_level)
            self.safety_text.set(f"Guvenlik: {safety_message}")
            self.safety_label.configure(fg=safety_color)
            self.refresh_recording_readiness()
            self.root.after(120, self.update_meter_ui)
        except TclError:
            pass

    def start_input_meter(self) -> None:
        try:
            input_idx, _ = self.selected_device_pair()
        except ValueError:
            self.meter_text.set("Meter başlatılamadı: aygıt kimliği sayısal olmalı.")
            return
        self.stop_live_monitor()
        self.stop_input_meter()
        input_count, _ = describe_device_state()
        if input_count == 0:
            self.meter_text.set("Meter başlatılamadı: mikrofon girişi bulunamadı.")
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
            self.meter_text.set("Canlı mikrofon seviyesi izleniyor. Konuşun veya gitar çalın.")
        except Exception as exc:
            self.meter_stream = None
            self.meter_text.set(f"Meter başlatılamadı: {exc}")

    def start_live_monitor(self) -> None:
        try:
            input_idx, output_idx = self.selected_device_pair()
        except ValueError:
            self.set_status("Monitor baslatilamadi: aygit kimligi sayisal olmali.")
            return
        self.stop_input_meter()
        self.stop_live_monitor()
        input_count, output_count = describe_device_state()
        if input_count == 0 or output_count == 0:
            self.set_status("Monitor baslatilamadi: giris veya cikis aygiti bulunamadi.")
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
            self.monitor_status_text.set("Canli monitor acik. Kulaklik kullanin.")
            self.meter_text.set("Canli monitor acik. Gecikmeyi azaltmak icin kulaklik onerilir.")
        except Exception as exc:
            self.monitor_stream = None
            self.monitor_status_text.set(f"Canli monitor acilamadi: {exc}")

    def stop_live_monitor(self) -> None:
        stream = self.monitor_stream
        self.monitor_stream = None
        if stream is None:
            self.monitor_status_text.set("Canli monitor kapali")
            return
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
        self.monitor_status_text.set("Canli monitor kapali")

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
        self.meter_text.set("Meter durduruldu.")
        self.clip_text.set("Headroom: guvenli")
        self.safety_text.set("Guvenlik: seviye analizi bekleniyor")

    def restart_input_meter(self) -> None:
        if self.monitor_stream is not None:
            return
        self.root.after(50, self.start_input_meter)

    def begin_recording_progress(self, mode: str, total_seconds: float) -> None:
        self.recording_active = True
        self.recording_started_at = time.time()
        self.recording_target_seconds = max(0.0, float(total_seconds))
        self.recording_mode = mode
        self.stop_recording_requested = False
        try:
            self.stop_recording_button.configure(state="normal")
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
            self.stop_recording_button.configure(state="disabled")
        except TclError:
            pass
        self.refresh_recent_output_buttons()

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
        except TclError:
            pass
        try:
            sd.stop()
        except Exception:
            pass

    def on_close(self) -> None:
        try:
            self.write_last_session_state(self.resolve_output_dir())
        except Exception:
            pass
        self.stop_live_monitor()
        self.stop_input_meter()
        self.root.destroy()

    def select_backing(self) -> None:
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
        self.refresh_recording_readiness()
        self.set_status(f"Arka plan muzigi secildi: {self.backing_file.name}. Backing + mikrofon kaydi hazir.")

    def clear_backing(self) -> None:
        if self.backing_file is None:
            self.set_status("Arka plan muzigi zaten secili degil.")
            return
        self.backing_file = None
        self.backing_label.config(text="Dosya seçilmedi", fg="#9aa7b5")
        self.refresh_recording_readiness()
        self.set_status("Arka plan muzigi temizlendi. Sadece mikrofon kaydi hazir.")

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
        return self.wav_export_mode.get() != "Sadece WAV (Mix + Vocal)"

    def should_export_mix_wav(self) -> bool:
        return self.wav_export_mode.get() in {"Mix + Vocal WAV", "Sadece WAV (Mix + Vocal)"}

    def ffmpeg_mp3_args(self) -> list[str]:
        quality = self.mp3_quality.get()
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
        if self.limiter_enabled.get() == "Acik":
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
            self.last_export_path = test_path
            summary_path = self.write_session_summary(output_dir, [test_path], "device_test")
            self.last_session_summary_path = summary_path if summary_path and summary_path.exists() else None
            self.write_last_session_state(output_dir, summary_path)
            self.refresh_recent_exports()

            peak = float(np.max(np.abs(voice))) if len(voice) else 0.0
            self.set_status(f"Test tamam. Peak={peak:.3f} | Dosya: {test_path}")
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
        base_name = self.output_name.get().strip() or f"guitar_mix_{time.strftime('%Y%m%d_%H%M%S')}"
        worker = threading.Thread(
            target=self.record_and_export,
            args=(self.backing_file, input_idx, output_idx, settings, base_name),
            daemon=True,
        )
        worker.start()

    def start_quick_record_thread(self) -> None:
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
        base_name = next_take_name_for_dir(self.resolve_output_dir(), "quick_take")
        worker = threading.Thread(
            target=self.record_and_export,
            args=(None, input_idx, output_idx, settings, base_name),
            daemon=True,
        )
        worker.start()

    def record_and_export(
        self,
        backing_file: Optional[Path],
        input_idx: Optional[int],
        output_idx: Optional[int],
        settings: Tuple[float, float, float, float, float, float, float],
        base_name: str,
    ) -> None:
        try:
            output_dir = self.resolve_output_dir()
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
                    self.set_status(f"Sample rate {backing_sr} -> {target_sr} dönüştürülüyor...")
                    backing = resample_linear(backing, backing_sr, target_sr)

                max_frames = sr * limit_seconds
                if len(backing) > max_frames:
                    self.set_status(f"Kayıt sınırı {limit_seconds // 3600} saat olarak uygulandı, dosya kırpıldı.")
                    backing = backing[:max_frames]

                duration_sec = len(backing) / sr
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
            if self.limiter_enabled.get() == "Acik":
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

                notes: list[str] = []
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
                    notes.append(f"MP3: {mp3_path}")
                elif self.should_export_mp3():
                    if not self.should_export_mix_wav():
                        sf.write(mix_wav_path, mix, sr)
                    notes.append(f"ffmpeg yok, MP3 yerine WAV mix kaydedildi: {mix_wav_path}")
                else:
                    notes.append("MP3 export kapali")

                if self.should_export_mix_wav():
                    notes.append(f"Mix WAV: {mix_wav_path}")
                notes.append(f"Vocal WAV: {vocal_wav_path}")
                if self.should_export_mp3() and ffmpeg_bin and mp3_path.exists():
                    self.last_export_path = mp3_path
                elif self.should_export_mix_wav() and mix_wav_path.exists():
                    self.last_export_path = mix_wav_path
                else:
                    self.last_export_path = vocal_wav_path
                generated_files = [path for path in [mp3_path, mix_wav_path, vocal_wav_path] if path.exists()]
                summary_path = self.write_session_summary(output_dir, generated_files, "record_export")
                self.last_session_summary_path = summary_path if summary_path and summary_path.exists() else None
                self.write_last_session_state(output_dir, summary_path)
                if summary_path is not None:
                    notes.append(f"Oturum Ozeti: {summary_path}")
                final_note = " | ".join(notes)
            finally:
                if tmp_wav_path.exists():
                    tmp_wav_path.unlink()

            self.set_status(
                f"Tamamlandı. {final_note}"
            )
            self.refresh_recent_exports()
            self.finish_recording_progress(f"Hazır | Klasör: {output_dir}")
        except Exception as exc:
            self.finish_recording_progress("Kayıt durumu: hata")
            self.set_status(f"Hata: {exc}")


def main() -> None:
    configure_tcl_tk_environment()
    root = Tk()
    GuitarAmpRecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
