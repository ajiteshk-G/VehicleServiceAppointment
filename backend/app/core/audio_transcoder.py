"""Real-time Audio Transcoder and Resampling Engine.

Handles bidirectional conversion between:
- Twilio Telephony: 8kHz G.711 mu-law (mono)
- Gemini 2.5 Live API Input: 16kHz 16-bit Linear PCM (mono, little-endian)
- Gemini 2.5 Live API Output: 24kHz 16-bit Linear PCM (mono, little-endian)
- Browser WebRTC / AudioWorklet: 16kHz/24kHz/48kHz PCM

Uses accelerated audioop / audioop-lts when available, with a fast, zero-dependency
pure-Python precomputed lookup table fallback (ideal for Python 3.13+ environments).
"""

import math
import struct
from typing import Optional, Tuple

# Attempt to load native audioop or audioop-lts
_AUDIOOP_AVAILABLE = False
try:
    import audioop_lts as audioop
    _AUDIOOP_AVAILABLE = True
except ImportError:
    try:
        import audioop  # type: ignore
        _AUDIOOP_AVAILABLE = True
    except ImportError:
        _AUDIOOP_AVAILABLE = False


# ==============================================================================
# Fast Precomputed G.711 Mu-Law Lookup Tables
# ==============================================================================

def _build_ulaw_tables() -> Tuple[list, bytes]:
    """Generates standard ITU-T / Sun G.711 mu-law conversion tables."""
    bias = 0x84
    clip = 32635
    seg_end = [0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF, 0x3FFF, 0x7FFF]

    # 1. 8-bit mu-law to 16-bit signed PCM table (256 entries)
    ulaw_to_pcm = []
    for i in range(256):
        u_val = ~i & 0xFF
        t = ((u_val & 0x0F) << 3) + bias
        t <<= ((u_val & 0x70) >> 4)
        sample = (bias - t) if (u_val & 0x80) else (t - bias)
        ulaw_to_pcm.append(max(-32768, min(32767, sample)))

    # 2. 16-bit signed PCM to 8-bit mu-law table (65536 entries, indexed by sample + 32768)
    pcm_to_ulaw = bytearray(65536)
    for idx in range(65536):
        pcm_val = idx - 32768
        if pcm_val < 0:
            pcm_val = -pcm_val
            mask = 0x7F
        else:
            mask = 0xFF

        if pcm_val > clip:
            pcm_val = clip
        pcm_val += bias

        seg = 8
        for s_idx in range(8):
            if pcm_val <= seg_end[s_idx]:
                seg = s_idx
                break

        if seg >= 8:
            uval = (0x7F ^ mask) & 0xFF
        else:
            uval = ((seg << 4) | ((pcm_val >> (seg + 3)) & 0x0F)) ^ mask
            uval &= 0xFF

        pcm_to_ulaw[idx] = uval

    return ulaw_to_pcm, bytes(pcm_to_ulaw)


_ULAW_TO_PCM16_TABLE, _PCM16_TO_ULAW_TABLE = _build_ulaw_tables()


# ==============================================================================
# Audio Transcoding Functions
# ==============================================================================

def decode_mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """Decodes 8kHz G.711 mu-law audio to 8kHz 16-bit Linear PCM (mono, little-endian)."""
    if not mulaw_bytes:
        return b""
    if _AUDIOOP_AVAILABLE:
        return audioop.ulaw2lin(mulaw_bytes, 2)

    # Fast table lookup fallback
    samples = [_ULAW_TO_PCM16_TABLE[b] for b in mulaw_bytes]
    return struct.pack(f"<{len(samples)}h", *samples)


def encode_pcm16_to_mulaw(pcm_8k: bytes) -> bytes:
    """Encodes 8kHz 16-bit Linear PCM to 8kHz G.711 mu-law."""
    if not pcm_8k:
        return b""
    if _AUDIOOP_AVAILABLE:
        return audioop.lin2ulaw(pcm_8k, 2)

    # Fast table lookup fallback
    num_samples = len(pcm_8k) // 2
    if num_samples == 0:
        return b""
    samples = struct.unpack(f"<{num_samples}h", pcm_8k[:num_samples * 2])
    out = bytearray(num_samples)
    for i, s in enumerate(samples):
        out[i] = _PCM16_TO_ULAW_TABLE[s + 32768]
    return bytes(out)


