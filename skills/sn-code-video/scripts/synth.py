"""A small procedural sound kit (numpy only). Import it, or copy the parts you need.

    from synth import *
    mix = Mix(dur=15.0)                       # stereo 48 kHz buffer
    mix.add(chime(880), at=12.0, gain=0.5)    # place a sound at 12.0 s
    mix.add(kick(), at=0.5, pan=-0.2)
    mix.write("build/sfx.wav")               # 16-bit stereo WAV

Everything is deterministic: random sounds take a seed.
"""
import wave
import numpy as np

SR = 48000

def t_axis(dur):
    return np.arange(int(dur * SR)) / SR

def adsr(n, a=0.005, d=0.05, s=0.6, r=0.1):
    """Attack/decay/sustain/release envelope over n samples (times in seconds)."""
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    sus = max(n - a - d - r, 0)
    env = np.concatenate([np.linspace(0, 1, a, endpoint=False), np.linspace(1, s, d, endpoint=False),
                          np.full(sus, s), np.linspace(s, 0, r)])
    return np.pad(env, (0, max(n - len(env), 0)))[:n]

def expdecay(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))

def osc(freq, dur, shape="sine", phase=0.0):
    """freq may be a number or an array (same length) for glides."""
    t = t_axis(dur)
    f = np.broadcast_to(np.asarray(freq, float), t.shape)
    ph = 2 * np.pi * np.cumsum(f) / SR + phase
    if shape == "sine": return np.sin(ph)
    if shape == "square": return np.sign(np.sin(ph))
    if shape == "triangle": return 2 / np.pi * np.arcsin(np.sin(ph))
    if shape == "saw": return 2 * ((ph / (2 * np.pi)) % 1) - 1
    raise ValueError(shape)

def noise(dur, seed=0, color="white"):
    x = np.random.default_rng(seed).standard_normal(int(dur * SR))
    if color == "pink":   # simple 1/f approximation by filtering white noise
        X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); f[0] = f[1]
        x = np.fft.irfft(X / np.sqrt(f), len(x))
    return x / (np.max(np.abs(x)) + 1e-9)

def lowpass(x, cutoff):
    """One-pole low-pass; cutoff may be an array (moving filter)."""
    if np.ndim(cutoff) == 0:   # fixed cutoff: vectorized when scipy is available
        a = 1 - np.exp(-2 * np.pi * float(cutoff) / SR)
        try:
            from scipy.signal import lfilter
            return lfilter([a], [1, a - 1], x)
        except ImportError:
            pass
    c = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    a = 1 - np.exp(-2 * np.pi * c / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc); y[i] = acc
    return y

def highpass(x, cutoff):
    return x - lowpass(x, cutoff)

def bandpass(x, lo, hi):
    return highpass(lowpass(x, hi), lo)

def norm(x, peak=0.9):
    m = np.max(np.abs(x)) + 1e-9
    return x * (peak / m)

def layer(*xs):
    """Sum mono signals of different lengths (shorter ones are zero-padded)."""
    n = max(len(x) for x in xs); out = np.zeros(n)
    for x in xs: out[: len(x)] += x
    return out

def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)

