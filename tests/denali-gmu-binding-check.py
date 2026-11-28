#!/usr/bin/env python3
"""Exercise the read-only GMU acceptance gate against synthetic sysfs."""

import runpy
import tempfile
from pathlib import Path

namespace = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/denali-gmu-binding-check.py'))
GCC, GPUCC, GMU, GPU, ICC, CRYPTO, LINK = (namespace[k] for k in (
    'GCC', 'GPUCC', 'GMU', 'GPU', 'ICC', 'CRYPTO', 'LINK',
))
inspect, verify = namespace['inspect'], namespace['verify']

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    for name, drv in {
        GCC: 'gcc-x1e80100', GPUCC: 'gpucc-x1e80100', GMU: None,
        GPU: 'adreno', **dict.fromkeys(ICC, 'qnoc-x1e80100'),
    }.items():
        node = root / name
        node.mkdir()
        if drv:
            (node / 'driver').symlink_to('/fixture/drivers/' + drv)
        if name in ICC:
            (node / 'state_synced').write_text('1\n')
        if name in (GCC, GPUCC):
            (node / 'state_synced').write_text('0\n')
            for link, status in ((LINK, 'available'), (f'consumer:platform:{GPU}', 'active')):
                (node / link).mkdir()
                (node / link / 'status').write_text(status + '\n')
    assert not verify(inspect(root), bound=False)
    assert verify(inspect(root), bound=True)

    (root / GMU / 'driver').symlink_to('/fixture/drivers/adreno_gmu')
    for node in (root / GCC, root / GPUCC):
        (node / LINK / 'status').write_text('active\n')
    errors = verify(inspect(root), bound=True)
    assert errors == [f'{name}: expected state_synced=1' for name in (GCC, GPUCC)], errors
    for node in (root / GCC, root / GPUCC):
        (node / 'state_synced').write_text('1\n')
    assert not verify(inspect(root), bound=True)

    (root / CRYPTO[0]).mkdir()
    assert any('unexpected crypto node' in err for err in verify(inspect(root), bound=True))
    (root / CRYPTO[0]).rmdir()
    (root / GCC / 'consumer:platform:unexpected').mkdir()
    assert any('unexpected pending consumers' in err for err in verify(inspect(root), bound=True))

print('GMU binding gate: baseline, incomplete sync, bound, and unexpected dependencies PASS')