def resample_8k_to_16k_pcm(pcm_8k: bytes) -> bytes:
    """Upsamples 8kHz 16-bit mono PCM to 16kHz 16-bit mono PCM (2x rate conversion)."""
    if not pcm_8k:
        return b""
    if _AUDIOOP_AVAILABLE:
        resampled, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
        return resampled

    # Fast 2x linear interpolation
    num_samples = len(pcm_8k) // 2
    if num_samples == 0:
        return b""
    samples = struct.unpack(f"<{num_samples}h", pcm_8k[:num_samples * 2])
    out_samples = []
    for i in range(num_samples - 1):
        s0 = samples[i]
        s1 = samples[i + 1]
        mid = (s0 + s1) // 2
        out_samples.extend([s0, mid])
    if num_samples > 0:
        last = samples[-1]
        out_samples.extend([last, last])

    return struct.pack(f"<{len(out_samples)}h", *out_samples)


def resample_24k_to_8k_pcm(pcm_24k: bytes) -> bytes:
    """Downsamples Gemini 24kHz 16-bit PCM to 8kHz 16-bit PCM (3:1 decimation with averaging)."""
    if not pcm_24k:
        return b""
    if _AUDIOOP_AVAILABLE:
        resampled, _ = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)
        return resampled

    num_samples = len(pcm_24k) // 2
    if num_samples == 0:
        return b""
    samples = struct.unpack(f"<{num_samples}h", pcm_24k[:num_samples * 2])
    out_samples = []
    # 3-tap averaging boxcar filter for anti-aliasing
    for i in range(0, num_samples, 3):
        chunk = samples[i:i + 3]
        avg = sum(chunk) // len(chunk)
        out_samples.append(avg)

    return struct.pack(f"<{len(out_samples)}h", *out_samples)


def resample_pcm(pcm_bytes: bytes, in_rate: int, out_rate: int) -> bytes:
    """Generic rate conversion for 16-bit mono PCM."""
    if in_rate == out_rate or not pcm_bytes:
        return pcm_bytes
    if _AUDIOOP_AVAILABLE:
        resampled, _ = audioop.ratecv(pcm_bytes, 2, 1, in_rate, out_rate, None)
        return resampled

    num_samples = len(pcm_bytes) // 2
    if num_samples == 0:
        return b""
    samples = struct.unpack(f"<{num_samples}h", pcm_bytes[:num_samples * 2])
    out_len = int(num_samples * out_rate / in_rate)
    if out_len == 0:
        return b""

    out_samples = []
    for i in range(out_len):
        src_idx = i * (num_samples - 1) / max(1, out_len - 1)
        idx_low = int(src_idx)
        idx_high = min(idx_low + 1, num_samples - 1)
        frac = src_idx - idx_low
        s = int((1.0 - frac) * samples[idx_low] + frac * samples[idx_high])
        out_samples.append(max(-32768, min(32767, s)))

    return struct.pack(f"<{len(out_samples)}h", *out_samples)


def calculate_pcm16_rms(pcm_bytes: bytes) -> float:
    """Calculates RMS energy for 16-bit mono PCM audio."""
    if not pcm_bytes:
        return 0.0
    if _AUDIOOP_AVAILABLE:
        return float(audioop.rms(pcm_bytes, 2))

    num_samples = len(pcm_bytes) // 2
    if num_samples == 0:
        return 0.0
    samples = struct.unpack(f"<{num_samples}h", pcm_bytes[:num_samples * 2])
    sum_squares = sum(s * s for s in samples)
    return math.sqrt(sum_squares / num_samples)


# ==============================================================================
# Compound High-Level Bridges
# ==============================================================================

def twilio_to_gemini(mulaw_8k_bytes: bytes) -> bytes:
    """Converts Twilio 8kHz mu-law audio chunk -> 16kHz PCM16 for Gemini Live input."""
    pcm_8k = decode_mulaw_to_pcm16(mulaw_8k_bytes)
    return resample_8k_to_16k_pcm(pcm_8k)


def gemini_to_twilio(pcm_24k_bytes: bytes) -> bytes:
    """Converts Gemini 24kHz PCM16 audio chunk -> 8kHz mu-law for Twilio phone output."""
    pcm_8k = resample_24k_to_8k_pcm(pcm_24k_bytes)
    return encode_pcm16_to_mulaw(pcm_8k)
