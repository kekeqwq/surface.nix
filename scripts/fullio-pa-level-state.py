#!/usr/bin/env python3
"""Bounded, read-only WSA state sampling for correlation with the level probe."""
import argparse
import datetime as dt
import errno
import json
import os
from pathlib import Path
import re
import time

PCM = Path('/proc/asound/card0/pcm0p/sub0/status')
SYS = Path('/sys/bus/soundwire/devices')
DEBUG = Path('/sys/kernel/debug/regmap')
CLOCKS = Path('/sys/bus/platform/devices/6b00000.codec/fullio_clock_snapshot')
AMPS = [f'sdw:1:0:0217:0204:00:{i}' for i in (0, 1)]
# Next24 wsa884x_readonly_register(): all are volatile, non-precious status
# registers. Keep ADC output bytes raw: validity and scale while PA is on
# are not established. No interrupt, test, control, or cache-bypass access.
REGS = (0x3076, 0x3077, 0x3078, 0x3079, 0x307A, 0x307B,
        0x3435, 0x3436, 0x3438, 0x3439, 0x3454, 0x3455, 0x345C, 0x345D, 0x3501)


def active_trigger():
    data = PCM.read_text()
    if not re.search(r'^state:\s+RUNNING$', data, re.M):
        return None
    match = re.search(r'^trigger_time:\s+(\d+\.\d+)$', data, re.M)
    if not match or not float(match[1]):
        return None
    for amp in AMPS:
        if ((SYS / amp / 'status').read_text().strip() != 'Attached' or
                (SYS / amp / 'power/runtime_status').read_text().strip() != 'active'):
            return None
    return match[1]


def offsets(amp):
    access = {int(reg.rstrip(':'), 16): flags for line in (amp / 'access').read_text().splitlines()
              if line and (reg_flags := line.split()) for reg, *flags in [reg_flags]}
    indexes = []
    for interval in (amp / 'range').read_text().splitlines():
        first, last = (int(x, 16) for x in interval.split('-'))
        indexes.extend(range(first, last + 1))
    result = {}
    for r in REGS:
        if access.get(r) != ['y', 'n', 'y', 'n']:
            raise ValueError(f'{amp}: unexpected access flags for {r:04x}')
        result[r] = indexes.index(r) * 9
    return result


def read_status(amp, layout, trigger):
    result = {}
    with (amp / 'registers').open('rb', buffering=0) as fd:
        for addr, offset in layout.items():
            if active_trigger() != trigger:
                return None
            record = os.pread(fd.fileno(), 9, offset).decode()
            if not re.fullmatch(rf'{addr:04x}: [0-9a-f]{{2}}\n', record):
                raise OSError(f'{amp}: unavailable or unexpected register {addr:04x}')
            result[f'{addr:04x}'] = record[6:8]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('closure', type=Path)
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--clocks', action='store_true', help='require the opt-in LPASS clock snapshot')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 900:
        parser.error('sampling duration must be between 1 and 900 seconds')
    if Path('/run/booted-system').resolve(strict=True) != args.closure:
        parser.error('unexpected boot closure')
    if args.clocks and not CLOCKS.is_file():
        parser.error('missing opt-in FullIO clock snapshot')
    layout = {amp: offsets(DEBUG / amp) for amp in AMPS}
    end = time.monotonic() + args.seconds
    while time.monotonic() < end:
        start = time.monotonic()
        trigger = active_trigger()
        samples = clocks = None
        if trigger:
            samples = [read_status(DEBUG / amp, layout[amp], trigger) for amp in AMPS]
            if args.clocks:
                try:
                    clocks = CLOCKS.read_text().strip()
                except OSError as exc:
                    if exc.errno != errno.EAGAIN:
                        raise
            if None in samples or active_trigger() != trigger:
                samples = clocks = None
        print(json.dumps({'time': dt.datetime.now().astimezone().isoformat(timespec='milliseconds'),
                          'mono': round(start, 3), 'trigger': trigger, 'amps': samples,
                          'clocks': clocks}), flush=True)
        # Keep readback slow enough not to stress the live SoundWire bus.
        time.sleep(max(0, min(start + 5, end) - time.monotonic()))


if __name__ == '__main__':
    main()
