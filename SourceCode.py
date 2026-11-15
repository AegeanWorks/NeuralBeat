import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import simpledialog
import time
import json
from pathlib import Path
from tkinter import filedialog
import logging
import threading
import os
import subprocess
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
from scipy import signal
from scipy.io import wavfile
import ttkbootstrap as tb

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import presets
import verification
import visual

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# =============================================================================
# Global Application State
# =============================================================================

osc_merge_var = None
live_status_after_id = None
play_mode = "manual"  # "manual" or "ramp"
beat_type_var = None  # "binaural", "monaural", or "isochronic"

# UI widgets and variables are created by main(); placeholders keep the logic functions testable.
root = None
left_frequency_entry = None
left_volume_entry = None
left_waveform_var = None
left_waveform_combobox = None
right_frequency_entry = None
right_volume_entry = None
right_waveform_var = None
right_waveform_combobox = None
monaural_beats_frame = None
binaural_beats_frame = None
isochronic_beats_frame = None
binaural_monaural_frame = None
preset_name_entry = None
preset_category_var = None
carrier_entry = None
start_beat_entry = None
end_beat_entry = None
ramp_minutes_entry = None
noise_type_var = None
noise_volume_entry = None
status_var = None
ramp_enabled_var = None

# Visual strobe mode state (the window and scheduler live on the Tk thread).
# Widget/variable globals are declared at module level (same pattern as
# beat_type_var/osc_merge_var) so tests can patch them before any window
# exists.
visual_mode_active = False
visual_window = None
visual_scheduler = None
visual_after_id = None
visual_lateness_monitor = None
visual_active_cap = None
visual_active_gen = None
visual_active_req = None
visual_beat_clock = None
visual_active_status = None
visual_last_reason = None
visual_status_last_refresh = 0.0
visual_toggle_button = None
visual_status_label = None
visual_intensity_var = None
visual_harmonics_var = None
theme_menu_var = None
osc_palette_var = None

PHOTOSENSITIVE_WARNING = (
    "PHOTOSENSITIVE SAFETY WARNING\n\n"
    "Visual mode produces full-screen light flashes.\n"
    "Flashing lights can trigger seizures in people with photosensitive\n"
    "epilepsy. The risk is highest in the 15-25 Hz band (which includes the\n"
    "16 Hz preset bundled with this app).\n\n"
    "Do not use it if you or someone in your family has epilepsy or a\n"
    "sensitivity to flashing lights; consult a doctor first.\n\n"
    "At any discomfort, leave the mode immediately: any key or click exits.\n\n"
    "NeuralBeat and its visual mode are NOT medical devices or treatments.\n\n"
    "Do you understand the risk and want to enable visual mode?"
)

# Defaults
ramp_carrier_hz = 432.0
ramp_start_beat_hz = 20.0
ramp_end_beat_hz = 3.0
ramp_duration_s = 30.0 * 60.0
manual_left_hz = 432.0
manual_right_hz = 432.0

APP_DIR = Path.home() / ".neuralbeat"
CONFIG_PATH = APP_DIR / "config.json"

# Visualizer state
osc_window = None
visualizer_canvas = None
visualizer_ax = None
visualizer_hline = None
line_left = None
line_right = None
OSC_BUFFER_SECONDS = 0.05
osc_plot_buffer_l = None
osc_plot_buffer_r = None

OSC_COLOR_PALETTES = {
    "Cyan / Magenta": {
        "dark": ("#00FFFF", "#FF00FF"),
        "light": ("#008B8B", "#8B008B")
    },
    "Green / Yellow": {
        "dark": ("#00FF00", "#FFFF00"),
        "light": ("#006400", "#BDB76B")
    },
    "Red / Blue": {
        "dark": ("#FF4500", "#1E90FF"),
        "light": ("#DC143C", "#0000CD")
    }
}


waveforms = {
    "Sine": np.sin,
    "Square": signal.square,
    "Sawtooth": signal.sawtooth,
    "Triangle": lambda t: signal.sawtooth(t, width=0.5),
}

# =============================================================================
# Noise Generation
# =============================================================================

class NoiseGenerator:
    """
    Generates blocks of colored noise with state preservation using digital filters.
    """
    def __init__(self):
        # Pink noise filter coeffs (-3dB/octave)
        self.pink_b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
        self.pink_a = [1, -2.494956002, 2.017265875, -0.522189400]
        self.pink_zi = signal.lfilter_zi(self.pink_b, self.pink_a)

        # Brown noise filter coeffs (leaky integrator, -6dB/octave)
        self.brown_b = [1.0]
        self.brown_a = [1.0, -0.999] # Very close to 1 for strong low-pass
        self.brown_zi = signal.lfilter_zi(self.brown_b, self.brown_a)

    def _normalize(self, noise):
        """Normalize noise to have RMS of 1."""
        rms = np.sqrt(np.mean(noise**2))
        if rms > 1e-9:
            return noise / rms
        return noise

    def generate(self, noise_type, n_samples):
        if noise_type == "White":
            return self._normalize(np.random.randn(n_samples))
        elif noise_type == "Pink":
            white = np.random.randn(n_samples)
            noise, self.pink_zi = signal.lfilter(self.pink_b, self.pink_a, white, zi=self.pink_zi)
            return self._normalize(noise)
        elif noise_type == "Brown":
            white = np.random.randn(n_samples)
            noise, self.brown_zi = signal.lfilter(self.brown_b, self.brown_a, white, zi=self.brown_zi)
            return self._normalize(noise)
        return np.zeros(n_samples)

# =============================================================================
# Configuration & Persistence
# =============================================================================

VALID_THEMES = ("darkly", "superhero", "flatly")

# Export duration policy shared by the UI validation and the export thread clamp.
EXPORT_MIN_DURATION_S = 1.0
EXPORT_MAX_DURATION_S = 3600.0

def is_combined_beat_label(category: str) -> bool:
    """True when the label carries both beat words (combined UI label)."""
    c = str(category).strip().lower()
    return "binaural" in c and "monaural" in c

def _quarantine_corrupt_config() -> None:
    """Moves an unparsable config file aside so a later save can recreate it."""
    target = CONFIG_PATH.with_name(CONFIG_PATH.name + ".corrupt")
    if target.exists():
        target = CONFIG_PATH.with_name(
            f"{CONFIG_PATH.name}.{time.strftime('%Y%m%d-%H%M%S')}.corrupt")
    CONFIG_PATH.replace(target)
    logger.error(f"Corrupt config {CONFIG_PATH} quarantined to {target}.")

def load_config() -> dict:
    """Loads configuration from the JSON file."""
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            logger.error(f"Config {CONFIG_PATH} root must be an object, ignoring.")
    except json.JSONDecodeError:
        # Preserve the unreadable file for recovery instead of letting the
        # next save_config silently overwrite it.
        try:
            _quarantine_corrupt_config()
        except Exception:
            logger.error(f"Could not quarantine corrupt config {CONFIG_PATH}", exc_info=True)
        return {}
    except Exception:
        logger.error(f"Error loading config from {CONFIG_PATH}", exc_info=True)
    return {}

def save_config(cfg: dict) -> None:
    """Saves the configuration dictionary to the JSON file."""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        logger.error(f"Error saving config to {CONFIG_PATH}", exc_info=True)

config = load_config()
if config.get("theme") not in VALID_THEMES:
    # Fall back to darkly for missing/invalid themes so tb.Window never crashes.
    if "theme" in config:
        logger.error(f"Invalid theme {config.get('theme')!r} in config, falling back to darkly.")
    config["theme"] = "darkly"
initial_theme = config.get("theme", "darkly")

def _normalize_category(category: str) -> str:
    c = str(category).strip().lower()
    if "isochronic" in c:
        return "Isochronic"
    if is_combined_beat_label(c):
        # Combined UI label "Binaural Beat / Monaural Beat" - caller decides
        # based on frequencies; default to Binaural for backward compat.
        return "Binaural"
    if "monaural" in c:
        return "Monaural"
    if "binaural" in c:
        return "Binaural"
    raise ValueError("Category must be 'Binaural Beat / Monaural Beat' or 'Isochronic Tone'")

def get_user_presets() -> dict:
    up = config.get("user_presets", {})
    return {
        "Monaural": list(up.get("Monaural", [])),
        "Binaural": list(up.get("Binaural", [])),
        "Isochronic": list(up.get("Isochronic", [])),
    }

def add_user_preset(category: str, label: str, left_hz: float, right_hz: float) -> None:
    category = _normalize_category(category)
    try:
        if category == "Isochronic":
            preset_obj = {
                "label": str(label).strip(),
                "carrier_hz": float(right_hz),
                "pulse_hz": float(left_hz),
            }
        else:
            preset_obj = {
                "label": str(label).strip(),
                "left_hz": float(left_hz),
                "right_hz": float(right_hz),
            }
    except ValueError:
        raise ValueError("Invalid numeric value for frequencies.")
    if not preset_obj["label"]:
        raise ValueError("Preset Name Cannot be Empty")

    up = get_user_presets()
    up[category].append(preset_obj)
    config["user_presets"] = up
    save_config(config)

def remove_user_preset(category: str, label: str) -> bool:
    category = _normalize_category(category)
    up = get_user_presets()
    label = str(label).strip()
    for i, p in enumerate(up[category]):
        if str(p.get("label", "")).strip() == label:
            up[category].pop(i)
            config["user_presets"] = up
            save_config(config)
            return True
    return False

def get_all_presets() -> dict:
    up = get_user_presets()
    return {
        "Monaural": list(presets.MONAURAL_PRESETS) + up["Monaural"],
        "Binaural": list(presets.BINAURAL_PRESETS) + up["Binaural"],
        "Isochronic": list(presets.ISOCHRONIC_PRESETS) + up["Isochronic"],
    }

# =============================================================================
# Audio Engine & DSP
# =============================================================================

def clamp(value, lo, hi):
    """Clamps a value between lo and hi."""
    return max(lo, min(hi, value))

def validate_audio_params(freq_l, freq_r, vol_l, vol_r, duration=None):
    """Validates audio parameters (frequencies, volumes, duration)."""
    if not (20.0 <= freq_l <= 20000.0):
        return "Frequency must be between 20 Hz and 20000 Hz."
    if not (20.0 <= freq_r <= 20000.0):
        return "Frequency must be between 20 Hz and 20000 Hz."
    if not (0.0 <= vol_l <= 100.0):
        return "Volume must be between 0% and 100%."
    if not (0.0 <= vol_r <= 100.0):
        return "Volume must be between 0% and 100%."
    if duration is not None and duration <= 0:
        return "Duration must be positive."
    return None

def _compute_ramped_beat_hz(elapsed_s: float, start_beat_hz: float, end_beat_hz: float, ramp_s: float) -> float:
    """Calculates the current beat frequency based on ramp progress."""
    if ramp_s <= 0:
        return end_beat_hz
    x = clamp(elapsed_s / ramp_s, 0.0, 1.0)
    return start_beat_hz + (end_beat_hz - start_beat_hz) * x

@dataclass
class AudioConfig:
    sample_rate: int
    left_volume: float
    right_volume: float
    left_waveform: str
    right_waveform: str
    noise_type: str
    noise_volume: float
    use_ramp: bool
    left_frequency: float
    right_frequency: float
    carrier_hz: float
    start_beat_hz: float
    end_beat_hz: float
    ramp_duration_s: float
    beat_type: str = "binaural"

