#!/usr/bin/env python3
"""Read-only Denali clock/GMU binding check. Does not exercise GPU or sleep."""

import argparse
import json
import os
from pathlib import Path
import platform

GCC = '100000.clock-controller'
GPUCC = '3d90000.clock-controller'
GMU = '3d6a000.gmu'
GPU = '3d00000.gpu'
ICC = ('interconnect-1', '1700000.interconnect')
CRYPTO = ('1d88000.crypto', '1dfa000.crypto')
LINK = f'consumer:platform:{GMU}'


def text(path):
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return None


def driver(path):
    try:
        return Path(os.readlink(path / 'driver')).name
    except FileNotFoundError:
        return None


def inspect(devices):
    snapshot = {}
    for name in (GCC, GPUCC, GMU, GPU, *ICC, *CRYPTO):
        node = devices / name
        if not node.is_dir():
            snapshot[name] = None
            continue
        snapshot[name] = {
            'driver': driver(node),
            'state_synced': text(node / 'state_synced'),
            'runtime_status': text(node / 'power/runtime_status'),
            'consumers': {link.name: text(link / 'status') for link in sorted(node.glob('consumer:*'))},
        }
    return snapshot


def verify(snapshot, bound):
    errors = []
    expected_driver = {
        GCC: 'gcc-x1e80100', GPUCC: 'gpucc-x1e80100', GMU: 'adreno_gmu' if bound else None,
        GPU: 'adreno', **dict.fromkeys(ICC, 'qnoc-x1e80100'),
    }
    for name, expected in expected_driver.items():
        node = snapshot[name]
        if node is None or node['driver'] != expected:
            errors.append(f'{name}: expected present and driver={expected!r}')
    for name, expected in {GCC: '1' if bound else '0', GPUCC: '1' if bound else '0', **dict.fromkeys(ICC, '1')}.items():
        node = snapshot[name]
        if node is None or node['state_synced'] != expected:
            errors.append(f'{name}: expected state_synced={expected}')
    for name in CRYPTO:
        if snapshot[name] is not None:
            errors.append(f'{name}: unexpected crypto node in the ICE/QCE experiment')
    for name in (GCC, GPUCC):
        node = snapshot[name]
        if node is None:
            continue
        consumers = node['consumers']
        relevant = 'active' if bound else 'available'
        if consumers.get(LINK) != relevant:
            errors.append(f'{name}: expected {LINK}={relevant}')
        inactive = {key: state for key, state in consumers.items() if state != 'active'}
        if inactive != ({} if bound else {LINK: 'available'}):
            errors.append(f'{name}: unexpected pending consumers {inactive}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('baseline', 'bound'))
    mode = parser.parse_args().mode
    boot_id = text(Path('/proc/sys/kernel/random/boot_id'))
    if not boot_id:
        parser.exit(2, 'Failed to read boot identity\n')
    snapshot = inspect(Path('/sys/bus/platform/devices'))
    errors = verify(snapshot, bound=mode == 'bound')
    print(json.dumps({
        'boot_id': boot_id, 'release': platform.release(), 'mode': mode,
        'devices': snapshot, 'errors': errors,
    }, sort_keys=True, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
