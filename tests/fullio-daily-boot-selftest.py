#!/usr/bin/env python3
"""Offline negative checks for the ordinary-boot verifier."""
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory

f = run_path(str(Path(__file__).with_name('fullio-daily-boot.py')))


def rejects(fn, *args):
    try:
        fn(*args)
    except ValueError:
        return
    raise AssertionError(f'{fn.__name__} accepted invalid boot data')


ordinary = dict(id='nixos-current.conf', isDefault=True, isSelected=True)
assert f['selected_default']([ordinary]) == ordinary['id']
rejects(f['selected_default'], [ordinary, ordinary])
rejects(f['selected_default'], [dict(ordinary, isSelected=False), dict(id='one-shot.conf', isSelected=True)])
with TemporaryDirectory() as tmp:
    root = Path(tmp)
    conf = root / 'loader/entries/nixos-current.conf'
    conf.parent.mkdir(parents=True)
    conf.write_text('title NixOS\nefi /EFI/surface/generation-cafe.efi\n')
    image = f['checked_image'](root, ordinary['id'])
    rejects(f['checked_image'], root, 'one-shot.conf')
    conf.write_text('efi /EFI/surface/generation-cafe.efi\nefi /EFI/surface/generation-dead.efi\n')
    rejects(f['checked_image'], root, ordinary['id'])
    parts = root / 'surface-boot'
    parts.mkdir()
    (parts / 'linux').write_bytes(b'kernel')
    (parts / 'dtb').write_bytes(b'device tree')
    sections = {b'.cmdline': f'quiet init={root}/init\x00'.encode(), b'.linux': b'kernel', b'.dtb': b'device tree'}
    section = lambda _, key: sections[key]
    assert f['verify_image'](image, root, section).endswith('/init')
    sections[b'.dtb'] = b'wrong'
    rejects(f['verify_image'], image, root, section)
    sections[b'.dtb'] = b'device tree'
    sections[b'.cmdline'] += f' init={root}/init'.encode()
    rejects(f['verify_image'], image, root, section)
print('Daily boot: rejects mismatched default/selected, duplicate entries, wrong DTB and wrong cmdline')
