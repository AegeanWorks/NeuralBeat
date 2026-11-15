# visual.py
# Core of the strobe visual mode (NeuralBeat task: strobe-adoption).
#
# Pure module (stdlib only): screen capability, frame patterns, refresh
# calibration, an audio pulse clock and a deadline-driven flip scheduler.
# The Tk layer lives in SourceCode.py.
#
# Gate rules (fork design decision 2), with measured refresh R and
# requested rate f:
#   - f > (R/2)(1 + tol)  -> no_disponible (no presentable fundamental;
#     forcing f aliases to ~|R - f|: entirely the wrong band).
#   - there is an integer n with |R/n - f|/f <= tol -> exact (fixed pattern,
#     ~50% duty, 0 jitter). E.g. 59.8 Hz -> 29.9 (n=2), 19.93 (n=3), 9.97 (n=6).
#   - otherwise -> approximate with a periodic pattern (window <= ~1 s) and a
#     reported one-frame jitter.
#   - harmonic (opt-in): pulses at R/n with ~1/3 duty whose 2nd harmonic
#     (2R/n) approximates f; |c2|/|c1| = 0.5 for duty 1/3; labelled
#     experimental.

import math
import statistics
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# UI / safety constants
# --------------------------------------------------------------------------

# (off, on) colour pairs per intensity. "comoda" = moderate contrast
# (less power, default); "brillante" = maximum contrast (opt-in).
INTENSITY_PAIRS = {
    "comoda": ("#202020", "#C9C9C9"),
    "brillante": ("#000000", "#FFFFFF"),
}

DEFAULT_INTENSITY = "comoda"

# Default refresh when no valid calibration exists (low-confidence label;
# recalibration on the real screen is recommended).
DEFAULT_REFRESH_HZ = 60.0

# Plausibility band for a stored/calibrated refresh. Values outside it are
# rejected on read (hard-edited or imported configs) and flag a live
# measurement as untrustworthy.
REFRESH_MIN_HZ = 23.0
REFRESH_MAX_HZ = 250.0

# Classification tolerance (1%): the delivered rate is re-labelled with its
# real effective frequency when it differs from the requested one.
TOLERANCE_PCT = 1.0

# Matching tolerance for the harmonic (2R/n vs f).
HARMONIC_TOLERANCE_PCT = 2.0

# Gate states.
STATE_EXACTO = "exacto"
STATE_APROXIMADO = "aproximado"
STATE_ARMONICO = "armonico"
STATE_NO_DISPONIBLE = "no_disponible"

# "Worst" ordering for the ramp gate (lower = worse).
_STATE_RANK = {
    STATE_NO_DISPONIBLE: 0,
    STATE_ARMONICO: 1,
    STATE_APROXIMADO: 2,
    STATE_EXACTO: 3,
}


# --------------------------------------------------------------------------
# Capability and patterns
# --------------------------------------------------------------------------

@dataclass
class VisualCapability:
    """Gate result for a requested rate against a measured refresh."""
    state: str
    # Effective frequency (the fundamental actually emitted, Hz).
    effective_hz: Optional[float] = None
    # Requested frequency this capability originated from (for labels).
    requested_hz: Optional[float] = None
    # Frames per period (fixed pattern) for exacto/armonico.
    frames_per_period: Optional[int] = None
    # Frame pattern of the period/window (True = on).
    pattern: Optional[List[bool]] = None
    # Audio pulse cycles per pattern window (for the scheduler).
    cycles_per_window: int = 1
    # Expected strobe jitter (ms). 0 for exacto and armonico.
    jitter_ms: Optional[float] = None
    # Effective vs requested frequency deviation (fraction, absolute).
    freq_error: Optional[float] = None
    # Human-readable reason when unavailable.
    reason: Optional[str] = None
    # Refresh used for the computation (Hz).
    refresh_hz: Optional[float] = None
    # Harmonic only: frequency the 2nd harmonic approximates (Hz).
    harmonic_of_hz: Optional[float] = None

    @property
    def available(self) -> bool:
        return self.state in (STATE_EXACTO, STATE_APROXIMADO, STATE_ARMONICO)


def pulse_train_coefficient(k: int, duty: float) -> float:
    """Magnitude of the k-th coefficient of a rectangular pulse train of duty d.

    c_k proportional to |sin(pi * k * d)| / k (with c_1 = 1 when duty = 1/2...
    in general only the ratio between coefficients matters).
    """
    if k < 1:
        raise ValueError("k must be >= 1")
    return abs(math.sin(math.pi * k * duty)) / k


