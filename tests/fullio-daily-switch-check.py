#!/usr/bin/env python3
"""Read-only verification between ordinary Surface switch and reboot.

Run as root after each switch. Pass the expected toplevel obtained from the
locked flake and, on the second run, the first run's entry ID. The selected
entry is intentionally not checked here; it only changes on reboot.
"""
import argparse
import hashlib
import json
from pathlib import Path
from runpy import run_path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('expected', type=Path)
    p.add_argument('--repeat-entry')
    a = p.parse_args()
    c = a.expected.resolve(strict=True)
    for name in ('/run/current-system', '/nix/var/nix/profiles/system'):
        if Path(name).resolve(strict=True) != c:
            raise ValueError(f'{name} does not match {c}')
    f = run_path(str(ROOT / 'tests/fullio-daily-boot.py'))
    pe = run_path(str(ROOT / 'scripts/install-ukis.py'))['pe_section']
    esp = Path(subprocess.check_output(['bootctl', '--print-esp-path'], text=True).strip())
    subprocess.run(['mountpoint', '-q', esp], check=True)
    efivars = Path('/sys/firmware/efi/efivars')
    subprocess.run(['mountpoint', '-q', efivars], check=True)
    oneshot = efivars / 'LoaderEntryOneShot-4a67b082-0a4c-41cf-b6c7-440b29bb8c4f'
    if oneshot.exists():
        raise ValueError('a pending one-shot would invalidate a default boot test')
    entries = json.loads(subprocess.check_output(['bootctl', '--json=short', 'list']))
    default, = (row['id'] for row in entries if row.get('isDefault') is True)
    if a.repeat_entry and a.repeat_entry != default:
        raise ValueError(f'repeated switch changed the default ID: {a.repeat_entry} -> {default}')
    image = f['checked_image'](esp, default)
    f['verify_image'](image, c, pe)
    f['verify_private_initrd'](image, c, pe)
    f['verify_recovery'](esp)
    for unit in ('sshd', 'greetd'):
        subprocess.run(['systemctl', 'is-active', '--quiet', unit], check=True)
    print(json.dumps({'closure': str(c), 'entry': default, 'uki_sha256': hashlib.sha256(image.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
