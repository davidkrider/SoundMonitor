Decibel Meter Prototype (Raspberry Pi)

This is a prototype for a Raspberry Pi desktop decibel meter with a touchscreen UI:
- Real-time A-weighted dB (dBA) reading
- A barred range view with red-green-red regions
- A 31-band spectrum view (old standard graphic EQ centers)

Hardware suggestions
- Microphone: miniDSP UMIK-1 (USB, calibrated, simple setup) or Dayton Audio iMM-6 with a USB audio interface
- Screen: official Raspberry Pi 7" Touchscreen (good compatibility, rugged, easy to mount)
- Housing: SmartiPi Touch 2 case (or a 3D-printed enclosure with vents and stand)

Quick start (prototype)
1) Install dependencies:
   python3 -m pip install -r requirements.txt
2) Run the app:
   python3 -m src.main

macOS notes
- Install PortAudio for `sounddevice`:
  brew install portaudio
- If you see `cffi`/`libffi` errors:
  brew install libffi
- Allow microphone access in System Settings > Privacy & Security > Microphone.
- List available input devices:
  python3 -m src.main --list-devices

Configuration
Edit `config.json` to tune:
- `calibration_db`: offsets the reading for your microphone calibration
- `range_low_db` / `range_high_db`: defines the green band for the range view
- `sample_rate`, `block_size`, `device`

Notes
- This prototype targets Raspberry Pi OS and uses a USB microphone.
- For deployment, consider autostart via systemd or desktop autostart.

Dependencies (Linux)
- libffi-dev
- libopenblas0, libopenblas-dev
- portaudio19-dev