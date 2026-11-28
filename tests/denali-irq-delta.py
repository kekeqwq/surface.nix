#!/usr/bin/env python3
import runpy
import unittest
from pathlib import Path

compare = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/denali-irq-delta.py'))['compare']


class InterruptDeltaTest(unittest.TestCase):
    def test_deltas_reject_remap_rollback_and_missing_irqs(self):
        before = '''           CPU0 CPU1
 11:       8    4   GICv3     27 Level arch_timer
 22:       0    1   GICv3     51 Edge old
 23:       3    2   GICv3     52 Level x
 24:       2    2   GICv3     53 Level y
IPI0:      2   11   Rescheduling interrupts
'''
        after = '''           CPU0 CPU1
 11:      10    9   GICv3     27 Level arch_timer
 22:       0   15   GICv3     51 Edge new
 23:       1    8   GICv3     52 Level x
'''
        r = compare(before, after)
        self.assertEqual(r['changes'], [{
            'irq': 11, 'label': 'GICv3 27 Level arch_timer', 'delta': 7,
            'per_cpu': {'CPU0': 2, 'CPU1': 5},
        }])
        self.assertEqual([entry['status'] for entry in r['skipped']],
                         ['missing_or_remapped', 'counter_decreased', 'missing_or_remapped'])

    def test_mismatched_cpu_columns(self):
        with self.assertRaises(ValueError):
            compare('CPU0 CPU1\n', 'CPU0 CPU2\n')


if __name__ == '__main__':
    unittest.main()
