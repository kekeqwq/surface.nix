#!/usr/bin/env python3
"""Exercise the extracted RX0 audit; no DSP access or audio playback."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def extract(text, name):
    return re.search(rf'^(?:static )?int {name}\([^{{]*\{{.*?^\}}', text, re.M | re.S)[0]


dai = Path(sys.argv[1]).read_text()
apm = Path(sys.argv[2]).read_text()
prepare = extract(dai, 'q6apm_fullio_dsp_prepare')
assert prepare.index('q6apm_graph_prepare(graph)') < prepare.index('q6apm_fullio_verify_sink(graph)')
assert prepare.index('q6apm_fullio_verify_sink(graph)') < prepare.index('audioreach_fullio_verify_mute(graph)')
assert 'microsoft,denali-fullio-dsp-start-audit' in prepare and 'q6apm_graph_start(' not in prepare
assert re.search(r'instance == 0x4157 && bytes == 12 &&\s*\(param == PARAM_ID_HW_EP_MF_CFG \|\| param == PARAM_ID_CODEC_DMA_INTF_CFG\)',
                 extract(apm, 'q6apm_fullio_get_cfg'))

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
typedef uint32_t u32, __le32;
#define cpu_to_le32(x) (x)
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#define PARAM_ID_HW_EP_MF_CFG 0x08001017
#define PARAM_ID_CODEC_DMA_INTF_CFG 0x08001063
struct q6apm_graph { void *dev; };
static unsigned calls, fail_at, corrupt_at;
static int fault;
static int dev_err_probe(void *dev, int ret, const char *msg, u32 arg)
{ assert(dev && msg && arg); return ret; }
static int q6apm_fullio_get_cfg(struct q6apm_graph *g, u32 iid, u32 pid, void *out, size_t size)
{
    const u32 media[] = {48000, 0x00020010, 1}, intf[] = {2, 1, 3};
    assert(g && iid == 0x4157 && size == 12 && calls < 2);
    assert(pid == (calls == 0 ? PARAM_ID_HW_EP_MF_CFG : PARAM_ID_CODEC_DMA_INTF_CFG));
    if (++calls == fail_at)
        return fault;
    memcpy(out, calls == 1 ? media : intf, size);
    if (calls == corrupt_at)
        ((u32 *)out)[2] ^= 1;
    return 0;
}
''' + extract(dai, 'q6apm_fullio_verify_sink') + r'''
int main(void)
{
    struct q6apm_graph g = { &g };
    assert(!q6apm_fullio_verify_sink(&g) && calls == 2);
    for (fail_at = 1; fail_at <= 2; fail_at++) {
        calls = 0; fault = -ETIMEDOUT;
        assert(q6apm_fullio_verify_sink(&g) == -ETIMEDOUT && calls == fail_at);
        calls = 0; fault = 4;
        assert(q6apm_fullio_verify_sink(&g) == -EPROTO && calls == fail_at);
    }
    fail_at = 0;
    for (corrupt_at = 1; corrupt_at <= 2; corrupt_at++) {
        calls = 0;
        assert(q6apm_fullio_verify_sink(&g) == -EILSEQ && calls == corrupt_at);
    }
}
'''
with tempfile.TemporaryDirectory() as d:
    c = Path(d) / 'sink.c'
    exe = c.with_suffix('')
    c.write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Same-graph RX0 endpoint audit demands both exact bodies, fails immediately on mismatch or missing reply, and never STARTs.')
