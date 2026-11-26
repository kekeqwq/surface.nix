#!/usr/bin/env python3
"""Generate a bounded, periodic stereo probe for the FullIO level logger."""
import argparse
from array import array
import math
from pathlib import Path
import sys
import wave

RATE = 48000
PERIOD = 4
LIMIT = 4608  # Hard digital peak ceiling; no speaker gain changes.
DEFAULT_PEAK = 4608


def waveform(peak):
    # Fixed phases, voice-band harmonics and separate left/right content.
    # All oscillators complete an integral number of cycles in one block.
    tones = [(131, 1.0), (203, 0.7), (277, 0.7), (449, 0.55), (577, 0.5),
             (727, 0.42), (1009, 0.36), (1471, 0.29), (2213, 0.23), (3089, 0.16)]
    weights = sum(abs(a) for _, a in tones)
    data = array('h')
    for i in range(RATE * PERIOD):
        t = i / RATE
        envelope = 0.78 + 0.22 * math.sin(math.tau * 2 * t)
        for ch in (0, 1):
            value = sum(a * math.sin(math.tau * (f + ch * (j + 2)) * t + (j + 1)**2)
                        for j, (f, a) in enumerate(tones))
            data.append(round(peak * envelope * value / weights))
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', help='new WAV path (never overwritten)')
    parser.add_argument('--seconds', type=int, default=120)
    parser.add_argument('--peak', type=int, default=DEFAULT_PEAK,
                        help='digital peak counts; scaled level-dependence probe')
    parser.add_argument('--force', action='store_true',
                        help='replace an existing output instead of failing')
    parser.add_argument('--silent-gap', nargs=2, type=int, metavar=('START', 'SECONDS'),
                        help='insert zero samples over this interval, inside the requested duration')
    args = parser.parse_args()
    if args.silent_gap:
        start, length = args.silent_gap
        if start < 2 * PERIOD or length < PERIOD or start + length > args.seconds - 2 * PERIOD or start % PERIOD or length % PERIOD:
            parser.error('gap must be 4-second aligned and leave at least 8 seconds on each side')
    if not 12 <= args.seconds <= 600 or args.seconds % PERIOD:
        parser.error('use a multiple of 4 seconds between 12 and 600')
    if not 1 <= args.peak <= LIMIT:
        parser.error('peak must be between 1 and %d' % LIMIT)
    block = waveform(args.peak)
    if max(map(abs, block)) > LIMIT:
        raise ValueError('stimulus exceeds peak bound')
    # Smooth both amplitude and slope at the start/stop boundaries.
    ramp_frames = 3 * RATE // 20  # 150 ms
    head, tail = block[:], block[:]
    for i in range(ramp_frames):
        fade = (1 - math.cos(math.pi * i / (ramp_frames - 1))) / 2
        for ch in (0, 1):
            head[2*i + ch] = round(head[2*i + ch] * fade)
            tail[-2*i - 1 - ch] = round(tail[-2*i - 1 - ch] * fade)
    if sys.byteorder != 'little':
        for samples in (block, head, tail):
            samples.byteswap()
    # Refuse a silent stale file: a shorter earlier probe must never be replayed.
    if args.force:
        Path(args.output).unlink(missing_ok=True)
    with open(args.output, 'xb') as file, wave.open(file, 'wb') as wav:
        wav.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
        wav.writeframesraw(head.tobytes())
        payload = block.tobytes()
        if args.silent_gap:
            silent = bytes(len(payload))
            fade_out = tail.tobytes()
            fade_in = head.tobytes()
        for at in range(PERIOD, args.seconds - PERIOD, PERIOD):
            if not args.silent_gap:
                piece = payload
            elif start <= at < start + length:
                piece = silent
            elif at + PERIOD == start:
                piece = fade_out
            elif at == start + length:
                piece = fade_in
            else:
                piece = payload
            wav.writeframesraw(piece)
        wav.writeframesraw(tail.tobytes())


if __name__ == '__main__':
    main()
