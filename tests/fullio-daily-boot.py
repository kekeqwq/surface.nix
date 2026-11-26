#!/usr/bin/env python3
"""Read-only acceptance check after an ordinary Denali switch and default boot.

Run as root on Surface. Pass the expected toplevel from the locked consumer
flake, not the currently selected symlink. Does not open a PCM or change EFI.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from runpy import run_path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = 'e7bb06a03e7bd9b869825a51775355a6743477d1579d78eb09fad5881cfb20f0'
RECOVERY = 'a1a61241ed970ef512f40c5a11a193006b99720e7540f609c66cfa008f09d4b0'
FW = 'qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0-tplg.bin'
ZAP = 'qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn'
PRIVATE = Path('/var/lib/surface-firmware')


def only(pattern, text, label):
    rows = re.findall(pattern, text, re.M)
    if len(rows) != 1:
        raise ValueError(f'expected one {label}, found {len(rows)}')
    return rows[0]


def selected_default(entries):
    def unique(key):
        ids = [entry['id'] for entry in entries if entry.get(key) is True]
        if len(ids) != 1:
            raise ValueError(f'expected one bootctl {key} entry')
        return ids[0]

    default, selected = unique('isDefault'), unique('isSelected')
    if selected != default:
        raise ValueError(f'booted entry {selected} differs from default {default}')
    return default


def checked_image(esp, entry):
    # No private diagnostic entry or auto-efi fallback may satisfy this gate.
    if not re.fullmatch(r'nixos-[a-zA-Z0-9-]+\.conf', entry):
        raise ValueError('default is not an ordinary NixOS entry')
    conf = (esp / 'loader' / 'entries' / entry).read_text()
    name = only(r'^efi\s+(/EFI/surface/generation-[0-9a-f]+\.efi)\s*$', conf, 'generation image')
    return esp / name.lstrip('/')


def verify_image(image, expected, section):
    # Read the PE command line directly; a sidecar cannot prove image identity.
    def read(key):
        return section(image, key)

    cmdline = read(b'.cmdline').rstrip(b'\0').decode()
    if re.findall(r'(?:^|\s)init=(\S+)', cmdline) != [f'{expected}/init']:
        raise ValueError('UKI init does not match the expected closure')
    for key, name in ((b'.linux', 'linux'), (b'.dtb', 'dtb')):
        if read(key) != (expected / 'surface-boot' / name).read_bytes():
            raise ValueError(f'UKI {name} does not match the expected closure')
    return cmdline


def newc_payload(data, offset, wanted):
    """Read one known appended newc archive by its record boundaries."""
    found = None
    while offset + 110 <= len(data):
        hdr = data[offset:offset + 110]
        if hdr[:6] != b'070701':
            raise ValueError('invalid appended firmware archive header')
        size, namesize = int(hdr[54:62], 16), int(hdr[94:102], 16)
        name = data[offset + 110:offset + 110 + namesize]
        start = (offset + 110 + namesize + 3) & ~3
        end = start + size
        if not name.endswith(b'\0') or end > len(data):
            raise ValueError('truncated appended firmware record')
        if name == b'TRAILER!!!\0':
            if size or found is None:
                raise ValueError('firmware archive did not contain the expected zap')
            return found
        if name == wanted + b'\0':
            if found is not None:
                raise ValueError('duplicated private zap in appended firmware archive')
            found = data[start:end]
        offset = (end + 3) & ~3
    raise ValueError('no trailer in private firmware archive')


def verify_private_initrd(image, expected, section, private=PRIVATE):
    data = section(image, b'.initrd')
    stock = (expected / 'surface-boot/initrd').read_bytes()
    if not data.startswith(stock):
        raise ValueError('UKI initrd does not start with the expected system initrd')
    embedded = newc_payload(data, (len(stock) + 3) & ~3, f'surface-firmware/{ZAP}'.encode())
    if embedded != (private / ZAP).read_bytes():
        raise ValueError('UKI zap differs from the privately provisioned source')


def verify_recovery(esp):
    recovery_conf = (esp / 'loader/entries/surface-recovery-gen20.conf').read_text()
    recovery_name = only(r'^efi\s+(\S+)\s*$', recovery_conf, 'Gen20 recovery image')
    if recovery_name != '/EFI/surface/recovery-gen20.efi':
        raise ValueError('Gen20 entry does not point to the protected recovery image')
    recovery = esp / recovery_name.lstrip('/')
    if hashlib.sha256(recovery.read_bytes()).hexdigest() != RECOVERY:
        raise ValueError('Gen20 recovery image hash mismatch')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('expected', type=Path)
    a = p.parse_args()
    c = a.expected.resolve(strict=True)
    if c.parent != Path('/nix/store') or not re.fullmatch(r'[0-9a-z]{32}-nixos-system-surface-.+', c.name):
        p.error('expected a Surface NixOS store closure')
    for link in ('/run/booted-system', '/run/current-system', '/nix/var/nix/profiles/system'):
        if Path(link).resolve(strict=True) != c:
            raise ValueError(f'{link} is not the expected closure')
    entries = json.loads(subprocess.check_output(['bootctl', '--json=short', 'list'], text=True))
    default = selected_default(entries)
    esp = Path(subprocess.check_output(['bootctl', '--print-esp-path'], text=True).strip())
    subprocess.run(['mountpoint', '-q', esp], check=True)
    verify_recovery(esp)
    section = run_path(str(ROOT / 'scripts/install-ukis.py'))['pe_section']
    image = checked_image(esp, default)
    cmdline = verify_image(image, c, section)
    verify_private_initrd(image, c, section)
    if Path('/proc/cmdline').read_text().split() != cmdline.split():
        raise ValueError('running command line differs from generation UKI')
    dt = Path('/sys/firmware/devicetree/base')
    for prop in ('sound/microsoft,denali-fullio-checked-capture',
                 'soc@0/soundwire@6b10000/qcom,denali-fullio-sidechain-audit',
                 'soc@0/soundwire@6b10000/qcom,denali-fullio-wait-frame-stop'):
        if not (dt / prop).is_file():
            raise ValueError(f'missing booted DT marker {prop}')
    if (dt / 'sound/microsoft,denali-fullio-pre-sp-logger-audit').exists():
        raise ValueError('pre-SP diagnostic DT selected')
    fwroot = Path('/sys/module/firmware_class/parameters/path').read_text().strip()
    if fwroot != '/run/surface/firmware':
        raise ValueError('unexpected runtime firmware root')
    path = Path(fwroot) / FW
    data = path.read_bytes() if path.exists() else subprocess.check_output(
        ['zstd', '-dc', path.with_suffix('.bin.zst').resolve(strict=True)])
    if hashlib.sha256(data).hexdigest() != GOLDEN:
        raise ValueError('runtime firmware is not the Golden topology')
    for unit in ('sshd', 'greetd'):
        subprocess.run(['systemctl', 'is-active', '--quiet', unit], check=True)
    print(f'{default}: exact default UKI and boot closure, Golden feedback DT/topology, Gen20, SSH and greetd verified')


if __name__ == '__main__':
    main()