# ---------------------------------------------------------------- instruments
def pluck(freq, dur=1.5, damp=0.996, bright=0.5, seed=0):
    """Karplus-Strong plucked string (guqin, lute, harp, ukulele, bass)."""
    n = int(dur * SR); p = max(int(SR / freq), 2)
    buf = np.random.default_rng(seed).uniform(-1, 1, p)
    buf = lowpass(buf, 2000 + 8000 * bright)
    out = np.empty(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = damp * 0.5 * (buf[i % p] + buf[(i + 1) % p])
    return norm(out) * expdecay(n, dur / 3)

def tone(freq, dur, shape="sine", a=0.01, d=0.1, s=0.7, r=0.2, cutoff=None):
    x = osc(freq, dur, shape) * adsr(int(dur * SR), a, d, s, r)
    return lowpass(x, cutoff) if cutoff else x

def pad(freqs, dur, detune=0.006, cutoff=2500):
    """Soft pad from detuned saws."""
    x = sum(osc(f * (1 + k * detune), dur, "saw") for f in freqs for k in (-1, 0, 1))
    return norm(lowpass(x, cutoff)) * adsr(int(dur * SR), 0.4, 0.3, 0.8, 0.8)

def kick(dur=0.35):
    t = t_axis(dur); f = 50 + 70 * np.exp(-t * 30)
    return osc(f, dur) * expdecay(len(t), 0.12)

def snare(dur=0.2, seed=1):
    n = int(dur * SR)
    return 0.6 * bandpass(noise(dur, seed), 1500, 8000) * expdecay(n, 0.05) + 0.4 * osc(190, dur) * expdecay(n, 0.04)

def hat(dur=0.06, seed=2):
    return highpass(noise(dur, seed), 7000) * expdecay(int(dur * SR), 0.015)

# ---------------------------------------------------------------- effects
def click(freq=2500, dur=0.012, seed=3):
    return bandpass(noise(dur, seed), freq * 0.6, freq * 1.6) * expdecay(int(dur * SR), 0.003)

def tap(freq=900, dur=0.08):
    return layer(osc(freq, dur) * expdecay(int(dur * SR), 0.012), 0.3 * click(freq * 2, 0.01))

def thud(dur=0.4, seed=4):
    t = t_axis(dur)
    return 0.8 * osc(50 + 70 * np.exp(-t * 25), dur) * expdecay(len(t), 0.1) + 0.3 * lowpass(noise(dur, seed), 400) * expdecay(len(t), 0.03)

def pop(f0=300, f1=900, dur=0.07):
    t = t_axis(dur)
    return osc(f0 + (f1 - f0) * t / dur, dur) * expdecay(len(t), 0.02)

def chime(freq=880, dur=2.0):
    n = int(dur * SR)
    parts = [(1, 1.0, 0.9), (2.76, 0.5, 0.5), (5.4, 0.25, 0.3), (8.9, 0.12, 0.2)]
    return norm(sum(g * osc(freq * r, dur) * expdecay(n, dur * k) for r, g, k in parts))

def whoosh(dur=0.6, f_lo=300, f_hi=3000, seed=5, level=None):
    """Noise sweep; pass `level` (array, len = dur*SR) to follow a speed curve."""
    n = int(dur * SR); t = np.linspace(0, 1, n)
    centre = f_lo + (f_hi - f_lo) * np.sin(np.pi * t)
    env = np.sin(np.pi * t) ** 2 if level is None else level
    return norm(bandpass(noise(dur, seed), centre * 0.5, centre * 1.5)) * env

def rain(dur, density=40, seed=6):
    bed = 0.3 * bandpass(noise(dur, seed, "pink"), 400, 6000)
    rng = np.random.default_rng(seed + 1); out = bed.copy()
    for _ in range(int(dur * density)):
        at = int(rng.uniform(0, dur - 0.02) * SR); d = click(rng.uniform(2000, 6000), 0.01, int(rng.integers(1e6)))
        out[at:at + len(d)] += rng.uniform(0.05, 0.2) * d
    return out

def wind(dur, seed=7):
    t = t_axis(dur)
    cutoff = 300 + 250 * np.sin(2 * np.pi * 0.13 * t) + 150 * np.sin(2 * np.pi * 0.31 * t + 1)
    return norm(lowpass(noise(dur, seed, "pink"), cutoff)) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t))

def chip(freq, dur, duty_square=True):
    """8-bit voice: square (or triangle) with a stepped decay."""
    n = int(dur * SR); steps = np.repeat(np.linspace(1, 0, 8), int(np.ceil(n / 8)))[:n]
    return osc(freq, dur, "square" if duty_square else "triangle") * steps * 0.5

# ---------------------------------------------------------------- mixing
class Mix:
    """Stereo buffer; place mono or stereo sounds at times (seconds) with gain and pan (-1..1)."""
    def __init__(self, dur):
        self.buf = np.zeros((int(round(dur * SR)), 2))

    def add(self, x, at=0.0, gain=1.0, pan=0.0):
        x = np.asarray(x, float)
        if x.ndim == 1:
            l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
            x = np.stack([x * l, x * r], 1) * np.sqrt(2)
        i = int(round(at * SR)); j = min(i + len(x), len(self.buf))
        if i < len(self.buf): self.buf[i:j] += gain * x[: j - i]
        return self

    def duck(self, voice_env, depth_db=12.0):
        """Lower this buffer where voice_env (0..1 per sample) is high."""
        g = 10 ** (-depth_db * np.clip(voice_env, 0, 1) / 20)
        self.buf *= g[: len(self.buf), None]
        return self

    def fade(self, fin=0.05, fout=0.5):
        n = len(self.buf); a, b = int(fin * SR), int(fout * SR)
        self.buf[:a] *= np.linspace(0, 1, a)[:, None]; self.buf[n - b:] *= np.linspace(1, 0, b)[:, None]
        return self

    def write(self, path, peak=0.89):
        y = norm(self.buf, peak) if np.max(np.abs(self.buf)) > peak else self.buf
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
        return path

def envelope_follow(x, attack=0.05, release=0.3):
    """Smoothed 0..1 envelope of a mono signal (e.g. a voice track for ducking)."""
    a, r = np.exp(-1 / (attack * SR)), np.exp(-1 / (release * SR))
    e = np.empty(len(x)); acc = 0.0
    for i, v in enumerate(np.abs(x)):
        acc = a * acc + (1 - a) * v if v > acc else r * acc + (1 - r) * v
        e[i] = acc
    return e / (e.max() + 1e-9)