def get_audio_config_from_ui() -> AudioConfig:
    """Reads values from UI entries and returns an AudioConfig object."""
    try:
        left_volume_val = float(left_volume_entry.get())
        right_volume_val = float(right_volume_entry.get())
        noise_volume_val = float(noise_volume_entry.get())
    except ValueError:
        raise ValueError("Please enter valid numeric values for volume.")

    if not (0.0 <= noise_volume_val <= 100.0):
        raise ValueError("Noise volume must be between 0% and 100%.")

    left_volume = clamp(left_volume_val / 100.0, 0.0, 1.0)
    right_volume = clamp(right_volume_val / 100.0, 0.0, 1.0)
    noise_volume = clamp(noise_volume_val / 100.0, 0.0, 1.0)

    left_waveform = left_waveform_var.get()
    right_waveform = right_waveform_var.get()
    noise_type = noise_type_var.get()
    use_ramp = bool(ramp_enabled_var.get())
    sample_rate = 44100
    beat_type = beat_type_var.get() if beat_type_var else "binaural"

    if use_ramp:
        try:
            r_carrier = float(carrier_entry.get())
            r_start = float(start_beat_entry.get())
            r_end = float(end_beat_entry.get())
            r_min = float(ramp_minutes_entry.get())
        except ValueError:
            raise ValueError("Please enter valid numeric values for ramp settings.")

        if not (20.0 <= r_carrier <= 20000.0):
             raise ValueError("Carrier frequency must be between 20 Hz and 20000 Hz.")
        if not (0.1 <= r_start <= 100.0):
             raise ValueError("Beat frequency must be between 0.1 Hz and 100 Hz.")
        if not (0.1 <= r_end <= 100.0):
             raise ValueError("Beat frequency must be between 0.1 Hz and 100 Hz.")
        if not (0.5 <= r_min <= 120.0):
             raise ValueError("Ramp duration must be between 0.5 and 120 minutes.")
        # Keep left channel non-negative: carrier - beat/2 >= 20 Hz lower bound
        max_beat = max(r_start, r_end)
        if beat_type != "isochronic" and r_carrier - (max_beat / 2.0) < 20.0:
             raise ValueError("Carrier must be at least 20 Hz above beat/2 so left channel stays audible (>=20 Hz).")

        ramp_duration_s = max(0.0, r_min * 60.0)

        return AudioConfig(
            sample_rate=sample_rate,
            left_volume=left_volume,
            right_volume=right_volume,
            left_waveform=left_waveform,
            right_waveform=right_waveform,
            noise_type=noise_type,
            noise_volume=noise_volume,
            use_ramp=True,
            left_frequency=0.0,
            right_frequency=0.0,
            carrier_hz=r_carrier,
            start_beat_hz=r_start,
            end_beat_hz=r_end,
            ramp_duration_s=ramp_duration_s,
            beat_type=beat_type
        )
    else:
        try:
            m_left = float(left_frequency_entry.get())
            m_right = float(right_frequency_entry.get())
        except ValueError:
            raise ValueError("Please enter valid numeric values for frequencies.")

        if beat_type == "isochronic":
            if not (0.1 <= m_left <= 100.0):
                raise ValueError("Beat frequency must be between 0.1 Hz and 100 Hz for isochronic tones.")
            if not (20.0 <= m_right <= 20000.0):
                raise ValueError("Carrier frequency must be between 20 Hz and 20000 Hz.")
        else:
            err = validate_audio_params(m_left, m_right, left_volume_val, right_volume_val)
            if err:
                raise ValueError(err)

        carrier_hz = m_right if beat_type == "isochronic" else 0.0

        return AudioConfig(
            sample_rate=sample_rate,
            left_volume=left_volume,
            right_volume=right_volume,
            left_waveform=left_waveform,
            right_waveform=right_waveform,
            noise_type=noise_type,
            noise_volume=noise_volume,
            use_ramp=False,
            left_frequency=m_left,
            right_frequency=m_right,
            carrier_hz=carrier_hz,
            start_beat_hz=0.0,
            end_beat_hz=0.0,
            ramp_duration_s=0.0,
            beat_type=beat_type
        )

class BinauralGenerator:
    """
    Generates binaural or monaural beats based on the provided AudioConfig.
    Handles waveform generation, ramping, and soft limiting.
    """
    def __init__(self, cfg: AudioConfig):
        self.cfg = cfg
        self.phase_l = 0.0
        self.phase_r = 0.0
        self.samples_generated = 0
        self.ramp_s = cfg.ramp_duration_s

        # Initialize noise generator if needed
        if self.cfg.noise_type != "None" and self.cfg.noise_volume > 0:
            self.noise_gen = NoiseGenerator()
        else:
            self.noise_gen = None

        # Resolve waveform functions
        # Default to Sine if not found to prevent crashes
        self.left_wave_func = waveforms.get(cfg.left_waveform, np.sin)
        self.right_wave_func = waveforms.get(cfg.right_waveform, np.sin)

        self.drive = 2.5
        self.tanh_drive = np.tanh(self.drive)

        # Fade configuration
        self.fade_in_len = int(0.02 * cfg.sample_rate) # 20 ms
        self.fade_out_len = int(0.02 * cfg.sample_rate) # 20 ms
        self.stopping = False
        self.fade_out_counter = 0
        self.is_finished = False

    def request_stop(self):
        """Signal the generator to start fading out."""
        self.stopping = True

    def generate_block(self, frames: int) -> np.ndarray:
        # Time array for this block (seconds relative to start of stream)
        # Using float64 for time accumulation to prevent jitter over long sessions, though inputs are float
        current_time = self.samples_generated / self.cfg.sample_rate

        # Calculate frequencies per sample
        if self.cfg.use_ramp:
            # Vectorized ramp calculation
            # Create global time array for this block
            t_global = current_time + np.arange(frames, dtype=np.float64) / self.cfg.sample_rate

            if self.ramp_s <= 0:
                 beat_hz = np.full(frames, self.cfg.end_beat_hz, dtype=np.float64)
            else:
                 # Linear interpolation with clamping
                 progress = np.clip(t_global / self.ramp_s, 0.0, 1.0)
                 beat_hz = self.cfg.start_beat_hz + (self.cfg.end_beat_hz - self.cfg.start_beat_hz) * progress

            lf_array = self.cfg.carrier_hz - (beat_hz / 2.0)
            rf_array = self.cfg.carrier_hz + (beat_hz / 2.0)

            # Enforce positive frequency
            lf_array = np.maximum(0.0, lf_array)
            rf_array = np.maximum(0.0, rf_array)

            # Calculate phase increments: 2 * pi * f / sr
            inc_l = (2.0 * np.pi * lf_array / self.cfg.sample_rate)
            inc_r = (2.0 * np.pi * rf_array / self.cfg.sample_rate)

            # Calculate cumulative phase shift
            # We start at self.phase_l. Sample 0 is at self.phase_l.
            # Sample n is at self.phase_l + sum(inc[0]...inc[n-1])
            # np.cumsum returns [inc0, inc0+inc1, ...]. We shift it.

            phase_shift_l = np.concatenate(([0.0], np.cumsum(inc_l)[:-1]))
            phase_shift_r = np.concatenate(([0.0], np.cumsum(inc_r)[:-1]))

            phase_vec_l = self.phase_l + phase_shift_l
            phase_vec_r = self.phase_r + phase_shift_r

            # Calculate next block seed phase
            # Total change over this block is sum of all increments
            self.phase_l = (self.phase_l + np.sum(inc_l)) % (2.0 * np.pi)
            self.phase_r = (self.phase_r + np.sum(inc_r)) % (2.0 * np.pi)

        else:
            # Constant frequency optimization
            # Avoid full array allocation and cumsum for constant frequency

            freq_l = max(0.0, self.cfg.left_frequency)
            freq_r = max(0.0, self.cfg.right_frequency)

            # Phase increment per sample
            inc_l = (2.0 * np.pi * freq_l / self.cfg.sample_rate)
            inc_r = (2.0 * np.pi * freq_r / self.cfg.sample_rate)

            # Create time vector for this block (0, 1, ..., frames-1)
            t_vec = np.arange(frames, dtype=np.float64)

            # phase[n] = phase_start + n * inc
            phase_vec_l = self.phase_l + t_vec * inc_l
            phase_vec_r = self.phase_r + t_vec * inc_r

            # Update phase for next block
            self.phase_l = (self.phase_l + frames * inc_l) % (2.0 * np.pi)
            self.phase_r = (self.phase_r + frames * inc_r) % (2.0 * np.pi)

        # Generate Waveforms
        left = self.cfg.left_volume * self.left_wave_func(phase_vec_l)
        right = self.cfg.right_volume * self.right_wave_func(phase_vec_r)

        stereo = np.column_stack((left, right))

        # Generate and mix noise before limiting
        if self.noise_gen:
            noise = self.noise_gen.generate(self.cfg.noise_type, frames)
            # Add mono noise to both channels using broadcasting
            stereo += (noise * self.cfg.noise_volume)[:, np.newaxis]

        # Stateless soft limiter/saturator
        stereo = np.tanh(stereo * self.drive) / self.tanh_drive
        stereo = np.clip(stereo, -1.0, 1.0)

        # Apply Fade In
        start_idx = self.samples_generated
        end_idx = start_idx + frames

        if start_idx < self.fade_in_len:
            # Generate ramp for fade in
            ramp_in = np.arange(start_idx, end_idx, dtype=np.float32) / self.fade_in_len
            ramp_in = np.clip(ramp_in, 0.0, 1.0)
            stereo *= ramp_in[:, np.newaxis]

        # Apply Fade Out if stopping
        if self.stopping:
            # Calculate remaining fade out samples
            remaining = self.fade_out_len - self.fade_out_counter

            if remaining <= 0:
                stereo.fill(0)
                self.is_finished = True
                self.samples_generated += frames
                return stereo

            # Generate fade out ramp
            t_fade = np.arange(self.fade_out_counter, self.fade_out_counter + frames, dtype=np.float32)
            ramp_out = 1.0 - (t_fade / self.fade_out_len)
            ramp_out = np.clip(ramp_out, 0.0, 1.0)

            stereo *= ramp_out[:, np.newaxis]

            self.fade_out_counter += frames

            if self.fade_out_counter >= self.fade_out_len:
                self.is_finished = True
                # Ensure silence after fade
                cutoff = int(remaining)
                if cutoff < frames:
                    stereo[cutoff:] = 0

        self.samples_generated += frames
        return stereo.astype(np.float32, copy=False)


class IsochronicGenerator:
    """
    Generates isochronic tones - rhythmic pulses of sound at a specific beat frequency.
    The carrier tone pulses on and off at the beat rate with equal intensity on both channels.
    """
    def __init__(self, cfg: AudioConfig):
        self.cfg = cfg
        self.phase = 0.0
        self.pulse_phase = 0.0  # 0..1 cycle phase for the gating LFO, phase-continuous across blocks
        self.samples_generated = 0
        self.ramp_s = cfg.ramp_duration_s

        if self.cfg.noise_type != "None" and self.cfg.noise_volume > 0:
            self.noise_gen = NoiseGenerator()
        else:
            self.noise_gen = None

        self.wave_func = waveforms.get(cfg.left_waveform, np.sin)

        self.drive = 2.5
        self.tanh_drive = np.tanh(self.drive)

        self.fade_in_len = int(0.02 * cfg.sample_rate)
        self.fade_out_len = int(0.02 * cfg.sample_rate)
        self.stopping = False
        self.fade_out_counter = 0
        self.is_finished = False

    def request_stop(self):
        self.stopping = True

    def generate_block(self, frames: int) -> np.ndarray:
        current_time = self.samples_generated / self.cfg.sample_rate

        if self.cfg.use_ramp:
            t_global = current_time + np.arange(frames, dtype=np.float64) / self.cfg.sample_rate

            if self.ramp_s <= 0:
                beat_hz = np.full(frames, self.cfg.end_beat_hz, dtype=np.float64)
            else:
                progress = np.clip(t_global / self.ramp_s, 0.0, 1.0)
                beat_hz = self.cfg.start_beat_hz + (self.cfg.end_beat_hz - self.cfg.start_beat_hz) * progress

            beat_hz = np.maximum(0.1, beat_hz)
            carrier_hz = np.full(frames, self.cfg.carrier_hz, dtype=np.float64)
        else:
            beat_hz = np.full(frames, max(0.1, self.cfg.left_frequency), dtype=np.float64)
            carrier_hz = np.full(frames, max(20.0, self.cfg.carrier_hz), dtype=np.float64)

        inc = (2.0 * np.pi * carrier_hz / self.cfg.sample_rate)
        phase_shift = np.concatenate(([0.0], np.cumsum(inc)[:-1]))
        phase_vec = self.phase + phase_shift
        self.phase = (self.phase + np.sum(inc)) % (2.0 * np.pi)

        carrier_wave = self.wave_func(phase_vec)

        # Phase-continuous 50% duty-cycle pulse gate.
        # Old code used mod(global_index, sr/beat) which glitches when beat_hz
        # ramps (period changes per-sample). Use a pulse-phase accumulator
        # instead: phase += beat/sr per sample, on when phase < 0.5.
        pulse_inc = beat_hz / self.cfg.sample_rate
        pulse_shift = np.concatenate(([0.0], np.cumsum(pulse_inc)[:-1]))
        pulse_vec = (self.pulse_phase + pulse_shift) % 1.0
        self.pulse_phase = (self.pulse_phase + np.sum(pulse_inc)) % 1.0
        pulse = pulse_vec < 0.5

        mono = self.cfg.left_volume * carrier_wave * pulse.astype(np.float64)

        stereo = np.column_stack((mono, mono))

        if self.noise_gen:
            noise = self.noise_gen.generate(self.cfg.noise_type, frames)
            stereo += (noise * self.cfg.noise_volume)[:, np.newaxis]

        stereo = np.tanh(stereo * self.drive) / self.tanh_drive
        stereo = np.clip(stereo, -1.0, 1.0)

        start_idx = self.samples_generated
        if start_idx < self.fade_in_len:
            ramp_in = np.arange(start_idx, start_idx + frames, dtype=np.float32) / self.fade_in_len
            ramp_in = np.clip(ramp_in, 0.0, 1.0)
            stereo *= ramp_in[:, np.newaxis]

        if self.stopping:
            remaining = self.fade_out_len - self.fade_out_counter
            if remaining <= 0:
                stereo.fill(0)
                self.is_finished = True
                self.samples_generated += frames
                return stereo

            t_fade = np.arange(self.fade_out_counter, self.fade_out_counter + frames, dtype=np.float32)
            ramp_out = 1.0 - (t_fade / self.fade_out_len)
            ramp_out = np.clip(ramp_out, 0.0, 1.0)

            stereo *= ramp_out[:, np.newaxis]

            self.fade_out_counter += frames

            if self.fade_out_counter >= self.fade_out_len:
                self.is_finished = True
                cutoff = int(remaining)
                if cutoff < frames:
                    stereo[cutoff:] = 0

        self.samples_generated += frames
        return stereo.astype(np.float32, copy=False)


