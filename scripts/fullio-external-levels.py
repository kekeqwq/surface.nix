#!/usr/bin/env python3
"""Convert an independent stereo 48 kHz S16_LE PCM pipe to scalar JSONL.

Run on the microphone host, either live from a verified capture frontend or
after decoding a private native-rate file to S16_LE. With --first-wall the
reported timestamps are derived from sample offsets, not read latency. The
caller owns the capture frontend and must verify its device; this program
neither stores PCM nor opens a mic.
"""
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import runpy
import sys
import time

probe = runpy.run_path(str(Path(__file__).with_name('fullio-level-probe.py')))
Levels, RATE, tone_basis = (probe[name] for name in ('Levels', 'RATE', 'tone_basis'))
FREQUENCIES = (203, 206, 449, 454, 1009, 1017)


def collect(stream, out, limit, first_wall=None, *, strict=False):
    detector = Levels(tone_basis(FREQUENCIES))
    frames = 0
    windows = 0
    heard = False
    for _ in range(limit):
        data = stream.read(4 * RATE)
        if not data:
            break
        if len(data) % 4:
            raise ValueError('truncated stereo frame')
        detector.add(data)
        measures = detector.take()
        if measures['frames'] < RATE:
            break
        if strict and (not all(measures['peak']) or max(measures['peak']) >= 32767):
            raise ValueError('zero or clipped external input lane')
        windows += 1
        heard |= any(measures['peak'])
        if windows == 5 and not heard:
            raise ValueError('five seconds of all-zero external input; check microphone access and routing')
        if first_wall is None:
            stamp = dt.datetime.now().astimezone().isoformat(timespec='milliseconds')
            mono = time.monotonic()
        else:
            stamp = dt.datetime.fromtimestamp(first_wall + frames / RATE).astimezone().isoformat(timespec='milliseconds')
            mono = first_wall + frames / RATE
        source = 'pipe-receipt' if first_wall is None else 'first-wall-plus-frame-offset'
        out.write(json.dumps({'time': stamp, 'mono': mono, 'sample_offset': frames,
                              'timestamp_source': source, **measures}) + '\n')
        frames += measures['frames']
    if strict and windows != limit:
        raise ValueError(f'incomplete external capture: {windows}/{limit} full seconds')
    if windows < 5 or not heard:
        raise ValueError('external capture too short or silent')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path, help='new private JSONL path')
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--first-wall', type=float,
                        help='UNIX time of the first sample; enables sample-accurate stamps')
    parser.add_argument('--strict', action='store_true',
                        help='require all requested seconds and reject zero or clipped lanes')
    args = parser.parse_args()
    if args.first_wall is not None and not math.isfinite(args.first_wall):
        parser.error('--first-wall must be finite')
    if not 5 <= args.seconds <= 900:
        parser.error('seconds must be between 5 and 900')
    os.umask(0o077)
    try:
        with args.log.open('x', buffering=1) as out:
            collect(sys.stdin.buffer, out, args.seconds, args.first_wall, strict=args.strict)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'external probe: {exc}\n')


if __name__ == '__main__':
    main()
