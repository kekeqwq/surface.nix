#!/usr/bin/env python3
"""Validate and measure a Denali GPT/UEFI Live ISO without booting it."""

import argparse
import hashlib
import json
import mmap
from pathlib import Path, PurePosixPath
import runpy
import struct
import subprocess
import tempfile
from uuid import UUID
import zlib

efi = runpy.run_path(str(Path(__file__).with_name('inspect-efi-payload.py')))
inspect = efi['inspect']


ESP_GUID = UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def layout(iso, esp):
    with iso.open('rb') as stream:
        def read(offset, count):
            stream.seek(offset)
            return stream.read(count)

        header = read(512, 512)
        require(header[:8] == b'EFI PART', 'missing GPT header')
        size, crc = struct.unpack_from('<II', header, 12)
        require(92 <= size <= 512, 'invalid GPT header size')
        require(zlib.crc32(header[:16] + b'\0' * 4 + header[20:size]) == crc, 'bad GPT header CRC')
        start, count, size, crc = struct.unpack_from('<QIII', header, 72)
        require(0 < count <= 4096 and 128 <= size <= 1024, 'invalid GPT entry table')
        entries = read(start * 512, count * size)
        require(zlib.crc32(entries) == crc, 'bad GPT entry CRC')
        parts = []
        for index in range(count):
            row = entries[index * size:(index + 1) * size]
            kind = UUID(bytes_le=row[:16])
            if not kind.int:
                continue
            first, last = struct.unpack_from('<QQ', row, 32)
            require(first <= last and (last + 1) * 512 <= iso.stat().st_size, 'invalid partition range')
            parts.append(dict(index=index + 1, type=str(kind), start_lba=first, end_lba=last))
        esps = [p for p in parts if p['type'] == str(ESP_GUID)]
        require(len(esps) == 1, 'expected exactly one EFI system partition')
        e = esps[0]
        offset = e['start_lba'] * 512
        pvd, catalog = None, None
        for sector in range(16, 64):
            descriptor = read(sector * 2048, 2048)
            if descriptor[1:6] != b'CD001':
                break
            if descriptor[0] == 1:
                pvd = descriptor
            if descriptor[0] == 0 and descriptor[7:39].rstrip(b'\0 ') == b'EL TORITO SPECIFICATION':
                catalog = struct.unpack_from('<I', descriptor, 71)[0]
            if descriptor[0] == 255:
                break
        require(pvd is not None and catalog is not None, 'missing ISO descriptor or El Torito catalog')
        boot = read(catalog * 2048, 64)
        require(boot[1] == 0xef and boot[32] == 0x88, 'expected a default UEFI El Torito entry')
        boot_lba = struct.unpack_from('<I', boot, 40)[0]
        require(boot_lba * 2048 == offset, 'El Torito entry points outside the beginning of the GPT ESP')
        end = (e['end_lba'] + 1) * 512
        stream.seek(offset)
        with esp.open('wb') as output:
            for length in range(offset, end, 1024 * 1024):
                output.write(stream.read(min(1024 * 1024, end - length)))
        date = pvd[813:829].decode('ascii')
        return dict(volume_label=pvd[40:72].decode('ascii').rstrip(),
                    volume_creation=date, el_torito_lba=boot_lba, partitions=parts)


def initrd_format(path):
    with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as image:
        pos = 0
        count = 0
        wireless = []
        while image[pos:pos + 6] in (b'070701', b'070702'):
            size = int(image[pos + 54:pos + 62], 16)
            length = int(image[pos + 94:pos + 102], 16)
            filename = image[pos + 110:pos + 110 + length - 1].decode(errors='replace')
            pos = ((pos + 110 + length + 3) & ~3) + ((size + 3) & ~3)
            if filename == 'TRAILER!!!':
                while image[pos:pos + 1] == b'\0':
                    pos += 1
            else:
                count += 1
                if 'ath12k/WCN7850/hw2.0/' in filename:
                    wireless.append(filename)
        return dict(uncompressed_newc_members=count, next_offset=pos,
                    next_magic=image[pos:pos + 8].hex(), early_wcn7850=wireless)


def settings(path):
    values = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, _, value = line.strip().partition(' ')
            require(key not in values, f'duplicate {key} in {path.name}')
            values[key] = value.strip()
    return values


