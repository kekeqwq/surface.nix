#!/usr/bin/env python3
"""Generate a low-level stereo listening check. Does not open any audio device."""

import argparse
from array import array
import math
from pathlib import Path
import sys
import wave

RATE = 48_000
# Approx. -30 dBFS peak per channel. Not a calibrated acoustic or PA limit.
PEAK = 1024
SECONDS = 8


def render():
    samples = array('h')
    for i in range(SECONDS * RATE):
        t = i / RATE
        if t < 2:
            # Two seconds left only; then two seconds right only.
            fade = min(t, 2 - t, .05) / .05
            pair = (fade * math.sin(math.tau * 440 * t), 0)
        elif t < 4:
            fade = min(t - 2, 4 - t, .05) / .05
            pair = (0, fade * math.sin(math.tau * 660 * t))
        else:
            # Distinct, continuous sweeps to make dropouts audible.
            x = t - 4
            fade = min(x, 8 - t, .05) / .05
            pair = (fade * math.sin(math.tau * (330 * x + 30 * x * x)),
                    fade * math.sin(math.tau * (550 * x + 45 * x * x)))
        samples.extend(round(v * PEAK) for v in pair)
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples.tobytes()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    with args.output.open('xb') as stream, wave.open(stream, 'wb') as wav:
        wav.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
        wav.writeframes(render())


if __name__ == '__main__':
    main()
