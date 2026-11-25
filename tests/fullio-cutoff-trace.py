#!/usr/bin/env python3
"""Offline check of a calibrated external capture; never controls hardware.

Use simultaneous scope channels or a common acquisition timebase. drive_* is
an externally derived nonnegative differential drive envelope (including
class-D switching), not signed audio samples or codec register values.
"""

import argparse
import csv
import math
from pathlib import Path

FIELDS = ('t_us', 'fault', 'transport_ok', 'sdn_l_v', 'sdn_r_v', 'drive_l_v', 'drive_r_v')
CONTROL_FIELDS = ('vbat_l_v', 'vbat_r_v', 'software_mute')


def trace(path, vbat_min=None):
    if vbat_min is not None and (not math.isfinite(vbat_min) or vbat_min <= 0):
        raise ValueError('VBAT minimum must be finite and positive')
    fields = FIELDS if vbat_min is None else FIELDS + CONTROL_FIELDS
    with path.open(newline='') as f:
        reader = csv.reader(f)
        if tuple(next(reader, ())) != fields:
            raise ValueError('unexpected trace columns')
        for i, row in enumerate(reader, 2):
            if len(row) != len(fields):
                raise ValueError(f'row {i}: invalid column count')
            values = tuple(map(float, row))
            t, fault, link, sl, sr, dl, dr = values[:len(FIELDS)]
            if not all(map(math.isfinite, values)):
                raise ValueError(f'row {i}: non-finite sample')
            if fault not in (0, 1) or link not in (0, 1) or min(dl, dr) < 0:
                raise ValueError(f'row {i}: invalid trigger/link/envelope sample')
            if vbat_min is not None:
                vl, vr, mute = values[len(FIELDS):]
                if min(vl, vr) < vbat_min:
                    raise ValueError(f'row {i}: amplifier supply fell below the qualified minimum')
                if mute != 0:
                    raise ValueError(f'row {i}: concurrent or unverified software mute')
            yield t, fault, link, (sl, sr), (dl, dr)


def verify(rows, *, sdn_low, sdn_high, off_v, on_v, fault_to_pin_us,
           pin_to_off_us, max_gap_us, pre_us, post_us):
    for x in (sdn_low, sdn_high, off_v, on_v, fault_to_pin_us, pin_to_off_us,
              max_gap_us, pre_us, post_us):
        if not math.isfinite(x) or x <= 0:
            raise ValueError('limits must be finite and positive')
    if not (sdn_low < sdn_high and off_v < on_v):
        raise ValueError('low/high criteria must be distinct')
    previous = baseline = fault_lower = restored = last = None
    pin = [None, None]
    off = [None, None]
    lost = False
    for t, fault, link, sdn, drive in rows:
        if previous is not None and not 0 < t - previous <= max_gap_us:
            raise ValueError('timestamps reversed or acquisition gap too large')
        if fault_lower is None:
            if not fault:
                if not link or min(sdn) < sdn_high or min(drive) < on_v:
                    raise ValueError('both channels must be demonstrably active before fault')
                if baseline is None:
                    baseline = t
                previous = t
                continue
            if baseline is None or previous - baseline < pre_us:
                raise ValueError('insufficient pre-fault active baseline')
            fault_lower = previous
        if not link:
            if restored is not None:
                raise ValueError('second loss after restoration')
            lost = True
        elif lost and restored is None:
            if any(x is None for x in off):
                raise ValueError('transport restored before paired shutdown')
            restored = t
        for lane in range(2):
            if pin[lane] is None and sdn[lane] <= sdn_low:
                if not lost:
                    raise ValueError(f'SD_N went low before observed transport loss on lane {lane}')
                pin[lane] = (previous, t)
            if pin[lane] is not None and sdn[lane] > sdn_low:
                raise ValueError(f'SD_N reasserted high on lane {lane}')
            if off[lane] is None and drive[lane] <= off_v:
                if pin[lane] is None:
                    raise ValueError(f'output went quiet before SD_N on lane {lane}; cutoff unproven')
                if pin[lane][1] == t:
                    raise ValueError(f'output-off and SD_N share one sample on lane {lane}; order unproven')
                off[lane] = t
            if off[lane] is not None and drive[lane] > off_v:
                raise ValueError(f'output drive returned on lane {lane}')
        previous = last = t
    if restored is None or last - restored < post_us:
        raise ValueError('missing transport loss/recovery or insufficient observation after recovery')
    result = [(upper - fault_lower, down - lower) for (lower, upper), down in zip(pin, off)]
    if any(a > fault_to_pin_us or b > pin_to_off_us for a, b in result):
        raise ValueError(f'one or both channels exceeded the configured limits: {result}')
    return result


