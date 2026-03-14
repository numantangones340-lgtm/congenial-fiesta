import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import Tk, Label, Button, Scale, HORIZONTAL, filedialog, StringVar, Entry, OptionMenu, TclError, Canvas, Frame, Scrollbar, messagebox
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
import soundfile as sf


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


def apply_amp_chain(
    voice: np.ndarray,
    sample_rate: int,
    gain_db: float,
    boost_db: float,
    bass_db: float,
    treble_db: float,
    distortion: float,
) -> np.ndarray:
    x = voice.astype(np.float32)

    x = x * db_to_linear(gain_db + boost_db)

    low = one_pole_lowpass(x, sample_rate, 220.0)
    high_base = one_pole_lowpass(x, sample_rate, 2800.0)
    high = x - high_base

    bass_mix = (db_to_linear(bass_db) - 1.0)
    treble_mix = (db_to_linear(treble_db) - 1.0)
    x = x + low * bass_mix + high * treble_mix

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


def reduce_background_noise(signal: np.ndarray, sample_rate: int, strength: float) -> np.ndarray:
    if strength <= 0 or len(signal) == 0:
        return signal

    # İlk 0.5 saniyeyi referans alıp basit bir gürültü kapısı uygular.
    ref_frames = max(1, int(sample_rate * 0.5))
    noise_ref = signal[:ref_frames]
    noise_floor = float(np.median(np.abs(noise_ref)))
    threshold = noise_floor * (1.0 + strength * 4.0)
    attenuation = max(0.05, 1.0 - strength * 0.9)

    out = signal.copy()
    mask = np.abs(out) < threshold
    out[mask] *= attenuation
    return out.astype(np.float32)


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


