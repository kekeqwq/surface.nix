#!/usr/bin/env python3
"""Exercise the private UKI fixture-DTB gates with a stub fdtget."""
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

script = Path(__file__).resolve().parent.parent / 'scripts' / 'prepare-fullio-uki.py'
spec = importlib.util.spec_from_file_location('prepare_fullio_uki', script)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)

SOUND_REF = ['microsoft,denali-fullio-reference-render', 'model', 'audio-routing']
SOUND_MUTED = ['microsoft,denali-fullio-muted-test', 'model']
CODEC = ['qcom,denali-fullio-reference-codec', 'compatible']
NODES = {
    '/sound': SOUND_REF,
    '/soc@0/soundwire@6b10000/speaker@0,0': CODEC,
    '/soc@0/soundwire@6b10000/speaker@0,1': CODEC,
}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        stub = tmp / 'fdtget.py'
        stub.write_text(
            '#!/usr/bin/env python3\n'
            'import json, sys\n'
            'args = [a for a in sys.argv[1:] if a != "-p"]\n'
            'table = json.load(open(args[0]))\n'
            'print("\\n".join(table.get(args[1], [])))\n'
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

        def verify(fn, table):
            path = tmp / 'table.json'
            path.write_text(json.dumps(table))
            try:
                fn(path, stub)
            except (ValueError, subprocess.CalledProcessError) as exc:
                return f'rejected:{exc}'
            return 'ok'

        assert verify(prep.verify_reference_dtb, NODES) == 'ok'
        muted_table = dict(NODES, **{'/sound': SOUND_MUTED})
        assert verify(prep.verify_pa_off_dtb, muted_table) == 'ok'
        assert verify(prep.verify_reference_dtb, muted_table).startswith('rejected:')
        assert verify(prep.verify_reference_dtb,
                      dict(NODES, **{'/sound': SOUND_MUTED + ['microsoft,denali-fullio-ring-map-audit']})) \
            .startswith('rejected:')
        assert verify(prep.verify_reference_dtb,
                      dict(NODES, **{'/sound': SOUND_REF + ['microsoft,denali-fullio-post-pa-test']})) \
            .startswith('rejected:')
        missing = dict(NODES)
        missing.pop('/soc@0/soundwire@6b10000/speaker@0,1')
        assert 'reference-codec' in verify(prep.verify_reference_dtb, missing)
        assert verify(prep.verify_pa_off_dtb,
                      dict(muted_table, **{'/sound': SOUND_MUTED + ['microsoft,denali-fullio-pa-on-smoke']})) \
            .startswith('rejected:')
    print('Private UKI DT gates: reference markers required, fixture/audit markers rejected.')


if __name__ == '__main__':
    main()
