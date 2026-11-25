#!/usr/bin/env python3
"""Exercise the native graph-replacement and transfer paths without a DSP."""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

text = Path(sys.argv[1]).read_text()


def function(name):
    return re.search(rf'^static [^\n]+\b{name}\([^;{{]*\{{.*?^\}}', text, re.M | re.S)[0]


prepare = function('q6apm_dai_prepare')
assert prepare.index('return prtd->fullio_reference_error;') < prepare.index('!prtd || !prtd->graph')
construct = function('q6apm_dai_pcm_new')
assert construct.index('q6apm_fullio_independent_pcm') < construct.index('rtd->ops.copy = q6apm_fullio_copy')
assert construct.index('pcm->streams[SNDRV_PCM_STREAM_CAPTURE].substream)') < construct.index('rtd->ops.fill_silence')

source = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define WRITE_ONCE(x,v) ((x) = (v))
#define IS_ERR(p) ((intptr_t)(p) < 0)
#define PTR_ERR(p) ((intptr_t)(p))
#define SNDRV_PCM_FORMAT_S16_LE 1
#ifndef EBADFD
#define EBADFD 77
#endif
struct snd_dma_buffer { char *data; };
struct snd_pcm_runtime { int format, rate, channels; char *dma_area; size_t dma_bytes; };
struct snd_pcm_substream { int stream; struct snd_pcm_runtime *runtime; };
struct snd_soc_card { int dummy; };
struct audioreach_module_config { int dummy; };
struct q6apm_graph { int id; };
struct q6apm_dai_data { bool fullio_render_locked, has_reserved_mem, use_scm_assign; void *dev; int sid; };
struct q6apm_dai_rtd {
    struct q6apm_graph *graph;
    struct snd_pcm_substream *substream;
    int watermark_work, last_pos_index, pcm_size, periods, fullio_reference_error;
    bool fullio_reference_prepared, fullio_reference_reopen, fullio_reference_started;
};
struct iov_iter { char *data; size_t limit; };
static struct q6apm_graph old, fresh;
static char sample[3840];
static struct snd_dma_buffer new_buffer = {sample};
static struct snd_pcm_runtime runtime = {SNDRV_PCM_FORMAT_S16_LE, 48000, 2, sample, sizeof(sample)};
static struct snd_pcm_substream sub = {0, &runtime};
static struct q6apm_dai_data pdata;
static struct q6apm_dai_rtd rt;
static int phase, fail_at;
static void event_handler(void) {}
static int step(int n) { assert(++phase == n); return fail_at == n ? -EIO : 0; }
static int q6apm_fullio_both_pa_off(struct snd_soc_card *c) { assert(c); return step(phase == 0 ? 1 : 9); }
static int wsa_macro_fullio_clock_off_for_feedback(struct snd_soc_card *c) { assert(c); return step(phase == 1 ? 2 : 10); }
static void q6apm_pcm_watermark_enable(struct q6apm_dai_rtd *r, bool enable)
{ assert(r == &rt && !enable && !step(3)); }
static void cancel_work_sync(int *w) { assert(w == &rt.watermark_work && !step(4)); }
static int q6apm_fullio_pcm_stop(struct q6apm_graph *g)
{ assert(g == &old && runtime.dma_area); return step(5); }
static void snd_pcm_set_runtime_buffer(struct snd_pcm_substream *p, struct snd_dma_buffer *buf)
{
    assert(p == &sub);
    assert(!step(buf ? 17 : 6));
    runtime.dma_area = buf ? buf->data : NULL;
    runtime.dma_bytes = buf ? sizeof(sample) : 0;
}
static int q6apm_graph_close(struct q6apm_graph *g)
{ assert(g == &old && !rt.graph && !runtime.dma_area); return step(7); }
static struct q6apm_graph *q6apm_graph_open(void *dev, void (*cb)(void), void *p, int id, int stream)
{
    assert(dev == pdata.dev && cb == event_handler && p == &rt && !id && !stream);
    assert(!runtime.dma_area);
    int ret = step(8);
    return ret ? (void *)(intptr_t)ret : &fresh;
}
static int snd_pcm_lib_period_bytes(struct snd_pcm_substream *p) { assert(p == &sub); return 1920; }
static int q6apm_fullio_pcm_configure(struct q6apm_graph *g, struct snd_soc_card *c, int sid)
{ assert(g == &fresh && c && sid == pdata.sid && !rt.fullio_reference_reopen && !rt.last_pos_index); return step(11); }
static int q6apm_fullio_prepare_pull_media(struct q6apm_graph *g, struct audioreach_module_config *c, int p)
{ assert(g == &fresh && c && p == 1920); return step(12); }
static int q6apm_fullio_prepare_cal(struct q6apm_dai_data *p, struct q6apm_dai_rtd *r, struct snd_soc_card *card, struct audioreach_module_config *c)
{ assert(p == &pdata && r == &rt && card && c); return step(13); }
static struct snd_dma_buffer *q6apm_fullio_pcm_buffer(struct q6apm_graph *g, int bytes)
{ assert(g == &fresh && bytes == 3840); return step(14) ? NULL : &new_buffer; }
static int q6apm_fullio_pcm_start(struct q6apm_graph *g) { assert(g == &fresh); return step(15); }
static int audioreach_fullio_verify_mute(struct q6apm_graph *g) { assert(g == &fresh); return step(16); }
static bool q6apm_fullio_mute_is_verified(struct q6apm_graph *g) { return g == &fresh; }
static size_t copy_from_iter(void *p, size_t n, struct iov_iter *i)
{ size_t copied = n < i->limit ? n : i->limit; memcpy(p,i->data,copied); return copied; }
''' + '\n'.join(function(name) for name in (
    'q6apm_fullio_reference_recycle', 'q6apm_fullio_reference_prepare',
    'q6apm_fullio_transfer_area', 'q6apm_fullio_copy', 'q6apm_fullio_fill_silence',
)) + r'''
static void reset(int fail)
{
    phase = 0;
    fail_at = fail;
    pdata.fullio_render_locked = false;
    runtime.dma_area = sample;
    runtime.dma_bytes = sizeof(sample);
    rt = (struct q6apm_dai_rtd){.graph=&old, .substream=&sub, .last_pos_index=16,
          .pcm_size=3840, .periods=2, .fullio_reference_prepared=true, .fullio_reference_reopen=true};
}
int main(void)
{
    struct snd_soc_card card;
    struct audioreach_module_config cfg;
    /* These cases must stop before a new OPEN, and before detaching if STOP is uncertain. */
    for (int fail = 1; fail <= 8; fail++) {
        if (fail == 3 || fail == 4 || fail == 6) continue;
        reset(fail);
        assert(q6apm_fullio_reference_prepare(&pdata, &rt, &card, &cfg) == -EIO);
        assert(phase == fail && rt.fullio_reference_error == -EIO);
        assert((fail <= 5) == !!runtime.dma_area && (fail <= 5) == !!rt.graph);
        assert(pdata.fullio_render_locked == (fail == 5));
    }
    reset(0);
    assert(!q6apm_fullio_reference_prepare(&pdata, &rt, &card, &cfg));
    assert(phase == 17 && rt.graph == &fresh && rt.fullio_reference_prepared && !rt.fullio_reference_reopen);
    assert(!q6apm_fullio_reference_prepare(&pdata, &rt, &card, &cfg) && phase == 17);
    char data[4] = {1,2,3,4};
    struct iov_iter iter = {data, sizeof(data)};
    assert(!q6apm_fullio_copy(&sub, 0, 3836, &iter, 4) && !memcmp(sample+3836,data,4));
    assert(!q6apm_fullio_fill_silence(&sub, 0, 3836, 4) && !memcmp(sample+3836,"\0\0\0\0",4));
    assert(q6apm_fullio_copy(&sub, 1, 0, &iter, 4) == -EBADFD);
    assert(q6apm_fullio_copy(&sub, 0, 3837, &iter, 4) == -EBADFD);
    iter.limit = 1;
    assert(q6apm_fullio_copy(&sub, 0, 0, &iter, 4) == -EFAULT);
    runtime.dma_area = NULL;
    assert(q6apm_fullio_copy(&sub, 0, 0, &iter, 4) == -EBADFD);
    assert(q6apm_fullio_fill_silence(&sub, 0, 0, 4) == -EBADFD);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'recycle.c'
    c.write_text(source)
    exe = c.with_suffix('')
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Native PCM: old graph must retire before OPEN; failed proof blocks reuse; guarded DMA transfers.')
