"""Validate resolved, time-aligned acoustic bands from the FullIO replay."""

import math


def band_gate(frequencies, changes):
    """Return (frequency, block, delta dB) for the worst resolved band.

    Frequencies alternate FL and FR in the stimulus. Do not average one
    speaker's loss away, or pass when one speaker could not be measured.
    """
    if changes.keys() - set(frequencies):
        raise ValueError('unexpected tone band')
    for lane in (0, 1):
        if not any(f in changes for f in frequencies[lane::2]):
            raise ValueError(f'no coherent tone for {("FL", "FR")[lane]}')
    counts = {len(blocks) for blocks in changes.values()}
    if len(counts) != 1 or 0 in counts:
        raise ValueError('missing or unaligned 10-second blocks')
    readings = [(f, i, delta) for f, blocks in changes.items()
                for i, delta in enumerate(blocks)]
    if not all(math.isfinite(delta) for _, _, delta in readings):
        raise ValueError('non-finite band measurement')
    return min(readings, key=lambda row: row[2])
