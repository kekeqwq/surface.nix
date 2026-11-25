#!/usr/bin/env python3
"""Compile the Qualcomm master port selector without device access."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
helper = re.search(r'^static int qcom_swrm_select_master_port\([^;{]*\{.*?^\}', text, re.M | re.S).group()
code = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
static unsigned find_first_zero_bit(const unsigned long *mask, unsigned max)
{
    for (unsigned i = 0; i < max; ++i)
        if (!(*mask & (1UL << i))) return i;
    return max;
}
''' + helper + r'''
int main(void)
{
    unsigned long full = 0x3fff; /* bits 0..13 */
    assert(qcom_swrm_select_master_port(&full, 14, 14) == 14);
    assert(qcom_swrm_select_master_port(&full, 14, 15) == -EBUSY);
    assert(qcom_swrm_select_master_port(&full, 14, UINT_MAX) == -EBUSY);
    assert(qcom_swrm_select_master_port(&full, 14, 0) == -EBUSY);
    unsigned long open = full & ~(1UL << 13);
    assert(qcom_swrm_select_master_port(&open, 14, 0) == 13);
    assert(qcom_swrm_select_master_port(&open, 0, 0) == -EBUSY);
}
'''
with tempfile.TemporaryDirectory() as d:
    c = Path(d) / 'port.c'
    exe = c.with_suffix('')
    c.write_text(code)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Qualcomm port bound: explicit final port accepted; auto-exhaustion and out-of-range mappings rejected.')