class AudioEngine:
    """
    Manages the audio playback stream using sounddevice.
    Handles thread safety for starting and stopping playback.
    """
    def __init__(self):
        self._stream = None
        self.generator = None
        self._lock = threading.Lock()
        self._data_lock = threading.Lock()
        self.is_playing = False
        self.start_time = 0.0
        self.current_config = None
        self.last_block = None

    def start(self, cfg: AudioConfig):
        self.stop()

        with self._lock:
            try:
                if cfg.beat_type == "isochronic":
                    gen = IsochronicGenerator(cfg)
                else:
                    gen = BinauralGenerator(cfg)
                self.generator = gen
                self.current_config = cfg

                def callback(outdata, frames, time, status):
                    if status:
                        logger.warning(f"Audio status: {status}")
                    try:
                        # Generate audio using local 'gen' reference
                        # This avoids race conditions if self.generator is set to None by stop()
                        data = gen.generate_block(frames)
                        outdata[:] = data

                        # Store the last block for visualization
                        with self._data_lock:
                            self.last_block = data.copy()

                        # Check if finished (fade out complete)
                        if gen.is_finished:
                            raise sd.CallbackStop

                    except Exception as e:
                        if not isinstance(e, sd.CallbackStop):
                            logger.error("Audio callback error", exc_info=True)
                        # Silence on error
                        outdata.fill(0)

                self._stream = sd.OutputStream(
                    samplerate=cfg.sample_rate,
                    channels=2,
                    callback=callback,
                    dtype="float32"
                )
                self._stream.start()
                self.is_playing = True
                self.start_time = time.time()
                logger.info("Audio started")
            except Exception as e:
                logger.error("Failed to start audio", exc_info=True)
                self.is_playing = False
                if self._stream:
                    try:
                        self._stream.close()
                    except Exception:
                        logger.debug("Could not close audio stream during startup cleanup", exc_info=True)
                    self._stream = None
                raise e

    def stop(self):
        """Stops audio gracefully with fade out."""
        # 1. Signal stop
        with self._lock:
            if not self.is_playing:
                return

            if self.generator:
                self.generator.request_stop()

        # 2. Wait for stream to finish (fade out)
        # We wait up to 200ms
        for _ in range(20):
             with self._lock:
                 if self.generator and self.generator.is_finished:
                     break
                 # Also check if stream is inactive?
                 # stream.active might be true until callback returns Stop
             time.sleep(0.01)

        # 3. Force stop
        with self._lock:
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    logger.error("Error closing stream", exc_info=True)
                self._stream = None
            self.is_playing = False
            self.generator = None
            with self._data_lock:
                self.last_block = None
            logger.info("Audio stopped")

    def get_elapsed_time(self):
        if self.is_playing:
            return time.time() - self.start_time
        return 0.0
    
    def get_last_block(self):
        with self._data_lock:
            if self.last_block is not None:
                return self.last_block.copy()
        return None

audio_engine = AudioEngine()

def stop_audio():
    global live_status_after_id
    global play_mode

    # Visual mode depends on playing audio: close it before stopping
    if visual_mode_active:
        close_visual_mode("audio stopped")

    # Stop UI update loop
    if live_status_after_id is not None:
        try:
            root.after_cancel(live_status_after_id)
        except Exception:
            logger.error("Error cancelling live status update", exc_info=True)
        live_status_after_id = None

    try:
        audio_engine.stop()
    except Exception as e:
        logger.error(f"Error stopping audio: {e}", exc_info=True)

    play_mode = "manual"


# =============================================================================
# Visual Strobe Mode
# =============================================================================

def get_visual_settings() -> dict:
    """The visual section of config merged with defaults (backwards compatible)."""
    return visual.merge_visual_config(config)


def save_visual_setting(key, value) -> None:
    """Persist one key of the visual section in ~/.neuralbeat/config.json."""
    v = config.get("visual") if isinstance(config.get("visual"), dict) else {}
    v[key] = value
    config["visual"] = v
    save_config(config)


def get_visual_refresh_hz() -> float:
    """Calibrated screen refresh (conservative default when absent)."""
    v = get_visual_settings()
    if v["refresh_hz"] and v["refresh_hz"] > 0:
        return v["refresh_hz"]
    return visual.DEFAULT_REFRESH_HZ


def probe_system_refresh_hz():
    """Nominal refresh reported by the system. None when unavailable.

    Not a measurement: it only avoids the 60 Hz default when real calibration
    is unreliable (e.g. a compositor that ignores deadlines). Windows uses the
    display API; Linux/X11 uses xrandr.
    """
    if os.name == "nt":
        return _windows_nominal_refresh_hz()
    try:
        out = subprocess.run(["xrandr", "--current"], capture_output=True,
                             text=True, timeout=3.0).stdout
    except Exception:
        logger.info("No xrandr available for the system refresh", exc_info=True)
        return None
    return visual.parse_xrandr_refresh_hz(out)


def _windows_nominal_refresh_hz():
    """Nominal refresh (Hz) of the primary display via the Win32 API.

    Same caveat as the xrandr path: it is not a measurement. Returns None
    when the API reports nothing usable (failure or frequency 0).
    """
    try:
        import ctypes
        from ctypes import wintypes

        class _DevModeUnion(ctypes.Union):
            _fields_ = [("dmPosition", wintypes.POINTL),
                        ("dmDisplayOrientation", wintypes.DWORD),
                        ("dmDisplayFixedOutput", wintypes.DWORD)]

        class _DevModeW(ctypes.Structure):
            _fields_ = [
                ("dmDeviceName", wintypes.WCHAR * 32),
                ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD),
                ("dmSize", wintypes.WORD),
                ("dmDriverExtra", wintypes.WORD),
                ("dmFields", wintypes.DWORD),
                ("u1", _DevModeUnion),
                ("dmColor", wintypes.SHORT),
                ("dmDuplex", wintypes.SHORT),
                ("dmYResolution", wintypes.SHORT),
                ("dmTTOption", wintypes.SHORT),
                ("dmCollate", wintypes.SHORT),
                ("dmFormName", wintypes.WCHAR * 32),
                ("dmLogPixels", wintypes.WORD),
                ("dmBitsPerPel", wintypes.DWORD),
                ("dmPelsWidth", wintypes.DWORD),
                ("dmPelsHeight", wintypes.DWORD),
                ("dmDisplayFlags", wintypes.DWORD),
                ("dmDisplayFrequency", wintypes.DWORD),
                ("dmICMMethod", wintypes.DWORD),
                ("dmICMIntent", wintypes.DWORD),
                ("dmMediaType", wintypes.DWORD),
                ("dmDitherType", wintypes.DWORD),
                ("dmReserved1", wintypes.DWORD),
                ("dmReserved2", wintypes.DWORD),
                ("dmPanningWidth", wintypes.DWORD),
                ("dmPanningHeight", wintypes.DWORD),
            ]

        dm = _DevModeW()
        dm.dmSize = ctypes.sizeof(_DevModeW)
        ENUM_CURRENT_SETTINGS = 0xFFFFFFFF  # DWORD -1
        user32 = ctypes.windll.user32
        if not user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS,
                                           ctypes.byref(dm)):
            return None
        freq = float(dm.dmDisplayFrequency)
        if freq <= 0:
            return None
        # Round-trips like 59.94/29.97 are reported as integers on some
        # drivers; accept whatever the driver reports, plausibility is
        # enforced by visual.merge_visual_config on read.
        return freq
    except Exception:
        logger.info("Windows refresh probe failed", exc_info=True)
        return None


def get_visual_rate_request() -> dict:
    """Resolves the requested visual rhythm from the UI state.

    Returns mode ("manual"/"ramp"), beat_type and rate_hz: binaural uses
    |right-left|, isochronic uses the pulse rate, and a ramp uses the WORST
    point of the sweep (gate). Raises ValueError when inputs are not numeric.
    """
    bt = beat_type_var.get() if beat_type_var else "binaural"
    if ramp_enabled_var.get():
        try:
            start = float(start_beat_entry.get())
            end = float(end_beat_entry.get())
            minutes = float(ramp_minutes_entry.get())
        except (ValueError, TypeError):
            raise ValueError("Ramp settings must be numeric.")
        worst = max(abs(start), abs(end))
        return {
            "mode": "ramp",
            "beat_type": bt,
            "rate_hz": worst,
            "start_hz": start,
            "end_hz": end,
            "ramp_s": max(0.0, minutes * 60.0),
        }
    try:
        left = float(left_frequency_entry.get())
        right = float(right_frequency_entry.get())
    except (ValueError, TypeError):
        raise ValueError("Frequencies must be numeric.")
    if bt == "isochronic":
        rate = abs(left)
    else:
        rate = abs(right - left)
    return {
        "mode": "manual",
        "beat_type": bt,
        "rate_hz": rate,
        "start_hz": None,
        "end_hz": None,
        "ramp_s": None,
    }


def get_visual_audio_time() -> float:
    """Audio time of the active stream (master clock: samples_generated)."""
    g = audio_engine.generator
    c = audio_engine.current_config
    if g is None or c is None:
        return 0.0
    return g.samples_generated / c.sample_rate


def compute_visual_capability():
    """(request, VisualCapability) from the UI state and current calibration."""
    req = get_visual_rate_request()
    refresh = get_visual_refresh_hz()
    harmonics = get_visual_settings()["harmonics_enabled"]
    if req["mode"] == "ramp":
        cap = visual.ramp_gate_capability(
            req["start_hz"], req["end_hz"], refresh, harmonics)
    else:
        cap = visual.visual_capability(req["rate_hz"], refresh, harmonics)
    return req, cap


def update_visual_button():
    """Visible state of the Visual mode button: exact / approximate / harmonic
    / unavailable plus reason and power feedback (honest gate)."""
    global visual_last_reason
    if visual_toggle_button is None or visual_status_label is None:
        return
    if visual_mode_active:
        try:
            visual_toggle_button.config(text="Close visual mode")
        except Exception:
            visual_toggle_button.config(text="Close visual mode")
        visual_status_label.config(
            text=visual_active_status or
            "Visual mode active - exit with any key")
        return
    try:
        req, cap = compute_visual_capability()
    except (ValueError, TypeError):
        try:
            visual_toggle_button.config(text="Visual mode")
        except Exception:
            visual_toggle_button.config(text="Visual mode")
        visual_status_label.config(text="Visual mode: enter a valid rate")
        return
    if not req["rate_hz"]:
        # Fresh 432/432 entries: no beat yet - guide instead of gate-error.
        try:
            visual_toggle_button.config(text="Visual mode")
        except Exception:
            visual_toggle_button.config(text="Visual mode")
        visual_status_label.config(
            text="Visual: enter a beat frequency to enable the strobe")
        return
    label = visual.capability_label(cap, req["rate_hz"])
    if req["mode"] == "ramp":
        label += " - gated at the worst sweep point"
    note = visual.intensity_note(get_visual_settings()["intensity"])
    if visual_last_reason:
        note = f"{visual_last_reason} - {note}"
        visual_last_reason = None
    state_txt = cap.state.replace("_", " ")
    try:
        visual_toggle_button.config(text=f"Visual mode - {state_txt}")
    except Exception:
        visual_toggle_button.config(text=f"Visual mode - {state_txt}")
    visual_status_label.config(text=f"Visual: {label} - {note}")


