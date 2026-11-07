"""Background LSL acquisition; bounded buffers and automatic reconnection."""
from threading import Thread, Event, Lock
from time import monotonic
import numpy as np
from .events import FlapInput
from .detector import BlinkDetector


def channel_indices(info):
    node = info.desc().child("channels").child("channel")
    labels, units = [], []
    for _ in range(info.channel_count()):
        labels.append(node.child_value("label").strip().upper())
        units.append(node.child_value("unit").strip().lower())
        node = node.next_sibling()
    if not all(label in labels for label in ("AF7", "AF8")):
        raise ValueError("Stream must label AF7 and AF8")
    indices = [labels.index("AF7"), labels.index("AF8")]
    scales = {"microvolts":1., "microvolt":1., "uv":1., "µv":1., "μv":1.,
              "v":1e6, "volt":1e6, "volts":1e6, "mv":1e3}
    if any(units[i] not in scales for i in indices):
        raise ValueError("Frontal channel units must be uV, mV or V")
    return indices, np.array([scales[units[i]] for i in indices])


def latest_samples(chunk, stamps, limit=64):
    """Bound latency by queue position, not absolute source-clock age.

    MuseLSL timestamps may have a constant offset even with clock correction.
    Receipt of a new chunk proves transport activity; absolute age does not.
    """
    data = np.asarray(chunk)
    if len(stamps) != len(data):
        raise ValueError("LSL sample/timestamp length mismatch")
    if not stamps:
        return data, []
    return data[-limit:], list(stamps[-limit:])


def pull_latest(inlet):
    """Drain the available queue without waiting, then retain its newest tail."""
    chunk, stamps = inlet.pull_chunk(timeout=.02, max_samples=4096)
    if not stamps:
        return chunk, stamps, False
    # Bounded nonblocking drain: cannot hang on a continuously producing source.
    for _ in range(4):
        more, newer = inlet.pull_chunk(timeout=0., max_samples=4096)
        if not newer:
            break
        chunk.extend(more)
        stamps.extend(newer)
    dropped = len(stamps) > 64
    data, times = latest_samples(chunk, stamps)
    return data, times, dropped


class MuseInput:
    def __init__(self, stream_name=None):
        self.name = stream_name
        self.flaps = FlapInput()
        self.stop_event, self.calibrate = Event(), Event()
        self.lock = Lock()
        self.adjust = 1.
        self.state = dict(stage="searching", message="Start MuseLSL to connect",
                          trace=[], trace_channels=[], threshold=12., count=0, progress=0., warning="", age_ms=None)
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def publish(self, **values):
        with self.lock:
            self.state.update(values)

    def recalibrate(self):
        self.flaps.clear()
        self.calibrate.set()

    def sensitivity(self, factor):
        with self.lock:
            self.adjust *= factor

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=2)

    def run(self):
        try:
            from pylsl import StreamInlet, resolve_streams, local_clock, proc_clocksync
        except Exception as exc:
            self.publish(stage="unavailable", message=f"Muse unavailable: {exc}")
            return
        while not self.stop_event.is_set():
            inlet = None
            try:
                self.publish(stage="searching", message="Looking for Muse EEG...")
                streams = [s for s in resolve_streams(wait_time=.5) if s.type().upper()=="EEG"]
                matches = [s for s in streams if s.name()==self.name] if self.name else [
                    s for s in streams if "muse" in s.name().lower()]
                if len(matches) != 1:
                    self.publish(message="No Muse found; start MuseLSL" if not matches
                                 else "Multiple Muse streams: use --stream-name")
                    self.stop_event.wait(.5)
                    continue
                inlet = StreamInlet(matches[0], max_buflen=1, max_chunklen=16,
                                    processing_flags=proc_clocksync, recover=False)
                info = inlet.info(timeout=2)
                indices, scale = channel_indices(info)
                detector = BlinkDetector(info.nominal_srate())
                inlet.open_stream(timeout=2)
                last_receive, last_stamp = monotonic(), None
                while not self.stop_event.is_set():
                    if self.calibrate.is_set():
                        detector.reset()
                        self.flaps.clear()
                        self.calibrate.clear()
                    with self.lock:
                        factor, self.adjust = self.adjust, 1.
                    if factor != 1.:
                        detector.sensitivity(factor)
                    data, times, dropped = pull_latest(inlet)
                    if not times:
                        if monotonic()-last_receive > 2.:
                            raise RuntimeError("Stream interrupted; reconnecting")
                        continue
                    received = monotonic()
                    # Timestamp jumps only reset the filter, never calibration.
                    # Absolute timestamp age is diagnostic, not an admission gate.
                    gap = (last_stamp is not None and
                           (not np.isfinite(times[0]-last_stamp) or
                            not 0 < times[0]-last_stamp <= .25))
                    if dropped or gap or received-last_receive > .25:
                        detector.reset_signal()
                        self.flaps.clear()
                    last_receive, last_stamp = received, times[-1]
                    age = (local_clock()-times[-1])*1000
                    timing_warning = ("Source timestamp offset; using live arrival timing"
                                      if not np.isfinite(age) or age < -50 or age > 200 else "")
                    count = detector.process(data[:, indices] * scale)
                    if count:
                        self.flaps.submit_flap()
                    self.publish(stage=detector.stage, message=detector.message,
                                 trace=list(detector.trace), trace_channels=list(detector.trace_channels), threshold=detector.threshold,
                                 count=detector.count, progress=detector.progress,
                                 warning=detector.warning or timing_warning,
                                 age_ms=float(age) if np.isfinite(age) else None)
            except Exception as exc:
                self.flaps.clear()
                self.publish(stage="disconnected", message=str(exc), trace=[], trace_channels=[], age_ms=None)
                self.stop_event.wait(.5)
            finally:
                if inlet is not None:
                    try:
                        inlet.close_stream()
                    except Exception:
                        pass
