import shutil
import subprocess
import time
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import sounddevice as sd
import soundfile as sf

PRESET_PATH = Path(__file__).resolve().with_name(".last_preset.json")
NAMED_PRESET_PATH = Path(__file__).resolve().with_name(".cli_presets.json")
DEFAULT_SETTINGS = {
    "gain": 6.0,
    "boost": 6.0,
    "bass": 3.0,
    "treble": 2.0,
    "dist": 25.0,
    "noise_reduction": 25.0,
    "speed_percent": 100.0,
    "output_gain_db": 0.0,
    "backing_level": 100.0,
    "vocal_level": 85.0,
    "record_seconds": 60.0,
    "input_device_id": None,
    "output_device_id": None,
}


def print_block(title: str, lines: list[str]) -> None:
    border = "=" * max(24, len(title) + 8)
    print(f"\n{border}")
    print(f"{title}")
    print(border)
    for line in lines:
        print(line)
    print(border)


def format_cli_value(value: object) -> str:
    if value is None or value == "":
        return "varsayılan"
    return str(value)


def format_kv_lines(items: list[tuple[str, object]]) -> list[str]:
    width = max((len(label) for label, _ in items), default=0)
    return [f"- {label.ljust(width)} : {format_cli_value(value)}" for label, value in items]


def print_status(message: str) -> None:
    print(f"[bilgi] {message}")


def print_success(message: str) -> None:
    print(f"[tamam] {message}")


def print_warning(message: str) -> None:
    print(f"[uyarı] {message}")


def print_run_summary(mode: str, preset_name: str, input_idx: Optional[int], output_idx: Optional[int], output_name: str) -> None:
    print_block(
        "CLI Oturum Özeti",
        format_kv_lines(
            [
                ("Mod", mode),
                ("Preset", preset_name or "son kullanılan"),
                ("Mikrofon aygıtı", input_idx),
                ("Çıkış aygıtı", output_idx),
                ("Çıkış adı", output_name),
            ]
        ),
    )


def print_settings_summary(settings: dict, preset_name: str = "") -> None:
    print_block(
        "CLI Ayar Özeti",
        format_kv_lines(
            [
                ("Kaynak", preset_name or "son kullanılan ayarlar"),
                ("Kazanç dB", settings["gain"]),
                ("Güçlendirme dB", settings["boost"]),
                ("Bas dB", settings["bass"]),
                ("Tiz dB", settings["treble"]),
                ("Distorsiyon %", settings["dist"]),
                ("Gürültü azaltma %", settings["noise_reduction"]),
                ("Hız %", settings["speed_percent"]),
                ("Çıkış kazancı dB", settings["output_gain_db"]),
                ("Arka plan %", settings["backing_level"]),
                ("Vokal %", settings["vocal_level"]),
                ("Kayıt süresi sn", settings["record_seconds"]),
                ("Mikrofon aygıtı", settings["input_device_id"]),
                ("Çıkış aygıtı", settings["output_device_id"]),
            ]
        ),
    )


def normalize_settings(raw: Optional[dict]) -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if not isinstance(raw, dict):
        return settings
    for key in settings:
        value = raw.get(key)
        if key in ("input_device_id", "output_device_id"):
            if isinstance(value, (int, float)):
                settings[key] = int(value)
            elif value is None:
                settings[key] = None
            continue
        if isinstance(value, (int, float)):
            settings[key] = float(value)
    return settings


def serialize_settings(settings: dict) -> dict:
    safe = {}
    for key in DEFAULT_SETTINGS:
        value = settings.get(key, DEFAULT_SETTINGS[key])
        if key in ("input_device_id", "output_device_id"):
            safe[key] = int(value) if isinstance(value, (int, float)) else None
        else:
            safe[key] = float(value) if isinstance(value, (int, float)) else DEFAULT_SETTINGS[key]
    return safe


def no_device_help_text() -> str:
    return (
        "Ses aygıtı bulunamadı. macOS'ta Sistem Ayarları > Gizlilik ve Güvenlik > Mikrofon bölümünden "
        "Terminal veya GuitarAmpRecorder için izin verin. Harici mikrofon/ses kartı kullanıyorsanız yeniden takıp programı tekrar açın."
    )