def toggle_visual_mode():
    """Visual mode button action: gate + consent + start-up.

    Never auto-starts: only from this explicit user action.
    """
    if visual_mode_active:
        close_visual_mode()
        return
    if not audio_engine.is_playing:
        # Spec: without playing audio it does not start and explains why
        messagebox.showinfo(
            "Visual mode",
            "Visual mode can only open while audio is playing.\n"
            "Press 'Generate Beat' first.")
        return
    settings = get_visual_settings()
    if not settings["photosensitive_consent"]:
        if not messagebox.askyesno("Photosensitivity warning",
                                   PHOTOSENSITIVE_WARNING):
            return
        save_visual_setting("photosensitive_consent", True)
    if not settings["refresh_hz"]:
        if messagebox.askyesno(
                "Screen calibration",
                "There is no saved screen calibration. Visual mode measures "
                "the real refresh rate of your screen to honestly decide "
                "which rhythms it can emit.\n\nCalibrate now? (~2s "
                "full-screen)"):
            run_screen_calibration()
    try:
        req, cap = compute_visual_capability()
    except (ValueError, TypeError) as e:
        messagebox.showerror("Visual mode", str(e))
        return
    if not cap.available:
        refresh = get_visual_refresh_hz()
        substitute = visual.best_substitute(refresh)
        harmonics_on = get_visual_settings()["harmonics_enabled"]
        harmonic = (visual.harmonic_candidate(req["rate_hz"], refresh)
                    if harmonics_on else None)
        msg = (
            f"The requested rhythm ({req['rate_hz']:.2f} Hz) cannot be "
            f"emitted on this screen.\n\nReason: {cap.reason}\n\n"
            f"Alternative: use the highest exact rate your screen supports, "
            f"{substitute.effective_hz:.2f} Hz - a DIFFERENT frequency than "
            f"the requested one.")
        if harmonic is not None:
            msg += (f"\n\nExperimental: harmonic ~{harmonic.harmonic_of_hz:.2f} Hz "
                    f"(pulses at {harmonic.effective_hz:.2f} Hz, lower power).")
            reply = messagebox.askyesnocancel(
                "Visual mode unavailable",
                msg + "\n\n[Yes] substitute - [No] harmonic - [Cancel] do not start")
            if reply is None:
                return
            cap = substitute if reply else harmonic
        else:
            if not messagebox.askyesno("Visual mode unavailable", msg):
                return
            cap = substitute
    start_visual_mode(cap, req)


def set_visual_intensity():
    """Comfy intensity (default) or bright (opt-in, with a warning)."""
    intensity = visual_intensity_var.get() if visual_intensity_var else "comoda"
    if intensity == "brillante":
        messagebox.showwarning(
            "Bright intensity",
            "You chose bright intensity: the strobe will use maximum "
            "contrast (pure black / white).\n\nThe higher contrast means a "
            "stronger expected visual response and more intense stimulation. "
            "At any discomfort, exit with any key and return to the comfy "
            "intensity.")
    save_visual_setting(
        "intensity", intensity if intensity in visual.INTENSITY_PAIRS else "comoda")
    update_visual_button()


def revoke_photosensitive_consent():
    """Clear the stored photosensitive consent so the strobe asks again."""
    if not get_visual_settings().get("photosensitive_consent"):
        messagebox.showinfo(
            "Revoke consent",
            "There is no stored photosensitive consent to revoke.")
        return
    if not messagebox.askyesno(
            "Revoke photosensitive consent",
            "This clears the stored consent and disables the visual strobe "
            "until you grant it again.\n\nRevoke the photosensitive consent?"):
        return
    save_visual_setting("photosensitive_consent", False)
    update_visual_button()
    messagebox.showinfo(
        "Revoke consent",
        "Photosensitive consent revoked. The visual strobe will ask for "
        "consent again before it can be used.")


def on_visual_harmonics_toggle():
    """Advanced flag of the experimental harmonic mode (off by default)."""
    enabled = bool(visual_harmonics_var.get()) if visual_harmonics_var else False
    save_visual_setting("harmonics_enabled", enabled)
    if enabled:
        messagebox.showinfo(
            "Experimental harmonic mode",
            "The EXPERIMENTAL harmonic mode is enabled.\n\nWhen the requested "
            "rhythm is unavailable on your screen, a pattern at an integer "
            "divisor of the refresh whose 2nd harmonic approximates the "
            "requested rhythm may be offered (e.g. 40 Hz requested on a ~60 "
            "Hz screen: pulses at ~19.93 Hz with the 2nd harmonic at ~39.87 "
            "Hz).\n\nIt delivers LESS power than the requested frequency and "
            "adds a component at the fundamental frequency.")
    update_visual_button()


