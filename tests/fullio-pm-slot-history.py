#!/usr/bin/env python3
"""Validate interpretation of raw Denali slot transitions, without hardware."""
from pathlib import Path
from runpy import run_path

analyze = run_path(str(Path(__file__).with_name('fullio-pm-replay-trace.py')))['summarize_slots']


def trace(*transitions):
    return '\n'.join(
        f'[{t:11.6f}] surface kernel: qcom-soundwire {device}: FullIO PM transition enum: '
        f'slaves={old:#010x}->{new:#010x}'
        for t, device, old, new in transitions
    )


swr = '6b10000.soundwire'
assert not analyze(trace((1, swr, 0, 1), (1.1, swr, 1, 5), (1.2, swr, 5, 0x14)))
assert not analyze(trace((1, swr, 0x14, 0x18), (1.1, swr, 0x18, 0x14)))
assert not analyze(trace((1, '6b20000.soundwire', 0x14, 0)))
loss = (44.680577, swr, 0x14, 0)
slot0 = (44.689302, swr, 0, 1)
lines = analyze(trace(loss, slot0))
assert len(lines) == 2 and 'slot loss' in lines[0] and 'No paired' in lines[1]
assert lines == analyze(trace(loss, slot0, (9.72, swr, 5, 0x14), loss, slot0))
lines = analyze(trace(loss, slot0, (44.7, swr, 1, 5), (44.704, swr, 5, 0x14)))
assert len(lines) == 2 and '23.423 ms' in lines[1] and 'retention unproven' in lines[1]
assert 'No paired' in analyze(trace(loss, (44.7, swr, 0, 0x18)))[-1]
print('Slot history: initial enumeration, ALERT, slot 0, and paired reattachment are distinguished.')
