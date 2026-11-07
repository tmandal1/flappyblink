import unittest
import numpy as np
from blinkbird.detector import BlinkDetector
from blinkbird.stream import recent_samples
from blinkbird.model import Game, FLOOR
from blinkbird.events import FlapInput


def wave(duration, blinks=(), fs=256):
    t = np.arange(int(duration*fs))/fs
    x = 800+np.random.default_rng(14).normal(0,.8,(len(t),2))
    for when in blinks:
        p = 90*np.exp(-.5*((t-when)/.045)**2)
        x += p[:,None]*np.array([1., .8])
    return x


class CoreTests(unittest.TestCase):
    def calibrated(self):
        d = BlinkDetector()
        d.process(wave(17,[7,8,9,10,11,12,13,14,15]))
        self.assertEqual(d.stage,"ready")
        self.assertGreaterEqual(len(d.peaks),5)
        return d

    def test_rapid_blinks_and_onset_latency(self):
        d = self.calibrated()
        hits = []
        for i, row in enumerate(wave(3,[.5,1.,1.5,2.,2.5])):
            if d.process([row]):
                hits.append(i/256)
        self.assertEqual(len(hits),5,hits)
        for found, peak in zip(hits,[.5,1,1.5,2,2.5]):
            self.assertLess(abs(found-peak),.12)

    def test_chunk_independence(self):
        x = wave(20,[7,8,9,10,11,12,13,14,15,18,19])
        a,b = BlinkDetector(),BlinkDetector()
        whole = a.process(x)
        chunks = sum(b.process(c) for c in np.array_split(x,343))
        self.assertEqual(whole,chunks)
        self.assertAlmostEqual(a.threshold,b.threshold)

    def test_sparse_calibration_and_invalid_recovery(self):
        d = BlinkDetector()
        d.process(wave(17))
        self.assertEqual(d.stage,"ready")
        d.process([[np.nan,800],[np.inf,800],[20000,800]])
        self.assertEqual(d.stage,"ready")
        self.assertGreater(d.process(wave(2,[1.])),0)

    def test_sensitivity_can_go_below_calibration(self):
        d = self.calibrated()
        old = d.threshold
        d.sensitivity(.5)
        self.assertLess(d.threshold,old)

    def test_large_movement_does_not_latch_error(self):
        d = self.calibrated()
        d.process(np.tile([3000.,3000.],(100,1)))
        d.process(wave(1))
        self.assertEqual(d.stage,"ready")
        self.assertGreater(d.process(wave(2,[1.])),0)

    def test_channel_traces_are_bounded_and_signed(self):
        d = self.calibrated()
        self.assertEqual(len(d.trace_channels),768)
        self.assertTrue(np.isfinite(d.trace_channels).all())
        self.assertGreater(np.max(d.trace_channels),0)
        self.assertLess(np.min(d.trace_channels),0)

    def test_flat_signal_no_crash(self):
        d = BlinkDetector()
        self.assertEqual(d.process(np.full((5000,2),800.)),0)
        self.assertEqual(d.stage,"ready")

    def test_stale_and_duplicate_samples(self):
        data,times = recent_samples([[1,1]]*5,[9.,9.9,9.9,10.,11.],10.,9.8)
        self.assertEqual(times,[9.9,10.])
        self.assertEqual(data.shape,(2,2))

    def test_pause_collision_restart_practice(self):
        g = Game()
        g.flap("test")
        g.state = "paused"
        y = g.y
        g.flap("ignored")
        g.update(.02)
        self.assertEqual(g.y,y)
        g.state,g.y = "playing",FLOOR
        g.update(.01)
        self.assertEqual(g.state,"over")
        g.practice = True
        g.reset()
        g.state,g.y = "playing",FLOOR
        g.update(.01)
        self.assertEqual(g.state,"playing")
        self.assertLess(g.y,FLOOR)

    def test_queue_drops_stale_events(self):
        q = FlapInput()
        q.events.put(0)
        self.assertFalse(q.poll())
        q.submit_flap()
        self.assertTrue(q.poll())
        self.assertFalse(q.poll())


if __name__=="__main__":
    unittest.main()
