#!/usr/bin/env python3
"""PA-off DSP master-gain readback: Q13-unity bound and placement."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

dai = Path(sys.argv[1]).read_text()
apm = Path(sys.argv[2]).read_text()

def body(text, name):
    return re.search(rf'^(?:static )?int {name}\(.*?^\}}', text, re.M | re.S)[0]

assert '(instance == 0x4a63 && param == 0x08001035 && bytes == 4)' in apm
gbody = body(dai, 'q6apm_fullio_verify_gain_bounds')
assert 'q6apm_fullio_get_cfg(graph, 0x4a63, 0x08001035, words, sizeof(words))' in gbody
sbody = body(dai, 'q6apm_fullio_verify_silent_audit')
assert 'microsoft,denali-fullio-pa-off-gain-audit' in sbody
assert 'q6apm_fullio_verify_gain_bounds(audit->graph, started)' in sbody
assert sbody.index('wsa_macro_fullio_clock_off_for_feedback') < \
       sbody.index('q6apm_fullio_verify_gain_bounds') < sbody.index('if (ring)')

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
typedef uint16_t __le16;
typedef uint32_t u32;
#define le16_to_cpu(v) (v)
struct q6apm_graph { int dev; };
static int status;
static __le16 gain_words[2];
static int dev_err_probe(int dev, int err, const char *fmt, ...)
{ assert(!dev && fmt); return err; }
static int calls;
static void dev_info(int dev, const char *fmt, ...) { assert(!dev && fmt); ++calls; }
''' + r'''
static int q6apm_fullio_get_cfg(struct q6apm_graph *g, u32 instance, u32 param,
                                void *body, size_t bytes)
{
    assert(g && instance == 0x4a63 && param == 0x08001035 && bytes == 4);
    if (status) return status;
    *(uint32_t *)body = *(uint32_t *)gain_words;
    return 0;
}
''' + gbody + r'''
int main(void)
{
    struct q6apm_graph graph = {0};

    /* Unity passes */
    gain_words[0] = 0x2000; gain_words[1] = 0;
    calls = 0;
    assert(!q6apm_fullio_verify_gain_bounds(&graph, false) && calls == 1);

    /* Below unity passes */
    gain_words[0] = 0x1000;
    assert(!q6apm_fullio_verify_gain_bounds(&graph, true) && calls == 2);

    /* Above unity fails */
    gain_words[0] = 0x2001;
    calls = 0;
    assert(q6apm_fullio_verify_gain_bounds(&graph, false) == -EILSEQ && !calls);

    /* Nonzero reserved fails */
    gain_words[0] = 0x2000; gain_words[1] = 1;
    calls = 0;
    assert(q6apm_fullio_verify_gain_bounds(&graph, false) == -EILSEQ && !calls);

    /* Transport errors propagate */
    gain_words[1] = 0;
    int errors[] = {-ETIMEDOUT, -EIO, 1};
    for (unsigned i = 0; i < 3; i++) {
        status = errors[i];
        calls = 0;
        int ret = q6apm_fullio_verify_gain_bounds(&graph, true);
        assert(ret == (errors[i] > 0 ? -EPROTO : errors[i]) && !calls);
    }
    return 0;
}
'''
with tempfile.TemporaryDirectory() as folder:
    src = Path(folder) / 'gain.c'
    exe = src.with_suffix('')
    src.write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)

print('DSP gain readback: Q13 unity bound, reserved-zero, error handling and PA-off placement verified.')