def verify_without_sdn(rows, *, sdn_high, off_v, on_v, fault_to_off_us,
                       max_gap_us, pre_us, post_us):
    """Check loss-to-off with SD_N high; does not identify the mechanism."""
    if not all(math.isfinite(v) and v > 0 for v in
               (sdn_high, off_v, on_v, fault_to_off_us, max_gap_us, pre_us, post_us)) or off_v >= on_v:
        raise ValueError('invalid no-SD_N limits')
    baseline = previous = lost = restored = None
    off = [None, None]
    for t, fault, link, sdn, drive in rows:
        if previous is not None and not 0 < t - previous <= max_gap_us:
            raise ValueError('timestamps reversed or acquisition gap too large')
        if min(sdn) < sdn_high:
            raise ValueError('SD_N not continuously deasserted on both chips')
        if lost is None:
            if not link:
                if not fault or baseline is None or previous - baseline < pre_us:
                    raise ValueError('loss requires a marked fault and a fully driven baseline')
                lost = previous  # earliest possible loss between two samples
            else:
                if fault or min(drive) < on_v:
                    raise ValueError('fault marker and observed loss must coincide; pre-fault outputs must be driven')
                if baseline is None:
                    baseline = t
        if lost is not None:
            if restored is not None and not link:
                raise ValueError('second transport loss after restoration')
            if link and restored is None:
                if not all(v is not None for v in off):
                    raise ValueError('transport restored before paired shutdown')
                restored = t
            for lane, value in enumerate(drive):
                if off[lane] is not None and value > off_v:
                    raise ValueError(f'output drive returned on lane {lane}')
                if off[lane] is None and value <= off_v:
                    off[lane] = t
        previous = t
    if restored is None or previous - restored < post_us:
        raise ValueError('missing transport loss/recovery or insufficient observation after recovery')
    result = [v - lost for v in off]
    if max(result) > fault_to_off_us:
        raise ValueError(f'one or both channels exceeded the configured loss-to-off limit: {result}')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv', type=Path)
    p.add_argument('--no-sdn-transition', action='store_true',
                   help='check loss-to-off while both SD_N pins stay deasserted')
    for name in ('sdn-high', 'off-v', 'on-v', 'max-gap-us', 'pre-us', 'post-us'):
        p.add_argument('--' + name, type=float, required=True)
    for name in ('sdn-low', 'fault-to-pin-us', 'pin-to-off-us', 'fault-to-off-us'):
        p.add_argument('--' + name, type=float)
    p.add_argument('--vbat-min-v', type=float,
                   help='require simultaneous vbat_l_v, vbat_r_v and independently verified software_mute columns')
    args = vars(p.parse_args())
    path = args.pop('csv')
    vbat_min = args.pop('vbat_min_v')
    no_sdn = args.pop('no_sdn_transition')
    keys = ('sdn_low', 'fault_to_pin_us', 'pin_to_off_us')
    if no_sdn:
        if any(args.pop(k) is not None for k in keys) or args['fault_to_off_us'] is None:
            p.error('--no-sdn-transition requires --fault-to-off-us and no SD_N assertion limits')
    elif args.pop('fault_to_off_us') is not None or any(args[k] is None for k in keys):
        p.error('SD_N cutoff requires --sdn-low, --fault-to-pin-us and --pin-to-off-us')
    try:
        if no_sdn:
            result = verify_without_sdn(trace(path, vbat_min), **args)
            for name, bound in zip(('L', 'R'), result):
                print(f'{name}: captured upper interval transport loss→output-off {bound:g} us; SD_N stayed high')
        else:
            result = verify(trace(path, vbat_min), **args)
            for name, (a, b) in zip(('L', 'R'), result):
                print(f'{name}: captured upper intervals fault→SD_N {a:g} us, SD_N→output-off {b:g} us')
    except (OSError, ValueError) as exc:
        p.exit(1, f'FAIL: {exc}\n')
    if vbat_min is None:
        print('Timing only: no supply/mute controls; not independent-cutoff evidence.')
    print('Meets supplied limits for this acquisition only; not a hardware worst-case guarantee.')


if __name__ == '__main__':
    main()
