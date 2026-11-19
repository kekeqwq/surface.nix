#!/usr/bin/env python3
"""Inspect an ARM64 EFI wrapper or Type #2 UKI without booting it."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pe_sections(efi):
    header = struct.unpack_from('<I', efi, 0x3C)[0]
    if efi[:2] != b'MZ' or efi[header:header + 4] != b'PE\0\0':
        raise ValueError('Not a PE image')
    machine, count = struct.unpack_from('<HH', efi, header + 4)
    if machine != 0xAA64:
        raise ValueError(f'Not ARM64: {machine:#x}')
    first = header + 24 + struct.unpack_from('<H', efi, header + 20)[0]
    for i in range(count):
        name, size, _, raw_size, raw = struct.unpack_from('<8sIIII', efi, first + 40 * i)
        if raw + raw_size > len(efi):
            raise ValueError('PE section extends past end of file')
        yield name.rstrip(b'\0').decode(), efi[raw:raw + min(size, raw_size)]


def fdt_root(dtb):
    magic, size, start, strings = struct.unpack_from('>IIII', dtb)
    if magic != 0xD00DFEED or size > len(dtb):
        raise ValueError('Invalid DTB')
    offset = start
    depth = 0
    props = {}
    while offset < size:
        token = struct.unpack_from('>I', dtb, offset)[0]
        offset += 4
        if token == 1:
            depth += 1
            if depth > 1:
                break
            offset = (dtb.index(b'\0', offset) + 4) & ~3
        elif token == 3 and depth == 1:
            length, key = struct.unpack_from('>II', dtb, offset)
            offset += 8
            name = dtb[strings + key:dtb.index(b'\0', strings + key)]
            if name in (b'model', b'compatible'):
                props[name.decode()] = dtb[offset:offset + length].rstrip(b'\0').decode().split('\0')
            offset = (offset + length + 3) & ~3
        elif token != 4:
            break
    props['sha256'] = digest(dtb[:size])
    return props


def inspect(path, config_out):
    data = path.read_bytes()
    sections = list(pe_sections(data))
    named = dict(sections)
    zboot = named['.linux']
    if zboot[4:8] != b'zimg':
        raise ValueError('.linux is not a zboot image')
    start, size = struct.unpack_from('<II', zboot, 8)
    if start + size > len(zboot):
        raise ValueError('Truncated zboot payload')
    compression = zboot[24:32].rstrip(b'\0').decode()
    result = {
        'image_sha256': digest(data),
        'uname': named['.uname'].rstrip(b'\0').decode(),
        'initrd_embedded': '.initrd' in named,
        'zboot': {'size': len(zboot), 'compression': compression, 'sha256': digest(zboot)},
        'denali_dtbs': [fdt_root(blob) for name, blob in sections
                        if name in ('.dtbauto', '.dtb') and b'microsoft,denali' in blob],
    }
    if config_out:
        compressed = zboot[start:start + size]
        if compression == 'zstd':
            image = subprocess.run(['zstd', '-dcq'], input=compressed, check=True, capture_output=True).stdout
        elif compression == 'gzip':
            image = gzip.decompress(compressed)
        else:
            raise ValueError(f'Unsupported compression: {compression}')
        begin = image.index(b'IKCFG_ST') + len(b'IKCFG_ST')
        config_out.write_bytes(gzip.decompress(image[begin:image.index(b'IKCFG_ED', begin)]))
    return result


def validate_uki(path, release, expected):
    sections = list(pe_sections(path.read_bytes()))
    named = dict(sections)
    for name in ('.linux', '.initrd', '.dtb', '.osrel', '.cmdline', '.uname'):
        if sum(section == name for section, _ in sections) != 1 or not named[name]:
            raise ValueError(f'Expected exactly one nonempty {name} section')
    if '.dtbauto' in named or '.hwids' in named:
        raise ValueError('Expected an explicit DTB, not HWID selection')
    if named['.uname'].rstrip(b'\0') != release.encode():
        raise ValueError('Unexpected UKI kernel release')
    if named['.linux'][4:8] != b'zimg' or named['.linux'][24:32].rstrip(b'\0') != b'zstd':
        raise ValueError('Expected a Zstd ARM64 zboot kernel, not a raw Image')
    props = fdt_root(named['.dtb'])
    if 'microsoft,denali-oled' not in props.get('compatible', []):
        raise ValueError('UKI does not embed the Denali non-5G OLED DTB')
    for name, contents in expected.items():
        if contents is not None and named[name] != contents:
            raise ValueError(f'{name} does not match its build input')
    return {'initrd_size': len(named['.initrd']), 'initrd_sha256': digest(named['.initrd'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('efi', type=Path)
    parser.add_argument('--config-out', type=Path, help='Extract the embedded Kconfig; requires zstd for zstd payloads')
    parser.add_argument('--expect-uki', metavar='KERNEL_RELEASE')
    for name in ('linux', 'dtb', 'initrd'):
        parser.add_argument(f'--expect-{name}', type=Path)
    parser.add_argument('--expect-cmdline')
    args = parser.parse_args()
    result = inspect(args.efi, args.config_out)
    if args.expect_uki:
        expected = {
            '.' + name: value.read_bytes() if value else None
            for name in ('linux', 'dtb', 'initrd')
            for value in [getattr(args, 'expect_' + name)]
        }
        result.update(validate_uki(args.efi, args.expect_uki, expected))
        if args.expect_cmdline is not None:
            cmdline = dict(pe_sections(args.efi.read_bytes()))['.cmdline'].rstrip(b'\0').decode()
            if cmdline != args.expect_cmdline:
                raise ValueError('.cmdline does not match its build input')
    print(json.dumps(result, indent=2))
