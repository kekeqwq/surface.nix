#!/usr/bin/env python3
"""Compile the patched frame helper and compare its bytes with the v19c oracle."""
from pathlib import Path
import re
from runpy import run_path
import struct
import subprocess
import sys
import tempfile

patch, oracle = map(Path, sys.argv[1:])
added = '\n'.join(line[1:] for line in patch.read_text().splitlines()
                  if line.startswith('+') and not line.startswith('+++'))
helper = re.search(r'^static int __maybe_unused audioreach_fullio_final_gain_frame\([^\{]+\{.*?^\}',
                   added, re.M | re.S).group()
source = r'''
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
typedef uint32_t __le32, u32;
#define __maybe_unused
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define cpu_to_le32(x) (x)
#else
#define cpu_to_le32(x) __builtin_bswap32(x)
#endif
''' + helper + r'''
int main(void)
{
    __le32 frame[30], unchanged[30];
    memset(frame, 0xbb, sizeof(frame));
    memcpy(unchanged, frame, sizeof(frame));
    assert(audioreach_fullio_final_gain_frame(frame, 0, 0, 0x10000001) == -ERANGE);
    assert(audioreach_fullio_final_gain_frame(frame, 0x51b9d8, 0, 0x51b9d7) == -ERANGE);
    assert(audioreach_fullio_final_gain_frame(frame, 0, 0x51b9d8, 0x51b9d7) == -ERANGE);
    assert(!memcmp(frame, unchanged, sizeof(frame)));
    assert(!audioreach_fullio_final_gain_frame(frame, 0x51b9d7, 0x398000, 0x51b9d7));
    assert(fwrite(frame, 1, sizeof(frame), stdout) == sizeof(frame));
}
'''
with tempfile.TemporaryDirectory() as work:
    c = Path(work) / 'gain.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    output = subprocess.check_output([exe])
body = bytearray(run_path(str(oracle))['multichannel_payload'](0x51b9d7))
struct.pack_into('<I', body, 24, 0x398000)
assert output == struct.pack('<IIII', 0x4a63, 0x08001038, 104, 0) + body
print('Final gain: v19c frame matched byte-for-byte; asymmetric L/R and cap rejection verified.')
