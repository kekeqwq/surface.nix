#!/usr/bin/env python3
"""A second bootloader install must recognize the UKI entry left by the first."""
import importlib.util
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('install_ukis', Path(__file__).parents[1] / 'scripts/install-ukis.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

calls = []


def fake_run(*args, **kwargs):
    calls.append(args)
    return None


def fake_uki(inspector, components, cmdline, firmware, extra, target, system):
    target.write_bytes(b'uki')


installer.run = fake_run
installer.private_uki = fake_uki

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    installer.STORE = root / 'store'
    boot = root / 'boot'
    system = installer.STORE / 'current-system'
    (system / 'surface-boot').mkdir(parents=True)
    firmware = root / 'zap.mbn'
    firmware.write_bytes(b'zap')
    entry = boot / 'loader/entries/nixos-current.conf'
    entry.parent.mkdir(parents=True)
    (boot / 'EFI/surface').mkdir(parents=True)
    entry.write_text(
        'title NixOS\nversion Generation 24\nsort-key nixos\nmachine-id abc\n'
        f'options init={system}/init quiet\n'
    )
    installer.finish(Path('inspector'), boot, system, firmware)
    assert entry.read_text().startswith('title NixOS\n')
    assert 'options ' not in entry.read_text()
    assert 'efi /EFI/surface/generation-' in entry.read_text()
    uki = next((boot / 'EFI/surface').glob('generation-*.efi'))
    assert uki.with_suffix('.system').read_text().strip() == str(system)
    calls.clear()
    installer.finish(Path('inspector'), boot, system, firmware)
    assert any(args[:2] == ('sync', '-f') for args in calls)
    assert 'options ' not in entry.read_text()
    assert uki.is_file()
print('Repeated UKI install recognizes the current generation without a new stock entry.')
