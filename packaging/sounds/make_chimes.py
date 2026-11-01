"""Original soft chimes for «موظف واتساب» (synthesized here, not copied from anywhere). python make_chimes.py OUTDIR"""
import sys, wave, numpy as np
SR = 44100
def bell(f, dur, amp=1.0):
    t = np.arange(int(SR * dur)) / SR
    env = (1 - np.exp(-t * 180)) * np.exp(-t * 5.5)                    # quick soft attack, glassy decay
    tone = np.sin(2 * np.pi * f * t) + 0.32 * np.sin(2 * np.pi * 2.0 * f * t) * np.exp(-t * 9) + 0.12 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 14)
    return amp * env * tone
def mix(notes, total):
    out = np.zeros(int(SR * total))
    for start, f, d, a in notes:
        x = bell(f, d, a); i = int(SR * start); out[i:i + len(x)] += x[:len(out) - i]
    for delay, g in ((0.071, .22), (0.113, .14), (0.167, .08)):          # small airy room
        k = int(SR * delay); out[k:] += g * out[:-k]
    fade = np.ones_like(out); n = int(SR * .06); fade[-n:] = np.linspace(1, 0, n); out *= fade
    return out / np.max(np.abs(out)) * 0.55
SOUNDS = {
    "msg":   mix([(0, 1318.5, .55, 1), (.09, 1975.5, .5, .7)], .75),                       # E6 → B6: light, quick
    "order": mix([(0, 1046.5, .6, .9), (.11, 1318.5, .6, .9), (.22, 1568.0, .8, 1)], 1.1),  # C6 E6 G6: bright, happy
    "alert": mix([(0, 1760.0, .6, 1), (.16, 1318.5, .8, .9)], 1.0),                        # A6 → E6: gentle "look here"
}
def write(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype("<i2").tobytes())
if __name__ == "__main__":
    import pathlib; out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "."); out.mkdir(parents=True, exist_ok=True)
    for k, x in SOUNDS.items(): write(out / f"{k}.wav", x)