def harmonic_amplitude_ratio(duty: float = 1.0 / 3.0, k: int = 2) -> float:
    """|c_k| / |c_1| for a pulse train of the given duty (duty 1/3, k=2 -> 0.5)."""
    c1 = pulse_train_coefficient(1, duty)
    if c1 <= 0:
        return float("inf")
    return pulse_train_coefficient(k, duty) / c1


def _exact_pattern(n: int) -> List[bool]:
    """Pattern of n frames, ~50% duty, starting at the pulse onset."""
    on = max(1, (n + 1) // 2)
    return [True] * on + [False] * (n - on)


def _window_pattern(w_frames: int, cycles: int) -> List[bool]:
    """Periodic pattern of w_frames with `cycles` pulses (~50% duty).

    The 2*cycles half-cycles are spread with a Bresenham-like distribution
    (boundaries at round(k * w / (2*cycles))).
    """
    half = w_frames / (2.0 * cycles)
    pattern = [False] * w_frames
    for k in range(2 * cycles):
        start = int(round(k * half))
        end = int(round((k + 1) * half))
        if k % 2 == 0:  # on half-cycle
            for i in range(start, min(end, w_frames)):
                pattern[i] = True
    return pattern


def _harmonic_pattern(n: int) -> List[bool]:
    """Pattern of n frames, ~1/3 duty (n=3 -> 1 on, 2 off)."""
    on = max(1, int(round(n / 3.0)))
    return [True] * on + [False] * (n - on)


def harmonic_candidate(rate_hz: float, refresh_hz: float,
                       tolerance_pct: float = HARMONIC_TOLERANCE_PCT
                       ) -> Optional[VisualCapability]:
    """Finds n such that the 2nd harmonic of pulses at R/n (duty 1/3) approximates rate.

    Returns None when no candidate lies within the tolerance.
    """
    if rate_hz <= 0 or refresh_hz <= 0:
        return None
    n_guess = 2.0 * refresh_hz / rate_hz
    for n in {max(3, int(round(n_guess)) - 1), int(round(n_guess)) + 1, max(3, int(round(n_guess)))}:
        if n < 3:
            continue
        fundamental = refresh_hz / n
        second = 2.0 * fundamental
        err = abs(second - rate_hz) / rate_hz
        if err * 100.0 <= tolerance_pct:
            return VisualCapability(
                state=STATE_ARMONICO,
                effective_hz=fundamental,
                requested_hz=rate_hz,
                frames_per_period=n,
                pattern=_harmonic_pattern(n),
                cycles_per_window=1,
                jitter_ms=0.0,
                freq_error=err,
                refresh_hz=refresh_hz,
                harmonic_of_hz=second,
            )
    return None


def best_substitute(refresh_hz: float) -> VisualCapability:
    """Highest exact rate supported (R/2, 2 frames, 50% duty)."""
    cap = visual_capability(refresh_hz / 2.0, refresh_hz)
    cap.requested_hz = None  # a DIFFERENT frequency than the requested one
    return cap


def visual_capability(rate_hz: float, refresh_hz: float,
                      harmonics_enabled: bool = False,
                      tolerance_pct: float = TOLERANCE_PCT
                      ) -> VisualCapability:
    """Classifies `rate_hz` on a screen of measured `refresh_hz`.

    Pure function: state, frames per period, effective frequency and expected
    jitter (fork tasks 1.1). Never returns an exact/approximate state when the
    rate exceeds half the refresh (raw-emission rejection, fork tasks 1.3).
    """
    if refresh_hz is None or refresh_hz <= 0:
        return VisualCapability(
            state=STATE_NO_DISPONIBLE, requested_hz=rate_hz,
            reason="no valid screen calibration (recalibrate in Settings)",
            refresh_hz=refresh_hz)
    if rate_hz is None or rate_hz <= 0:
        return VisualCapability(
            state=STATE_NO_DISPONIBLE, requested_hz=rate_hz,
            reason="invalid rate (must be > 0 Hz)", refresh_hz=refresh_hz)

    limit_hz = refresh_hz / 2.0 * (1.0 + tolerance_pct / 100.0)

    # Hard gate: above R/2 no presentable fundamental exists.
    if rate_hz > limit_hz:
        if harmonics_enabled:
            harm = harmonic_candidate(rate_hz, refresh_hz)
            if harm is not None:
                return harm
        return VisualCapability(
            state=STATE_NO_DISPONIBLE, requested_hz=rate_hz,
            reason=(f"{rate_hz:.2f} Hz exceeds half the measured refresh "
                    f"(maximum {refresh_hz / 2.0:.1f} Hz on a {refresh_hz:.1f} Hz screen)"),
            refresh_hz=refresh_hz)

    # Exact: whole number of frames per period, within tolerance.
    n0 = refresh_hz / rate_hz
    candidates = {max(2, int(round(n0)) - 1), int(round(n0)), max(2, int(round(n0)) + 1)}
    best_n, best_err = None, None
    for n in sorted(candidates):
        if n < 2:
            continue
        err = abs(refresh_hz / n - rate_hz) / rate_hz
        if best_err is None or err < best_err:
            best_n, best_err = n, err
    if best_err is not None and best_err * 100.0 <= tolerance_pct:
        eff = refresh_hz / best_n
        return VisualCapability(
            state=STATE_EXACTO,
            effective_hz=eff,
            requested_hz=rate_hz,
            frames_per_period=best_n,
            pattern=_exact_pattern(best_n),
            cycles_per_window=1,
            jitter_ms=0.0,
            freq_error=best_err,
            refresh_hz=refresh_hz)

    # Approximate: periodic window (<= ~1 s) with m cycles, minimum error.
    max_cycles = max(1, int(rate_hz))
    best = None  # (err, m, w)
    for m in range(1, max_cycles + 1):
        w = int(round(m * refresh_hz / rate_hz))
        w = max(w, 2 * m)
        if m > 1 and w > int(refresh_hz):  # window <= ~1 s (m=1 is always allowed)
            continue
        err = abs(m * refresh_hz / w - rate_hz) / rate_hz
        if best is None or err < best[0] - 1e-12:
            best = (err, m, w)
    if best is None or best[0] * 100.0 > 5.0:
        return VisualCapability(
            state=STATE_NO_DISPONIBLE, requested_hz=rate_hz,
            reason=("no periodic frame pattern of <= 1 s approximates "
                    f"{rate_hz:.2f} Hz on a {refresh_hz:.1f} Hz screen"),
            refresh_hz=refresh_hz)

    err, m, w = best
    eff = m * refresh_hz / w
    return VisualCapability(
        state=STATE_APROXIMADO,
        effective_hz=eff,
        requested_hz=rate_hz,
        frames_per_period=None,
        pattern=_window_pattern(w, m),
        cycles_per_window=m,
        jitter_ms=1000.0 / refresh_hz,
        freq_error=err,
        refresh_hz=refresh_hz)


def ramp_gate_capability(start_hz: float, end_hz: float, refresh_hz: float,
                         harmonics_enabled: bool = False,
                         n_points: int = 65,
                         tolerance_pct: float = TOLERANCE_PCT
                         ) -> VisualCapability:
    """Ramp gate: evaluated at the WORST point of the sweep (fork tasks 1.3).

    Samples the linear sweep [start_hz, end_hz] and returns the capability of
    the point with the worst state
    (no_disponible < armonico < aproximado < exacto).
    """
    if n_points < 2:
        n_points = 2
    worst = None
    for i in range(n_points):
        f = start_hz + (end_hz - start_hz) * i / (n_points - 1)
        cap = visual_capability(f, refresh_hz, harmonics_enabled, tolerance_pct)
        if worst is None or _STATE_RANK[cap.state] < _STATE_RANK[worst.state]:
            worst = cap
    return worst


# --------------------------------------------------------------------------
# Labels (power feedback, fork tasks 4.4)
# --------------------------------------------------------------------------

def capability_label(cap: VisualCapability, requested_hz: Optional[float] = None) -> str:
    """Status label for the button/UI (with power feedback)."""
    if cap is None:
        return "Visual mode: no data"
    req = requested_hz if requested_hz is not None else cap.requested_hz

    if cap.state == STATE_EXACTO:
        txt = "exact"
        if cap.effective_hz is not None and req is not None:
            if abs(cap.effective_hz - req) / req > 0.001:
                txt += f" @ {cap.effective_hz:.2f} Hz"
        return txt.capitalize() if txt else "Exact"

    if cap.state == STATE_APROXIMADO:
        jitter = cap.jitter_ms or 0.0
        eff = f" @ {cap.effective_hz:.2f} Hz" if cap.effective_hz else ""
        return f"Approximate{eff} · jitter ±{jitter:.0f} ms"

    if cap.state == STATE_ARMONICO:
        harm = cap.harmonic_of_hz or (2.0 * (cap.effective_hz or 0.0))
        fund = cap.effective_hz or 0.0
        return (f"≈{harm:.2f} Hz via harmonic · experimental "
                f"(fundamental {fund:.2f} Hz, lower power)")

    # no_disponible
    reason = cap.reason or "rate not supported by this screen"
    return f"Unavailable: {reason}"


def intensity_note(intensity: str) -> str:
    """Power note for the chosen intensity (specs: feedback)."""
    if intensity == "brillante":
        return "bright intensity: maximum contrast (stronger visual response)"
    return "comfy intensity: weaker visual response than bright"


# --------------------------------------------------------------------------
# Refresh calibration (fork tasks 2.1)
# --------------------------------------------------------------------------

def compute_refresh_stats(timestamps: Sequence[float]) -> Tuple[float, float]:
    """Refresh statistics from presentation timestamps.

    Returns (refresh_hz, jitter_ms): median of 1/delta and p95 of the absolute
    deviation of the deltas (in ms). The first delta and outliers are dropped.
    """
    if len(timestamps) < 8:
        raise ValueError("at least 8 timestamps needed for statistics")
    deltas = [b - a for a, b in zip(timestamps, timestamps[1:])]
    deltas = [d for d in deltas if d > 0]
    if len(deltas) < 6:
        raise ValueError("non-positive deltas: invalid measurement")
    med = statistics.median(deltas)
    refresh_hz = 1.0 / med
    devs = [abs(d - med) for d in deltas]
    jitter_ms = _percentile(devs, 95) * 1000.0
    return refresh_hz, jitter_ms


def _percentile(sortedable: Sequence[float], pct: float) -> float:
    """Percentile by linear interpolation (equivalent to numpy p95)."""
    data = sorted(sortedable)
    if not data:
        return 0.0
    if len(data) == 1:
        return data[0]
    k = (len(data) - 1) * (pct / 100.0)
    f = int(math.floor(k))
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[f]
    return data[f] + (data[c] - data[f]) * (k - f)


def validate_refresh_measurement(refresh_hz: float, jitter_ms: float
                                 ) -> Tuple[bool, str]:
    """Validates measurement plausibility. Returns (ok, confidence)."""
    if not (REFRESH_MIN_HZ <= refresh_hz <= REFRESH_MAX_HZ):
        return False, "low"
    if jitter_ms > 6.0:
        return False, "low"
    if jitter_ms > 3.0:
        return True, "medium"
    return True, "high"


def parse_xrandr_refresh_hz(text: str) -> Optional[float]:
    """Refresh of the output marked as current (`*`) in `xrandr --current`.

    The nominal value reported by the server, not a measurement.
    """
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2 or "x" not in parts[0] or "*" not in parts[1]:
            continue
        try:
            return float(parts[1].rstrip("*+"))
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# Persistent configuration (fork tasks 2.2)
# --------------------------------------------------------------------------

def merge_visual_config(cfg: dict) -> dict:
    """Merges the "visual" section of config with default values.

    Backwards compatibility: a config without the "visual" key (or with
    partial keys) does not break; missing values take the defaults.
    """
    raw = cfg.get("visual") if isinstance(cfg, dict) else None
    if not isinstance(raw, dict):
        raw = {}

    def _num(key):
        try:
            v = raw.get(key)
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    refresh = _num("refresh_hz")
    jitter = _num("jitter_ms")
    # Read-side plausibility: a hand-edited or imported config must not feed
    # an absurd refresh into BeatClock/LatenessMonitor.
    if refresh is not None and not (REFRESH_MIN_HZ <= refresh <= REFRESH_MAX_HZ):
        refresh = None
    consent = raw.get("photosensitive_consent")
    intensity = raw.get("intensity")
    harmonics = raw.get("harmonics_enabled")

    return {
        "refresh_hz": refresh if (refresh and refresh > 0) else None,
        "jitter_ms": jitter if (jitter is not None and jitter >= 0) else None,
        "calibrated_at": raw.get("calibrated_at") if isinstance(raw.get("calibrated_at"), str) else None,
        "confidence": raw.get("confidence") if isinstance(raw.get("confidence"), str) else None,
        "photosensitive_consent": bool(consent),
        "intensity": intensity if intensity in INTENSITY_PAIRS else DEFAULT_INTENSITY,
        "harmonics_enabled": bool(harmonics),
    }


# --------------------------------------------------------------------------
# Audio pulse clock (audio rhythm phase in audio time)
# --------------------------------------------------------------------------

class BeatClock:
    """Accumulated cycles of the audio pulse as a function of audio time.

    Constant: cycles(t) = f * t.
    Linear ramp (like SourceCode.py _compute_ramped_beat_hz):
        f(t) = f0 + (f1 - f0) * clip(t / T, 0, 1)
        cycles(t) = f0*t + (f1-f0)*t^2/(2T)  for t <= T; linear afterwards.
    """

    def __init__(self, rate_hz: Optional[float] = None,
                 start_hz: Optional[float] = None,
                 end_hz: Optional[float] = None,
                 ramp_s: Optional[float] = None):
        if start_hz is None or end_hz is None or not ramp_s:
            self.constant = True
            self.f0 = float(rate_hz or 0.0)
            self.f1 = self.f0
            self.T = 0.0
        else:
            self.constant = False
            self.f0 = float(start_hz)
            self.f1 = float(end_hz)
            self.T = float(ramp_s)
        if self.f0 <= 0 or self.f1 <= 0:
            raise ValueError("pulse frequency must be > 0")

    def rate_at(self, t: float) -> float:
        if self.constant or t >= self.T:
            return self.f1
        if t <= 0:
            return self.f0
        return self.f0 + (self.f1 - self.f0) * (t / self.T)

    def cycles(self, t: float) -> float:
        if self.constant:
            return self.f0 * t
        if t <= 0:
            return 0.0
        if t >= self.T:
            c_T = self.f0 * self.T + (self.f1 - self.f0) * self.T / 2.0
            return c_T + self.f1 * (t - self.T)
        return self.f0 * t + (self.f1 - self.f0) * t * t / (2.0 * self.T)

    def next_boundary(self, t: float) -> float:
        """Audio time of the next pulse boundary after t."""
        c = self.cycles(t)
        k = math.floor(c) + 1.0
        lo, hi = t, t + (k - c) / min(self.f0, self.f1) + 1.0
        for _ in range(60):  # monotone bisection (robust for ramps)
            mid = (lo + hi) / 2.0
            if self.cycles(mid) < k:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0


# --------------------------------------------------------------------------
# Deadline-driven flip scheduler (fork design decision 4, tasks 3.2)
# --------------------------------------------------------------------------

class StrobeScheduler:
    """Strobe scheduler anchored to the audio clock (samples_generated).

    - Pattern position: the AUDIO pulse phase (BeatClock), not the system
      clock: the first visual pulse is aligned to an audio pulse boundary and
      the phase stays locked to the audio.
    - Between re-anchors (~1 s) audio time is extrapolated with the system
      clock; each re-anchor snaps to the real samples_generated value
      (absorbs crystal drift).
    - Deadline-driven flips: poll(now) emits the state corresponding to
      `now`; late flips are SKIPPED (a direct jump to the correct state,
      never accumulated lag).
    - Free-running mode (harmonic): the pattern advances at the frame rate R
      anchored to the pulse boundary (exact R/n fundamental, 0 jitter).
    """

    def __init__(self, pattern: Sequence[bool], refresh_hz: float,
                 on_flip: Callable[[bool], None],
                 clock: Callable[[], float],
                 get_audio_time: Callable[[], float],
                 beat_clock: BeatClock,
                 cycles_per_window: int = 1,
                 free_running: bool = False,
                 reanchor_interval_s: float = 1.0,
                 rebuild_fn: Optional[Callable[[float], Optional[Tuple[List[bool], int]]]] = None):
        self.pattern = [bool(p) for p in pattern]
        if not self.pattern:
            raise ValueError("pattern must not be empty")
        self.W = len(self.pattern)
        self.refresh_hz = float(refresh_hz)
        self.on_flip = on_flip
        self.clock = clock
        self.get_audio_time = get_audio_time
        self.beat_clock = beat_clock
        self.cpw = max(1, int(cycles_per_window))
        self.free_running = bool(free_running)
        self.reanchor_interval_s = float(reanchor_interval_s)
        self.rebuild_fn = rebuild_fn

        self.started = False
        self.stalled = False
        self.state: Optional[bool] = None
        self.sys_ref = 0.0
        self.audio_ref = 0.0
        self.align_audio = 0.0
        self.phase0 = 0.0
        self.last_flip_lateness: Optional[float] = None
        self._prev_deadline: Optional[float] = None

    # -- life cycle ---------------------------------------------------------

    def start(self) -> float:
        """Starts aligned to the next audio pulse boundary.

        Returns the deadline (clock time) of the first scheduled flip.
        """
        audio0 = self.get_audio_time()
        self.align_audio = self.beat_clock.next_boundary(audio0)
        # The bisection converges with an epsilon above the whole cycle:
        # round so we do not land on the wrong side of the boundary.
        self.phase0 = float(round(self.beat_clock.cycles(self.align_audio)))
        self._snap(self.clock(), audio0)
        self.started = True
        self.stalled = False
        self.state = None
        return self.poll()

    def stop(self) -> None:
        self.started = False

    def _snap(self, sys_now: float, audio_now: float) -> None:
        self.sys_ref = sys_now
        self.audio_ref = audio_now

    def _audio_est(self, sys_now: float) -> float:
        return self.audio_ref + (sys_now - self.sys_ref)

    # -- pattern position ----------------------------------------------------

    def _pos_frames(self, audio_t: float) -> float:
        """Position (float, in frames) inside the pattern window."""
        if self.free_running:
            return (audio_t - self.align_audio) * self.refresh_hz
        phase = self.beat_clock.cycles(audio_t) - self.phase0
        return (phase % self.cpw) / self.cpw * self.W

    def _state_at(self, audio_t: float) -> bool:
        frame = math.floor(self._pos_frames(audio_t))
        return self.pattern[frame % self.W]

    def _next_crossing(self, sys_now: float) -> float:
        """Deadline (clock time) of the next pattern state change."""
        audio_t = self._audio_est(sys_now)
        p = self._pos_frames(audio_t)
        target = math.floor(p) + 1.0
        if target >= self.W:  # wraps to the start of the window
            target = float(self.W)
        delta_frames = target - p
        if self.free_running:
            delta_audio = delta_frames / self.refresh_hz
        else:
            rate = max(self.beat_clock.rate_at(audio_t), 1e-6)
            delta_cycles = delta_frames * self.cpw / self.W
            delta_audio = delta_cycles / rate
        return sys_now + delta_audio

    # -- main loop ------------------------------------------------------------

    def poll(self, now: Optional[float] = None) -> Optional[float]:
        """Processes due flips at `now`; returns the next deadline.

        If late, jumps straight to the state corresponding to `now`
        (missed intermediate flips are not emitted: no accumulated lag).
        """
        if not self.started:
            return None
        now = self.clock() if now is None else now

        # Periodic re-anchor to the real audio counter.
        if now - self.sys_ref >= self.reanchor_interval_s:
            audio_now = self.get_audio_time()
            if audio_now <= self.audio_ref:
                self.stalled = True  # audio not advancing (stopped/finished)
            self._snap(now, audio_now)
            if self.rebuild_fn is not None and not self.stalled:
                rebuilt = self.rebuild_fn(self.beat_clock.rate_at(audio_now))
                if rebuilt is not None:
                    new_pattern, new_cpw = rebuilt
                    if new_pattern != self.pattern or new_cpw != self.cpw:
                        self.pattern = [bool(p) for p in new_pattern]
                        self.W = len(self.pattern)
                        self.cpw = max(1, int(new_cpw))

        if self.stalled:
            return None

        audio_t = self._audio_est(now)
        target = self._state_at(audio_t)
        if target != self.state:
            self.state = target
            if self._prev_deadline is not None and now > self._prev_deadline:
                self.last_flip_lateness = now - self._prev_deadline
            self.on_flip(target)

        deadline = self._next_crossing(now)
        self._prev_deadline = deadline
        return deadline


class LatenessMonitor:
    """Aborts when median lateness exceeds a threshold (fork design decision 7).

    Keeps (now, lateness_s) samples from the last `window_s` and exposes
    should_abort() when the median lateness > ratio * frame_period_s.
    """

    def __init__(self, frame_period_s: float, ratio: float = 0.15,
                 window_s: float = 2.0, min_samples: int = 8):
        self.frame_period_s = float(frame_period_s)
        self.ratio = float(ratio)
        self.window_s = float(window_s)
        self.min_samples = int(min_samples)
        self._samples: List[Tuple[float, float]] = []

    def record(self, now: float, lateness_s: float) -> None:
        self._samples.append((now, max(0.0, lateness_s)))
        cutoff = now - self.window_s
        self._samples = [s for s in self._samples if s[0] >= cutoff]

    def should_abort(self) -> bool:
        if len(self._samples) < self.min_samples:
            return False
        med = statistics.median([lat for _, lat in self._samples])
        return med > self.ratio * self.frame_period_s