def load_saved_settings() -> dict:
    if not PRESET_PATH.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        raw = json.loads(PRESET_PATH.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_SETTINGS.copy()
    return normalize_settings(raw)


def save_settings(settings: dict) -> None:
    PRESET_PATH.write_text(json.dumps(serialize_settings(settings), ensure_ascii=False, indent=2), encoding="utf-8")


def default_named_preset_store() -> dict:
    return {"selected": "", "presets": {}}


def load_named_preset_store() -> dict:
    if not NAMED_PRESET_PATH.exists():
        return default_named_preset_store()
    try:
        raw = json.loads(NAMED_PRESET_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default_named_preset_store()
    if not isinstance(raw, dict):
        return default_named_preset_store()
    raw_presets = raw.get("presets", {})
    presets = {}
    if isinstance(raw_presets, dict):
        for name, preset in raw_presets.items():
            if isinstance(name, str):
                presets[name] = normalize_settings(preset)
    selected = raw.get("selected", "")
    if not isinstance(selected, str):
        selected = ""
    if selected and selected not in presets:
        selected = ""
    return {"selected": selected, "presets": presets}


def write_named_preset_store(store: dict) -> None:
    presets = {}
    raw_presets = store.get("presets", {})
    if isinstance(raw_presets, dict):
        for name, preset in raw_presets.items():
            if isinstance(name, str):
                presets[name] = serialize_settings(preset)
    selected = store.get("selected", "")
    if not isinstance(selected, str) or selected not in presets:
        selected = ""
    NAMED_PRESET_PATH.write_text(
        json.dumps({"selected": selected, "presets": presets}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_named_presets() -> list[str]:
    return sorted(load_named_preset_store().get("presets", {}).keys())


def load_named_preset(name: str) -> Optional[dict]:
    store = load_named_preset_store()
    preset = store.get("presets", {}).get(name)
    return normalize_settings(preset) if preset else None


def save_named_preset(name: str, settings: dict) -> None:
    safe_name = name.strip()
    if not safe_name:
        raise ValueError("Preset adı boş olamaz.")
    store = load_named_preset_store()
    store.setdefault("presets", {})[safe_name] = normalize_settings(settings)
    store["selected"] = safe_name
    write_named_preset_store(store)


def delete_named_preset(name: str) -> bool:
    safe_name = name.strip()
    if not safe_name:
        return False
    store = load_named_preset_store()
    presets = store.get("presets", {})
    if safe_name not in presets:
        return False
    del presets[safe_name]
    store["selected"] = safe_name if store.get("selected") != safe_name else ""
    if presets and not store["selected"]:
        store["selected"] = sorted(presets.keys())[0]
    write_named_preset_store(store)
    return True


def extract_flag_value(args: list[str], flag: str) -> Optional[str]:
    for idx, arg in enumerate(args):
        if arg == flag and idx + 1 < len(args):
            return args[idx + 1]
        if arg.startswith(flag + "="):
            return arg.split("=", 1)[1]
    return None


def ask_named_preset_selection(default_name: str = "") -> str:
    names = list_named_presets()
    if not names:
        return ""
    print_block(
        "Kayıtlı CLI Presetleri",
        [f"- {name}{' *' if name == default_name else ''}" for name in names],
    )
    prompt = "Yüklenecek preset adı"
    if default_name:
        prompt += f" [varsayılan={default_name}]"
    raw = input(f"{prompt} (boş=geç): ").strip()
    if not raw:
        return default_name if default_name in names else ""
    return raw


def cli_usage_text() -> str:
    return (
        "Kullanim:\n"
        "  python3 cli_app.py [--quick] [--preset ADI]\n"
        "  python3 cli_app.py --show-settings [--preset ADI]\n"
        "  python3 cli_app.py --list-devices\n"
        "  python3 cli_app.py --test [--preset ADI]\n"
        "  python3 cli_app.py --list-presets\n"
        "  python3 cli_app.py --delete-preset ADI\n"
        "  python3 cli_app.py --save-preset ADI\n"
        "  python3 cli_app.py --help\n\n"
        "Secenekler:\n"
        "  --quick                 Kayitli ayarlar ile sorusuz hizli kayit baslatir.\n"
        "  --show-settings         Etkin CLI ayarlarini gosterir ve cikar.\n"
        "  --list-devices          Kullanilabilir ses aygitlarini listeler ve cikar.\n"
        "  --test                  5 sn cihaz testi yapar ve cikar.\n"
        "  --preset ADI            Isimli CLI preset yukler.\n"
        "  --save-preset ADI       Calisma sonunda mevcut ayarlari bu isimle kaydeder.\n"
        "  --delete-preset ADI     Isimli CLI preset siler ve cikar.\n"
        "  --list-presets          Kayitli CLI presetlerini listeler ve cikar.\n"
        "  --help, -h              Bu yardim metnini gosterir.\n"
    )


def parse_cli_args(args: list[str]) -> tuple[dict, Optional[str]]:
    parsed = {
        "quick_mode": False,
        "list_only": False,
        "list_devices_only": False,
        "show_settings_only": False,
        "test_only": False,
        "help_only": False,
        "preset_name": None,
        "save_preset": None,
        "delete_preset": None,
    }
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--help", "-h"):
            parsed["help_only"] = True
            i += 1
            continue
        if arg == "--quick":
            parsed["quick_mode"] = True
            i += 1
            continue
        if arg == "--list-presets":
            parsed["list_only"] = True
            i += 1
            continue
        if arg == "--list-devices":
            parsed["list_devices_only"] = True
            i += 1
            continue
        if arg == "--show-settings":
            parsed["show_settings_only"] = True
            i += 1
            continue
        if arg == "--test":
            parsed["test_only"] = True
            i += 1
            continue
        if arg in ("--preset", "--save-preset", "--delete-preset"):
            if i + 1 >= len(args):
                return parsed, f"Eksik deger: {arg}"
            value = args[i + 1].strip()
            if not value:
                return parsed, f"Gecersiz bos deger: {arg}"
            if arg == "--preset":
                parsed["preset_name"] = value
            elif arg == "--save-preset":
                parsed["save_preset"] = value
            else:
                parsed["delete_preset"] = value
            i += 2
            continue
        if arg.startswith("--preset="):
            parsed["preset_name"] = arg.split("=", 1)[1].strip()
            if not parsed["preset_name"]:
                return parsed, "Gecersiz bos deger: --preset"
            i += 1
            continue
        if arg.startswith("--save-preset="):
            parsed["save_preset"] = arg.split("=", 1)[1].strip()
            if not parsed["save_preset"]:
                return parsed, "Gecersiz bos deger: --save-preset"
            i += 1
            continue
        if arg.startswith("--delete-preset="):
            parsed["delete_preset"] = arg.split("=", 1)[1].strip()
            if not parsed["delete_preset"]:
                return parsed, "Gecersiz bos deger: --delete-preset"
            i += 1
            continue
        return parsed, f"Bilinmeyen secenek: {arg}"
    return parsed, None


def device_test_output_name(base_name: str = "") -> str:
    safe_name = base_name.strip()
    return f"{safe_name or next_take_name('quick_take')}_device_test"


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

    x = x + low * (db_to_linear(bass_db) - 1.0) + high * (db_to_linear(treble_db) - 1.0)

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

    channels = [np.interp(dst_x, src_x, audio[:, ch]) for ch in range(audio.shape[1])]
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

    ref_frames = max(1, int(sample_rate * 0.5))
    noise_ref = signal[:ref_frames]
    noise_floor = float(np.median(np.abs(noise_ref)))
    threshold = noise_floor * (1.0 + strength * 4.0)
    attenuation = max(0.05, 1.0 - strength * 0.9)

    out = signal.copy()
    mask = np.abs(out) < threshold
    out[mask] *= attenuation
    return out.astype(np.float32)


def ask_float(label: str, default: float) -> float:
    raw = input(f"{label} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("Geçersiz değer, varsayılan kullanılıyor.")
        return default


def ask_int_optional(label: str) -> Optional[int]:
    raw = input(f"{label} (boş bırak = varsayılan): ").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("Geçersiz aygıt kimliği, varsayılan kullanılıyor.")
        return None


def ask_int_optional_with_default(label: str, default: Optional[int]) -> Optional[int]:
    if default is None:
        return ask_int_optional(label)

    raw = input(f"{label} [kayıtlı={default}] (boş bırak = kayıtlı): ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Geçersiz aygıt kimliği, kayıtlı değer kullanılıyor.")
        return default


def ask_record_limit_seconds() -> int:
    raw = input("Kayıt sınırı saat [1/2] (varsayılan: 1): ").strip()
    if raw == "2":
        return 7200
    return 3600


def list_devices() -> None:
    devices = sd.query_devices()
    if len(devices) == 0:
        print_block("Ses Aygıtları", [no_device_help_text()])
        return
    print_block(
        "Ses Aygıtları",
        [f"{i}: {dev['name']} | in={dev['max_input_channels']} out={dev['max_output_channels']}" for i, dev in enumerate(devices)],
    )


def find_first_input_device() -> Optional[int]:
    try:
        devices = sd.query_devices()
    except Exception:
        return None
    for i, dev in enumerate(devices):
        if int(dev.get("max_input_channels", 0)) > 0:
            return i
    return None


def candidate_input_devices(preferred: Optional[int]) -> list[Optional[int]]:
    out: list[Optional[int]] = []
    for cand in (preferred, None, find_first_input_device()):
        if cand not in out:
            out.append(cand)
    return out


def next_take_name(prefix: str = "quick_take") -> str:
    desktop = Path.home() / "Desktop"
    for i in range(1, 10000):
        name = f"{prefix}_{i:03d}"
        if not (desktop / f"{name}.mp3").exists() and not (desktop / f"{name}_mix.wav").exists():
            return name
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"


def run_test(
    sr: int,
    input_idx: Optional[int],
    output_idx: Optional[int],
    gain: float,
    boost: float,
    bass: float,
    treble: float,
    dist: float,
    name: str,
) -> None:
    print_status("5 sn test kaydı başlıyor...")
    rec = sd.rec(frames=sr * 5, samplerate=sr, channels=1, dtype="float32", device=input_idx)
    sd.wait()
    voice = rec[:, 0]
    proc = apply_amp_chain(voice, sr, gain, boost, bass, treble, dist)
    preview = np.stack([proc, proc], axis=1)
    if output_idx is not None:
        print_status("Test oynatılıyor...")
        sd.play(preview, samplerate=sr, device=output_idx)
        sd.wait()

    out = Path.home() / "Desktop" / f"{name}_device_test.wav"
    sf.write(out, proc, sr)
    print_success(f"Test kaydı yazıldı: {out}")


def ask_backing_file() -> Optional[Path]:
    backing_path = input("Arka plan müzik dosya yolu (.wav/.aiff/.flac) [boş=sadece-mikrofon]: ").strip()
    if not backing_path:
        return None

    backing_file = Path(backing_path).expanduser()
    if not backing_file.exists():
        print(f"Dosya bulunamadı: {backing_file}")
        return None
    return backing_file


def prepare_backing(backing_file: Optional[Path], sr: int, record_seconds: float, limit_seconds: int) -> Tuple[np.ndarray, bool]:
    if backing_file is None:
        capped_seconds = min(record_seconds, float(limit_seconds))
        frames = max(1, int(sr * capped_seconds))
        return np.zeros((frames, 2), dtype=np.float32), False

    print_status("Arka plan müzik yükleniyor...")
    backing, backing_sr = sf.read(backing_file, dtype="float32")
    backing = ensure_stereo(backing)
    if backing_sr != sr:
        print_status(f"Örnekleme hızı {backing_sr} -> {sr} dönüştürülüyor...")
        backing = resample_linear(backing, backing_sr, sr)
    max_frames = int(sr * limit_seconds)
    if len(backing) > max_frames:
        print_warning(f"Kayıt sınırı uygulandı: {limit_seconds // 3600} saat (dosya kırpıldı).")
        backing = backing[:max_frames]
    return backing, True


def main() -> None:
    args = sys.argv[1:]
    parsed_args, parse_error = parse_cli_args(args)
    if parse_error:
        print(parse_error)
        print()
        print(cli_usage_text())
        return

    quick_mode = bool(parsed_args["quick_mode"])
    list_only = bool(parsed_args["list_only"])
    list_devices_only = bool(parsed_args["list_devices_only"])
    show_settings_only = bool(parsed_args["show_settings_only"])
    test_only = bool(parsed_args["test_only"])
    preset_name_arg = parsed_args["preset_name"]
    save_preset_arg = parsed_args["save_preset"]
    delete_preset_arg = parsed_args["delete_preset"]
    help_only = bool(parsed_args["help_only"])

    if help_only:
        print(cli_usage_text())
        return

    print_block(
        "Gitar Amfi Kaydedici (Terminal Sürümü)",
        ["Not: Aygıt kimliği bilmiyorsanız boş bırakın. Enter ile varsayılan seçilir."],
    )

    if list_only:
        names = list_named_presets()
        if names:
            print_block("Kayıtlı CLI Presetleri", [f"- {name}" for name in names])
        else:
            print_warning("Kayıtlı CLI preseti bulunmuyor.")
        return

    if list_devices_only:
        try:
            list_devices()
        except Exception as exc:
            print_warning(f"Aygıt listeleme hatası: {exc}")
        return

    if delete_preset_arg:
        if delete_named_preset(delete_preset_arg):
            print_success(f"CLI preset silindi: {delete_preset_arg}")
        else:
            print_warning(f"CLI preset bulunamadı: {delete_preset_arg}")
        return

    settings = load_saved_settings()
    named_store = load_named_preset_store()
    selected_preset_name = ""
    if preset_name_arg:
        preset = load_named_preset(preset_name_arg)
        if preset is None:
            print_warning(f"CLI preset bulunamadı: {preset_name_arg}")
            return
        settings = preset
        selected_preset_name = preset_name_arg

    if show_settings_only:
        print_settings_summary(settings, selected_preset_name)
        print_status(f"Ayar dosyası: {PRESET_PATH}")
        if NAMED_PRESET_PATH.exists():
            print_status(f"CLI preset deposu: {NAMED_PRESET_PATH}")
        return

    if quick_mode:
        if selected_preset_name:
            print_status(f"Hızlı mod: '{selected_preset_name}' preset'i ile sorusuz kayıt başlatılıyor.")
        else:
            print_status("Hızlı mod: kayıtlı ayarlar ile sorusuz kayıt başlatılıyor.")
    elif PRESET_PATH.exists():
        use_saved = input("Kayıtlı ayarlar yüklensin mi? [E/h]: ").strip().lower()
        if use_saved in ("h", "hayır", "hayir", "n", "no"):
            settings = DEFAULT_SETTINGS.copy()
        elif not selected_preset_name and named_store.get("presets"):
            requested_name = ask_named_preset_selection(str(named_store.get("selected", "") or ""))
            if requested_name:
                preset = load_named_preset(requested_name)
                if preset is not None:
                    settings = preset
                    selected_preset_name = requested_name
                    print_success(f"CLI preset yüklendi: {selected_preset_name}")
                else:
                    print_warning(f"CLI preset bulunamadı: {requested_name}. Son kullanılan ayarlar ile devam ediliyor.")

    if not quick_mode and input("Aygıt listesi gösterilsin mi? [E/h]: ").strip().lower() in ("", "e", "evet", "y", "yes"):
        try:
            list_devices()
        except Exception as exc:
            print_warning(f"Aygıt listeleme hatası: {exc}")

    if find_first_input_device() is None:
        print(no_device_help_text())
        return

    backing_file = None if quick_mode else ask_backing_file()

    if quick_mode:
        output_name = next_take_name("quick_take")
    else:
        output_name = input("Çıkış dosya adı [guitar_mix_YYYYMMDD_HHMMSS]: ").strip()
        if not output_name:
            output_name = f"guitar_mix_{time.strftime('%Y%m%d_%H%M%S')}"

    if quick_mode:
        gain = settings["gain"]
        boost = settings["boost"]
        bass = settings["bass"]
        treble = settings["treble"]
        dist = settings["dist"]
        noise_reduction = settings["noise_reduction"]
        speed_percent = settings["speed_percent"]
        output_gain_db = settings["output_gain_db"]
        backing_level = settings["backing_level"]
        vocal_level = settings["vocal_level"]
        record_seconds = settings["record_seconds"]
        limit_seconds = 3600
        input_idx = settings["input_device_id"]
        output_idx = settings["output_device_id"]
    else:
        gain = ask_float("Kazanç dB", settings["gain"])
        boost = ask_float("Güçlendirme dB", settings["boost"])
        bass = ask_float("Bas dB", settings["bass"])
        treble = ask_float("Tiz dB", settings["treble"])
        dist = ask_float("Distorsiyon %", settings["dist"])
        noise_reduction = ask_float("Gürültü azaltma %", settings["noise_reduction"])
        speed_percent = ask_float("Hız % (50-150)", settings["speed_percent"])
        output_gain_db = ask_float("Çıkış kazancı dB", settings["output_gain_db"])

        backing_level = ask_float("Arka plan seviye %", settings["backing_level"])
        vocal_level = ask_float("Vokal seviye %", settings["vocal_level"])

        record_seconds = ask_float("Kayıt süresi sn (sadece mikrofon için)", settings["record_seconds"])
        if record_seconds <= 0:
            record_seconds = 60
        limit_seconds = ask_record_limit_seconds()

        input_idx = ask_int_optional_with_default("Mikrofon Aygıt Kimliği", settings["input_device_id"])
        output_idx = ask_int_optional_with_default("Çıkış Aygıt Kimliği", settings["output_device_id"])

    sr = 44100
    if quick_mode and input_idx is None:
        auto_input = find_first_input_device()
        if auto_input is not None:
            input_idx = auto_input
            print_status(f"Hızlı mod: otomatik mikrofon aygıtı seçildi ({input_idx}).")

    mode_name = "test" if test_only else ("hızlı kayıt" if quick_mode else "etkileşimli kayıt")
    print_run_summary(mode_name, selected_preset_name, input_idx, output_idx, output_name)

    if test_only:
        test_output_name = device_test_output_name(selected_preset_name)
        try:
            run_test(sr, input_idx, output_idx, gain, boost, bass, treble, dist, test_output_name)
        except Exception as exc:
            print_warning(f"Test hatası: {exc}")
            return
        save_settings(
            {
                "gain": gain,
                "boost": boost,
                "bass": bass,
                "treble": treble,
                "dist": dist,
                "noise_reduction": noise_reduction,
                "speed_percent": speed_percent,
                "output_gain_db": output_gain_db,
                "backing_level": backing_level,
                "vocal_level": vocal_level,
                "record_seconds": record_seconds,
                "input_device_id": input_idx,
                "output_device_id": output_idx,
            }
        )
        print_success(f"Ayarlar kaydedildi: {PRESET_PATH}")
        if NAMED_PRESET_PATH.exists():
            print_status(f"CLI preset deposu: {NAMED_PRESET_PATH}")
        return

    do_test = "" if quick_mode else input("Önce 5 sn test yapılsın mı? [E/h]: ").strip().lower()
    if do_test in ("", "e", "evet", "y", "yes") and not quick_mode:
        try:
            run_test(sr, input_idx, output_idx, gain, boost, bass, treble, dist, output_name)
        except Exception as exc:
            print_warning(f"Test hatası: {exc}")
            go_on = input("Yine de ana kayda devam edilsin mi? [E/h]: ").strip().lower()
            if go_on not in ("", "e", "evet", "y", "yes"):
                return

    try:
        backing, has_backing = prepare_backing(backing_file, sr, record_seconds, limit_seconds)
    except Exception as exc:
        print_warning(f"Arka plan müzik yükleme hatası: {exc}")
        return

    duration_sec = len(backing) / sr
    recorded = None
    record_error: Optional[Exception] = None
    if has_backing:
        try:
            print_status(f"Kayıt başlıyor ({duration_sec:.1f} sn). Kulaklık önerilir...")
            recorded = sd.playrec(backing, samplerate=sr, channels=1, dtype="float32", device=(input_idx, output_idx))
            sd.wait()
        except Exception as exc:
            print_warning(f"Kayıt hatası: {exc}")
            print_warning("İpucu: Programı yeniden açıp aygıt listesini gösterin ve Mikrofon/Çıkış Aygıt Kimliği değerlerini girin.")
            return
    else:
        for cand in candidate_input_devices(input_idx):
            try:
                if cand is None:
                    print_status(f"Sadece mikrofon kaydı başlıyor ({duration_sec:.1f} sn).")
                else:
                    print_status(f"Sadece mikrofon kaydı başlıyor ({duration_sec:.1f} sn), aygıt={cand}.")
                recorded = sd.rec(frames=len(backing), samplerate=sr, channels=1, dtype="float32", device=cand)
                sd.wait()
                input_idx = cand
                record_error = None
                break
            except Exception as exc:
                record_error = exc
                continue
        if recorded is None:
            print_warning(f"Kayıt hatası: {record_error}")
            print_warning("İpucu: Programı yeniden açıp aygıt listesini gösterin ve Mikrofon/Çıkış Aygıt Kimliği değerlerini girin.")
            return

    voice = recorded[:, 0]
    print_status("Amfi efektleri uygulanıyor...")
    processed = apply_amp_chain(voice, sr, gain, boost, bass, treble, dist)
    processed = reduce_background_noise(processed, sr, max(0.0, min(100.0, noise_reduction)) / 100.0)

    speed_ratio = max(0.5, min(1.5, speed_percent / 100.0))
    if abs(speed_ratio - 1.0) > 1e-6:
        print_status(f"Hız ayarı uygulanıyor (%{speed_percent:.0f})...")
        backing = change_speed(backing, speed_ratio)
        processed = change_speed(processed, speed_ratio)

    min_len = min(len(backing), len(processed))
    backing = backing[:min_len]
    processed = processed[:min_len]

    mix = backing.copy() * (backing_level / 100.0)
    mix[:, 0] += processed * (vocal_level / 100.0)
    mix[:, 1] += processed * (vocal_level / 100.0)
    mix = apply_output_gain(mix, output_gain_db)
    processed = apply_output_gain(processed, output_gain_db)
    peak = np.max(np.abs(mix))
    if peak > 0.98:
        mix = mix / peak * 0.98
    mix = np.clip(mix, -1.0, 1.0)

    desktop = Path.home() / "Desktop"
    mp3_path = desktop / f"{output_name}.mp3"
    mix_wav_path = desktop / f"{output_name}_mix.wav"
    vocal_wav_path = desktop / f"{output_name}_vocal.wav"

    sf.write(mix_wav_path, mix, sr)
    sf.write(vocal_wav_path, processed, sr)

    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        cmd = [ffmpeg_bin, "-y", "-i", str(mix_wav_path), "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print_success(f"MP3 yazıldı: {mp3_path}")
        except Exception as exc:
            print_warning(f"MP3 dönüştürme hatası: {exc}")
    else:
        print_warning("ffmpeg bulunamadı, MP3 atlandı.")

    save_settings(
        {
            "gain": gain,
            "boost": boost,
            "bass": bass,
            "treble": treble,
            "dist": dist,
            "noise_reduction": noise_reduction,
            "speed_percent": speed_percent,
            "output_gain_db": output_gain_db,
            "backing_level": backing_level,
            "vocal_level": vocal_level,
            "record_seconds": record_seconds,
            "input_device_id": input_idx,
            "output_device_id": output_idx,
        }
    )

    if save_preset_arg:
        try:
            save_named_preset(save_preset_arg, settings)
            selected_preset_name = save_preset_arg.strip()
            print_success(f"CLI preset kaydedildi: {selected_preset_name}")
        except ValueError as exc:
            print_warning(f"CLI preset kaydedilemedi: {exc}")
    elif not quick_mode:
        prompt_default = selected_preset_name or str(named_store.get("selected", "") or "")
        raw_name = input(
            f"İsimli CLI preset olarak da kaydedilsin mi? [{prompt_default or 'boş=hayır'}]: "
        ).strip()
        target_name = raw_name or prompt_default
        if raw_name or (prompt_default and raw_name == ""):
            try:
                save_named_preset(target_name, settings)
                print_success(f"CLI preset kaydedildi: {target_name}")
            except ValueError as exc:
                print_warning(f"CLI preset kaydedilemedi: {exc}")

    print_block(
        "Çıktılar",
        format_kv_lines(
            [
                ("Mix WAV", mix_wav_path),
                ("İşlenmiş WAV", vocal_wav_path),
                ("Ayarlar", PRESET_PATH),
            ]
        ),
    )
    if NAMED_PRESET_PATH.exists():
        print_status(f"CLI preset deposu: {NAMED_PRESET_PATH}")
    print_success("Tamamlandı.")


if __name__ == "__main__":
    main()
