#!/usr/bin/env python3
"""Exercise the real keeper loop without ALSA, DSP, or a Surface."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Keeper(unittest.TestCase):
    def run_keeper(self, triggers, results, *endpoint, expected_db='-3'):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            for name, lines in [('triggers', triggers), ('results', results)]:
                (work / name).write_text(''.join(f'{line}\n' for line in lines))
            for name, code in {
                'awk': 'head -n1 "$WORK/triggers"\ntail -n+2 "$WORK/triggers" > "$WORK/next"\nmv "$WORK/next" "$WORK/triggers"',
                'sleep': ':',
                'python3': 'printf "%s\\n" "$*" >> "$WORK/calls"\nrc=$(head -n1 "$WORK/results")\ntail -n+2 "$WORK/results" > "$WORK/next"\nmv "$WORK/next" "$WORK/results"\nexit "${rc:-2}"',
            }.items():
                path = work / name
                path.write_text('#!/bin/sh\n' + code + '\n')
                path.chmod(0o700)
            result = subprocess.run(['bash', str(ROOT / 'scripts/fullio-endpoint-keeper.sh'),
                                     'unused-amixer', 'unused-volume', *endpoint], text=True, capture_output=True,
                                    env={**os.environ, 'WORK': str(work),
                                         'PATH': f'{work}:{os.environ["PATH"]}'}, timeout=5)
            calls = (work / 'calls').read_text().splitlines()
            self.assertEqual(result.returncode, 1, result)
            for call in calls:
                self.assertIn(f'--endpoint-db {expected_db} --mute off', call)
            return result, len(calls)

    def test_ack_loss_does_not_retry_even_if_trigger_remains_running(self):
        result, count = self.run_keeper(['1.1'] * 12, [1, 0])
        self.assertEqual(count, 1)
        self.assertIn('arm failed', result.stderr)
        self.assertNotIn('Endpoint armed', result.stdout)

    def test_success_same_epoch_not_written_again_next_epoch_armed(self):
        result, count = self.run_keeper(['1.1'] * 5 + ['2.2'] * 2, [0, 1])
        self.assertEqual(count, 2)
        self.assertEqual(result.stdout.count('Endpoint armed for trigger_time=1.1'), 1)
        self.assertIn('arm failed for trigger_time=2.2', result.stderr)

    def test_trigger_replaced_before_submit_is_skipped(self):
        result, count = self.run_keeper(['1.1', '2.2', '2.2', '2.2'], [1])
        self.assertEqual(count, 1)
        self.assertNotIn('1.1', result.stdout)
        self.assertIn('arm failed for trigger_time=2.2', result.stderr)

    def test_trigger_replaced_during_arm_is_not_logged_as_verified(self):
        result, count = self.run_keeper(['1.1', '1.1', '2.2'], [0])
        self.assertEqual(count, 1)
        self.assertIn('trigger changed during arm', result.stderr)
        self.assertNotIn('Endpoint armed', result.stdout)

    def test_explicit_unity_uses_same_fail_closed_transaction(self):
        result, count = self.run_keeper(['1.1'] * 5, [1], '0', expected_db='0')
        self.assertEqual(count, 1)
        self.assertIn('arm failed', result.stderr)

    def test_invalid_endpoint_is_rejected_before_loop(self):
        result = subprocess.run(['bash', str(ROOT / 'scripts/fullio-endpoint-keeper.sh'),
                                 'unused-amixer', 'unused-volume', '1'], capture_output=True,
                                timeout=2)
        self.assertEqual(result.returncode, 2)

    def test_service_does_not_restart_failed_keeper(self):
        source = (ROOT / 'modules/denali/fullio-reference-render.nix').read_text()
        service = source.split('fullio-endpoint-keeper = {', 1)[1].split('};', 1)[0]
        self.assertIn('Restart = "no";', service)


if __name__ == '__main__':
    unittest.main()
