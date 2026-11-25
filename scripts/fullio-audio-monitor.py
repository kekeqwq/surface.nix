#!/usr/bin/env python3
"""Autonomous acoustic monitor for the protected Denali render path.

The internal MicArray physically picks up what the internal speakers
emit, so this verifies real playback without a human listener:

- every new PCM stream start is captured for 3 s; the first 300 ms are
  checked for a startup transient (the reported brief pop) and the tail
  for acoustic energy above the quiet-room floor;
- periodic samples while a stream is running report EMITTING/SILENT.

Everything is appended to acoustic-monitor.log in the fixture state
directory. This never replaces the user's listening acceptance.
"""

import argparse
import math
from pathlib import Path
import struct
import subprocess
import time

RATE = 48000
QUIET_FLOOR = 25.0        # quiet-room RMS observed on this hardware
EMITTING_FLOOR = 60.0     # comfortably above the quiet-room floor
POP_FLOOR = 2000.0        # peak magnitude of a suspicious startup transient


def find_tool(pattern):
    import glob
    hits = sorted(glob.glob(pattern))
    if not hits:
        raise SystemExit(f'tool not found: {pattern}')
    return hits[-1]


def trigger_time():
    try:
        for line in Path('/proc/asound/card0/pcm0p/sub0/status').read_text().splitlines():
            if line.startswith('trigger_time'):
                return line.split()[1]
    except OSError:
        return None
    return None


def pcm_running():
    try:
        return 'state: RUNNING' in Path('/proc/asound/card0/pcm0p/sub0/status').read_text()
    except OSError:
        return False


def capture(pw_record, seconds, out):
    frames = int(seconds * RATE)
    subprocess.run([pw_record, '--rate', str(RATE), '--channels', '2', '--format', 's16',
                    '--raw', '-n', str(frames), str(out)], capture_output=True)
    raw = out.read_bytes()
    n = len(raw) // 4
    samples = []
    peak = 0
    for i in range(n):
        left, right = struct.unpack_from('<hh', raw, i * 4)
        value = (left + right) / 2.0
        samples.append(value)
        peak = max(peak, abs(left), abs(right))
    rms = math.sqrt(sum(v * v for v in samples) / len(samples)) if samples else 0.0
    head = samples[:int(0.3 * RATE)]
    head_peak = max((abs(v) for v in head), default=0)
    tail = samples[int(1.0 * RATE):]
    tail_rms = math.sqrt(sum(v * v for v in tail) / len(tail)) if tail else 0.0
    return rms, peak, head_peak, tail_rms


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('state', type=Path)
    cli.add_argument('--periodic', type=float, default=300.0)
    args = cli.parse_args()
    pw_record = find_tool('/nix/store/*-pipewire-*/bin/pw-record')
    args.state.mkdir(parents=True, exist_ok=True)
    log = args.state / 'acoustic-monitor.log'
    work = args.state / 'acoustic-monitor'
    work.mkdir(exist_ok=True)
    for stale in sorted(work.glob('*.raw'))[:-60]:
        stale.unlink(missing_ok=True)

    def emit(message):
        line = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {message}'
        print(line, flush=True)
        with log.open('a') as out:
            out.write(line + '\n')

    emit('monitor start')
    last_trigger = None
    last_periodic = 0.0
    index = 0
    while True:
        now = time.time()
        trigger = trigger_time()
        if trigger and trigger != last_trigger:
            if last_trigger is not None:
                index += 1
                out = work / f'start-{index}.raw'
                rms, peak, head_peak, tail_rms = capture(pw_record, 3.0, out)
                pop = 'POP' if head_peak > POP_FLOOR else 'clean-startup'
                sound = 'EMITTING' if tail_rms > EMITTING_FLOOR else (
                    'QUIET-PASSAGE?' if tail_rms > QUIET_FLOOR else 'SILENT')
                emit(f'stream-start trigger={trigger} pop={pop} head_peak={head_peak:.0f} '
                     f'tail_rms={tail_rms:.1f} verdict={sound}')
            last_trigger = trigger
        if now - last_periodic >= args.periodic:
            last_periodic = now
            if pcm_running():
                index += 1
                out = work / f'periodic-{index}.raw'
                rms, peak, head_peak, tail_rms = capture(pw_record, 2.0, out)
                verdict = 'EMITTING' if tail_rms > EMITTING_FLOOR else (
                    'QUIET-PASSAGE?' if tail_rms > QUIET_FLOOR else 'SILENT')
                emit(f'periodic tail_rms={tail_rms:.1f} peak={peak} verdict={verdict}')
            else:
                emit('periodic: no active stream')
        time.sleep(1.0)


if __name__ == '__main__':
    raise SystemExit(main())
