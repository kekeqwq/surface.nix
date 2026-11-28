#!/usr/bin/env python3
"""Verify that suspend, residency and invalid evidence stay separate."""

from copy import deepcopy
from pathlib import Path
import runpy
import unittest

script = Path(__file__).resolve().parents[1] / 'scripts/denali-suspend-readout.py'
api = runpy.run_path(str(script))
compare, snapshots, OFFSET, STATS = (api[key] for key in ('compare', 'snapshots', 'OFFSET', 'STATS'))


def sample(index):
    text = f'''utc=2026-11-29T01:0{index}:00Z
boot_id=same-boot
release=test-kernel
{STATS}success={index}
{STATS}fail=0
{OFFSET}={index * 10_000_000_000}
/sys/class/power_supply/BAT1/energy_now=38128000
/sys/class/power_supply/ADP1/online=1
'''
    for mode in ('cxsd', 'aosd', 'ddr'):
        text += f'''--- /sys/kernel/debug/qcom_stats/{mode} ---
Count: 0
Last Entered At: 0
Last Exited At: 0
Accumulated Duration: 0
'''
    return text


class ReadoutTest(unittest.TestCase):
    def setUp(self):
        self.before, self.after = snapshots(sample(0) + sample(1))

    def test_os_sleep_with_zero_residency(self):
        result = compare(self.before, self.after)
        self.assertEqual(result['os_suspended_ns'], 10_000_000_000)
        self.assertEqual(result['residency'], 'no_counter_advance')
        self.assertEqual(result['ADP1_online'], ['1', '1'])

    def test_counter_advance(self):
        entry = self.after['counters']['qcom_stats', 'cxsd']
        entry.update({'Count': 1, 'Accumulated Duration': 100})
        self.assertEqual(compare(self.before, self.after)['residency'], 'counter_advance')

    def test_quantity_reset_not_zero(self):
        self.before['counters']['qcom_stats', 'cxsd']['Count'] = 5
        result = compare(self.before, self.after)
        self.assertEqual(result['residency'], 'inconclusive')
        self.assertEqual(result['modes']['cxsd']['status'], 'counter_reset_or_wrap')

    def test_missing_or_truncated(self):
        del self.after['counters']['qcom_stats', 'cxsd']
        del self.after['counters']['qcom_stats', 'ddr']['Accumulated Duration']
        result = compare(self.before, self.after)
        self.assertEqual(result['residency'], 'inconclusive')
        self.assertEqual(result['modes']['cxsd']['status'], 'missing')
        self.assertEqual(result['modes']['ddr']['status'], 'unreadable')

    def test_provider_mismatch(self):
        self.after['counters']['rpmh_stats', 'aosd'] = self.after['counters'].pop(('qcom_stats', 'aosd'))
        result = compare(self.before, self.after)
        self.assertEqual(result['residency'], 'inconclusive')
        self.assertEqual(result['modes']['aosd']['status'], 'ambiguous_source')

    def test_wrong_boot_or_cycle(self):
        for key, val in [('boot_id', 'new-boot'), (STATS+'success', '2'), (STATS+'fail', '1'), (OFFSET, '0')]:
            with self.subTest(key=key):
                invalid = deepcopy(self.after)
                invalid['values'][key] = val
                with self.assertRaises(ValueError):
                    compare(self.before, invalid)


if __name__ == '__main__':
    unittest.main()
