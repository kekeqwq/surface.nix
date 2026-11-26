#!/usr/bin/env python3
"""Exercise the fixed reference endpoint transaction helper end to end."""
from pathlib import Path
import hashlib
import json
import math
import os
import stat
import struct
import subprocess
import sys
import tempfile

script = Path(__file__).resolve().parent.parent / 'scripts' / 'fullio-reference-volume-once.py'
Q28_ONE = 1 << 28


def expected_q28(db: float) -> int:
    db = max(-75.0, min(0.0, float(db)))
    q16 = round(db * 65536.0)
    quarter_index = ((-q16) >> 14) if q16 < 0 else 0
    return max(0, min(Q28_ONE, round((10.0 ** (-(quarter_index / 4.0) / 20.0)) * Q28_ONE)))


def make_table(path: Path, corrupt_step: int | None = None) -> dict[int, bytes]:
    rows, payloads = [], {}
    for step in range(1, 31):
        size = 272 if step in (3, 9, 24) else 216
        delta = struct.pack('<I', step) * (size // 4)
        delta = delta[:size]
        digest = hashlib.sha256(delta).hexdigest()
        if corrupt_step == step:
            digest = '00' * 32
        payloads[step] = delta
        rows.append({'gain_step': step, 'serialized_hex': delta.hex(),
                     'serialized_sha256': digest})
    path.write_text(json.dumps({'format': 'test', 'steps': rows}))
    return payloads


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        table = tmp / 'deltas.json'
        payloads = make_table(table)
        listing = tmp / 'listing.txt'
        listing.write_text(
            "numid=11,iface=CARD,name='SP11 Windows Volume Transaction'\n"
            "numid=12,iface=CARD,name='SP11 Windows Volume Only'\n"
            "numid=13,iface=CARD,name='SP11 Windows Endpoint Mute'\n"
        )
        amixer = tmp / 'amixer'
        amixer.write_text('#!/bin/sh\ncat "$(dirname "$0")/listing.txt"\n')
        amixer.chmod(amixer.stat().st_mode | stat.S_IEXEC)
        log = tmp / 'writes.log'
        tlv = tmp / 'tlv_write'
        tlv.write_text('#!/bin/sh\nprintf "%s %s\\n" "$2" "$3" >> "%s"\n' % ('%s', '%s', log)
                       + 'if [ "$2" = "$FAIL_NUMID" ]; then exit 1; fi\n')
        tlv.chmod(tlv.stat().st_mode | stat.S_IEXEC)

        def run(*extra, fail_numid='', check=True):
            return subprocess.run(
                [sys.executable, str(script), '--card', 'hw:0', '--amixer', str(amixer),
                 '--tlv-write', str(tlv), '--delta-table', str(table), *extra],
                capture_output=True, text=True, check=check,
                env={**os.environ, 'FAIL_NUMID': fail_numid})

        for db, mute in ((-12.0, 'off'), (0.0, 'on'), (0.0, 'off'), (3.0, 'off'),
                         (-75.0, 'off'), (-3.25, 'off')):
            log.write_text('')
            run('--endpoint-db', str(db), '--mute', mute)
            lines = log.read_text().splitlines()
            assert len(lines) == 2, lines
            q28 = expected_q28(db)
            steps = [0x00000000, 0x016d0e6f, 0x018dfa93, 0x01b1dece, 0x01d8ffab, 0x0203a7e6,
                     0x023228f6, 0x0264dbae, 0x029c20e0, 0x02d8621c, 0x031a1276, 0x0361af63,
                     0x03afc1a9, 0x0404de62, 0x0461a81c, 0x04c6d00e, 0x0535176a, 0x05ad50ce,
                     0x063061d6, 0x06bf44d5, 0x075b0ab0, 0x0804dce8, 0x08bdffd3, 0x0987d507,
                     0x0a63ddfe, 0x0b53bef5, 0x0c59420f, 0x0d765ac1, 0x0ead2988, 0x10000000]
            step = min(range(30), key=lambda i: (abs(steps[i] - q28), i)) + 1
            numid, payload = lines[0].split(' ', 1)
            assert numid == '11', lines
            assert bytes.fromhex(payload) == struct.pack('<II', q28, q28) + payloads[step]
            numid, payload = lines[1].split(' ', 1)
            assert numid == '13'
            assert bytes.fromhex(payload) == struct.pack('<I', 1 if mute == 'on' else 0)
            assert 'gainstep=%d' % step in run('--endpoint-db', str(db), '--dry-run').stdout

        for fail_numid, writes, stage in [('11', ['11'], 'gain/GainStep'),
                                          ('13', ['11', '13'], 'unmute')]:
            log.write_text('')
            result = run('--endpoint-db', '0', fail_numid=fail_numid, check=False)
            assert result.returncode != 0
            assert [x.split()[0] for x in log.read_text().splitlines()] == writes
            assert f'Endpoint {stage}: submit' in result.stdout.splitlines()[-1]
            assert f'Endpoint {stage}: ACK' not in result.stdout

        log.write_text('')
        run('--volume-only', '--endpoint-db', '-12', '--mute', 'on')
        lines = log.read_text().splitlines()
        assert lines[0].split(' ', 1)[0] == '12'
        assert bytes.fromhex(lines[0].split(' ', 1)[1]) == struct.pack('<II', expected_q28(-12.0),
                                                                      expected_q28(-12.0))
        assert lines[1].split(' ', 1)[0] == '13'

        # Diagnostic reassertion must not touch the mute selector at all,
        # even before the write: with 'keep' its control may be unavailable.
        listing.write_text('\n'.join(listing.read_text().splitlines()[:2]) + '\n')
        for volume_only, numid in ((True, '12'), (False, '11')):
            log.write_text('')
            extra = ['--volume-only'] if volume_only else []
            run('--endpoint-db', '-3', '--mute', 'keep', *extra)
            gain = struct.pack('<II', expected_q28(-3), expected_q28(-3))
            if not volume_only:
                gain += payloads[26]
            assert log.read_text().splitlines() == [f'{numid} {gain.hex()}']

        payloads = make_table(table, corrupt_step=7)
        failed = subprocess.run(
            [sys.executable, str(script), '--card', 'hw:0', '--amixer', str(amixer),
             '--tlv-write', str(tlv), '--delta-table', str(table), '--dry-run'],
            capture_output=True, text=True)
        assert failed.returncode != 0 and 'delta hash' in failed.stderr

        payloads = make_table(table)
        bad = json.loads(table.read_text())
        bad['steps'] = bad['steps'][:29]
        table.write_text(json.dumps(bad))
        failed = subprocess.run(
            [sys.executable, str(script), '--card', 'hw:0', '--amixer', str(amixer),
             '--tlv-write', str(tlv), '--delta-table', str(table), '--dry-run'],
            capture_output=True, text=True)
        assert failed.returncode != 0 and 'exactly 30' in failed.stderr

    print('Reference endpoint transaction: q28/step selection, volume-then-mute order and table validation passed.')


if __name__ == '__main__':
    main()
