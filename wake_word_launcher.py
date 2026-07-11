#!/usr/bin/env python3
"""
JARVIS Wake-Word Launcher
Wartet auf "Jarvis wake up" Befehl, dann startet JARVIS UI
"""
import os
import sys
import subprocess
import time
from pathlib import Path

# Setze Working Directory
os.chdir(Path(__file__).parent)

try:
    from agent.wake_word_detector import WakeWordDetector
    import sounddevice as sd
    import numpy as np
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Versuche zu installieren...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "sounddevice", "numpy"])
    try:
        from agent.wake_word_detector import WakeWordDetector
        import sounddevice as sd
        import numpy as np
    except Exception as e2:
        print(f"[FATAL] Still missing: {e2}")
        sys.exit(1)


def play_boot_sound():
    """Spiele Boot-Sound ab wenn JARVIS aktiviert wird"""
    try:
        sample_rate = 44100
        duration = 0.5
        
        # Futuristic activation sound (aufsteigend)
        t = np.linspace(0, duration, int(sample_rate * duration))
        f1, f2, f3 = 600, 1000, 1400
        tone = 0.25 * (
            0.7 * np.sin(2 * np.pi * f1 * t) +
            0.2 * np.sin(2 * np.pi * f2 * t) +
            0.1 * np.sin(2 * np.pi * f3 * t)
        )
        
        sd.play(tone, sample_rate)
        sd.wait()
        print("[LAUNCHER] 🔊 Activation sound")
    except Exception as e:
        print(f"[LAUNCHER] Sound failed: {e}")


def on_wake_word():
    """Callback wenn Wake-Word erkannt wird"""
    print("\n" + "="*70)
    print("  🤖 'JARVIS WAKE UP' DETECTED!")
    print("  Starting MARK-XXXIX...")
    print("="*70 + "\n")
    
    # Play boot sound
    play_boot_sound()
    
    # Starte JARVIS main.py
    jarvis_script = Path(__file__).parent / "main.py"
    if jarvis_script.exists():
        print("[LAUNCHER] ✅ Launching JARVIS...")
        try:
            subprocess.Popen(
                [sys.executable, str(jarvis_script)],
                cwd=str(jarvis_script.parent),
                env={**os.environ, "PYTHONPATH": ""}
            )
            print("[LAUNCHER] ✅ JARVIS is online!")
        except Exception as e:
            print(f"[LAUNCHER] ❌ Start failed: {e}")
    else:
        print(f"[LAUNCHER] ❌ main.py not found")
    
    # Exit listener
    time.sleep(2)
    sys.exit(0)


def main():
    print("\n" + "="*70)
    print("  🤖 JARVIS WAKE-WORD LISTENER")
    print("="*70)
    print("""
  Listening for voice command: "Jarvis wake up"
  
  Just say clearly into your microphone:
    → "Jarvis wake up"
    or
    → "Wake up Jarvis"
    or just
    → "Jarvis"
  
  Sensitivity: HIGH
  Listening on default audio input device...
  [Press Ctrl+C to stop]
  
""")
    
    detector = WakeWordDetector(sample_rate=16000, sensitivity=0.85)
    detector.on_wake_word = on_wake_word
    detector.start()
    
    try:
        while True:
            time.sleep(0.5)
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
