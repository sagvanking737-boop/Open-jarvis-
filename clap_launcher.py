#!/usr/bin/env python3
"""
JARVIS Clap Launcher
Wartet auf Handklatscher, dann startet JARVIS UI mit Sound-Effekt
"""
import os
import sys
import subprocess
import time
from pathlib import Path

# Setze Working Directory
os.chdir(Path(__file__).parent)

try:
    from agent.clap_detector import ClapDetector
    import sounddevice as sd
    import numpy as np
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Trying to install sounddevice...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "sounddevice", "numpy"])
    try:
        from agent.clap_detector import ClapDetector
        import sounddevice as sd
        import numpy as np
    except Exception as e2:
        print(f"[FATAL] Still missing: {e2}")
        sys.exit(1)


def play_startup_sound():
    """Spiele Boot-Sound ab"""
    try:
        sample_rate = 44100
        duration = 0.3  # 300ms
        
        # Futuristic beep sound (ascending tones)
        t = np.linspace(0, duration, int(sample_rate * duration))
        f1, f2 = 800, 1200  # Hz
        tone = 0.3 * (
            0.5 * np.sin(2 * np.pi * f1 * t) +
            0.5 * np.sin(2 * np.pi * f2 * t)
        )
        
        sd.play(tone, sample_rate)
        sd.wait()
        print("[LAUNCHER] 🔊 Boot sound played")
    except Exception as e:
        print(f"[LAUNCHER] Sound play failed: {e}")


def on_clap_detected():
    """Callback wenn Clap erkannt wird"""
    print("\n" + "="*60)
    print("  👏 CLAP DETECTED! JARVIS ACTIVATING...")
    print("="*60 + "\n")
    
    # Play startup sound
    play_startup_sound()
    
    # Starte JARVIS
    jarvis_script = Path(__file__).parent / "main.py"
    if jarvis_script.exists():
        print("[LAUNCHER] Starting JARVIS main.py...")
        try:
            subprocess.Popen(
                [sys.executable, str(jarvis_script)],
                cwd=str(jarvis_script.parent),
                env={**os.environ, "PYTHONPATH": ""}
            )
            print("[LAUNCHER] ✅ JARVIS launched!")
        except Exception as e:
            print(f"[LAUNCHER] ❌ Failed to launch: {e}")
    else:
        print(f"[LAUNCHER] ❌ main.py not found: {jarvis_script}")
    
    # Exit listener
    time.sleep(1)
    sys.exit(0)


def main():
    print("\n" + "="*60)
    print("  🤖 JARVIS CLAP LISTENER - READY")
    print("="*60)
    print("\n  Waiting for hand clap to activate JARVIS...")
    print("  Clap Detection Sensitivity: HIGH")
    print("  Listening on default audio input device...\n")
    
    detector = ClapDetector(sensitivity=0.75)  # 75% sensitivity
    detector.on_clap = on_clap_detected
    detector.start()
    
    try:
        print("  [Press Ctrl+C to stop listening]\n")
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n[LAUNCHER] Stopped by user")
        detector.stop()
        sys.exit(0)
    except Exception as e:
        print(f"\n[LAUNCHER] Fatal error: {e}")
        detector.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
