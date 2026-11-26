#!/usr/bin/env python3
"""Create an offline diagnostic topology, moving only logger 0x467a to SP input.

No deploy support. This changes the ADSP graph and is not an audio fix.
Input must be the exact compiled geocausa 3232e1d Golden topology.
"""
import argparse
import hashlib
import struct
from pathlib import Path
from runpy import run_path

GOLDEN = 'e7bb06a03e7bd9b869825a51775355a6743477d1579d78eb09fad5881cfb20f0'
LOGGER = 'sp11.data_logging.467a'
MIXER = 'sp11.chmixer.402c'
SP = 'sp11.speaker_protection.4027'
MSIIR = 'sp11.msiir.48a1'
SAL = 'sp11.sal.4001'


def replace_once(data, before, after):
    if len(before) != len(after) or data.count(before) != 1:
        raise ValueError('ambiguous or differently sized transformation')
    return data.replace(before, after, 1)


def retarget(golden):
    if hashlib.sha256(golden).hexdigest() != GOLDEN:
        raise ValueError('expected byte-exact Golden v19c topology')
    helpers = run_path(str(Path(__file__).with_name('fullio-topology.py')))
    payload = helpers['widget_payload']
    words = helpers['word_tuple']
    out = golden
    edits = {
        # The replacement logger must live within the SP container. Copy
        # its exact subgraph/container tuples, not its calibration data.
        LOGGER: {2: (2952790143, 2952790017), 100: (3758096660, 3758096385),
                 101: (184553472, 184553473), 103: (1, 4),
                 207: (12, 2), 209: (0x4001, 0x4027)},
        MSIIR: {207: (2, 12), 209: (0x467A, 0x4001)},
        MIXER: {209: (0x4027, 0x467A)},
    }
    original = {}
    for name, changes in edits.items():
        old = payload(golden, name)
        changed = old
        for token, (a, b) in changes.items():
            changed = replace_once(changed, struct.pack('<II', token, a), struct.pack('<II', token, b))
        original[name] = (old, changed)
        out = replace_once(out, old, changed)
    for name in (SP, SAL, 'sp11.data_logging.4003'):
        if payload(out, name) != payload(golden, name):
            raise ValueError(f'unexpected {name} change')

    def route(source, sink):
        return struct.pack('<44s44s44s', sink.encode(), b'', source.encode())

    links = ((MSIIR, LOGGER, MSIIR, SAL), (LOGGER, SAL, LOGGER, SP), (MIXER, SP, MIXER, LOGGER))
    for a, b, c, d in links:
        out = replace_once(out, route(a, b), route(c, d))
    old = out
    for a, b, c, d in links:
        old = replace_once(old, route(c, d), route(a, b))
    for a, b in original.values():
        old = replace_once(old, b, a)
    if old != golden:
        raise ValueError('topology round trip changed unrelated bytes')
    a = payload(out, LOGGER)
    b = payload(out, SP)
    for _ in range(2):
        row_a, i = words(a, 0)
        row_b, j = words(b, 0)
        if row_a != row_b:
            raise ValueError('diagnostic logger outside the SP container')
        a, b = a[i:], b[j:]
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('golden', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    out = retarget(a.golden.read_bytes())
    with a.output.open('xb') as f:
        f.write(out)
    print(hashlib.sha256(out).hexdigest())


if __name__ == '__main__':
    main()
