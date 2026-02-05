import json
import os
import re
import threading

import numpy as np
import sounddevice as sd
from scipy.signal import bilinear, lfilter, lfilter_zi

REF_PASCAL = 20e-6

GRAPHIC_EQ_BANDS = [
    20, 25, 31.5, 40, 50, 63, 80, 100,
    125, 160, 200, 250, 315, 400, 500, 630,
    800, 1000, 1250, 1600, 2000, 2500, 3150, 4000,
    5000, 6300, 8000, 10000, 12500, 16000, 20000,
]


def load_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_calibration_profile(path):
    if not path or not os.path.exists(path):
        return {"sens_db": None, "freqs": None, "gains": None}

    with open(path, "r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]

    if not lines:
        return {"sens_db": None, "freqs": None, "gains": None}

    sens_db = None
    data_lines = lines
    header = lines[0]
    if "Sens Factor" in header:
        match = re.search(r"Sens Factor\s*=\s*([+-]?\d+(?:\.\d+)?)\s*dB", header)
        if match:
            sens_db = float(match.group(1))
        data_lines = lines[1:]

    freqs = []
    gains = []
    for line in data_lines:
        if line.startswith(("#", ";")):
            continue
        parts = line.replace(",", " ").split()
        if len(parts) < 2:
            continue
        try:
            freqs.append(float(parts[0]))
            gains.append(float(parts[1]))
        except ValueError:
            continue

    if len(freqs) < 2:
        return {"sens_db": sens_db, "freqs": None, "gains": None}

    return {
        "sens_db": sens_db,
        "freqs": np.array(freqs, dtype=np.float32),
        "gains": np.array(gains, dtype=np.float32),
    }


def design_a_weighting(sample_rate):
    f1 = 20.598997
    f2 = 107.65265
    f3 = 737.86223
    f4 = 12194.217
    a1000 = 1.9997

    nums = [(2 * np.pi * f4) ** 2 * (10 ** (a1000 / 20)), 0, 0, 0, 0]
    dens = np.polymul([1, 4 * np.pi * f4, (2 * np.pi * f4) ** 2],
                      [1, 4 * np.pi * f1, (2 * np.pi * f1) ** 2])
    dens = np.polymul(np.polymul(dens, [1, 2 * np.pi * f3]), [1, 2 * np.pi * f2])
    b, a = bilinear(nums, dens, sample_rate)
    return b, a


class AudioProcessor:
    def __init__(self, config):
        self.sample_rate = int(config["sample_rate"])
        self.block_size = int(config["block_size"])
        self.device = config.get("device")
        self.calibration_db = float(config.get("calibration_db", 0.0))
        self.calibration_file = config.get("calibration_file")
        self.spectrum_smooth = float(config.get("spectrum_smooth", 0.6))

        self._lock = threading.Lock()
        self._last_db = 0.0
        self._spectrum = np.zeros(len(GRAPHIC_EQ_BANDS), dtype=np.float32)
        self._ring = np.zeros(self.sample_rate, dtype=np.float32)
        self._ring_idx = 0

        self._b, self._a = design_a_weighting(self.sample_rate)
        self._zi = lfilter_zi(self._b, self._a) * 0.0

        calibration_path = self._resolve_calibration_path()
        calibration = load_calibration_profile(calibration_path)
        self._calibration_sens_db = calibration["sens_db"]
        self._calibration_freqs = calibration["freqs"]
        self._calibration_gains = calibration["gains"]

        self._stream = None

    def _resolve_calibration_path(self):
        if self.calibration_file:
            return os.path.abspath(self.calibration_file)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(base_dir, "..", "calibration.txt")
        return default_path if os.path.exists(default_path) else None

    def start(self):
        if self._stream:
            return

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            device=self.device,
            channels=1,
            callback=self._on_audio,
        )
        self._stream.start()

    def stop(self):
        if not self._stream:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def _on_audio(self, indata, frames, time, status):
        if status:
            return

        samples = indata[:, 0].astype(np.float32, copy=False)
        weighted, self._zi = lfilter(self._b, self._a, samples, zi=self._zi)
        rms = np.sqrt(np.mean(weighted ** 2))
        if self._calibration_sens_db is not None:
            dbfs = 20 * np.log10(max(rms, 1e-12))
            db = dbfs - self._calibration_sens_db + 94.0
        else:
            db = 20 * np.log10(max(rms, 1e-12) / REF_PASCAL)

        db += self.calibration_db

        with self._lock:
            self._last_db = db
            self._append_ring(samples)

    def _append_ring(self, samples):
        count = len(samples)
        end = self._ring_idx + count
        if end <= len(self._ring):
            self._ring[self._ring_idx:end] = samples
        else:
            first = len(self._ring) - self._ring_idx
            self._ring[self._ring_idx:] = samples[:first]
            self._ring[:count - first] = samples[first:]
        self._ring_idx = end % len(self._ring)

    def get_last_db(self):
        with self._lock:
            return float(self._last_db)

    def get_spectrum(self):
        with self._lock:
            return self._spectrum.copy()

    def compute_spectrum(self):
        with self._lock:
            data = np.roll(self._ring, -self._ring_idx).copy()

        if not np.any(data):
            return

        window = np.hanning(len(data))
        spectrum = np.fft.rfft(data * window)
        # Scale FFT to approximate dBFS for a full-scale sine.
        # Window sum/2 gives correct amplitude for Hann window.
        scale = max(np.sum(window) / 2.0, 1e-12)
        mag = (np.abs(spectrum) / scale) / np.sqrt(2.0)
        freqs = np.fft.rfftfreq(len(data), 1.0 / self.sample_rate)

        band_levels = np.zeros(len(GRAPHIC_EQ_BANDS), dtype=np.float32)
        for i, center in enumerate(GRAPHIC_EQ_BANDS):
            low = center / (2 ** (1 / 6))
            high = center * (2 ** (1 / 6))
            mask = (freqs >= low) & (freqs <= high)
            if not np.any(mask):
                level = -120.0
            else:
                power = np.mean(mag[mask] ** 2)
                level = 10 * np.log10(power + 1e-20)
            band_levels[i] = level

        if self._calibration_freqs is not None:
            corrections = np.interp(
                GRAPHIC_EQ_BANDS,
                self._calibration_freqs,
                self._calibration_gains,
                left=self._calibration_gains[0],
                right=self._calibration_gains[-1],
            )
            band_levels = band_levels + corrections

        with self._lock:
            self._spectrum = (
                self.spectrum_smooth * self._spectrum
                + (1.0 - self.spectrum_smooth) * band_levels
            )
