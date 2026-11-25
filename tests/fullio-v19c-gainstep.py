#!/usr/bin/env python3
"""Validate reference GainStep metadata and optionally check private deltas.

No DSP or ALSA operations. Passing does not authorize application of a delta.
Use the reviewed runtime inventory from the pinned SP11X1e-audio checkout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

IIDS = (0x489E,) * 4
PIDS = (0x08001020, 0x08001021, 0x08001022, 0x08001026)
HEADER = struct.Struct('<IIII')
SIZES = (216, 272, 280)
# Metadata-only review artifact and the pinned reference runtime inventory.
INVENTORY_HASHES = {
    '52068f0a4e8d534c11bd1655f6c94cdcd7e89294f60a34b7135511ba03251ac4',
    '2077bea085cea94f52853b8524205824ea36ac038522d7b2f93906c84756337e',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_rows(inventory):
    if (inventory['format_version'] != 1 or not inventory['source_matches_reviewed_rev_0d']
            or int(inventory['delta_key_id'], 16) != 0x01000011
            or int(inventory['subgraph_id'], 16) != 0xB000007F):
        raise ValueError('not the reviewed v19c speaker GainStep inventory')
    steps = inventory['steps']
    if [r['gain_step'] for r in steps] != list(range(1, 31)):
        raise ValueError('expected GainSteps 1–30 exactly once')
    for row in steps:
        params = row['parameters']
        if row['parameter_count'] != len(params) or len(params) != 4:
            raise ValueError('expected exactly four parameters')
        total = 0
        for p, iid, pid in zip(params, IIDS, PIDS):
            size = p['payload_size']
            span = (size + HEADER.size + 7) & ~7
            if ((int(p['iid'], 16), int(p['param_id'], 16)) != (iid, pid)
                    or not 0 < size <= max(SIZES) or p['frame_size'] != span
                    or not re.fullmatch('[0-9a-f]{64}', p['payload_sha256'])):
                raise ValueError('unexpected module, parameter, size or payload hash')
            total += span
        if total not in SIZES or total != row['serialized_size']:
            raise ValueError(f'unexpected serialized delta size: {total}')
        if not re.fullmatch('[0-9a-f]{64}', row['serialized_sha256']):
            raise ValueError('invalid reviewed delta hash')
    return steps


def verify_blob(row, raw):
    if len(raw) != row['serialized_size']:
        raise ValueError('wrong delta length')
    offset = 0
    for p in row['parameters']:
        iid, pid, size, error = HEADER.unpack_from(raw, offset)
        if error or (iid, pid, size) != (int(p['iid'], 16), int(p['param_id'], 16), p['payload_size']):
            raise ValueError(f'unexpected header at +{offset}')
        start, end = offset + HEADER.size, offset + p['frame_size']
        if digest(raw[start:start + size]) != p['payload_sha256'] or any(raw[start + size:end]):
            raise ValueError(f'unexpected payload or padding at +{offset}')
        offset = end
    if offset != len(raw) or digest(raw) != row['serialized_sha256']:
        raise ValueError('serialized delta does not match reviewed hash')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('inventory', type=Path)
    p.add_argument('--private-deltas', type=Path, help='optionally check step-01.bin through step-30.bin')
    args = p.parse_args()
    try:
        inventory = args.inventory.read_bytes()
        if digest(inventory) not in INVENTORY_HASHES:
            raise ValueError('inventory hash differs from the pinned reference')
        rows = checked_rows(json.loads(inventory))
        if args.private_deltas:
            for r in rows:
                with (args.private_deltas / f"step-{r['gain_step']:02}.bin").open('rb') as f:
                    verify_blob(r, f.read(max(SIZES) + 1))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.exit(1, f'FAIL: {exc}\n')
    print(f"Checked 30 GainStep {'payloads against reference hashes' if args.private_deltas else 'metadata rows (no payloads supplied)'}; no DSP writes.")


if __name__ == '__main__':
    main()
