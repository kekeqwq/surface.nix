#!/usr/bin/env python3
"""Offline checks for per-speaker/per-band replay admission."""

import unittest

from fullio_replay_bands import band_gate


FREQUENCIES = ('203', '206', '449', '454', '1009', '1017')


class Bands(unittest.TestCase):
    def test_stable_duplex_measurement(self):
        self.assertEqual(band_gate(FREQUENCIES, {'203': [0, -1], '206': [0, -.6]}),
                         ('203', 1, -1))

    def test_one_speaker_cannot_hide_behind_other_bands(self):
        readings = {f: [0, 0, 0] for f in FREQUENCIES}
        readings['454'][-1] = -6
        self.assertEqual(band_gate(FREQUENCIES, readings), ('454', 2, -6))

    def test_same_lane_tones_do_not_prove_stereo(self):
        for lane in (0, 1):
            with self.subTest(lane=lane), self.assertRaisesRegex(ValueError, 'no coherent tone'):
                band_gate(FREQUENCIES, {f: [0] for f in FREQUENCIES[lane::2]})

    def test_no_silent_truncation(self):
        for lengths in ((0, 0), (1, 0), (1, 2)):
            with self.subTest(lengths=lengths), self.assertRaisesRegex(ValueError, 'blocks'):
                band_gate(FREQUENCIES, {f: [0] * n for f, n in zip(FREQUENCIES, lengths)})

    def test_non_finite_is_not_a_pass(self):
        with self.assertRaisesRegex(ValueError, 'non-finite'):
            band_gate(FREQUENCIES, {'203': [0], '206': [float('nan')]})

    def test_threshold_is_not_rounded_before_comparison(self):
        self.assertLess(band_gate(FREQUENCIES, {'203': [-3.004], '206': [0]})[2], -3)


if __name__ == '__main__':
    unittest.main()
