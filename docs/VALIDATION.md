# Validation performed
- 10 automated regression tests passed.
- Headless pygame launch/render completed; preview visually inspected.
- Real local LSL outlet/inlet test using synthetic EEG completed calibration
  and delivered two live blink events.
- Stopping the outlet produced a disconnected/searching state and cleared events.
- Network interface/multicast warnings occurred in the test environment, but
  local LSL transport completed successfully.
- No physical Muse, Bluetooth link, or real-user movement trial was available.
  Real-world accuracy and total latency remain unverified.

## Portrait UI correction
- Re-ran all 10 automated tests: passed.
- Rendered gameplay, welcome, calibration, settings, and game-over states.
- Used the reference repository's actual PNG sprites.
- Added signed, bounded AF7/AF8 trace buffers; blink decisions unchanged.
- Re-ran local LSL calibration/event/disconnect check after trace additions: passed.
- Physical headset accuracy and latency remain unverified.
