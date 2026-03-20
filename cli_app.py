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


def no_device_help_text() -> str:
    return (
        "Ses aygıtı bulunamadı. macOS'ta Sistem Ayarları > Gizlilik ve Güvenlik > Mikrofon bölümünden "
        "Terminal veya GuitarAmpRecorder için izin verin. Harici mikrofon/ses kartı kullanıyorsanız yeniden takıp programı tekrar açın."
    )


def load_saved_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if not PRESET_PATH.exists():
        return settings
    try:
        raw = json.loads(PRESET_PATH.read_text(encoding="utf-8"))
    except Exception:
        return settings
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


def save_settings(settings: dict) -> None:
    safe = {}
    for key in DEFAULT_SETTINGS:
        value = settings.get(key, DEFAULT_SETTINGS[key])
        if key in ("input_device_id", "output_device_id"):
            safe[key] = int(value) if isinstance(value, (int, float)) else None
        else:
            safe[key] = float(value) if isinstance(value, (int, float)) else DEFAULT_SETTINGS[key]
    PRESET_PATH.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")


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
    print("\n--- Ses Aygıtları ---")
    devices = sd.query_devices()
    if len(devices) == 0:
        print(no_device_help_text())
        print("---------------------\n")
        return
    for i, dev in enumerate(devices):
        print(f"{i}: {dev['name']} | in={dev['max_input_channels']} out={dev['max_output_channels']}")
    print("---------------------\n")


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
    print("5 sn test kaydı başlıyor...")
    rec = sd.rec(frames=sr * 5, samplerate=sr, channels=1, dtype="float32", device=input_idx)
    sd.wait()
    voice = rec[:, 0]
    proc = apply_amp_chain(voice, sr, gain, boost, bass, treble, dist)
    preview = np.stack([proc, proc], axis=1)
    if output_idx is not None:
        print("Test oynatılıyor...")
        sd.play(preview, samplerate=sr, device=output_idx)
        sd.wait()

    out = Path.home() / "Desktop" / f"{name}_device_test.wav"
    sf.write(out, proc, sr)
    print(f"Test kaydı yazıldı: {out}")


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

    print("Arka plan müzik yükleniyor...")
    backing, backing_sr = sf.read(backing_file, dtype="float32")
    backing = ensure_stereo(backing)
    if backing_sr != sr:
        print(f"Örnekleme hızı {backing_sr} -> {sr} dönüştürülüyor...")
        backing = resample_linear(backing, backing_sr, sr)
    max_frames = int(sr * limit_seconds)
    if len(backing) > max_frames:
        print(f"Kayıt sınırı uygulandı: {limit_seconds // 3600} saat (dosya kırpıldı).")
        backing = backing[:max_frames]
    return backing, True


def main() -> None:
    quick_mode = "--quick" in sys.argv[1:]

    print("\n=== Gitar Amfi Kaydedici (Terminal Sürümü) ===")
    print("Not: Aygıt kimliği bilmiyorsanız boş bırakın. Enter ile varsayılan seçilir.\n")

    settings = load_saved_settings()
    if quick_mode:
        print("Hızlı mod: kayıtlı ayarlar ile sorusuz kayıt başlatılıyor.")
    elif PRESET_PATH.exists():
        use_saved = input("Kayıtlı ayarlar yüklensin mi? [E/h]: ").strip().lower()
        if use_saved in ("h", "hayır", "hayir", "n", "no"):
            settings = DEFAULT_SETTINGS.copy()

    if not quick_mode and input("Aygıt listesi gösterilsin mi? [E/h]: ").strip().lower() in ("", "e", "evet", "y", "yes"):
        try:
            list_devices()
        except Exception as exc:
            print(f"Aygıt listeleme hatası: {exc}")

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
            print(f"Hızlı mod: otomatik mikrofon aygıtı seçildi ({input_idx}).")

    do_test = "" if quick_mode else input("Önce 5 sn test yapılsın mı? [E/h]: ").strip().lower()
    if do_test in ("", "e", "evet", "y", "yes") and not quick_mode:
        try:
            run_test(sr, input_idx, output_idx, gain, boost, bass, treble, dist, output_name)
        except Exception as exc:
            print(f"Test hatası: {exc}")
            go_on = input("Yine de ana kayda devam edilsin mi? [E/h]: ").strip().lower()
            if go_on not in ("", "e", "evet", "y", "yes"):
                return

    try:
        backing, has_backing = prepare_backing(backing_file, sr, record_seconds, limit_seconds)
    except Exception as exc:
        print(f"Arka plan müzik yükleme hatası: {exc}")
        return

    duration_sec = len(backing) / sr
    recorded = None
    record_error: Optional[Exception] = None
    if has_backing:
        try:
            print(f"Kayıt başlıyor ({duration_sec:.1f} sn). Kulaklık önerilir...")
            recorded = sd.playrec(backing, samplerate=sr, channels=1, dtype="float32", device=(input_idx, output_idx))
            sd.wait()
        except Exception as exc:
            print(f"Kayıt hatası: {exc}")
            print("İpucu: Programı yeniden açıp aygıt listesini gösterin ve Mikrofon/Çıkış Aygıt Kimliği değerlerini girin.")
            return
    else:
        for cand in candidate_input_devices(input_idx):
            try:
                if cand is None:
                    print(f"Sadece mikrofon kaydı başlıyor ({duration_sec:.1f} sn).")
                else:
                    print(f"Sadece mikrofon kaydı başlıyor ({duration_sec:.1f} sn), aygıt={cand}.")
                recorded = sd.rec(frames=len(backing), samplerate=sr, channels=1, dtype="float32", device=cand)
                sd.wait()
                input_idx = cand
                record_error = None
                break
            except Exception as exc:
                record_error = exc
                continue
        if recorded is None:
            print(f"Kayıt hatası: {record_error}")
            print("İpucu: Programı yeniden açıp aygıt listesini gösterin ve Mikrofon/Çıkış Aygıt Kimliği değerlerini girin.")
            return

    voice = recorded[:, 0]
    print("Amfi efektleri uygulanıyor...")
    processed = apply_amp_chain(voice, sr, gain, boost, bass, treble, dist)
    processed = reduce_background_noise(processed, sr, max(0.0, min(100.0, noise_reduction)) / 100.0)

    speed_ratio = max(0.5, min(1.5, speed_percent / 100.0))
    if abs(speed_ratio - 1.0) > 1e-6:
        print(f"Hız ayarı uygulanıyor (%{speed_percent:.0f})...")
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
            print(f"MP3 yazıldı: {mp3_path}")
        except Exception as exc:
            print(f"MP3 dönüştürme hatası: {exc}")
    else:
        print("ffmpeg bulunamadı, MP3 atlandı.")

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

    print(f"Mix WAV: {mix_wav_path}")
    print(f"İşlenmiş WAV: {vocal_wav_path}")
    print(f"Ayarlar kaydedildi: {PRESET_PATH}")
    print("Tamamlandı.")


if __name__ == "__main__":
    main()
