"""Causal blink detector. Signal warnings never stop the game."""
from collections import deque
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi


class BlinkDetector:
    def __init__(self, fs=256):
        if not 50 <= fs <= 1000:
            raise ValueError("Sample rate must be 50–1000 Hz")
        self.fs = fs
        self.sos = butter(2, [1, 15], btype="bandpass", fs=fs, output="sos")
        self.reset()

    def reset(self):
        self.zi = None
        self.n = 0
        self.stage = "settle"
        self.rest = []
        self.peaks = []
        self.threshold = 12.
        self.base_threshold = 12.
        self.sensitivity_factor = 1.
        self.count = 0
        self.trace = deque(maxlen=int(self.fs * 3))
        self.trace_channels = deque(maxlen=int(self.fs * 3))
        self.warning = ""
        self.armed = True
        self.above = self.below = 0
        self.last_event = -10.
        self.peak = 0.
        self.collect_until = 0.
        self.message = "Let the headset settle"
        self.progress = 0.

    def reset_signal(self):
        """Recover filter state after a gap without losing calibration."""
        self.zi = None
        self.above = self.below = 0
        self.armed = False
        self.collect_until = 0.
        self.last_event = self.n / self.fs

    def sensitivity(self, factor):
        self.sensitivity_factor = float(np.clip(self.sensitivity_factor * factor, .25, 2.5))
        self.threshold = max(3., self.base_threshold * self.sensitivity_factor)

    def finish_calibration(self):
        # Sparse calibration is usable, with explicit feedback rather than an error.
        estimate = np.median(self.peaks) * .32 if self.peaks else self.base_threshold
        self.base_threshold = float(np.clip(estimate, 6., 80.))
        self.threshold = max(3., self.base_threshold * self.sensitivity_factor)
        self.stage = "ready"
        self.message = "Ready. Try a natural blink, then start."
        if len(self.peaks) < 3:
            self.message = "Few blinks found. Try More sensitive or recalibrate."
        self.progress = 1.
        self.armed = False
        self.below = self.above = 0

    def process(self, samples):
        x = np.asarray(samples, dtype=float)
        if x.size == 0:
            return 0
        if x.ndim != 2 or x.shape[1] != 2:
            raise ValueError("Expected N x 2 frontal-channel samples")
        events = 0
        # Per-sample filtering makes decisions independent of input chunk size.
        for raw in x:
            self.n += 1
            t = self.n / self.fs
            if not np.isfinite(raw).all() or np.max(np.abs(raw)) > 10000:
                self.warning = "Signal disturbance; automatically recovering"
                self.reset_signal()
                continue
            if self.zi is None:
                self.zi = sosfilt_zi(self.sos)[:, :, None] * raw[None, None, :]
            filtered, self.zi = sosfilt(self.sos, raw[None, :], axis=0, zi=self.zi)
            row = filtered[0]
            # Same-polarity bilateral energy; geometric mean tolerates uneven contact.
            strength = float(np.sqrt(abs(row[0]*row[1]))) if row[0]*row[1] > 0 else 0.
            self.trace.append(strength)
            self.trace_channels.append((float(row[0]), float(row[1])))
            self.warning = "Movement may produce extra flaps" if strength > 450 else ""
            if t < 1.5:
                self.progress = t / 1.5
                continue
            if t < 6.5:
                self.stage = "rest"
                self.message = "Look ahead and relax. Natural blinking is okay."
                self.rest.append(strength)
                self.progress = (t-1.5)/5
                continue
            if self.stage in ("settle", "rest"):
                baseline = np.asarray(self.rest or [0.])
                median = float(np.median(baseline))
                mad = float(np.median(abs(baseline-median)))
                self.base_threshold = float(np.clip(median + 6*mad, 6., 60.))
                self.threshold = self.base_threshold
                self.stage = "blinks"
                self.armed = True
            if self.stage == "blinks":
                self.message = "Make 5 comfortable blinks, at your own pace."
                self.progress = min(1., (t-6.5)/10)
                if t >= 16.5:
                    self.finish_calibration()
            if self.collect_until:
                self.peak = max(self.peak, strength)
                if t >= self.collect_until:
                    self.peaks.append(self.peak)
                    self.collect_until = 0.
            if strength < self.threshold * .55:
                self.below += 1
                self.above = 0
                if self.below / self.fs >= .04 and t-self.last_event >= .22:
                    self.armed = True
            else:
                self.below = 0
                self.above = self.above+1 if strength >= self.threshold else 0
            if self.armed and self.above / self.fs >= .016 and t-self.last_event >= .22:
                self.armed = False
                self.last_event = t
                self.above = 0
                if self.stage == "blinks":
                    self.peak = strength
                    self.collect_until = t+.18
                elif self.stage == "ready":
                    self.count += 1
                    events += 1
        return events