def detect_ffmpeg() -> Optional[str]:
    candidates = [
        shutil.which("ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return None


PRESETS = {
    "Clean (Temiz)": {
        "gain": 3,
        "boost": 2,
        "bass": 2,
        "treble": 3,
        "distortion": 6,
        "backing_level": 100,
        "vocal_level": 90,
        "noise_reduction": 22,
        "speed_ratio": 100,
        "output_gain": -1,
        "record_limit_hours": "1",
    },
    "Crunch (Ritmik)": {
        "gain": 7,
        "boost": 5,
        "bass": 4,
        "treble": 4,
        "distortion": 30,
        "backing_level": 92,
        "vocal_level": 98,
        "noise_reduction": 26,
        "speed_ratio": 100,
        "output_gain": -2,
        "record_limit_hours": "1",
    },
    "Lead (Solo)": {
        "gain": 9,
        "boost": 7,
        "bass": 5,
        "treble": 6,
        "distortion": 48,
        "backing_level": 82,
        "vocal_level": 108,
        "noise_reduction": 30,
        "speed_ratio": 100,
        "output_gain": -2,
        "record_limit_hours": "1",
    },
}


def profile_slug(profile_label: str) -> str:
    label = profile_label.split("(", 1)[0].strip().lower()
    tr_map = str.maketrans("çğıöşü", "cgiosu")
    label = label.translate(tr_map)
    label = re.sub(r"[^a-z0-9]+", "_", label).strip("_")
    return label or "preset"


class GuitarAmpRecorderApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Gitar Amfi Kaydedici")
        self.root.geometry("640x760")
        self.root.minsize(560, 620)

        outer = Frame(root)
        outer.pack(fill="both", expand=True)

        self.canvas = Canvas(outer, highlightthickness=0)
        self.scrollbar = Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.content = Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        self.backing_file: Optional[Path] = None

        self.status_text = StringVar(value="Hazır")
        self.output_name = StringVar(value="")
        self.input_device_id = StringVar(value="")
        self.output_device_id = StringVar(value="")
        self.record_limit_hours = StringVar(value="1")

        Label(self.content, text="Mikrofon Aygıt Kimliği (boş = varsayılan):").pack(anchor="w", padx=12, pady=(12, 2))
        Entry(self.content, textvariable=self.input_device_id, width=20).pack(anchor="w", padx=12)

        Label(self.content, text="Çıkış Aygıt Kimliği (boş = varsayılan):").pack(anchor="w", padx=12, pady=(8, 2))
        Entry(self.content, textvariable=self.output_device_id, width=20).pack(anchor="w", padx=12)

        Label(
            self.content,
            text="Not: Aygıt kimliği bilmiyorsanız iki alanı da boş bırakın (en güvenli yol).",
            fg="#2c3e50",
        ).pack(anchor="w", padx=12, pady=(4, 8))

        Label(self.content, text="Arka Plan Müzik:").pack(anchor="w", padx=12, pady=(10, 2))
        self.backing_label = Label(self.content, text="Dosya seçilmedi", fg="gray")
        self.backing_label.pack(anchor="w", padx=12)

        Button(self.content, text="Müzik Dosyası Seç", command=self.select_backing).pack(anchor="w", padx=12, pady=8)

        Label(self.content, text="Çıkış Dosya Adı (MP3):").pack(anchor="w", padx=12, pady=(8, 2))
        Entry(self.content, textvariable=self.output_name, width=48).pack(anchor="w", padx=12)

        self.preset_name = StringVar(value="Clean (Temiz)")
        Label(self.content, text="Hazır Profil:").pack(anchor="w", padx=12, pady=(8, 2))
        OptionMenu(self.content, self.preset_name, *PRESETS.keys()).pack(anchor="w", padx=12, pady=(0, 4))
        Button(
            self.content,
            text="Profili Uygula",
            command=self.apply_selected_preset,
            bg="#fff3e8",
            fg="#111111",
            activeforeground="#111111",
            highlightthickness=1,
        ).pack(fill="x", padx=12, pady=(0, 8))
        Button(
            self.content,
            text="Dosya Adını Otomatik Oluştur",
            command=self.refresh_output_name,
            bg="#f4f4f4",
            fg="#111111",
            activeforeground="#111111",
            highlightthickness=1,
        ).pack(fill="x", padx=12, pady=(0, 8))
        Button(
            self.content,
            text="Yardım (Hızlı Kullanım)",
            command=self.show_help,
            bg="#f3f8ff",
            fg="#111111",
            activeforeground="#111111",
            highlightthickness=1,
        ).pack(fill="x", padx=12, pady=(0, 8))

        self.gain = self.make_slider("Kazanç (dB)", -12, 24, 6)
        self.boost = self.make_slider("Güçlendirme (dB)", 0, 18, 6)
        self.bass = self.make_slider("Bas (dB)", -12, 12, 3)
        self.treble = self.make_slider("Tiz (dB)", -12, 12, 2)
        self.distortion = self.make_slider("Distorsiyon (%)", 0, 100, 25)
        self.backing_level = self.make_slider("Arka Plan Seviye (%)", 0, 200, 100)
        self.vocal_level = self.make_slider("Vokal Seviye (%)", 0, 200, 85)
        self.noise_reduction = self.make_slider("Gürültü Azaltma (%)", 0, 100, 25)
        self.speed_ratio = self.make_slider("Hız (%)", 50, 150, 100)
        self.output_gain = self.make_slider("Çıkış Kazancı (dB)", -12, 12, 0)

        Label(self.content, text="Kayıt Sınırı (saat):").pack(anchor="w", padx=12, pady=(2, 0))
        OptionMenu(self.content, self.record_limit_hours, "1", "2").pack(anchor="w", padx=12, pady=(0, 8))

        Button(
            self.content,
            text="Hızlı Kayıt (Test + Kayıt)",
            command=self.start_quick_record_thread,
            bg="#fff1dc",
            fg="#111111",
            activeforeground="#111111",
            highlightthickness=1,
        ).pack(
            fill="x", padx=12, pady=(8, 4)
        )
        Button(
            self.content,
            text="Mikrofon/Ses Kartı Testi (5 sn)",
            command=self.start_test_thread,
            bg="#eaf2ff",
            fg="#111111",
            activeforeground="#111111",
            highlightthickness=1,
        ).pack(
            fill="x", padx=12, pady=(10, 6)
        )
        Button(
            self.content,
            text="Kaydı Başlat ve MP3 Çıkar",
            command=self.start_recording_thread,
            bg="#e9f9ef",
            fg="#111111",
            activeforeground="#111111",
            highlightthickness=1,
        ).pack(
            fill="x", padx=12, pady=12
        )

        Label(self.content, textvariable=self.status_text, fg="#2c3e50", wraplength=560, justify="left").pack(
            anchor="w", padx=12, pady=(0, 16)
        )
        self.apply_selected_preset()

    def make_slider(self, label: str, min_v: int, max_v: int, default: int) -> Scale:
        Label(self.content, text=label).pack(anchor="w", padx=12)
        slider = Scale(self.content, from_=min_v, to=max_v, orient=HORIZONTAL, length=540, resolution=1)
        slider.set(default)
        slider.pack(anchor="w", padx=12)
        return slider

    def _on_content_configure(self, _event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        if event.num == 5:
            self.canvas.yview_scroll(1, "units")
            return
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
            return
        if event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def apply_selected_preset(self) -> None:
        preset_label = self.preset_name.get()
        preset = PRESETS.get(preset_label)
        if not preset:
            self.set_status(f"Profil bulunamadı: {preset_label}")
            return

        self.gain.set(preset["gain"])
        self.boost.set(preset["boost"])
        self.bass.set(preset["bass"])
        self.treble.set(preset["treble"])
        self.distortion.set(preset["distortion"])
        self.backing_level.set(preset["backing_level"])
        self.vocal_level.set(preset["vocal_level"])
        self.noise_reduction.set(preset["noise_reduction"])
        self.speed_ratio.set(preset["speed_ratio"])
        self.output_gain.set(preset["output_gain"])
        self.record_limit_hours.set(preset["record_limit_hours"])
        self.refresh_output_name()
        self.set_status(f"Profil uygulandı: {preset_label}")

    def refresh_output_name(self) -> None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        slug = profile_slug(self.preset_name.get())
        self.output_name.set(f"guitar_mix_{ts}_{slug}")

    def show_help(self) -> None:
        help_text = (
            "Hızlı Kullanım Kartı\n\n"
            "1) Müzik Dosyası Seç\n"
            "2) Hazır Profil seç + Profili Uygula\n"
            "3) Dosya Adını Otomatik Oluştur\n"
            "4) Hızlı Kayıt (Test + Kayıt)\n\n"
            "Hazır Profiller:\n"
            "- Clean (Temiz)\n"
            "- Crunch (Ritmik)\n"
            "- Lead (Solo)\n\n"
            "Çıktılar (Masaüstü):\n"
            "- guitar_mix_... .mp3\n"
            "- guitar_mix_..._mix.wav\n"
            "- guitar_mix_..._vocal.wav\n"
            "- guitar_mix_..._device_test.wav\n\n"
            "Not: MP3 oluşmazsa kayıt yine tamamlanır ve WAV dosyaları garanti yazılır."
        )
        messagebox.showinfo("Yardım - Gitar Amfi Kaydedici", help_text)

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

    def start_quick_record_thread(self) -> None:
        if self.backing_file is None:
            self.set_status("Hızlı kayıt için önce bir arka plan müzik dosyası seçin.")
            return
        try:
            input_idx, output_idx = self.selected_device_pair()
        except ValueError:
            self.set_status("Aygıt kimliği alanlarına sadece sayı girin (veya boş bırakın).")
            return
        settings = self.current_amp_settings()
        base_name = self.output_name.get().strip() or f"guitar_mix_{time.strftime('%Y%m%d_%H%M%S')}"
        worker = threading.Thread(
            target=self.run_quick_record,
            args=(self.backing_file, input_idx, output_idx, settings, base_name),
            daemon=True,
        )
        worker.start()

    def current_amp_settings(self) -> Tuple[float, float, float, float, float]:
        return (
            float(self.gain.get()),
            float(self.boost.get()),
            float(self.bass.get()),
            float(self.treble.get()),
            float(self.distortion.get()),
        )

    def run_device_test(
        self,
        input_idx: Optional[int],
        output_idx: Optional[int],
        settings: Tuple[float, float, float, float, float],
        base_name: str,
    ) -> bool:
        try:
            sr = 44100
            seconds = 5
            frames = sr * seconds
            gain_db, boost_db, bass_db, treble_db, distortion = settings

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
                bass_db=bass_db,
                treble_db=treble_db,
                distortion=distortion,
            )
            noise_strength = float(self.noise_reduction.get()) / 100.0
            output_gain_db = float(self.output_gain.get())
            processed = reduce_background_noise(processed, sr, noise_strength)
            processed = apply_output_gain(processed, output_gain_db)

            preview = np.stack([processed, processed], axis=1)
            self.set_status("Test çalınıyor...")
            sd.play(preview, samplerate=sr, device=output_idx)
            sd.wait()

            desktop = Path.home() / "Desktop"
            test_path = desktop / f"{base_name}_device_test.wav"
            sf.write(test_path, processed, sr)

            peak = float(np.max(np.abs(voice))) if len(voice) else 0.0
            self.set_status(f"Test tamam. Peak={peak:.3f} | Dosya: {test_path}")
            return True
        except Exception as exc:
            self.set_status(f"Test hatası: {exc}")
            return False

    def run_quick_record(
        self,
        backing_file: Path,
        input_idx: Optional[int],
        output_idx: Optional[int],
        settings: Tuple[float, float, float, float, float],
        base_name: str,
    ) -> None:
        self.set_status("Hızlı kayıt: 5 sn test başlıyor...")
        test_ok = self.run_device_test(input_idx, output_idx, settings, base_name)
        if not test_ok:
            self.set_status("Hızlı kayıt durdu: test adımı başarısız.")
            return
        self.set_status("Hızlı kayıt: test tamam, ana kayıt başlıyor...")
        self.record_and_export(backing_file, input_idx, output_idx, settings, base_name)

    def start_recording_thread(self) -> None:
        if self.backing_file is None:
            self.set_status("Önce bir arka plan müzik dosyası seçin.")
            return
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

    def record_and_export(
        self,
        backing_file: Path,
        input_idx: Optional[int],
        output_idx: Optional[int],
        settings: Tuple[float, float, float, float, float],
        base_name: str,
    ) -> None:
        try:
            self.set_status("Arka plan müzik yükleniyor...")
            backing, sr = sf.read(backing_file, dtype="float32")
            backing = ensure_stereo(backing)

            target_sr = 44100
            if sr != target_sr:
                self.set_status(f"Sample rate {sr} -> {target_sr} dönüştürülüyor...")
                backing = resample_linear(backing, sr, target_sr)
                sr = target_sr

            limit_seconds = 7200 if self.record_limit_hours.get() == "2" else 3600
            max_frames = sr * limit_seconds
            if len(backing) > max_frames:
                self.set_status(f"Kayıt sınırı {limit_seconds // 3600} saat olarak uygulandı, dosya kırpıldı.")
                backing = backing[:max_frames]

            duration_sec = len(backing) / sr
            self.set_status(
                f"Kayıt başlıyor ({duration_sec:.1f} sn). Kulaklık önerilir. Arka plan müzik çalarken mikrofona söyleyin/çalın..."
            )

            recorded = sd.playrec(backing, samplerate=sr, channels=1, dtype="float32", device=(input_idx, output_idx))
            sd.wait()

            voice = recorded[:, 0]
            self.set_status("Amfi efektleri uygulanıyor...")
            gain_db, boost_db, bass_db, treble_db, distortion = settings
            processed_voice = apply_amp_chain(
                voice=voice,
                sample_rate=sr,
                gain_db=gain_db,
                boost_db=boost_db,
                bass_db=bass_db,
                treble_db=treble_db,
                distortion=distortion,
            )
            noise_strength = float(self.noise_reduction.get()) / 100.0
            speed_ratio = float(self.speed_ratio.get()) / 100.0
            output_gain_db = float(self.output_gain.get())
            backing_level = float(self.backing_level.get()) / 100.0
            vocal_level = float(self.vocal_level.get()) / 100.0

            processed_voice = reduce_background_noise(processed_voice, sr, noise_strength)

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

            peak = np.max(np.abs(mix))
            if peak > 0.98:
                mix = mix / peak * 0.98
            mix = np.clip(mix, -1.0, 1.0)

            desktop = Path.home() / "Desktop"
            mp3_path = desktop / f"{base_name}.mp3"
            mix_wav_path = desktop / f"{base_name}_mix.wav"
            vocal_wav_path = desktop / f"{base_name}_vocal.wav"

            self.set_status("Dosyalar hazırlanıyor...")
            ffmpeg_bin = detect_ffmpeg()

            # WAV dosyalarini her zaman yaz. MP3 basarisiz olursa kullanici ciktiyi kaybetmesin.
            sf.write(mix_wav_path, mix, sr)
            sf.write(vocal_wav_path, processed_voice, sr)

            if ffmpeg_bin:
                cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    str(mix_wav_path),
                    "-codec:a",
                    "libmp3lame",
                    "-qscale:a",
                    "2",
                    str(mp3_path),
                ]
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    if mp3_path.exists() and mp3_path.stat().st_size > 0:
                        final_note = f"MP3: {mp3_path}"
                    else:
                        final_note = f"MP3 oluşmadı, WAV mix kaydedildi: {mix_wav_path}"
                except Exception as exc:
                    final_note = f"MP3 dönüştürme hatası ({exc}), WAV mix kaydedildi: {mix_wav_path}"
            else:
                final_note = f"ffmpeg yok, WAV mix kaydedildi: {mix_wav_path}"

            self.set_status(
                f"Tamamlandı. {final_note} | İşlenmiş WAV: {vocal_wav_path}"
            )
        except Exception as exc:
            self.set_status(f"Hata: {exc}")


def main() -> None:
    configure_tcl_tk_environment()
    root = Tk()
    GuitarAmpRecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
