#!/usr/bin/env python3
"""Compare denali-power-snapshot.sh captures from one attended suspend cycle."""

import argparse
import json
from pathlib import Path
import re

POWER = '/sys/class/power_supply/'
STATS = '/sys/power/suspend_stats/'
OFFSET = 'boottime_minus_monotonic_ns'
MODES = ('cxsd', 'aosd', 'ddr')
SUBSYSTEMS = ('adsp', 'adsp_island')
FIELD = re.compile(r'^(Count|Last Entered At|Last Exited At|Accumulated Duration):\s*(\d+)\s*$')
HEADER = re.compile(r'^--- /sys/kernel/debug/(qcom_stats|rpmh_stats)/(\w+) ---$')


def snapshots(text):
    captures = []
    capture = None
    source = None
    for line in text.splitlines():
        if line.startswith('utc='):
            capture = {'values': {'utc': line[4:]}, 'counters': {}}
            captures.append(capture)
            source = None
        if capture is None:
            continue
        if line.startswith('--- '):
            match = HEADER.fullmatch(line)
            source = match.groups() if match else None
            if source is not None:
                if source in capture['counters']:
                    raise ValueError(f'duplicate residency section: {source}')
                capture['counters'][source] = {}
        elif source is not None and (match := FIELD.fullmatch(line)):
            field, value = match.groups()
            counters = capture['counters'][source]
            if field in counters:
                raise ValueError(f'duplicate residency field: {source} {field}')
            counters[field] = int(value)
        elif '=' in line:
            key, value = line.split('=', 1)
            if key in ('boot_id', 'release', OFFSET) or key.startswith(('/sys/',)):
                if key in capture['values']:
                    raise ValueError(f'duplicate snapshot field: {key}')
                capture['values'][key] = value
    return captures


def probe_mode(before, after, mode):
    sources = [{source for source, name in s['counters'] if name == mode} for s in (before, after)]
    if not all(sources):
        return {'status': 'missing'}
    if sources[0] != sources[1] or len(sources[0]) != 1:
        return {'status': 'ambiguous_source', 'sources': [sorted(s) for s in sources]}
    source = next(iter(sources[0]))
    b, a = (s['counters'][source, mode] for s in (before, after))
    fields = ('Count', 'Last Entered At', 'Last Exited At', 'Accumulated Duration')
    if not all(field in sample for sample in (b, a) for field in fields):
        return {'status': 'unreadable', 'source': source}
    count = a['Count'] - b['Count']
    ticks = a['Accumulated Duration'] - b['Accumulated Duration']
    if count < 0 or ticks < 0:
        status = 'counter_reset_or_wrap'
    elif count > 0 and ticks > 0:
        status = 'advanced'
    elif count == ticks == 0 and b == a:
        status = 'unchanged'
    else:
        status = 'inconclusive'
    return {'status': status, 'source': source, 'count_delta': count, 'duration_ticks_delta': ticks,
            'before': b, 'after': a}


def compare(before, after):
    b, a = (s['values'] for s in (before, after))
    boot = b.get('boot_id')
    if not boot or boot != a.get('boot_id') or not b.get('release') or b.get('release') != a.get('release'):
        raise ValueError('snapshots must be from the same identifiable boot and kernel')
    try:
        success, fail, suspended = (int(a[key]) - int(b[key]) for key in (STATS+'success', STATS+'fail', OFFSET))
    except KeyError as exc:
        raise ValueError(f'missing OS suspend evidence: {exc.args[0]}') from None
    if (success, fail) != (1, 0) or suspended <= 0:
        raise ValueError(f'not one verified OS suspend: success_delta={success} fail_delta={fail} sleep_ns={suspended}')
    modes = {mode: probe_mode(before, after, mode) for mode in MODES}
    statuses = [entry['status'] for entry in modes.values()]
    if all(status == 'unchanged' for status in statuses):
        result = 'no_counter_advance'
    elif all(status in ('advanced', 'unchanged') for status in statuses):
        result = 'counter_advance'
    else:
        result = 'inconclusive'
    return {
        'boot_id': boot, 'snapshot_utc': [b['utc'], a['utc']],
        'os_suspended_ns': suspended, 'wake_irq': a.get('/sys/power/pm_wakeup_irq'),
        'residency': result, 'modes': modes,
        # Subsystem entries span the full sampling interval, including awake
        # edges. Do not promote them to SoC residency or infer a wake rate.
        'subsystems': {name: probe_mode(before, after, name) for name in SUBSYSTEMS},
        # Do not estimate watts from snapshots: charging/settling and awake time may differ.
        'BAT1_energy_uWh': [s.get(POWER+'BAT1/energy_now') for s in (b, a)],
        'BAT1_status': [s.get(POWER+'BAT1/status') for s in (b, a)],
        'ADP1_online': [s.get(POWER+'ADP1/online') for s in (b, a)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', type=Path, nargs='+', help='one log with two snapshots, or one file per snapshot (before, then after)')
    args = parser.parse_args()
    try:
        captures = [snapshots(path.read_text()) for path in args.files]
        if [len(items) for items in captures] not in ([2], [1, 1]):
            raise ValueError('expected exactly two snapshots; use one log or two single-snapshot files')
        print(json.dumps(compare(*(item for group in captures for item in group)), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f'invalid suspend comparison: {exc}\n')


if __name__ == '__main__':
    main()