def report(iso, profile):
    expected = {'arch': ('ARCH_202610', 'arch/aarch64/airootfs.sfs'),
                'nixos': ('NIXOS_DENALI', 'nix-store.squashfs'),
                'nixos-uki': ('SURFACE_LIVE', 'nix-store.squashfs')}
    label, root = expected[profile]
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        esp = work / 'esp.fat'
        report = layout(iso, esp)
        require(report['volume_label'] == label, f'expected Live label {label}')
        require(any(p['start_lba'] == 64 for p in report['partitions']), 'missing ISO partition at offset 16')
        listing = subprocess.check_output(['bsdtar', '-tf', str(iso)], text=True).splitlines()
        require(root in {name.removeprefix('./') for name in listing}, f'missing {root}')
        fat = work / 'fat'
        fat.mkdir()
        subprocess.run(['mcopy', '-s', '-i', str(esp), '::/*', str(fat)], check=True)
        loader = fat / 'EFI/BOOT/BOOTAA64.EFI'
        image = loader.read_bytes()
        pe = struct.unpack_from('<I', image, 0x3c)[0]
        require(image[:2] == b'MZ' and image[pe:pe + 6] == b'PE\0\0\x64\xaa', 'loader is not ARM64 EFI')
        config = settings(fat / 'loader/loader.conf')
        if profile == 'nixos-uki':
            name = config['default']
            require(name == 'surface-live.efi', 'unexpected default UKI')
            ukis = sorted((fat / 'EFI/Linux').glob('*.efi'))
            require([file.name for file in ukis] == [name], 'expected a single Type #2 UKI')
            require(not list((fat / 'loader/entries').glob('*.conf')), 'unexpected Type #1 entry')
            uki = ukis[0]
            measured = inspect(uki, None)
            measured.update(efi['validate_uki'](uki, measured['uname'], {}))
            sections = dict(efi['pe_sections'](uki.read_bytes()))
            cmdline = sections['.cmdline'].rstrip(b'\0').decode().split()
            require(any(arg.startswith('init=/nix/store/') and arg.endswith('/init') for arg in cmdline),
                    'missing NixOS init path')
            fbcon_options = [option for arg in cmdline if arg.startswith('fbcon=')
                             for option in arg.removeprefix('fbcon=').split(',')]
            require([option for option in fbcon_options if option.startswith('font:')] == ['font:TER16x32'],
                    'missing or conflicting large console font')
            report.update(profile=profile, iso_sha256=sha256(iso), live_root=root,
                          esp_sha256=sha256(esp), loader={'bytes': loader.stat().st_size, 'sha256': sha256(loader), 'config': config},
                          uki=measured)
            return report
        entries = {}
        measured = {}
        for entry in sorted((fat / 'loader/entries').glob('*.conf')):
            fields = settings(entry)
            for key in ('linux', 'initrd'):
                path = PurePosixPath(fields[key])
                require(path.is_absolute() and '..' not in path.parts, f'invalid {key} path')
                relative = str(path).lstrip('/')
                artifact = fat / relative
                require(artifact.is_file() and artifact.stat().st_size > 0, f'{key} missing on FAT: {path}')
                if relative not in measured:
                    entry_report = {'sha256': sha256(artifact), 'bytes': artifact.stat().st_size}
                    if key == 'linux':
                        entry_report.update(inspect(artifact, None))
                        require(not entry_report['initrd_embedded'], 'initrd should be external')
                        require(any(dt.get('compatible', [''])[0] == 'microsoft,denali-oled'
                                    for dt in entry_report['denali_dtbs']), 'missing Denali OLED DTB')
                    else:
                        entry_report.update(initrd_format(artifact))
                    measured[relative] = entry_report
            options = fields['options'].split()
            if profile == 'arch':
                date = report['volume_creation']
                uuid = '-'.join(date[a:b] for a, b in ((0, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16)))
                require(f'archisosearchuuid={uuid}' in options and 'archisobasedir=arch' in options,
                        'Arch menu does not point at this ISO')
            else:
                require(any(o.startswith('init=/nix/store/') and o.endswith('/init') for o in options),
                        'missing NixOS init path')
            entries[entry.name] = fields
        require(config['default'] in entries, 'default entry is missing from the ESP')
        report.update(profile=profile, iso_sha256=sha256(iso), live_root=root,
                      loader={'bytes': loader.stat().st_size, 'sha256': sha256(loader), 'config': config},
                      entries=entries, payloads=measured)
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=('arch', 'nixos', 'nixos-uki'))
    parser.add_argument('iso', type=Path)
    args = parser.parse_args()
    print(json.dumps(report(args.iso, args.profile), indent=2, sort_keys=True))
