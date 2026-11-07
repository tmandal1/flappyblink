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


def recent_samples(chunk, stamps, now, last_stamp=None):
    """Only fresh, increasing corrected LSL timestamps enter the detector."""
    keep = []
    previous = last_stamp
    for i, stamp in enumerate(stamps):
        if -.05 <= now-stamp <= .20 and (previous is None or stamp > previous):
            keep.append(i)
            previous = stamp
    return np.asarray(chunk)[keep], [stamps[i] for i in keep]


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
                    chunk, stamps = inlet.pull_chunk(timeout=.02, max_samples=64)
                    if not stamps:
                        if monotonic()-last_receive > 1.:
                            raise RuntimeError("Stream interrupted; reconnecting")
                        continue
                    data, times = recent_samples(chunk, stamps, local_clock(), last_stamp)
                    if not times:
                        self.publish(warning="Discarding delayed samples", age_ms=None)
                        if monotonic()-last_receive > 1.:
                            raise RuntimeError("No fresh data; reconnecting")
                        continue
                    if last_stamp is not None and times[0]-last_stamp > .1:
                        detector.reset_signal()
                        self.flaps.clear()
                    last_receive, last_stamp = monotonic(), times[-1]
                    count = detector.process(data[:, indices] * scale)
                    if count:
                        self.flaps.submit_flap()
                    self.publish(stage=detector.stage, message=detector.message,
                                 trace=list(detector.trace), trace_channels=list(detector.trace_channels), threshold=detector.threshold,
                                 count=detector.count, progress=detector.progress,
                                 warning=detector.warning,
                                 age_ms=max(0., (local_clock()-times[-1])*1000))
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
