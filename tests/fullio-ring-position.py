#!/usr/bin/env python3
"""Require advancing coherent publications from the real DMA evidence helper."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
def extract(decl):
    return re.search(rf'^{decl}\([^{{]*\{{.*?^\}}', text, re.M | re.S).group()

helper = '\n'.join(map(extract, (
    'static int q6apm_fullio_ring_cursor', 'struct snd_dma_buffer \\*q6apm_fullio_pcm_buffer',
    'int q6apm_fullio_pcm_cursor', 'int q6apm_fullio_ring_position_audit',
)))
attach = extract('static int q6apm_fullio_ring_attach')
assert (attach.index('ring->config_bytes = config_bytes;') < attach.index('smp_store_release')
        < attach.index('q6apm_fullio_oob_rpc') < attach.index('if (ret)')
        < attach.index('ring->pcm_buffer.area = ring->cpu')
        < attach.index('smp_store_release(&ring->pcm_buffer.bytes, config_bytes)'))
assert 'smp_load_acquire' in helper
state = re.search(r'^enum q6apm_fullio_pull_state \{.*?^\};', text, re.M | re.S)[0]
source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
typedef uint32_t u32, __le32;
typedef uint16_t __le16;
#define BIT(n) (1UL << (n))
#define lockdep_assert_held(lock) assert(*(lock))
#define dma_rmb() ((void)0)
#define dma_wmb() ((void)0)
#define le32_to_cpu(x) (x)
#define READ_ONCE(x) read_word(&(x))
#define smp_load_acquire(x) (*(x))
#define dev_info(...) ((void)0)
struct q6apm { bool graph_lock; };
struct region { u32 size; };
struct snd_dma_buffer { void *area; size_t bytes; };
''' + state + r'''
struct q6apm_fullio_ring {
    u32 config_bytes;
    enum q6apm_fullio_pull_state state;
    void *cpu;
    struct region data, pos;
    struct snd_dma_buffer pcm_buffer;
};
struct audioreach_graph { struct q6apm_fullio_ring *fullio_ring; };
struct q6apm_graph { struct audioreach_graph *ar_graph; struct q6apm *apm; };
static const struct {
    u32 seq[8], index[8];
    int result;
} schedules[] = {
    {{0}, {0}, -ENODATA},
    {{10,10,10,10,10,10,10,10}, {0}, -ENODATA},
    {{0,2,3}, {0,0,4}, 0},
    {{9,8,7,6,5,4,3,2}, {0}, -EILSEQ},
    {{1,2,3,4,5,6,7,8}, {0}, -ENODATA},
    {{2,3}, {4,0}, 0}, /* modulo ring wrap */
    {{10,10}, {0,4}, -EILSEQ},
    {{1}, {8}, -ERANGE},
    {{1}, {2}, -ERANGE},
    {{UINT32_MAX,0,1}, {4,0,0}, 0}, /* zero is not a published sequence */
    {{1,0x80000001u}, {0,4}, -EILSEQ},
};
static u32 backing[4], step, schedule, reads;
static bool torn;
static u32 read_word(const u32 *p)
{
    if (p == &backing[2]) return schedules[schedule].seq[step] + (torn && ++reads % 2 == 0);
    assert(p == &backing[3]);
    return schedules[schedule].index[step];
}
static void usleep_range(int min, int max) { assert(min == 3000 && max == 4000); step++; }
static bool memchr_inv(const void *p, int c, int n)
{
    for (int i = 0; i < n; ++i) if (((const unsigned char *)p)[i] != c) return true;
    return false;
}
''' + helper + r'''
int main(void)
{
    struct q6apm_fullio_ring ring = {.config_bytes = 8, .cpu = backing, .data = {8}, .pos = {8}};
    struct q6apm apm = {true};
    struct audioreach_graph ar = {&ring};
    struct q6apm_graph g = {&ar, &apm};
    assert(!q6apm_fullio_ring_position_audit(&g, false));
    backing[2] = 1;
    assert(q6apm_fullio_ring_position_audit(&g, false) == -EILSEQ);
    backing[2] = 0;
    backing[0] = 1;
    assert(q6apm_fullio_ring_position_audit(&g, false) == -EILSEQ);
    backing[0] = 0;
    assert(q6apm_fullio_ring_position_audit(&g, true) == -EPERM);
    ring.state = FULLIO_PULL_RUNNING;
    for (schedule = 0; schedule < sizeof schedules / sizeof schedules[0]; ++schedule) {
        step = 0;
        assert(q6apm_fullio_ring_position_audit(&g, true) == schedules[schedule].result);
    }
    step = 0; schedule = 2; torn = true;
    assert(q6apm_fullio_ring_position_audit(&g, true) == -ENODATA);
    u32 seq = 99, bytes = 99;
    step = 0; schedule = 0; torn = false;
    assert(q6apm_fullio_ring_cursor(&ring, 4, &seq, &bytes) == -EAGAIN);
    assert(seq == 99 && bytes == 99);
    step = 1; schedule = 2;
    assert(q6apm_fullio_ring_cursor(&ring, 0, &seq, &bytes) == -ERANGE);
    assert(seq == 99 && bytes == 99);
    assert(!q6apm_fullio_ring_cursor(&ring, 4, &seq, &bytes));
    assert(seq == 2 && bytes == 0);
    bytes = 99;
    assert(!q6apm_fullio_pcm_cursor(&g, 4, &bytes) && bytes == 0);
    assert(!q6apm_fullio_pcm_buffer(&g, 8)); /* Ring owned, but SET_CFG unconfirmed. */
    ring.pcm_buffer = (struct snd_dma_buffer){.area = backing, .bytes = 8};
    assert(!q6apm_fullio_pcm_buffer(&g, 0) && !q6apm_fullio_pcm_buffer(&g, 16));
    struct snd_dma_buffer *view = q6apm_fullio_pcm_buffer(&g, 8);
    assert(view == &ring.pcm_buffer && view->area == backing && view->bytes == 8);
    ar.fullio_ring = 0;
    assert(!q6apm_fullio_pcm_buffer(&g, 8));
    bytes = 99;
    assert(q6apm_fullio_pcm_cursor(&g, 4, &bytes) == -EAGAIN && bytes == 99);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'position.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('DSP position audit: coherent sequence and stereo-aligned byte progress required; modulo wrap allowed, stationary or invalid cursors rejected.')
