#!/usr/bin/env python3
"""Run the native GainStep frame validator over the pinned runtime inventory."""
import ctypes
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


patch = Path(__file__).resolve().parents[1] / 'pkgs/patches/fullio/audioreach-fullio.patch'
added = '\n'.join(line[1:] for line in patch.read_text().splitlines() if line.startswith('+'))
constants = '\n'.join(re.findall(r'^#define FULLIO_GAINSTEP_.*$', added, re.M))
validator = added[added.index('static int q6apm_fullio_validate_gainstep('):
                  added.index('static int q6apm_fullio_map_gainstep(')]
source = r'''
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;
#define SHA256_DIGEST_SIZE 32
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
static void (*sha256)(const u8 *, size_t, u8 *);
void set_sha256(void (*callback)(const u8 *, size_t, u8 *)) { sha256 = callback; }
''' + constants + '\n' + validator + r'''
int validate(const u8 *p, size_t n) { return q6apm_fullio_validate_gainstep(p, n); }
'''

raw = Path(sys.argv[1]).read_bytes()
assert hashlib.sha256(raw).hexdigest() == '2077bea085cea94f52853b8524205824ea36ac038522d7b2f93906c84756337e'
steps = json.loads(raw)['steps']
assert [row['gain_step'] for row in steps] == list(range(1, 31))
with tempfile.TemporaryDirectory() as tmp:
    harness = Path(tmp) / 'gainstep.c'
    lib = harness.with_suffix('.so')
    harness.write_text(source)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    str(harness), '-o', str(lib)], check=True)
    compiled = ctypes.CDLL(str(lib))
    sha256_callback = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p)

    @sha256_callback
    def sha256(data, size, out):
        digest = hashlib.sha256(ctypes.string_at(data, size)).digest()
        ctypes.memmove(out, digest, len(digest))

    compiled.set_sha256.argtypes = (sha256_callback,)
    compiled.set_sha256.restype = None
    compiled.set_sha256(sha256)
    validate = compiled.validate
    validate.argtypes = (ctypes.c_char_p, ctypes.c_size_t)
    for row in steps:
        delta = bytes.fromhex(row['serialized_hex'])
        assert hashlib.sha256(delta).hexdigest() == row['serialized_sha256']
        assert validate(delta, len(delta)) == 0, row['gain_step']
        assert validate(delta, len(delta) - 1) < 0
        assert validate(delta + b'\0', len(delta) + 1) < 0
        offset = 0
        for param in row['parameters']:
            for field in (0, 4, 8, 12, 16):
                corrupt = bytearray(delta)
                corrupt[offset + field] ^= 1
                assert validate(bytes(corrupt), len(corrupt)) < 0
            end = offset + 16 + param['payload_size']
            offset += param['frame_size']
            if end < offset:
                corrupt = bytearray(delta)
                corrupt[end] = 1
                assert validate(bytes(corrupt), len(corrupt)) < 0
        assert offset == len(delta)
print('Native GainStep validator accepts all 30 pinned deltas and rejects changed lengths, headers, payload bytes and padding.')
