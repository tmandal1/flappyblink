"""Optional up-to-65-second local LSL integration test with synthetic samples."""
import math
import time
import numpy as np
from pylsl import StreamInfo, StreamOutlet, local_clock
from blinkbird.stream import MuseInput


def main():
    info = StreamInfo("Muse-BlinkBird-Test","EEG",4,256,"float32","blink-bird-test-only")
    ch = info.desc().append_child("channels")
    for label in ("TP9","AF7","AF8","TP10"):
        node = ch.append_child("channel")
        node.append_child_value("label",label)
        node.append_child_value("unit","microvolts")
    outlet = StreamOutlet(info)
    receiver = MuseInput("Muse-BlinkBird-Test")
    rng = np.random.default_rng(2)
    begin = local_clock()
    phase_start = begin
    last_stage = None
    try:
        # Follow the receiver's calibration prompts instead of assuming the
        # receiver started at the same instant as the publisher.
        while local_clock()-begin < 65:
            state = receiver.snapshot()
            if state["stage"] != last_stage:
                print(state["stage"],state["message"],flush=True)
                last_stage, phase_start = state["stage"], local_clock()
            now = local_clock()
            for j in range(8):
                when = now-(7-j)/256
                phase = (when-phase_start)%2
                blink = (180*math.exp(-.5*((phase-1)/.065)**2)
                         if state["stage"] in ("blinks","ready") else 0)
                row = 800+rng.normal(0,1.5,4)
                row[1] += blink
                row[2] += blink*.9
                outlet.push_sample(row.tolist(),when)
            if state["stage"]=="ready" and state["count"]>=2:
                break
            time.sleep(8/256)
        state = receiver.snapshot()
        assert state["stage"]=="ready",(state["stage"],state["message"])
        assert state["count"]>=2,(state["stage"],state["count"])
        print("PASS: live LSL calibration and blink events",state["count"],flush=True)
        time.sleep(1.5)
        assert receiver.snapshot()["stage"]in ("disconnected", "searching"),receiver.snapshot()["stage"]
        assert not receiver.flaps.poll()
        print("PASS: missing samples disarm detector",flush=True)
    finally:
        receiver.close()


if __name__ == "__main__":
    main()