def run_screen_calibration():
    """Measures the real screen refresh (~2s full-screen).

    Alternates frames while timing each presentation with perf_counter;
    persists refresh (median) and jitter (p95) in ~/.neuralbeat/config.json.
    """
    stamps = []
    cal_win = None
    try:
        cal_win = tk.Toplevel(root)
        cal_win.attributes("-fullscreen", True)
        cal_win.configure(bg="#000000")
        cal_canvas = tk.Canvas(cal_win, bg="#000000", highlightthickness=0)
        cal_canvas.pack(fill=tk.BOTH, expand=True)
        cal_rect = cal_canvas.create_rectangle(
            0, 0, cal_win.winfo_screenwidth(),
            cal_win.winfo_screenheight(),
            fill="#000000", outline="")
        cal_win.focus_force()
        try:
            cal_win.update_idletasks()
            cal_win.update()
        # hygiene: allow best-effort Tk guard; window may be closing
        except tk.TclError:
            pass
        colors = ("#FFFFFF", "#000000")
        t_end = time.perf_counter() + 2.0
        i = 0
        while time.perf_counter() < t_end:
            cal_canvas.itemconfig(cal_rect, fill=colors[i % 2])
            cal_win.update()
            stamps.append(time.perf_counter())
            i += 1
    except Exception:
        logger.error("Screen calibration failed", exc_info=True)
    finally:
        if cal_win is not None:
            try:
                cal_win.destroy()
            # hygiene: allow best-effort Tk guard; window may be closing
            except tk.TclError:
                pass
    try:
        refresh, jitter = visual.compute_refresh_stats(stamps)
        ok, confidence = visual.validate_refresh_measurement(refresh, jitter)
        v = config.get("visual") if isinstance(config.get("visual"), dict) else {}
        if ok:
            v["refresh_hz"] = refresh
            v["confidence"] = confidence
            detail = (f"Measured refresh: {refresh:.1f} Hz "
                      f"(p95 jitter {jitter:.2f} ms, confidence {confidence}).")
        else:
            # Implausible measurement (remote session, a compositor without
            # frame limits...): the nominal system refresh if available;
            # otherwise the conservative default plus a recalibration hint.
            sys_hz = probe_system_refresh_hz()
            if sys_hz:
                v["refresh_hz"] = sys_hz
                v["confidence"] = "system"
                detail = (f"Unreliable measurement ({refresh:.0f} Hz, jitter "
                          f"{jitter:.1f} ms). Using the refresh reported by "
                          f"the system: {sys_hz:.2f} Hz (not measured). Try "
                          f"'Recalibrate screen' on a real desktop.")
            else:
                v["refresh_hz"] = visual.DEFAULT_REFRESH_HZ
                v["confidence"] = "low"
                detail = (f"Unreliable measurement ({refresh:.0f} Hz, jitter "
                          f"{jitter:.1f} ms). Using the {visual.DEFAULT_REFRESH_HZ:.0f} Hz "
                          f"default and the gate stays conservative. Try "
                          f"'Recalibrate screen' on a real desktop.")
        v["jitter_ms"] = jitter
        v["calibrated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        config["visual"] = v
        save_config(config)
        messagebox.showinfo("Screen calibration", detail)
        logger.info("Screen calibration: %s", detail)
    except (ValueError, ZeroDivisionError) as e:
        messagebox.showerror("Screen calibration",
                             f"Could not measure the refresh: {e}")
    update_visual_button()


def start_visual_mode(cap, req):
    """Opens the full-screen strobe anchored to the playing audio."""
    global visual_mode_active, visual_window, visual_scheduler
    global visual_lateness_monitor, visual_active_cap, visual_active_gen
    global visual_active_req, visual_beat_clock, visual_active_status

    settings = get_visual_settings()
    off_color, on_color = visual.INTENSITY_PAIRS.get(
        settings["intensity"], visual.INTENSITY_PAIRS["comoda"])
    refresh = get_visual_refresh_hz()

    gen = audio_engine.generator
    cfg = audio_engine.current_config
    if gen is None or cfg is None:
        messagebox.showerror("Visual mode", "No active audio.")
        return

    if req["mode"] == "ramp" and req["ramp_s"]:
        beat_clock = visual.BeatClock(start_hz=max(0.1, req["start_hz"]),
                                      end_hz=max(0.1, req["end_hz"]),
                                      ramp_s=req["ramp_s"])
    else:
        beat_clock = visual.BeatClock(rate_hz=max(0.1, req["rate_hz"]))

    strobe_win = tk.Toplevel(root)
    strobe_win.attributes("-fullscreen", True)
    strobe_win.configure(bg=off_color)
    strobe_canvas = tk.Canvas(strobe_win, bg=off_color, highlightthickness=0)
    strobe_canvas.pack(fill=tk.BOTH, expand=True)
    strobe_rect = strobe_canvas.create_rectangle(
        0, 0, 4000, 4000, fill=off_color, outline="")

    def _on_strobe_resize(event):
        try:
            strobe_canvas.coords(strobe_rect, 0, 0, event.width, event.height)
        # hygiene: allow best-effort flip; widget may be destroyed at exit
        except tk.TclError:
            pass

    strobe_canvas.bind("<Configure>", _on_strobe_resize)

    def _on_flip(state):
        try:
            strobe_canvas.itemconfig(strobe_rect,
                                     fill=on_color if state else off_color)
        # hygiene: allow best-effort flip; widget may be destroyed at exit
        except tk.TclError:
            pass

    def _rebuild(rate_hz):
        # Ramps: the pattern follows the current sweep value
        if req["mode"] != "ramp":
            return None
        try:
            cap_now = visual.visual_capability(
                rate_hz, refresh, get_visual_settings()["harmonics_enabled"])
        except Exception:
            return None
        if not cap_now.available:
            return None  # the gate already validated the sweep; keep the pattern
        return (cap_now.pattern, cap_now.cycles_per_window)

    scheduler = visual.StrobeScheduler(
        cap.pattern, refresh, _on_flip,
        clock=time.perf_counter,
        get_audio_time=get_visual_audio_time,
        beat_clock=beat_clock,
        cycles_per_window=cap.cycles_per_window,
        free_running=(cap.state == "armonico"),
        reanchor_interval_s=1.0,
        rebuild_fn=_rebuild)

    # Immediate exit: any key or click closes and restores the main window
    for btn in (1, 2, 3):
        strobe_win.bind(f"<Button-{btn}>", lambda e: close_visual_mode())
    strobe_win.bind("<Key>", lambda e: close_visual_mode())
    strobe_win.protocol("WM_DELETE_WINDOW", lambda: close_visual_mode())
    try:
        strobe_win.focus_force()
    # hygiene: allow best-effort focus grab; window may be closing
    except tk.TclError:
        pass

    visual_window = strobe_win
    visual_scheduler = scheduler
    visual_lateness_monitor = visual.LatenessMonitor(1.0 / refresh)
    visual_active_cap = cap
    visual_active_gen = gen
    visual_active_req = req
    visual_beat_clock = beat_clock
    visual_mode_active = True

    base_label = visual.capability_label(
        cap, req["rate_hz"] if req["mode"] != "ramp" else None)
    if cap.requested_hz is None and req["rate_hz"]:
        base_label += " (substitute: a different frequency than requested)"
    visual_active_status = (
        f"Visual active: {base_label} - exit with any key/click - "
        f"{visual.intensity_note(settings['intensity'])} - "
        f"not a medical device or treatment")
    update_visual_button()
    # start() anchors to the audio pulse and sets started=True: without it,
    # the first poll() returns None and the mode closes instantly
    # ("the audio is not advancing").
    scheduler.start()
    visual_poll()


def visual_poll():
    """Tk loop of the visual mode: deadline flips, audio watchdog and an
    automatic abort when the achieved rate drops below the requested one."""
    global visual_after_id, visual_active_status, visual_status_last_refresh
    if not visual_mode_active:
        visual_after_id = None
        return
    # The audio stopped, finished or changed session -> immediate close
    gen = visual_active_gen
    if ((not audio_engine.is_playing) or (audio_engine.generator is not gen)
            or gen.is_finished):
        close_visual_mode("the audio stopped or finished")
        return
    sched = visual_scheduler
    if sched is None:
        close_visual_mode()
        return
    now = time.perf_counter()
    next_deadline = sched.poll()
    if next_deadline is None:
        close_visual_mode("the audio is not advancing")
        return
    # Automatic abort: median lateness above 15% of the frame period
    lateness = sched.last_flip_lateness
    if lateness is not None and visual_lateness_monitor is not None:
        visual_lateness_monitor.record(now, lateness)
        sched.last_flip_lateness = None
        if visual_lateness_monitor.should_abort():
            close_visual_mode(
                "closed: achieved rate insufficient (overloaded compositor)")
            return
    # Ramp: refresh the current rate in the label (~2 Hz)
    try:
        if (visual_active_req is not None
                and visual_active_req["mode"] == "ramp"
                and visual_beat_clock is not None
                and now - visual_status_last_refresh > 0.5):
            visual_status_last_refresh = now
            cur = visual_beat_clock.rate_at(get_visual_audio_time())
            cap_now = visual.visual_capability(cur, get_visual_refresh_hz())
            visual_active_status = (
                f"Visual active: ramp at {cur:.2f} Hz - "
                f"{visual.capability_label(cap_now, cur)} - "
                f"exit with any key/click")
            update_visual_button()
    except Exception:
        logger.debug("Visual status refresh failed", exc_info=True)
    delay_ms = 100.0
    try:
        delay_ms = max(1.0, min(100.0,
                                (next_deadline - time.perf_counter()) * 1000.0 - 1.0))
    # hygiene: allow defensive tail scheduling; next iteration reschedules anyway
    except (TypeError, ValueError):
        pass
    visual_after_id = root.after(int(delay_ms), visual_poll)


def close_visual_mode(reason=None):
    """Closes the visual mode and restores the main window (focus included)."""
    global visual_mode_active, visual_window, visual_scheduler, visual_after_id
    global visual_active_gen, visual_active_cap, visual_active_req
    global visual_beat_clock, visual_active_status, visual_last_reason
    if visual_after_id is not None:
        try:
            root.after_cancel(visual_after_id)
        # hygiene: allow best-effort cancel; loop may have already fired
        except tk.TclError:
            pass
        visual_after_id = None
    if visual_scheduler is not None:
        visual_scheduler.stop()
        visual_scheduler = None
    if visual_window is not None:
        win = visual_window
        visual_window = None
        try:
            win.destroy()
        # hygiene: allow best-effort close; window may already be destroyed
        except tk.TclError:
            pass
    was_active = visual_mode_active
    visual_mode_active = False
    visual_active_gen = None
    visual_active_cap = None
    visual_active_req = None
    visual_beat_clock = None
    visual_active_status = None
    if reason:
        visual_last_reason = f"visual mode {reason}"
        logger.info("Visual mode: %s", reason)
    if was_active:
        try:
            root.deiconify()
            root.focus_set()
        # hygiene: allow best-effort restore; root may be shutting down
        except tk.TclError:
            pass
    update_visual_button()


# =============================================================================
# UI & Interaction
# =============================================================================

def set_osc_merge_waves():
    """Saves the merge waves setting and updates the live plot's static elements."""
    if osc_merge_var is None:
        return

    is_merged = osc_merge_var.get()
    config["osc_merge_waves"] = is_merged
    save_config(config)

    # If window is open, update its appearance in real-time
    if osc_window and visualizer_ax and visualizer_canvas:
        try:
            # Update horizontal line visibility
            if visualizer_hline is not None:
                visualizer_hline.set_visible(not is_merged)

            # Update Y-ticks
            if is_merged:
                visualizer_ax.set_yticks([-1, 0, 1])
                visualizer_ax.tick_params(axis='y', colors=visualizer_ax.yaxis.label.get_color(), length=4)
            else:
                visualizer_ax.set_yticks([])
                visualizer_ax.tick_params(axis='y', length=0)
            visualizer_canvas.draw_idle()
        except Exception:
            # The oscilloscope widgets may already be destroyed by a concurrent close.
            logger.debug("Could not refresh oscilloscope merge state", exc_info=True)

def set_osc_colors(palette_name: str):
    """Sets the oscilloscope color palette and saves to config."""
    if palette_name not in OSC_COLOR_PALETTES:
        return

    config["osc_colors"] = palette_name
    save_config(config)
    if osc_palette_var is not None:
        osc_palette_var.set(palette_name)

    # If oscilloscope is open, update its colors in real-time
    if osc_window and visualizer_canvas and line_left and line_right:
        try:
            is_dark = root.style.theme_use() in ["darkly", "superhero"]
            theme_mode = "dark" if is_dark else "light"

            colors = OSC_COLOR_PALETTES[palette_name][theme_mode]
            line_left.set_color(colors[0])
            line_right.set_color(colors[1])
            visualizer_canvas.draw_idle()
        except Exception:
            # The oscilloscope widgets may be in an inconsistent state while closing.
            logger.debug("Could not apply oscilloscope colors", exc_info=True)

def toggle_oscilloscope_window():
    """Opens or closes the real-time oscilloscope window."""
    global osc_window, visualizer_canvas, visualizer_ax, visualizer_hline, line_left, line_right
    global osc_plot_buffer_l, osc_plot_buffer_r

    # If window exists, destroy it and clear references
    if osc_window and osc_window.winfo_exists():
        osc_window.destroy()
        osc_window = None
        visualizer_canvas = None
        visualizer_ax = None
        visualizer_hline = None
        line_left = None
        line_right = None
        osc_plot_buffer_l = None
        osc_plot_buffer_r = None
        return

    # Create new window
    osc_window = tb.Toplevel(root)
    osc_window.title("Real-time Oscilloscope")
    osc_window.geometry("600x300")

    def on_osc_close():
        """Callback for when the oscilloscope window is closed by the user."""
        global osc_window, visualizer_canvas, visualizer_ax, visualizer_hline, line_left, line_right
        global osc_plot_buffer_l, osc_plot_buffer_r

        win_to_destroy = osc_window

        # Nullify globals to prevent race conditions with the update loop
        osc_window = None
        visualizer_canvas = None
        visualizer_ax = None
        visualizer_hline = None
        line_left = None
        line_right = None
        osc_plot_buffer_l = None
        osc_plot_buffer_r = None

        # Since we overrode the protocol, we are responsible for destroying the window.
        if win_to_destroy:
            try:
                win_to_destroy.destroy()
            except tk.TclError:
                logger.debug("Oscilloscope window was already destroyed", exc_info=True)

    osc_window.protocol("WM_DELETE_WINDOW", on_osc_close)

    # Initialize plot buffers
    sample_rate = 44100  # Match audio engine
    buffer_size = int(OSC_BUFFER_SECONDS * sample_rate)
    osc_plot_buffer_l = np.zeros(buffer_size, dtype=np.float32)
    osc_plot_buffer_r = np.zeros(buffer_size, dtype=np.float32)

    fig = Figure(figsize=(5, 2), dpi=100)
    visualizer_ax = fig.add_subplot(111)

    # Style the plot to match the theme
    is_dark = root.style.theme_use() in ["darkly", "superhero"]
    theme_mode = "dark" if is_dark else "light"

    current_palette_name = config.get("osc_colors", "Cyan / Magenta")
    palette = OSC_COLOR_PALETTES.get(current_palette_name, OSC_COLOR_PALETTES["Cyan / Magenta"])
    colors = palette[theme_mode]
    line_color_l, line_color_r = colors

    bg_color = root.style.colors.get("bg")
    fg_color = root.style.colors.get("fg")

    fig.patch.set_facecolor(bg_color)
    visualizer_ax.set_facecolor(bg_color)
    visualizer_ax.tick_params(axis='both', colors=fg_color, length=0)
    visualizer_ax.spines['bottom'].set_color(fg_color)
    visualizer_ax.spines['top'].set_color(fg_color)
    visualizer_ax.spines['left'].set_color(fg_color)
    visualizer_ax.spines['right'].set_color(fg_color)
    visualizer_ax.xaxis.label.set_color(fg_color)
    visualizer_ax.yaxis.label.set_color(fg_color)

    # Add a horizontal line to separate channels, and store a reference to it
    visualizer_hline = visualizer_ax.axhline(0, color=fg_color, lw=0.5, ls='--')

    x_data = np.arange(buffer_size)
    line_left, = visualizer_ax.plot(x_data, osc_plot_buffer_l, lw=1, color=line_color_l)
    line_right, = visualizer_ax.plot(x_data, osc_plot_buffer_r, lw=1, color=line_color_r)

    visualizer_ax.set_ylim(-1.1, 1.1)
    visualizer_ax.set_xlim(0, buffer_size)
    visualizer_ax.set_xticks([])

    # Set initial view based on config
    is_merged = config.get("osc_merge_waves", False)
    visualizer_hline.set_visible(not is_merged)
    if is_merged:
        visualizer_ax.set_yticks([-1, 0, 1])
        visualizer_ax.tick_params(axis='y', colors=fg_color, length=4)
    else:
        visualizer_ax.set_yticks([])
        visualizer_ax.tick_params(axis='y', length=0)

    fig.tight_layout()

    visualizer_canvas = FigureCanvasTkAgg(fig, master=osc_window)
    visualizer_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

# Set by on_close so the running export thread cancels instead of outliving
# the window; cleared when a new export starts.
export_cancel_event = threading.Event()

def _run_export_thread(cfg, filename, duration, progress_win, progress_bar, progress_label, on_success, on_error, cancel_event=None):
    """Background thread function for exporting audio to a WAV file."""
    try:
        sample_rate = cfg.sample_rate
        # Clamp to 1s..60min to avoid accidental multi-GB exports; mirrors the
        # UI validation via the shared duration policy constants.
        duration = max(EXPORT_MIN_DURATION_S, min(float(duration), EXPORT_MAX_DURATION_S))
        total_frames = int(duration * sample_rate)
        block_size = 4096

        if cfg.beat_type == "isochronic":
            generator = IsochronicGenerator(cfg)
        else:
            generator = BinauralGenerator(cfg)

        frames_written = 0
        all_audio = []

        while frames_written < total_frames:
            # A set event (currently only from on_close) cancels the export:
            # no file is written and no completion callback fires.
            if cancel_event is not None and cancel_event.is_set():
                logger.info("Export cancelled; no file written.")
                return

            chunk_size = min(block_size, total_frames - frames_written)
            audio_block = generator.generate_block(chunk_size)
            all_audio.append(audio_block)
            frames_written += chunk_size

            percent = (frames_written / total_frames) * 100

            def update_ui(p=percent):
                try:
                    if progress_win.winfo_exists():
                        progress_bar['value'] = p
                        progress_label.config(text=f"Generating... {int(p)}%")
                except Exception:
                    logger.debug("Could not update export progress", exc_info=True)

            root.after(0, update_ui)

        full_audio = np.concatenate(all_audio)

        # Apply fade out to the very end (last 20ms) for clean cut
        fade_len = int(0.02 * sample_rate)
        if len(full_audio) > fade_len:
            ramp = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
            full_audio[-fade_len:] *= ramp[:, np.newaxis]

        wavfile.write(filename, sample_rate, full_audio)

        root.after(0, lambda: on_success(filename))

    except Exception as e:
        root.after(0, lambda: on_error(e))

def export_audio_file():
    """Initiates the audio export process with UI dialogs."""
    stop_audio()

    try:
        cfg = get_audio_config_from_ui()
        default_duration = cfg.ramp_duration_s if cfg.use_ramp else 300.0

        duration_str = simpledialog.askstring("Export Audio", f"Enter duration in seconds:", initialvalue=str(int(default_duration)))
        if not duration_str:
            return

        try:
            duration = float(duration_str)
            if duration <= 0:
                raise ValueError
            if duration > EXPORT_MAX_DURATION_S:
                messagebox.showerror("Input Error", f"Duration must be 1-{int(EXPORT_MAX_DURATION_S)} seconds (max 60 min) to avoid huge files.")
                return
            if duration < EXPORT_MIN_DURATION_S:
                messagebox.showerror("Input Error", "Duration must be at least 1 second.")
                return
        except ValueError:
            messagebox.showerror("Input Error", "Duration must be a positive number.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export WAV",
            defaultextension=".wav",
            filetypes=[("WAV files", "*.wav")]
        )
        if not filename:
            return

        # Progress Window
        progress_win = tb.Toplevel(root)
        progress_win.title("Exporting...")
        progress_win.geometry("300x100")

        progress_label = ttk.Label(progress_win, text="Generating audio...")
        progress_label.pack(pady=10)
        progress_bar = ttk.Progressbar(progress_win, mode='determinate')
        progress_bar.pack(fill=tk.X, padx=20, pady=10)

        def on_success(fname):
            try:
                if progress_win.winfo_exists():
                    progress_win.destroy()
                logger.info(f"Exported audio to {fname}")
                messagebox.showinfo("Export Complete", f"Saved to {fname}")
            except Exception:
                logger.debug("Could not finalize the export success dialog", exc_info=True)

        def on_error(e):
            try:
                if progress_win.winfo_exists():
                    progress_win.destroy()
                logger.error("Export failed", exc_info=True)
                messagebox.showerror("Export Error", f"Export failed: {str(e)}")
            except Exception:
                logger.debug("Could not finalize the export error dialog", exc_info=True)

        export_cancel_event.clear()
        t = threading.Thread(target=_run_export_thread, args=(cfg, filename, duration, progress_win, progress_bar, progress_label, on_success, on_error, export_cancel_event))
        t.start()

    except ValueError as e:
        messagebox.showerror("Input Error", str(e))
    except Exception as e:
        logger.error("Export initialization failed", exc_info=True)
        messagebox.showerror("Export Error", str(e))

def play_audio():
    """Starts audio playback based on current UI settings."""
    global play_mode
    global ramp_carrier_hz, ramp_start_beat_hz, ramp_end_beat_hz, ramp_duration_s
    global manual_left_hz, manual_right_hz
    global live_status_after_id

    try:
        cfg = get_audio_config_from_ui()

        if cfg.use_ramp:
            play_mode = "ramp"
            ramp_carrier_hz = cfg.carrier_hz
            ramp_start_beat_hz = cfg.start_beat_hz
            ramp_end_beat_hz = cfg.end_beat_hz
            ramp_duration_s = cfg.ramp_duration_s

            beat_now = ramp_start_beat_hz
            left_frequency_entry.delete(0, tk.END)
            right_frequency_entry.delete(0, tk.END)
            left_frequency_entry.insert(0, str(ramp_carrier_hz - beat_now / 2.0))
            right_frequency_entry.insert(0, str(ramp_carrier_hz + beat_now / 2.0))
        else:
            play_mode = "manual"
            manual_left_hz = cfg.left_frequency
            manual_right_hz = cfg.right_frequency

        audio_engine.start(cfg)

        if live_status_after_id is None:
            update_live_status()

        # The visual gate can change (ramp mode rewrites the entries)
        update_visual_button()
    except ValueError as e:
         messagebox.showerror("Input Error", str(e))
    except Exception as e:
        logger.error("Error playing audio", exc_info=True)
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")

def show_about():
    about_text = """
This project is free for personal use under the Aegean License 1.1 (AL-1.1); commercial use needs the Aegean Commercial License 1.0 (ACL-1.0). I appreciate any donations made on Patreon.

Social Media Accounts:

Twitter: twitter.com/@Aegean_E
Youtube: youtube.com/@Aegean_E
Patreon: patreon.com/Aegean_E

Ægean - 2023-2026
    """
    messagebox.showinfo("About", about_text)

def set_theme(theme_name: str):
    try:
        root.style.theme_use(theme_name)
        config["theme"] = theme_name
        save_config(config)
        if theme_menu_var is not None:
            theme_menu_var.set(theme_name)
    except Exception as e:
        messagebox.showerror("Theme Error", str(e))

def export_config_json():
    """Export the current in-memory config dict to a JSON file the user selects."""
    try:
        out_path = filedialog.asksaveasfilename(
            title="Export config.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="config.json",
        )
        if not out_path:
            return

        Path(out_path).write_text(json.dumps(dict(config), indent=2), encoding="utf-8")
        messagebox.showinfo("Export", f"Exported configuration to:\n{out_path}")
    except Exception as e:
        messagebox.showerror("Export Error", str(e))

def import_config_json():
    """Import config from a JSON file, persist it, and refresh UI (theme + presets)."""
    global config

    try:
        in_path = filedialog.askopenfilename(
            title="Import config.json",
            filetypes=[("JSON files", "*.json")],
        )
        if not in_path:
            return

        imported = json.loads(Path(in_path).read_text(encoding="utf-8"))
        if not isinstance(imported, dict):
            raise ValueError("Invalid config file: root JSON value must be an object.")

        # Normalize user_presets shape so preset UI won't crash
        up = imported.get("user_presets", {})
        if not isinstance(up, dict):
            up = {}

        def _validate_presets(presets_list):
            valid_presets = []
            if not isinstance(presets_list, list):
                return []
            for p in presets_list:
                if not isinstance(p, dict) or "label" not in p or not isinstance(p["label"], str):
                    continue
                if "carrier_hz" in p and "pulse_hz" in p:
                    try:
                        p["carrier_hz"] = float(p["carrier_hz"])
                        p["pulse_hz"] = float(p["pulse_hz"])
                        valid_presets.append(p)
                    except (ValueError, TypeError):
                        continue
                elif "left_hz" in p and "right_hz" in p:
                    try:
                        p["left_hz"] = float(p["left_hz"])
                        p["right_hz"] = float(p["right_hz"])
                        valid_presets.append(p)
                    except (ValueError, TypeError):
                        continue
            return valid_presets

        new_config = {
            "user_presets": {
                "Monaural": _validate_presets(up.get("Monaural")),
                "Binaural": _validate_presets(up.get("Binaural")),
                "Isochronic": _validate_presets(up.get("Isochronic")),
            }
        }

        if "theme" in imported:
            t = imported["theme"]
            if isinstance(t, str) and t.strip() in VALID_THEMES:
                new_config["theme"] = t.strip()
            else:
                logger.error(f"Ignoring invalid theme {t!r} in imported profile.")

        if imported.get("osc_colors") in OSC_COLOR_PALETTES:
            new_config["osc_colors"] = imported["osc_colors"]

        if isinstance(imported.get("osc_merge_waves"), bool):
            new_config["osc_merge_waves"] = imported["osc_merge_waves"]

        config = new_config
        save_config(config)

        # Apply theme if available
        theme = config.get("theme")
        if isinstance(theme, str) and theme.strip():
            try:
                root.style.theme_use(theme.strip())
            except Exception:
                logger.debug("Could not apply the imported theme", exc_info=True)

        # Rebuild preset buttons to reflect imported presets
        build_preset_buttons()

        messagebox.showinfo("Import", f"Imported configuration from:\n{in_path}")
    except Exception as e:
        logger.error("Error importing config", exc_info=True)
        messagebox.showerror("Import Error", str(e))

def apply_preset(left_hz: float = 0, right_hz: float = 0, category: str = "Binaural", carrier_hz: float = None, pulse_hz: float = None):
    if category == "Isochronic" and carrier_hz is not None and pulse_hz is not None:
        left_frequency_entry.delete(0, tk.END)
        right_frequency_entry.delete(0, tk.END)
        left_frequency_entry.insert(0, str(pulse_hz))
        right_frequency_entry.insert(0, str(carrier_hz))
        
        if beat_type_var:
            beat_type_var.set("isochronic")
        if carrier_entry:
            carrier_entry.delete(0, tk.END)
            carrier_entry.insert(0, str(carrier_hz))
    else:
        left_frequency_entry.delete(0, tk.END)
        right_frequency_entry.delete(0, tk.END)
        left_frequency_entry.insert(0, str(left_hz))
        right_frequency_entry.insert(0, str(right_hz))
        if beat_type_var:
            beat_type_var.set("binaural")

    # The visual gate state depends on the active rhythm
    update_visual_button()


def build_preset_buttons():
    allp = get_all_presets()
    
    # Clear frames
    for w in binaural_monaural_frame.winfo_children():
        w.destroy()
    for w in isochronic_beats_frame.winfo_children():
        w.destroy()

    # Combined Binaural + Monaural presets
    combined_presets = allp["Binaural"] + allp["Monaural"]
    for i, p in enumerate(combined_presets):
        btn = ttk.Button(
            binaural_monaural_frame,
            text=p["label"],
            command=lambda l=p["left_hz"], r=p["right_hz"], c="Binaural": apply_preset(l, r, c)
        )
        btn.grid(row=i, column=0, padx=10, pady=3, sticky="new")
        binaural_monaural_frame.rowconfigure(i, weight=1)

    # Isochronic presets - use carrier_hz and pulse_hz
    for i, p in enumerate(allp["Isochronic"]):
        carrier = p.get("carrier_hz", p.get("right_hz", 200.0))
        pulse = p.get("pulse_hz", p.get("left_hz", 10.0))
        btn = ttk.Button(
            isochronic_beats_frame,
            text=p["label"],
            command=lambda c=carrier, pl=pulse: apply_preset(0, 0, "Isochronic", carrier_hz=c, pulse_hz=pl)
        )
        btn.grid(row=i, column=0, padx=10, pady=3, sticky="new")
        isochronic_beats_frame.rowconfigure(i, weight=1)

def save_current_as_preset():
    try:
        name = preset_name_entry.get().strip()
        try:
            left_hz = float(left_frequency_entry.get())
            right_hz = float(right_frequency_entry.get())
        except ValueError:
            messagebox.showerror("Input Error", "Invalid frequency values.")
            return

        category = preset_category_var.get().strip()
        # Combined UI label carries both words; auto-split so Monaural user
        # presets are actually reachable (left == right -> Monaural).
        if is_combined_beat_label(category) or not category:
            category = "Monaural" if abs(right_hz - left_hz) <= 1e-9 else "Binaural"

        if _normalize_category(category) == "Isochronic":
            if not (0.1 <= left_hz <= 100.0):
                messagebox.showerror("Input Error", "Beat frequency must be between 0.1 Hz and 100 Hz for isochronic tones.")
                return
            if not (20.0 <= right_hz <= 20000.0):
                messagebox.showerror("Input Error", "Carrier frequency must be between 20 Hz and 20000 Hz.")
                return
        else:
            err = validate_audio_params(left_hz, right_hz, 50, 50)  # Volumes do not matter for a preset.
            if err and "Frequency" in err:
                messagebox.showerror("Input Error", err)
                return

        add_user_preset(category=category, label=name, left_hz=left_hz, right_hz=right_hz)

        preset_name_entry.delete(0, tk.END)
        build_preset_buttons()
        messagebox.showinfo("Preset Saved", f"Saved preset '{name}'")
    except Exception as e:
        logger.error("Error saving preset", exc_info=True)
        messagebox.showerror("Preset Error", str(e))

def delete_preset():
    try:
        category = preset_category_var.get().strip()
        label = preset_name_entry.get().strip()
        if not label:
            raise ValueError("Enter the preset name to remove (must match exactly).")

        if messagebox.askyesno("Remove Preset", f"Remove user preset '{label}' from {category}?"):
            if is_combined_beat_label(category):
                # Combined UI label: try both stores so Monaural deletions work.
                removed = remove_user_preset(category="Binaural", label=label)
                if not removed:
                    removed = remove_user_preset(category="Monaural", label=label)
            else:
                removed = remove_user_preset(category=category, label=label)
            if removed:
                build_preset_buttons()
                messagebox.showinfo("Preset Removed", f"Removed preset '{label}'")
            else:
                messagebox.showwarning("Not Found", f"No user preset named '{label}' found in {category}.")
    except Exception as e:
        messagebox.showerror("Remove Preset Error", str(e))

def update_live_status():
    """Updates the status bar with current frequencies and remaining time."""
    global live_status_after_id
    global osc_merge_var
    global osc_plot_buffer_l, osc_plot_buffer_r

    # If window is gone, do not reschedule
    try:
        if not root.winfo_exists():
            live_status_after_id = None
            return
    except Exception:
        live_status_after_id = None
        return

    if audio_engine.is_playing:
        elapsed = audio_engine.get_elapsed_time()

        if play_mode == "ramp":
            beat = _compute_ramped_beat_hz(elapsed, ramp_start_beat_hz, ramp_end_beat_hz, ramp_duration_s)
            lf = ramp_carrier_hz - (beat / 2.0)
            rf = ramp_carrier_hz + (beat / 2.0)

            remaining_s = max(0.0, ramp_duration_s - elapsed)
            rem_m = int(remaining_s // 60)
            rem_s = int(remaining_s % 60)

            current_beat_type = beat_type_var.get() if beat_type_var else "binaural"
            if current_beat_type == "isochronic":
                status_var.set(
                    f"Isochronic: {beat:.2f} Hz Beat | Carrier: {ramp_carrier_hz:.2f} Hz | Remaining: {rem_m:02d}:{rem_s:02d}"
                )
            else:
                status_var.set(
                    f"Beat: {beat:.2f} Hz | L: {lf:.2f} Hz | R: {rf:.2f} Hz | Remaining: {rem_m:02d}:{rem_s:02d}"
                )
        else:
            beat = abs(manual_right_hz - manual_left_hz)
            current_beat_type = beat_type_var.get() if beat_type_var else "binaural"
            if current_beat_type == "isochronic":
                status_var.set(f"Isochronic: {manual_left_hz:.2f} Hz Beat | Carrier: {manual_right_hz:.2f} Hz")
            else:
                status_var.set(f"Beat: {beat:.2f} Hz | L: {manual_left_hz:.2f} Hz | R: {manual_right_hz:.2f} Hz")
    else:
        status_var.set("Beat: — Hz | L: — Hz | R: — Hz")

    # Update Oscilloscope
    if visualizer_canvas:
        try:
            is_merged = config.get("osc_merge_waves", False)
            block = audio_engine.get_last_block()
            if block is not None and len(block) > 0 and osc_plot_buffer_l is not None:
                n_frames = len(block)
                buf_len = len(osc_plot_buffer_l)
                # Guard against callback blocks larger than the plot buffer.
                if n_frames >= buf_len:
                    osc_plot_buffer_l = np.asarray(block[-buf_len:, 0], dtype=np.float32)
                    osc_plot_buffer_r = np.asarray(block[-buf_len:, 1], dtype=np.float32)
                else:
                    # Roll the buffers and append new data
                    osc_plot_buffer_l = np.roll(osc_plot_buffer_l, -n_frames)
                    osc_plot_buffer_r = np.roll(osc_plot_buffer_r, -n_frames)
                    osc_plot_buffer_l[-n_frames:] = block[:, 0]
                    osc_plot_buffer_r[-n_frames:] = block[:, 1]

                # Update the plot data
                if is_merged:
                    line_left.set_ydata(osc_plot_buffer_l)
                    line_right.set_ydata(osc_plot_buffer_r)
                else:
                    line_left.set_ydata(0.5 + osc_plot_buffer_l * 0.5)
                    line_right.set_ydata(-0.5 + osc_plot_buffer_r * 0.5)
                visualizer_canvas.draw_idle()

            elif not audio_engine.is_playing:
                # Clear the buffers and the plot when stopped
                if osc_plot_buffer_l is not None and np.any(osc_plot_buffer_l):
                    osc_plot_buffer_l.fill(0)
                    osc_plot_buffer_r.fill(0)
                    if is_merged:
                        line_left.set_ydata(osc_plot_buffer_l)
                        line_right.set_ydata(osc_plot_buffer_r)
                    else:
                        line_left.set_ydata(0.5 + osc_plot_buffer_l * 0.5)
                        line_right.set_ydata(-0.5 + osc_plot_buffer_r * 0.5)
                    visualizer_canvas.draw_idle()
        except Exception:
            # The window might have been closed during this update.
            logger.debug("Live oscilloscope update skipped", exc_info=True)

    live_status_after_id = root.after(50, update_live_status)

def on_close():
    try:
        if visual_mode_active:
            close_visual_mode()
        export_cancel_event.set()
        stop_audio()
    finally:
        try:
            root.destroy()
        except Exception:
            logger.error("Error closing application", exc_info=True)

def create_frequency_control_frame(parent, title, column, waveform_options, default_freq="432", default_vol="50", default_waveform="Sine"):
    frame = ttk.LabelFrame(parent, text=title)
    frame.grid(row=0, column=column, padx=10, pady=10, sticky="nsew")

    freq_label = ttk.Label(frame, text="Frequency (Hz):")
    freq_label.grid(row=0, column=0, padx=10, pady=5, sticky="e")
    freq_entry = ttk.Entry(frame, width=10)
    freq_entry.grid(row=0, column=1, padx=10, pady=5)
    freq_entry.insert(0, default_freq)

    vol_label = ttk.Label(frame, text="Volume (%):")
    vol_label.grid(row=1, column=0, padx=10, pady=5, sticky="e")
    vol_entry = ttk.Entry(frame, width=10)
    vol_entry.grid(row=1, column=1, padx=10, pady=5)
    vol_entry.insert(0, default_vol)

    waveform_label = ttk.Label(frame, text="Waveform:")
    waveform_label.grid(row=2, column=0, padx=10, pady=5, sticky="e")
    waveform_var = tk.StringVar()
    waveform_combobox = ttk.Combobox(
        frame,
        textvariable=waveform_var,
        values=waveform_options,
        width=14
    )
    waveform_combobox.grid(row=2, column=1, padx=10, pady=5)
    waveform_combobox.set(default_waveform)

    return freq_entry, vol_entry, waveform_var, waveform_combobox, freq_label, vol_label, waveform_label, frame

def main():
    """Main application entry point. Initializes UI and starts the event loop."""
    global root
    global left_frequency_entry, left_volume_entry, left_waveform_var, left_waveform_combobox
    global right_frequency_entry, right_volume_entry, right_waveform_var, right_waveform_combobox
    global monaural_beats_frame, binaural_beats_frame, isochronic_beats_frame, binaural_monaural_frame
    global preset_name_entry, preset_category_var
    global carrier_entry, start_beat_entry, end_beat_entry, ramp_minutes_entry, noise_type_var, noise_volume_entry
    global status_var, ramp_enabled_var, osc_merge_var, beat_type_var
    global visual_toggle_button, visual_status_label, visual_intensity_var
    global visual_harmonics_var, theme_menu_var, osc_palette_var

    import sys
    if "--debug" in sys.argv:
        print("========================================")
        print("SCIENTIFIC VERIFICATION & DEBUG REPORT")
        print("========================================")
        try:
            # Generate a test signal: 432 Hz Carrier, 10 Hz Beat (Alpha)
            print("[INFO] Generating 1s test signal (432Hz Carrier, 10Hz Beat)...")
            test_cfg = AudioConfig(
                sample_rate=44100,
                left_volume=0.8,
                right_volume=0.8,
                noise_type="None",
                noise_volume=0.0,
                left_waveform="Sine",
                right_waveform="Sine",
                use_ramp=False,
                left_frequency=427.0, # 432 - 5
                right_frequency=437.0, # 432 + 5
                carrier_hz=0.0,
                start_beat_hz=0.0,
                end_beat_hz=0.0,
                ramp_duration_s=0.0
            )

            gen = BinauralGenerator(test_cfg)
            audio = gen.generate_block(44100)

            print(f"[INFO] Signal generated. Shape: {audio.shape}, Type: {audio.dtype}")
            print(f"[METRICS] Base Freq: 432 Hz")
            print(f"[METRICS] Target Beat: 10 Hz")
            print(f"[METRICS] Total Samples: {len(audio)}")

            # Run Validation
            print("[INFO] Running Signal Validation...")
            errors = verification.validate_signal(audio, 44100, 427.0, 437.0, 1.0)

            if errors:
                print("[FAIL] Signal Verification Failed:")
                for e in errors:
                    print(f"  - {e}")
            else:
                print("[PASS] Signal Verification Passed.")
                print("  - Frequency Accuracy: OK")
                print("  - Amplitude Safety: OK")
                print("  - DC Offset: OK")
                print("  - Stereo Separation: OK")

            # Run Export Validation
            print("\n[INFO] Running Export Validation...")
            exp_errors = verification.validate_export(BinauralGenerator, test_cfg, 1.0)
            if exp_errors:
                print("[FAIL] Export Verification Failed:")
                for e in exp_errors:
                    print(f"  - {e}")
            else:
                print("[PASS] Export Verification Passed.")

        except Exception as e:
            print(f"[ERROR] Debug execution failed: {e}")
            import traceback
            traceback.print_exc()

        print("========================================")
        # Continue to app or exit?
        # Usually debug report prints and exits or prints and continues.
        # If the user just wants the report, they might prefer exit.
        # But if they use --debug to debug the running app, they want it to run.
        # I'll let it run.

    root = tb.Window(themename=initial_theme)
    root.title("NeuralBeat 1.0.0")
    
    # Set window icon
    try:
        if os.path.exists("icon.ico"):
            root.iconbitmap("icon.ico")
    except Exception:
        logger.debug("Could not set the window icon", exc_info=True)
    
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Makes maximizing work: the presets column gets extra width and the
    # height is absorbed by the presets/editor rows that use sticky="nsew".
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=1)
    root.columnconfigure(2, weight=2)
    root.rowconfigure(2, weight=1)
    root.minsize(1000, 640)

    root.style.configure("Status.TLabel", font=("Segoe UI", 10))

    osc_merge_var = tk.BooleanVar(value=config.get("osc_merge_waves", False))
    status_var = tk.StringVar(value="Beat: — Hz | L: — Hz | R: — Hz")

    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)

    settings_menu = tk.Menu(menu_bar, tearoff=False)
    menu_bar.add_cascade(label="Settings", menu=settings_menu)

    user_profile_menu = tk.Menu(settings_menu, tearoff=False)
    settings_menu.add_cascade(label="User Profile", menu=user_profile_menu)
    user_profile_menu.add_command(label="Import User Profile", command=import_config_json)
    user_profile_menu.add_command(label="Export User Profile", command=export_config_json)

    theme_menu = tk.Menu(settings_menu, tearoff=False)
    settings_menu.add_cascade(label="Theme", menu=theme_menu)
    theme_menu_var = tk.StringVar(value=config.get("theme", initial_theme))
    theme_menu.add_radiobutton(
        label="Dark (Darkly)", variable=theme_menu_var, value="darkly",
        command=lambda: set_theme("darkly"))
    theme_menu.add_radiobutton(
        label="Dark (Superhero)", variable=theme_menu_var, value="superhero",
        command=lambda: set_theme("superhero"))
    theme_menu.add_radiobutton(
        label="Light (Flatly)", variable=theme_menu_var, value="flatly",
        command=lambda: set_theme("flatly"))

    settings_menu.add_separator()

    osc_menu = tk.Menu(settings_menu, tearoff=False)
    settings_menu.add_cascade(label="Oscilloscope", menu=osc_menu)
    osc_menu.add_command(label="Show/Hide Window", command=toggle_oscilloscope_window)
    osc_menu.add_separator()
    color_menu = tk.Menu(osc_menu, tearoff=False)
    osc_menu.add_cascade(label="Line Colors", menu=color_menu)
    osc_palette_var = tk.StringVar(
        value=config.get("osc_colors", next(iter(OSC_COLOR_PALETTES))))
    for name in OSC_COLOR_PALETTES:
        color_menu.add_radiobutton(
            label=name, variable=osc_palette_var, value=name,
            command=lambda n=name: set_osc_colors(n))

    osc_menu.add_separator()
    osc_menu.add_checkbutton(label="Merge Waves", variable=osc_merge_var, command=set_osc_merge_waves)

    # --- Visual strobe mode ---
    visual_settings_menu = tk.Menu(settings_menu, tearoff=False)
    settings_menu.add_cascade(label="Visual", menu=visual_settings_menu)
    visual_settings_menu.add_command(label="Recalibrate screen",
                                      command=run_screen_calibration)
    visual_settings_menu.add_separator()
    visual_intensity_var = tk.StringVar(value=get_visual_settings()["intensity"])
    visual_settings_menu.add_radiobutton(
        label="Intensity: Comfy (default)",
        variable=visual_intensity_var, value="comoda",
        command=set_visual_intensity)
    visual_settings_menu.add_radiobutton(
        label="Intensity: Bright",
        variable=visual_intensity_var, value="brillante",
        command=set_visual_intensity)
    visual_settings_menu.add_separator()
    visual_harmonics_var = tk.BooleanVar(
        value=get_visual_settings()["harmonics_enabled"])
    visual_settings_menu.add_checkbutton(
        label="Experimental harmonic mode (advanced)",
        variable=visual_harmonics_var, command=on_visual_harmonics_toggle)
    visual_settings_menu.add_separator()
    visual_settings_menu.add_command(
        label="Revoke photosensitive consent",
        command=revoke_photosensitive_consent)

    help_menu = tk.Menu(menu_bar, tearoff=False)
    menu_bar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="About", command=show_about)

    beat_type_var = tk.StringVar(value="binaural")
    left_frequency_entry, left_volume_entry, left_waveform_var, left_waveform_combobox, left_freq_label, left_vol_label, left_waveform_lbl, left_freq_frame = create_frequency_control_frame(
        root, "Left Ear Frequency", 0, list(waveforms.keys()), default_freq="432", default_vol="50", default_waveform="Sine"
    )

    right_frequency_entry, right_volume_entry, right_waveform_var, right_waveform_combobox, right_freq_label, right_vol_label, right_waveform_lbl, right_freq_frame = create_frequency_control_frame(
        root, "Right Ear Frequency", 1, list(waveforms.keys()), default_freq="432", default_vol="50", default_waveform="Sine"
    )

    def update_freq_labels(*args):
        bt = beat_type_var.get() if beat_type_var else "binaural"
        if bt == "isochronic":
            left_freq_label.config(text="Pulse Rate (Hz):")
            right_freq_label.config(text="Carrier Tone (Hz):")
            left_freq_frame.config(text="Isochronic Tone Settings")
            right_freq_frame.config(text="Isochronic Tone Settings")
            # The isochronic generator is mono; the right volume and waveform do not apply.
            right_vol_label.grid_remove()
            right_volume_entry.grid_remove()
            right_waveform_lbl.grid_remove()
            right_waveform_combobox.grid_remove()
        else:
            left_freq_label.config(text="Frequency (Hz):")
            right_freq_label.config(text="Frequency (Hz):")
            left_freq_frame.config(text="Left Ear Frequency")
            right_freq_frame.config(text="Right Ear Frequency")
            right_vol_label.grid()
            right_volume_entry.grid()
            right_waveform_lbl.grid()
            right_waveform_combobox.grid()

    beat_type_var.trace_add("write", update_freq_labels)
    update_freq_labels()

    # Presets UI (built-in presets.py + user presets from config.json)
    presets_frame = ttk.LabelFrame(root, text="Presets")
    presets_frame.grid(row=0, column=2, rowspan=3, padx=10, pady=10, sticky="nsew")
    presets_frame.columnconfigure(0, weight=1)
    presets_frame.columnconfigure(1, weight=1)
    presets_frame.rowconfigure(0, weight=1)
    presets_frame.rowconfigure(1, weight=0)

    binaural_monaural_frame = ttk.LabelFrame(presets_frame, text="Binaural Beat / Monaural Beat")
    binaural_monaural_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    isochronic_beats_frame = ttk.LabelFrame(presets_frame, text="Isochronic Tone")
    isochronic_beats_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

    create_preset_frame = ttk.LabelFrame(presets_frame, text="Create / Remove Preset (User Presets)")
    create_preset_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

    preset_name_label = ttk.Label(create_preset_frame, text="Name (Exact):")
    preset_name_label.grid(row=0, column=0, padx=10, pady=6, sticky="e")
    preset_name_entry = ttk.Entry(create_preset_frame, width=28)
    preset_name_entry.grid(row=0, column=1, padx=10, pady=6, sticky="w")

    preset_category_label = ttk.Label(create_preset_frame, text="Type:")
    preset_category_label.grid(row=1, column=0, padx=10, pady=6, sticky="e")
    preset_category_var = tk.StringVar(value="Binaural Beat / Monaural Beat")
    preset_category_combo = ttk.Combobox(
        create_preset_frame,
        textvariable=preset_category_var,
        values=["Binaural Beat / Monaural Beat", "Isochronic Tone"],
        state="readonly",
        width=25
    )
    preset_category_combo.grid(row=1, column=1, padx=10, pady=6, sticky="w")

    save_preset_button = ttk.Button(create_preset_frame, text="Save Current Frequencies as Preset", command=save_current_as_preset)
    save_preset_button.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

    delete_preset_button = ttk.Button(create_preset_frame, text="Remove Preset", command=delete_preset)
    delete_preset_button.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

    build_preset_buttons()

    # Ramp controls (under frequency frames)
    advanced_controls_frame = ttk.LabelFrame(root, text="Advanced Controls")
    advanced_controls_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    # Configure grid to center content
    advanced_controls_frame.columnconfigure(0, weight=1)
    advanced_controls_frame.columnconfigure(1, weight=0)
    advanced_controls_frame.columnconfigure(2, weight=1)

    # --- Beat Type selector ---
    beat_type_subsection = ttk.LabelFrame(advanced_controls_frame, text="Beat Type")
    beat_type_subsection.grid(row=0, column=0, columnspan=3, pady=4, sticky="w")
    beat_type_subsection.columnconfigure(0, weight=1)
    beat_type_subsection.columnconfigure(1, weight=1)

    ttk.Radiobutton(beat_type_subsection, text="Binaural Beat / Monaural Beat", variable=beat_type_var, value="binaural").grid(row=0, column=0, padx=10, pady=5)
    ttk.Radiobutton(beat_type_subsection, text="Isochronic Tone", variable=beat_type_var, value="isochronic").grid(row=0, column=1, padx=10, pady=5)

    # --- Subsections within the main ramp frame ---
    noise_subsection_frame = ttk.LabelFrame(advanced_controls_frame, text="Background Noise")
    noise_subsection_frame.grid(row=1, column=0, columnspan=3, pady=4, sticky="w")

    ramp_subsection_frame = ttk.LabelFrame(advanced_controls_frame, text="Ramp Settings")
    ramp_subsection_frame.grid(row=2, column=0, columnspan=3, pady=4, sticky="w")

    # --- Populate Background Noise subsection ---
    noise_type_label = ttk.Label(noise_subsection_frame, text="Noise Type:")
    noise_type_label.grid(row=0, column=0, padx=10, pady=4, sticky="e")

    noise_type_var = tk.StringVar(value="None")
    noise_type_combo = ttk.Combobox(
        noise_subsection_frame,
        textvariable=noise_type_var,
        values=["None", "White", "Pink", "Brown"],
        state="readonly",
        width=15
    )
    noise_type_combo.grid(row=0, column=1, padx=10, pady=4, sticky="w")

    noise_volume_label = ttk.Label(noise_subsection_frame, text="Volume (%):")
    noise_volume_label.grid(row=1, column=0, padx=10, pady=4, sticky="e")
    noise_volume_entry = ttk.Entry(noise_subsection_frame, width=10)
    noise_volume_entry.grid(row=1, column=1, padx=10, pady=4, sticky="w")
    noise_volume_entry.insert(0, "10")

    # --- Populate Ramp Settings subsection ---
    ramp_enabled_var = tk.BooleanVar(value=False)
    # Container for the switch to center it
    switch_container = ttk.Frame(ramp_subsection_frame)
    switch_container.grid(row=0, column=0, columnspan=2, pady=10)
    ramp_label = ttk.Label(switch_container, text="Enable Ramp")
    ramp_label.pack(side='left', padx=5)
    ramp_switch = tb.Checkbutton(switch_container, variable=ramp_enabled_var, bootstyle="success-round-toggle")
    ramp_switch.pack(side='left')

    carrier_label = ttk.Label(ramp_subsection_frame, text="Carrier (Hz):")
    carrier_label.grid(row=1, column=0, padx=10, pady=4, sticky="e")
    carrier_entry = ttk.Entry(ramp_subsection_frame, width=10)
    carrier_entry.grid(row=1, column=1, padx=10, pady=4, sticky="w")
    carrier_entry.insert(0, "432")

    start_beat_label = ttk.Label(ramp_subsection_frame, text="Start beat (Hz):")
    start_beat_label.grid(row=2, column=0, padx=10, pady=4, sticky="e")
    start_beat_entry = ttk.Entry(ramp_subsection_frame, width=10)
    start_beat_entry.grid(row=2, column=1, padx=10, pady=4, sticky="w")
    start_beat_entry.insert(0, "20")

    end_beat_label = ttk.Label(ramp_subsection_frame, text="End beat (Hz):")
    end_beat_label.grid(row=3, column=0, padx=10, pady=4, sticky="e")
    end_beat_entry = ttk.Entry(ramp_subsection_frame, width=10)
    end_beat_entry.grid(row=3, column=1, padx=10, pady=4, sticky="w")
    end_beat_entry.insert(0, "3")

    ramp_minutes_label = ttk.Label(ramp_subsection_frame, text="Duration (min):")
    ramp_minutes_label.grid(row=4, column=0, padx=10, pady=4, sticky="e")
    ramp_minutes_entry = ttk.Entry(ramp_subsection_frame, width=10)
    ramp_minutes_entry.grid(row=4, column=1, padx=10, pady=4, sticky="w")
    ramp_minutes_entry.insert(0, "30")

    # --- Bottom control bar ---
    bottom_frame = ttk.Frame(root)
    bottom_frame.grid(row=3, column=0, columnspan=3, pady=6, sticky="ew")
    bottom_frame.columnconfigure(0, weight=1)
    bottom_frame.columnconfigure(1, weight=1)
    bottom_frame.columnconfigure(2, weight=1)

    generate_button = ttk.Button(bottom_frame, text="Generate Beat", command=play_audio)
    generate_button.grid(row=0, column=0, sticky="e", padx=20)

    status_label = ttk.Label(bottom_frame, textvariable=status_var,
                             anchor="center", style="Status.TLabel")
    status_label.grid(row=0, column=1, sticky="ew")

    stop_button = ttk.Button(bottom_frame, text="Stop", width=14,
                             command=stop_audio)
    stop_button.grid(row=0, column=2, sticky="w", padx=20)

    # --- Visual mode (strobe): its own row in the bottom bar ---
    # No LabelFrame (its title stole the height this row needs) and a
    # wraplength on the label: long status text widened the window and pushed
    # the preset column off screen.
    visual_toggle_button = tb.Button(
        bottom_frame, text="Visual mode", command=toggle_visual_mode,
        bootstyle="secondary")
    visual_toggle_button.grid(row=1, column=0, sticky="e", padx=20, pady=(10, 4))

    visual_status_label = ttk.Label(
        bottom_frame, text="Visual: -", anchor="center", justify="center",
        wraplength=640, style="Status.TLabel")
    visual_status_label.grid(row=1, column=1, sticky="ew", pady=(10, 4))

    visual_disclaimer_label = ttk.Label(
        bottom_frame, text="Not a medical device or treatment.",
        anchor="e")
    visual_disclaimer_label.grid(row=1, column=2, sticky="e", padx=20, pady=(10, 4))

    # The gate state is recomputed when rhythm, category or ramp changes
    beat_type_var.trace_add("write", lambda *a: update_visual_button())
    ramp_enabled_var.trace_add("write", lambda *a: update_visual_button())
    for visual_entry in (left_frequency_entry, right_frequency_entry,
                         start_beat_entry, end_beat_entry,
                         ramp_minutes_entry):
        visual_entry.bind("<KeyRelease>", lambda e: update_visual_button())
    update_visual_button()

    update_live_status()

    root.mainloop()
if __name__ == "__main__":
    main()
