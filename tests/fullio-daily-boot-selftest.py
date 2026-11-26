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

    def record(name, data=b''):
        name = name + b'\0'
        header = b'070701' + b'00000000' * 13
        header = header[:54] + f'{len(data):08x}'.encode() + header[62:94] + f'{len(name):08x}'.encode() + header[102:]
        padded = lambda x: x + b'\0' * (-len(x) % 4)
        return padded(header + name) + padded(data)

    stock = b'initrd!'  # Non-aligned prefix.
    (parts / 'initrd').write_bytes(stock)
    private = root / 'firmware'
    zap = private / f['ZAP']
    zap.parent.mkdir(parents=True)
    zap.write_bytes(b'known payload')
    payload = record(f"surface-firmware/{f['ZAP']}".encode(), zap.read_bytes())
    trailer = record(b'TRAILER!!!')
    sections[b'.initrd'] = stock + b'\0' + payload + trailer
    f['verify_private_initrd'](image, root, section, private)
    zap.write_bytes(b'wrong payload')
    rejects(f['verify_private_initrd'], image, root, section, private)
    zap.write_bytes(b'known payload')
    sections[b'.initrd'] = stock + b'\0' + payload + payload + trailer
    rejects(f['verify_private_initrd'], image, root, section, private)
    sections[b'.initrd'] = stock + b'\0' + payload[:-1]
    rejects(f['verify_private_initrd'], image, root, section, private)
print('Daily boot: rejects mismatched default/selected, duplicate entries, wrong sections and wrong or malformed private initrd')
