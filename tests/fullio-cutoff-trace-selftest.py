#!/usr/bin/env python3
"""Synthetic parser/checker tests; these figures are not hardware limits."""
from pathlib import Path
from runpy import run_path
import tempfile

load = run_path(str(Path(__file__).with_name('fullio-cutoff-trace.py')))
limits = dict(sdn_low=.2, sdn_high=1, off_v=.1, on_v=1, fault_to_pin_us=30,
              pin_to_off_us=30, max_gap_us=10, pre_us=20, post_us=20)
lines = [
    '0,0,1,1.2,1.2,2,2', '10,0,1,1.2,1.2,2,2', '20,0,1,1.2,1.2,2,2',
    '30,1,0,1.2,1.2,2,2', '40,1,0,0,1.2,2,2', '50,1,0,0,0,0,2',
    '60,1,0,0,0,0,0', '70,0,1,0,0,0,0', '80,0,1,0,0,0,0', '90,0,1,0,0,0,0',
]

with tempfile.TemporaryDirectory() as d:
    path = Path(d) / 'synthetic.csv'

    def run(rows, **kw):
        path.write_text(','.join(load['FIELDS']) + '\n' + '\n'.join(rows) + '\n')
        return load['verify'](load['trace'](path), **(limits | kw))

    assert run(lines) == [(20, 20), (30, 20)]
    cases = (
        ('acquisition gap', lines[:4] + lines[5:], {}),
        ('returned', lines[:-1] + ['90,0,1,0,0,0,2'], {}),
        ('reasserted high', lines[:-1] + ['90,0,1,0,1.2,0,0'], {}),
        ('before paired shutdown', lines[:6] + ['60,0,1,0,0,0,2'] + lines[7:], {}),
        ('recovery', lines[:8], {}),
        ('demonstrably active', ['0,0,1,1.2,1.2,0,2'] + lines[1:], {}),
        ('exceeded', lines, dict(fault_to_pin_us=29)),
        ('went quiet before SD_N', lines[:3] + ['30,1,0,1.2,1.2,0,2'] + lines[4:], {}),
        ('share one sample', lines[:4] + ['40,1,0,0,1.2,0,2'] + lines[5:], {}),
        ('non-finite', lines[:-1] + ['90,0,1,0,0,nan,0'], {}),
    )
    for expected, samples, overrides in cases:
        try:
            run(samples, **overrides)
        except ValueError as err:
            assert expected in str(err), err
        else:
            raise AssertionError(f'accepted invalid trace: expected {expected}')
    autonomous = [','.join((*v[:3], '1.2', '1.2', *v[5:])) for v in (r.split(',') for r in lines)]
    auto_limits = {k: v for k, v in limits.items() if k not in {'sdn_low', 'fault_to_pin_us', 'pin_to_off_us'}}
    auto_limits['fault_to_off_us'] = 40

    def run_auto(rows, **kw):
        path.write_text(','.join(load['FIELDS']) + '\n' + '\n'.join(rows) + '\n')
        return load['verify_without_sdn'](load['trace'](path), **(auto_limits | kw))

    assert run_auto(autonomous) == [30, 40]
    for reason, samples, overrides in (
        ('not continuously deasserted', lines, {}),
        ('marked fault', autonomous[:3] + ['30,0,0,1.2,1.2,2,2'] + autonomous[4:], {}),
        ('returned', autonomous[:-1] + ['90,0,1,1.2,1.2,0,2'], {}),
        ('exceeded', autonomous, {'fault_to_off_us': 39}),
        ('before paired shutdown', autonomous[:6] + ['60,0,1,1.2,1.2,0,2'] + autonomous[7:], {}),
    ):
        try:
            run_auto(samples, **overrides)
        except ValueError as err:
            assert reason in str(err), err
        else:
            raise AssertionError(f'no-SD_N mode accepted invalid trace: expected {reason}')
    control_cols = ','.join(load['FIELDS'] + load['CONTROL_FIELDS']) + '\n'
    controls = [r + ',4,4,0' for r in autonomous]
    path.write_text(control_cols + '\n'.join(controls) + '\n')
    assert load['verify_without_sdn'](load['trace'](path, 3.5), **auto_limits) == [30, 40]
    for suffix, reason in ((',3.4,4,0', 'supply fell'), (',4,3.4,0', 'supply fell'),
                           (',4,4,1', 'software mute'), (',4,4,-1', 'unverified software mute'),
                           (',4,4,nan', 'non-finite')):
        bad = controls[:4] + [autonomous[4] + suffix] + controls[5:]
        path.write_text(control_cols + '\n'.join(bad) + '\n')
        try:
            load['verify_without_sdn'](load['trace'](path, 3.5), **auto_limits)
        except ValueError as err:
            assert reason in str(err), err
        else:
            raise AssertionError(f'accepted invalid control: expected {reason}')
print('Cutoff trace checker: both modes accept complete traces and reject 20 invalid cases.')
