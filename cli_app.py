import shutil
import subprocess
import time
from pathlib import Path
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


def ask_float(label: str, default: float) -> float:
    raw = input(f"{label} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("Gecersiz deger, varsayilan kullaniliyor.")
        return default


def ask_int_optional(label: str) -> Optional[int]:
    raw = input(f"{label} (bos birak = varsayilan): ").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("Gecersiz ID, varsayilan kullaniliyor.")
        return None


def list_devices() -> None:
    print("\n--- Ses Cihazlari ---")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        print(f"{i}: {dev['name']} | in={dev['max_input_channels']} out={dev['max_output_channels']}")
    print("---------------------\n")


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
    print("5 sn test kaydi basliyor...")
    rec = sd.rec(frames=sr * 5, samplerate=sr, channels=1, dtype="float32", device=input_idx)
    sd.wait()
    voice = rec[:, 0]
    proc = apply_amp_chain(voice, sr, gain, boost, bass, treble, dist)
    preview = np.stack([proc, proc], axis=1)
    if output_idx is not None:
        print("Test oynatiliyor...")
        sd.play(preview, samplerate=sr, device=output_idx)
        sd.wait()

    out = Path.home() / "Desktop" / f"{name}_device_test.wav"
    sf.write(out, proc, sr)
    print(f"Test kaydi yazildi: {out}")


def ask_backing_file() -> Optional[Path]:
    backing_path = input("Backing dosya yolu (.wav/.aiff/.flac) [bos=mic-only]: ").strip()
    if not backing_path:
        return None

    backing_file = Path(backing_path).expanduser()
    if not backing_file.exists():
        print(f"Dosya bulunamadi: {backing_file}")
        return None
    return backing_file


def prepare_backing(backing_file: Optional[Path], sr: int, record_seconds: float) -> Tuple[np.ndarray, bool]:
    if backing_file is None:
        frames = max(1, int(sr * record_seconds))
        return np.zeros((frames, 2), dtype=np.float32), False

    print("Backing yukleniyor...")
    backing, backing_sr = sf.read(backing_file, dtype="float32")
    backing = ensure_stereo(backing)
    if backing_sr != sr:
        print(f"Sample rate {backing_sr} -> {sr} donusturuluyor...")
        backing = resample_linear(backing, backing_sr, sr)
    return backing, True


def main() -> None:
    print("\n=== Guitar Amp Recorder (Terminal Surumu) ===")
    print("Not: Device ID bilmiyorsaniz bos birakin. Enter ile varsayilan secilir.\n")

    if input("Cihaz listesi gosterilsin mi? [E/h]: ").strip().lower() in ("", "e", "evet", "y", "yes"):
        try:
            list_devices()
        except Exception as exc:
            print(f"Cihaz listeleme hatasi: {exc}")

    backing_file = ask_backing_file()

    output_name = input("Cikis dosya adi [guitar_mix_YYYYMMDD_HHMMSS]: ").strip()
    if not output_name:
        output_name = f"guitar_mix_{time.strftime('%Y%m%d_%H%M%S')}"

    gain = ask_float("Gain dB", 6)
    boost = ask_float("Boost dB", 6)
    bass = ask_float("Bass dB", 3)
    treble = ask_float("Treble dB", 2)
    dist = ask_float("Distortion %", 25)

    backing_level = ask_float("Backing seviye %", 100)
    vocal_level = ask_float("Vokal seviye %", 85)

    record_seconds = ask_float("Kayit suresi sn (sadece mic-only icin)", 60)
    if record_seconds <= 0:
        record_seconds = 60

    input_idx = ask_int_optional("Mikrofon Device ID")
    output_idx = ask_int_optional("Cikis Device ID")

    sr = 44100
    do_test = input("Once 5 sn test yapilsin mi? [E/h]: ").strip().lower()
    if do_test in ("", "e", "evet", "y", "yes"):
        try:
            run_test(sr, input_idx, output_idx, gain, boost, bass, treble, dist, output_name)
        except Exception as exc:
            print(f"Test hatasi: {exc}")
            go_on = input("Yine de ana kayda devam edilsin mi? [E/h]: ").strip().lower()
            if go_on not in ("", "e", "evet", "y", "yes"):
                return

    try:
        backing, has_backing = prepare_backing(backing_file, sr, record_seconds)
    except Exception as exc:
        print(f"Backing yukleme hatasi: {exc}")
        return

    duration_sec = len(backing) / sr
    try:
        if has_backing:
            print(f"Kayit basliyor ({duration_sec:.1f} sn). Kulaklik onerilir...")
            recorded = sd.playrec(backing, samplerate=sr, channels=1, dtype="float32", device=(input_idx, output_idx))
        else:
            print(f"Mic-only kayit basliyor ({duration_sec:.1f} sn).")
            recorded = sd.rec(frames=len(backing), samplerate=sr, channels=1, dtype="float32", device=input_idx)
        sd.wait()
    except Exception as exc:
        print(f"Kayit hatasi: {exc}")
        print("Ipucu: Programi yeniden acip cihaz listesini gosterin ve Mikrofon/Cikis Device ID degerlerini girin.")
        return

    voice = recorded[:, 0]
    print("Amfi efektleri uygulaniyor...")
    processed = apply_amp_chain(voice, sr, gain, boost, bass, treble, dist)

    mix = backing.copy() * (backing_level / 100.0)
    mix[:, 0] += processed * (vocal_level / 100.0)
    mix[:, 1] += processed * (vocal_level / 100.0)
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
            print(f"MP3 yazildi: {mp3_path}")
        except Exception as exc:
            print(f"MP3 cevirme hatasi: {exc}")
    else:
        print("ffmpeg bulunamadi, MP3 atlandi.")

    print(f"Mix WAV: {mix_wav_path}")
    print(f"Vocal WAV: {vocal_wav_path}")
    print("Tamamlandi.")


if __name__ == "__main__":
    main()
