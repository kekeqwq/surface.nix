#!/usr/bin/env python3
"""Offline exercise of the PREPARE-only SP/SPVI tag recheck ordering."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
helper = re.search(r'^static int q6apm_fullio_dsp_prepare\([^;{]*\{.*?^\}', text, re.M | re.S).group()
call = text.index('ret = q6apm_fullio_dsp_prepare(prtd->graph, card, &stages);')
native_commit = text.index('return q6apm_fullio_mute_commit(prtd->graph, &ticket)', call)
commit = text.index('ret = q6apm_fullio_mute_commit(prtd->graph, &ticket)', native_commit)
assert 'if (ret)\n\t\treturn ret;' in text[call:commit]
# The actual audit's STOP ordering and fault paths are separately exercised
# by fullio-start-audit.py. Check the enclosing caller's scope as well.
start = text.index('"microsoft,denali-fullio-dsp-start-audit")) {', call)
audit = text.index('q6apm_fullio_audit_start_stop(prtd->graph', commit)
finish = text.index('q6apm_fullio_finish_audit(pdata, card', audit)
end = text.index('\n\t} else {', finish)
assert call < native_commit < start < commit < audit < finish < end
assert re.search(r'if \(q6apm_fullio_mute_is_verified\(prtd->graph\)\)\s*'
                 r'q6apm_fullio_mute_invalidate\(prtd->graph\);', text[audit:finish])
assert text[call:text.index('\nrelease_claim:', end)].count('q6apm_fullio_mute_commit') == 2
source = r'''
#include <stdbool.h>
#include <assert.h>
#include <string.h>
#include <errno.h>
#define READ_ONCE(v) (v)
#define dev_info(...) ((void)0)
#define dev_err_probe(d, r, ...) (r)
#define AR_FULLIO_SP_TAG 3
#define AR_FULLIO_SPVI_TAG 4
struct device_node { bool off, prepare, post_pa, native; };
struct device { struct device_node *of_node; };
struct snd_soc_card { struct device *dev; };
struct ar { int start_count; };
struct q6apm_graph { struct ar *ar_graph; int apm; struct device *dev; };
struct audioreach_fullio_stages { int tag; };
static int step, failure;
static int checked(void) { return ++step == failure ? -EILSEQ : 0; }
static int of_property_read_bool(struct device_node *n, const char *p)
{
    if (strstr(p, "sink-readback")) return false;
    if (strstr(p, "dsp-prepare")) return n->prepare;
    if (strstr(p, "clock-off")) return n->off;
    assert(strstr(p, "post-pa")); return n->post_pa;
}
static bool q6apm_fullio_transport_enabled(int apm) { return apm == 1; }
static bool q6apm_fullio_reference_render(struct snd_soc_card *c) { return c->dev->of_node->native; }
static int q6apm_fullio_verify_sink(struct q6apm_graph *g) { assert(g && false); return -EINVAL; }
static int q6apm_fullio_both_pa_off(struct snd_soc_card *card)
{ assert(card && (step == 0 || step == 5)); return checked(); }
static int q6apm_graph_prepare(struct q6apm_graph *g)
{ assert(g && step == 1); return checked(); }
static int audioreach_fullio_verify_tag(struct q6apm_graph *g,
                                     const struct audioreach_fullio_stages *s, int tag)
{ assert(g && s->tag && step == tag - 1); return checked(); }
static int audioreach_fullio_verify_mute(struct q6apm_graph *g)
{ assert(g && step == 4); return checked(); }
''' + helper + r'''
int main(void)
{
    struct device_node n = { .off = true, .prepare = true };
    struct device d = { &n };
    struct snd_soc_card card = { &d };
    struct ar a = {0};
    struct q6apm_graph graph = { &a, 1, &d };
    const struct audioreach_fullio_stages stages = {1};
    assert(!q6apm_fullio_dsp_prepare(&graph, &card, &stages) && step == 6);
    for (int native = 0; native <= 1; ++native) {
        n.native = native;
        n.prepare = n.off = !native;
        for (failure = 1; failure <= 6; failure++) {
            step = 0;
            assert(q6apm_fullio_dsp_prepare(&graph, &card, &stages) == -EILSEQ);
            assert(step == failure);
        }
    }
    step = 0; n.post_pa = true;
    assert(q6apm_fullio_dsp_prepare(&graph, &card, &stages) == -EPERM && !step);
}
'''
with tempfile.TemporaryDirectory() as d:
    c = Path(d) / 'tags.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('PREPARE: native and audit both verify SP/SPVI and physical mute before committing the proof.')
