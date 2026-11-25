#!/usr/bin/env python3
"""Check the actual inactive PA readiness predicate without any registers."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
helper = re.search(r'^static int wsa884x_fullio_check_ready\([^;{]*\{.*?^\}', text, re.M | re.S).group()
snapshot = re.search(r'^struct wsa884x_fullio_pa_snapshot \{.*?^\};', text, re.M | re.S).group()
read = text[text.index('static int wsa884x_fullio_read_pa('):text.index(helper)]
assert read.index('WSA884X_PDM_WD_CTL, &snapshot.pdm_wd') < read.index('&snapshot.enable')
assert read.index('WSA884X_VPHX_SYS_EN_STATUS, &snapshot.vphx') < read.index('&snapshot.enable')
assert read.index('&snapshot.enable') < read.index('*result = snapshot')
source = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
typedef long long s64;
typedef unsigned char u8;
#define WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK 1
#define WSA884X_PDM_WD_CTL_PDM_WD_EN_MASK 1
#define WSA884X_PDM_WD_CTL_TIME_OUT_SEL_MASK 2
#define WSA884X_PDM_WD_CTL_HOLD_OFF_MASK 4
''' + snapshot + '\n' + helper + r'''
int main(void)
{
    struct wsa884x_fullio_pa_snapshot s = { .enable = 1, .sta0 = 0x2f, .vphx = 2 };
    for (unsigned val = 0; val < 8; ++val) {
        s.pdm_wd = val;
        assert(wsa884x_fullio_check_ready(&s) == (val == 1 ? 0 : -EIO));
    }
    s.pdm_wd = 1;
    for (unsigned val = 0; val < 256; ++val) {
        s.vphx = val;
        assert(wsa884x_fullio_check_ready(&s) == (val == 2 ? 0 : -EIO));
    }
    s.vphx = 2;
    s.sta0 = 0x2a;
    assert(wsa884x_fullio_check_ready(&s) == -EAGAIN);
    s.sta0 = 0x2f;
    s.enable = 0;
    assert(wsa884x_fullio_check_ready(&s) == -EAGAIN);
    s.enable = 1;
    s.err0 = 0x20;
    assert(wsa884x_fullio_check_ready(&s) == -EIO);
}
'''
with tempfile.TemporaryDirectory() as d:
    src = Path(d) / 'ready.c'
    exe = src.with_suffix('')
    src.write_text(source)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('PA readiness: fresh 2S VPHX, reference watchdog fields, no PA error and ready state all required.')
