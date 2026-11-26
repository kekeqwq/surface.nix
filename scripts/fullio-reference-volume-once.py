#!/usr/bin/env python3
"""Apply one fixed reference endpoint volume/mute transaction.

Drives the FullIO endpoint controls introduced by
audioreach-fullio.patch: the pinned v19c final
VOL_CTRL (Q28 per channel) followed by its exact GainStep calibration
delta, then the reviewed mute selector. This arms the protected route
for a controlled listening check; it does not run the UbiG/Stage-B live
volume service and writes no DSP gain outside the pinned inventory.

Selection semantics follow the reviewed reference helpers: qcadcm
quarter-dB quantization and GetGainTableStepFrmQ28Gain nearest-neighbor
matching (sp11_windows_volume_transaction_sync.py at geocausa 3232e1d).
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

Q28_ONE = 1 << 28

# GetGainTableStepFrmQ28Gain gain table (30 entries), from the reviewed
# sp11_msiir_volume_sync.py at 3232e1d.
Q28_GAIN_STEPS = (
    0x00000000,
    0x016d0e6f,
    0x018dfa93,
    0x01b1dece,
    0x01d8ffab,
    0x0203a7e6,
    0x023228f6,
    0x0264dbae,
    0x029c20e0,
    0x02d8621c,
    0x031a1276,
    0x0361af63,
    0x03afc1a9,
    0x0404de62,
    0x0461a81c,
    0x04c6d00e,
    0x0535176a,
    0x05ad50ce,
    0x063061d6,
    0x06bf44d5,
    0x075b0ab0,
    0x0804dce8,
    0x08bdffd3,
    0x0987d507,
    0x0a63ddfe,
    0x0b53bef5,
    0x0c59420f,
    0x0d765ac1,
    0x0ead2988,
    0x10000000,
)
assert len(Q28_GAIN_STEPS) == 30


def qcadcm_q28_from_db(db: float) -> int:
    if db != db or db in (float('inf'), float('-inf')):
        raise ValueError('non-finite endpoint dB')
    db = max(-75.0, min(0.0, float(db)))
    q16 = round(db * 65536.0)
    quarter_index = ((-q16) >> 14) if q16 < 0 else 0
    effective_db = -(quarter_index / 4.0)
    return max(0, min(Q28_ONE, round((10.0 ** (effective_db / 20.0)) * Q28_ONE)))


def select_ckv_step_q28(q28_gain: int) -> int:
    q = max(0, min(Q28_ONE, int(q28_gain)))
    index = min(range(len(Q28_GAIN_STEPS)), key=lambda i: (abs(Q28_GAIN_STEPS[i] - q), i))
    return index + 1


def load_deltas(path: Path) -> list[bytes]:
    data = json.loads(path.read_bytes())
    rows = data.get('steps')
    if not isinstance(rows, list) or len(rows) != 30:
        raise ValueError('gainstep table must contain exactly 30 steps')
    deltas = []
    for expected_step, row in enumerate(rows, 1):
        if row.get('gain_step') != expected_step:
            raise ValueError('gainstep rows are not sequential')
        delta = bytes.fromhex(row['serialized_hex'])
        expected_size = 272 if expected_step in (3, 9, 24) else 216
        if len(delta) != expected_size:
            raise ValueError(f'invalid GainStep {expected_step} delta size')
        if hashlib.sha256(delta).hexdigest() != row.get('serialized_sha256'):
            raise ValueError(f'invalid GainStep {expected_step} delta hash')
        deltas.append(delta)
    return deltas


def find_named_control_numid(name: str, card: str, amixer: str) -> int:
    # amixer takes a card index/name; snd_ctl_open takes a CTL device.
    amixer_card = card.removeprefix('hw:')
    listing = subprocess.run([amixer, '-c', amixer_card, 'controls'], capture_output=True,
                             text=True, check=True).stdout
    for line in listing.splitlines():
        fields = dict(part.split('=', 1) for part in line.split(',') if '=' in part)
        if fields.get('name', '').strip("'") == name:
            return int(fields['numid'])
    raise LookupError(f'control not found: {name}')


def write_tlv(helper: Path, card: str, numid: int, blob: bytes, dry_run: bool,
              *, stage: str) -> None:
    if dry_run:
        print(f'dry-run: numid={numid} payload={len(blob)} bytes sha256='
              f'{hashlib.sha256(blob).hexdigest()}')
        return
    print(f'Endpoint {stage}: submit', flush=True)
    done = subprocess.run([str(helper), card, str(numid), blob.hex()],
                          capture_output=True, text=True)
    output = (done.stdout + done.stderr).strip()
    if done.returncode:
        raise RuntimeError(output or f'tlv_write rc={done.returncode}')
    print(f'Endpoint {stage}: ACK ({output})', flush=True)


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--card', default='hw:0')
    cli.add_argument('--amixer', default='amixer')
    cli.add_argument('--tlv-write', type=Path, required=True)
    cli.add_argument('--delta-table', type=Path, required=True)
    cli.add_argument('--endpoint-db', type=float, default=-12.0,
                     help='fixed Windows endpoint position (default: the reviewed -12.0 dB)')
    cli.add_argument('--mute', choices=('off', 'on', 'keep'), default='off',
                     help='keep leaves the existing endpoint mute state untouched')
    cli.add_argument('--volume-only', action='store_true',
                     help='skip the GainStep calibration delta')
    cli.add_argument('--dry-run', action='store_true')
    args = cli.parse_args()

    if not args.tlv_write.exists():
        raise SystemExit(f'missing tlv_write helper: {args.tlv_write}')
    q28 = qcadcm_q28_from_db(args.endpoint_db)
    step = select_ckv_step_q28(q28)
    deltas = load_deltas(args.delta_table)
    print(f'endpoint_db={args.endpoint_db:g} q28={q28} (0x{q28:08x}) gainstep={step}')

    control = 'SP11 Windows Volume Only' if args.volume_only else 'SP11 Windows Volume Transaction'
    volume_numid = find_named_control_numid(control, args.card, args.amixer)
    mute_numid = None if args.mute == 'keep' else find_named_control_numid(
        'SP11 Windows Endpoint Mute', args.card, args.amixer)

    volume = struct.pack('<II', q28, q28)
    if not args.volume_only:
        volume += deltas[step - 1]
    write_tlv(args.tlv_write, args.card, volume_numid, volume, args.dry_run,
              stage='gain' if args.volume_only else 'gain/GainStep')
    if mute_numid is not None:
        # Never update mute if the preceding volume transaction failed.
        write_tlv(args.tlv_write, args.card, mute_numid,
                  struct.pack('<I', 1 if args.mute == 'on' else 0), args.dry_run,
                  stage='mute' if args.mute == 'on' else 'unmute')
    return 0


if __name__ == '__main__':
    sys.exit(main())
