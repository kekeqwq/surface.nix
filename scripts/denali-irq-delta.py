#!/usr/bin/env python3
"""Compare paired /proc/interrupts tables from the same boot."""

import argparse
import json
from pathlib import Path
import re


def parse(text):
    head, *lines = text.splitlines()
    cpus = head.split()
    if not cpus or len(set(cpus)) != len(cpus) or not all(re.fullmatch(r'CPU\d+', c) for c in cpus):
        raise ValueError('invalid CPU columns')
    rows = {}
    for line in lines:
        match = re.match(r'^\s*(\d+):\s+(.*)$', line)
        if not match:
            continue
        irq, cells = int(match[1]), match[2].split()
        counts, label = cells[:len(cpus)], cells[len(cpus):]
        if not label or not all(c.isdecimal() for c in counts) or irq in rows:
            raise ValueError(f'invalid interrupt row: {line}')
        rows[irq] = (tuple(map(int, counts)), ' '.join(label))
    return cpus, rows


def compare(before, after):
    cpus, b = parse(before)
    other, a = parse(after)
    if cpus != other:
        raise ValueError('CPU columns changed')
    changes, skipped = [], []
    for irq in sorted(b.keys() | a.keys()):
        if irq not in b or irq not in a or a[irq][1] != b[irq][1]:
            skipped.append({'irq': irq, 'status': 'missing_or_remapped'})
            continue
        deltas = [end - start for start, end in zip(b[irq][0], a[irq][0])]
        if any(n < 0 for n in deltas):
            skipped.append({'irq': irq, 'status': 'counter_decreased'})
            continue
        changes.append({'irq': irq, 'label': a[irq][1], 'delta': sum(deltas), 'per_cpu': dict(zip(cpus, deltas))})
    changes.sort(key=lambda entry: (-entry['delta'], entry['irq']))
    return {'changes': changes, 'skipped': skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(compare(args.before.read_text(), args.after.read_text()), indent=2))
    except (IndexError, ValueError, OSError) as exc:
        parser.exit(2, f'invalid interrupt comparison: {exc}\n')


if __name__ == '__main__':
    main()
