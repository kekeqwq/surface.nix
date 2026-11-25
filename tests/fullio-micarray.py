#!/usr/bin/env python3
"""Locate the FullIO MicArray PCM or check a private raw-ALSA capture."""

import argparse
from array import array
import math
from pathlib import Path
import re
import sys
import wave

MODEL = "X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0"


def find_micarray(model, pcms):
    if model.rstrip("\0\n") != MODEL:
        raise ValueError("running DT is not the Denali FullIO fixture")
    ids = []
    for line in pcms.splitlines():
        match = re.match(r"^(\d+)-(\d+):\s*MultiMedia3 Capture(?: \(\*\))?\s*:.*:\s*capture\s+([1-9]\d*)\s*$", line)
        if match:
            ids.append(f"hw:{int(match[1])},{int(match[2])}")
    if len(ids) != 1:
        raise ValueError(f"expected one MultiMedia3 Capture PCM, found {len(ids)}")
    return ids[0]


def inspect_capture(path):
    with wave.open(str(path), "rb") as capture:
        if (capture.getnchannels(), capture.getsampwidth(), capture.getframerate()) != (2, 2, 48000):
            raise ValueError("expected 48 kHz S16_LE stereo, recorded with hw: (no plug conversion)")
        frames = capture.getnframes()
        if not 48000 <= frames <= 480000:
            raise ValueError("expected a 1–10 second diagnostic clip")
        data = capture.readframes(frames)
        if len(data) != frames * 4:
            raise ValueError("truncated capture")
    samples = array("h", data)
    if sys.byteorder != "little":
        samples.byteswap()
    left, right = samples[::2], samples[1::2]
    for name, channel in (("left", left), ("right", right)):
        mean = sum(channel) / frames
        rms = math.sqrt(sum((sample - mean) ** 2 for sample in channel) / frames)
        peak = max(abs(sample) for sample in channel)
        clipped = sum(sample in (-32768, 32767) for sample in channel)
        print(f"{name}: AC RMS {rms:.2f}, peak {peak}, clipped frames {clipped}/{frames}")
        if rms < 1:
            raise ValueError(f"{name} channel is silent or effectively constant")
    if left == right or all(l == -r for l, r in zip(left, right)):
        raise ValueError("channels are exact copies (possibly inverted)")
    print("Both channels vary and are not exact copies; physical routing and clarity still need listening.")


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("wav", type=Path, nargs="?", help="existing private S16_LE stereo WAV; omit to locate the PCM")
    ns = args.parse_args()
    try:
        if ns.wav:
            inspect_capture(ns.wav)
        else:
            print(find_micarray(
                Path("/sys/firmware/devicetree/base/sound/model").read_text(),
                Path("/proc/asound/pcm").read_text(),
            ))
    except (OSError, ValueError, EOFError, wave.Error) as error:
        args.exit(1, f"FullIO MicArray: {error}\n")


if __name__ == "__main__":
    main()
