#!/usr/bin/env python3
"""Check the probe's scalar metrics without PipeWire or a microphone."""
from array import array
from io import BytesIO, StringIO
import json
import math
from pathlib import Path
import runpy
import tempfile

probe = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/fullio-level-probe.py'))
rate = probe['RATE']
levels = probe['Levels'](probe['tone_basis']((203, 206, 449)))

# Misaligned reads and windows straddling the basis period must not shift
# channels, drop frames or change coherent amplitude.
frames = array('h', (round(1000 * math.sin(math.tau * freq * i / rate))
                     for i in range(3 * rate + 217) for freq in (203, 206))).tobytes()
start = 0
for length, chunk in ((rate + 217, 8195), (2 * rate, 13731)):
    end = start + length * 4
    for offset in range(start, end, chunk):
        levels.add(frames[offset:min(offset + chunk, end)])
    start = end
    data = levels.take()
    assert data['frames'] == length and data['peak'] == [1000, 1000], data
    assert all(abs(x - 1000) < 1 for x in (data['tone_amplitudes'][203][0], data['tone_amplitudes'][206][1])), data
    assert all(x < 5 for x in (*data['tone_amplitudes'][449], data['tone_amplitudes'][203][1],
                               data['tone_amplitudes'][206][0])), data
assert levels.take() == {'frames': 0, 'rms_dbfs': [None, None], 'peak': [0, 0]}
phase_steps = probe['Levels'](probe['tone_basis']((1000,)))
for i in range(4):
    samples = array('h', (round((-1)**i * 500 * math.cos(math.tau * 1000 * j / rate))
                          for j in range(rate // 4) for _ in range(2)))
    phase_steps.add(samples.tobytes())
sample = phase_steps.take()
assert sample['tone_amplitudes'][1000] == [0., 0.], sample
assert all(abs(a - 500) < 1 for a in sample['short_tone_amplitudes'][1000]), sample
plain = probe['Levels']()
plain.add(array('h', [-32768, 0, 0, 400]).tobytes())
assert plain.take() == {'frames': 2, 'rms_dbfs': [-3.01, -41.28], 'peak': [32768, 400]}

# Transient windows have an independent stream cursor, even when a full
# block spans both a misaligned pipe read and an earlier metric report.
block = probe['TRANSIENT_FRAMES']
levels = probe['Levels'](transient=True)
samples = array('h', [0] * (4 * block + 2))
samples[0] = -32768
samples[2 * block - 1] = 600
samples[2 * block] = 210
samples[4 * block - 1] = -700
samples[4 * block] = 100
raw = samples.tobytes()
levels.add(raw[:4 * block - 1], received=1.)
assert levels.take()['peak_blocks'] == []
levels.add(raw[4 * block - 1:4 * block + 1], received=2.)
assert levels.take()['peak_blocks'] == [[block, 2., 32768, 600]]
levels.add(raw[4 * block + 1:], received=3.)
assert levels.take()['peak_blocks'] == [[2 * block, 3., 210, 700]]
assert levels.take()['peak_blocks'] == []  # final partial block not reported
with tempfile.TemporaryDirectory() as tmp:
    status = Path(tmp) / 'status'
    status.write_text('state: RUNNING\ntrigger_time: 18.123\nhw_ptr      : 100\n')
    assert probe['pcm_state'](status) == {'state': 'RUNNING', 'trigger_time': '18.123', 'hw_ptr': '100'}
    status.write_text('closed\n')
    assert probe['pcm_state'](status) == {'state': 'closed'}
external = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/fullio-external-levels.py'))
try:
    external['collect'](BytesIO(bytes(5 * rate * 4)), StringIO(), 5)
except ValueError as exc:
    assert 'all-zero external input' in str(exc), exc
else:
    raise AssertionError('all-zero external capture passed')
output = StringIO()
external['collect'](BytesIO(frames[:4*rate] * 5), output, 5)
rows = list(map(json.loads, output.getvalue().splitlines()))
assert len(rows) == 5 and all(abs(r['tone_amplitudes']['203'][0] - 1000) < 1 for r in rows)
print('Scalar levels handle fragments and window boundaries; external zero input fails closed.')
