#!/usr/bin/env python3
"""Exercise the actual PCM watermark work callbacks against delayed delivery."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
callbacks = '\n'.join(re.search(rf'^static void q6apm_pcm_watermark_{name}\(.*?^\}}', text, re.M | re.S)[0]
                      for name in ('work', 'queue', 'enable'))
source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
struct work_struct { bool queued; };
struct snd_pcm_substream { bool locked, running; unsigned int notified; };
struct q6apm_dai_rtd {
    struct snd_pcm_substream *substream;
    struct work_struct watermark_work;
    bool lock, watermark_enabled, watermark_pending;
};
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
static void unlock(bool **lock) { assert(**lock); **lock = false; }
static bool *lock(bool *l) { assert(!*l); *l = true; return l; }
#define guard(kind) __attribute__((cleanup(unlock))) bool *held = lock
#define scoped_guard(kind, l) \
    for (bool once = true; once; once = false) \
        for (__attribute__((cleanup(unlock))) bool *held = lock(l); once; once = false)
#define snd_pcm_stream_lock_irqsave(s, flags) do { assert(!(s)->locked); (s)->locked = true; (flags) = 0; } while (0)
#define snd_pcm_stream_unlock_irqrestore(s, flags) do { assert((s)->locked && (flags) == 0); (s)->locked = false; } while (0)
static void schedule_work(struct work_struct *work) { work->queued = true; }
static void snd_pcm_period_elapsed_under_stream_lock(struct snd_pcm_substream *stream)
{
    assert(stream->locked);
    if (stream->running)
        stream->notified++;
}
''' + callbacks + r'''
static void deliver(struct q6apm_dai_rtd *prtd)
{
    assert(prtd->watermark_work.queued);
    prtd->watermark_work.queued = false;
    q6apm_pcm_watermark_work(&prtd->watermark_work);
}
int main(void)
{
    struct snd_pcm_substream alsa = {.running = true};
    struct q6apm_dai_rtd prtd = {.substream = &alsa};
    q6apm_pcm_watermark_queue(&prtd);
    assert(!prtd.watermark_work.queued);
    q6apm_pcm_watermark_enable(&prtd, true);
    q6apm_pcm_watermark_queue(&prtd);
    q6apm_pcm_watermark_queue(&prtd);
    deliver(&prtd);
    assert(alsa.notified == 1 && !prtd.watermark_pending);

    q6apm_pcm_watermark_queue(&prtd);
    q6apm_pcm_watermark_enable(&prtd, false);
    q6apm_pcm_watermark_queue(&prtd);
    q6apm_pcm_watermark_enable(&prtd, true);
    deliver(&prtd);
    assert(alsa.notified == 1);

    q6apm_pcm_watermark_queue(&prtd);
    alsa.running = false;
    deliver(&prtd);
    assert(alsa.notified == 1);
    alsa.running = true;
    q6apm_pcm_watermark_queue(&prtd);
    deliver(&prtd);
    assert(alsa.notified == 2);
}
'''
with tempfile.TemporaryDirectory() as td:
    path = Path(td) / 'watermark.c'
    binary = path.with_suffix('')
    path.write_text(source)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', path, '-o', binary], check=True)
    subprocess.run([binary], check=True)
print('PCM watermark work uses the stream lock, coalesces wakeups, and drops STOP-revoked notifications.')
