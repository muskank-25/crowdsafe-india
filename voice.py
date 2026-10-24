"""Server-side alert sound for the Streamlit app: spoken message (gTTS, needs internet) or a siren/beep fallback that always works."""
import io, math, struct, threading, wave
from functools import lru_cache

def siren(severity="danger", rate=22050):
    """Pure-Python WAV: two-tone siren for danger, double beep otherwise."""
    seq = ([650, 900] * 4) if severity == "danger" else [800, 0, 800]
    frames = bytearray()
    for f in seq:
        for i in range(int(rate * .22)):
            frames += struct.pack("<h", int(9000 * math.sin(2 * math.pi * f * i / rate)) if f else 0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(frames))
    return buf.getvalue()

@lru_cache(maxsize=64)
def speech(text, lang="en"):
    """MP3 bytes of the spoken text via gTTS, or None if gTTS is missing or offline (6 s limit)."""
    try: from gtts import gTTS
    except ImportError: return None
    out = {}
    def work():
        try:
            b = io.BytesIO(); gTTS(text, lang=lang, **({"tld": "co.in"} if lang == "en" else {})).write_to_fp(b); out["d"] = b.getvalue()
        except Exception: pass
    t = threading.Thread(target=work, daemon=True); t.start(); t.join(6)
    return out.get("d")

def make_clip(text, lang="en", severity="danger"):
    """(bytes, mime). Spoken message when possible, otherwise the siren."""
    mp3 = speech(text, lang)
    return (mp3, "audio/mp3") if mp3 else (siren(severity), "audio/wav")
