#!/usr/bin/env python3
"""Compile the composed logger readback check and verify its START boundary."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
dai = (root / 'q6apm-dai.c').read_text()
apm = (root / 'q6apm.c').read_text()
header = (root / 'q6apm.h').read_text()

def function(text, name):
    return re.search(rf'^(?:static )?int {name}\(.*?^\}}', text, re.M | re.S)[0]

verify = function(dai, 'q6apm_fullio_verify_silent_audit')
assert verify.count('q6apm_fullio_verify_logger_tags(') == 2
assert re.search(r'if \(!started\) \{\s*ret = q6apm_fullio_audit_configure_taps.*?'
                 r'if \(!ret && logger_tags\)\s*ret = q6apm_fullio_verify_logger_tags\(audit->graph, false,\s*rx0_log_off, feedback_log_off\);'
                 r'\s*if \(ret\)\s*return ret;', verify, re.S)
assert re.search(r'if \(!ret && started && logger_tags\)\s*ret = q6apm_fullio_verify_logger_tags\(audit->graph, true,\s*rx0_log_off, feedback_log_off\);', verify)
assert '(feedback_off && !rx0_log_off) || (keep_cps_log && !feedback_off))\n\t\treturn -EPERM;' in verify
assert 'feedback_log_off = keep_cps_log ? BIT(0) : BIT(0) | BIT(1);' in verify
assert 'q6apm_fullio_audit_configure_taps(audit->graph, feedback_log_off)' in verify
assert 'q6apm_fullio_audit_configure_taps(audit->graph, 0)' in verify
assert 'cpu_to_le32(feedback_log_off & BIT(i) ? 0 : Q6APM_FULLIO_DIAG_LOG_CODE)' in function(dai, 'q6apm_fullio_audit_configure_taps')
start = function(apm, 'q6apm_fullio_audit_start_stop')
assert re.search(r'ret = verify\(ctx, false\);\s*if \(ret \|\| !q6apm_fullio_mute_is_verified\(graph\)\)'
                 r'\s*return ret \?: -ESTALE;', start)
assert start.index('verify(ctx, false)') < start.index('APM_CMD_GRAPH_START')
allowlist = function(apm, 'q6apm_fullio_get_cfg')
assert re.search(r'param == Q6APM_FULLIO_LOG_CFG && bytes == 12 &&\s*'
                 r'\(instance == 0x4003 \|\| instance == 0x4025 \|\| instance == 0x402a\)', allowlist)
macro = re.search(r'^#define Q6APM_FULLIO_LOG_CFG 0x08001031$', header, re.M)[0]
code = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
typedef uint32_t u32, __le32;
#define le32_to_cpu(v) (v)
#define BIT(i) (1U << (i))
#define ARRAY_SIZE(v) (sizeof(v) / sizeof((v)[0]))
struct q6apm_graph { int dev; };
static const u32 instances[] = {0x4003, 0x4025, 0x402a};
static const u32 tags[] = {4, 2, 3};
static int issued, matched, fail_row, fail_field, status;
static bool logger_off, vi_off, cps_off;
static int dev_err_probe(int dev, int err, const char *fmt, ...)
{ assert(!dev && fmt); return err; }
static void dev_info(int dev, const char *fmt, ...) { assert(!dev && fmt); ++matched; }
''' + macro + r'''
static int q6apm_fullio_get_cfg(struct q6apm_graph *g, u32 instance, u32 param,
                              void *body, size_t bytes)
{
    assert(g && issued < 3 && instance == instances[issued]);
    assert(param == Q6APM_FULLIO_LOG_CFG && bytes == 12);
    __le32 *cfg = body;
    cfg[0] = (instance == 0x4003 ? logger_off : instance == 0x4025 ? vi_off : cps_off) ? 0 : 0x1586;
    cfg[1] = tags[issued];
    cfg[2] = 1;
    if (issued++ != fail_row) return 0;
    if (fail_field >= 0) cfg[fail_field] ^= 1;
    return status;
}
''' + re.search(r'^#define Q6APM_FULLIO_DIAG_LOG_CODE 0x1586$', dai, re.M)[0] + '\n' + function(dai, 'q6apm_fullio_verify_logger_tags') + r'''
int main(void)
{
    struct q6apm_graph graph = {0};
    fail_row = -1;
    assert(!q6apm_fullio_verify_logger_tags(&graph, false, false, false) && issued == 3 && matched == 3);
    issued = matched = 0;
    assert(q6apm_fullio_verify_logger_tags(&graph, false, true, false) == -EILSEQ && issued == 1 && !matched);
    issued = matched = 0;
    logger_off = true;
    assert(!q6apm_fullio_verify_logger_tags(&graph, true, true, false) && issued == 3 && matched == 3);
    issued = matched = 0;
    assert(q6apm_fullio_verify_logger_tags(&graph, true, false, false) == -EILSEQ && issued == 1 && !matched);
    issued = matched = 0;
    assert(q6apm_fullio_verify_logger_tags(&graph, true, true, 3) == -EILSEQ && issued == 2 && matched == 1);
    issued = matched = 0;
    vi_off = true;
    assert(q6apm_fullio_verify_logger_tags(&graph, true, true, 3) == -EILSEQ && issued == 3 && matched == 2);
    issued = matched = 0;
    assert(!q6apm_fullio_verify_logger_tags(&graph, true, true, 1) && issued == 3 && matched == 3);
    issued = matched = 0;
    cps_off = true;
    assert(q6apm_fullio_verify_logger_tags(&graph, true, true, 1) == -EILSEQ && issued == 3 && matched == 2);
    issued = matched = 0;
    assert(!q6apm_fullio_verify_logger_tags(&graph, true, true, 3) && issued == 3 && matched == 3);
    for (fail_row = 0; fail_row < 3; fail_row++) {
        for (fail_field = 0; fail_field < 3; fail_field++) {
            issued = matched = 0;
            assert(q6apm_fullio_verify_logger_tags(&graph, true, true, 3) == -EILSEQ);
            assert(issued == fail_row + 1 && matched == fail_row);
        }
        fail_field = -1;
        int errors[] = {-ETIMEDOUT, -EIO, 1};
        for (unsigned int i = 0; i < ARRAY_SIZE(errors); i++) {
            issued = matched = 0;
            status = errors[i];
            assert(q6apm_fullio_verify_logger_tags(&graph, true, true, 3) == (status > 0 ? -EPROTO : status));
            assert(issued == fail_row + 1 && matched == fail_row);
        }
        status = 0;
    }
}
'''
with tempfile.TemporaryDirectory() as folder:
    src = Path(folder) / 'logger.c'
    exe = src.with_suffix('')
    src.write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('FullIO logger GET: exact tuples, first error/mismatch, and pre/post-START audit placement verified.')
