#!/usr/bin/env python3
"""Check native PREPARE ownership and exercise actual tokenized START/STOP control flow."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

apm, dai = (Path(p).read_text() for p in sys.argv[1:])


def get(text, name):
    return re.search(rf'^(?:static )?int {name}\([^;{{]*\{{.*?^\}}', text, re.M | re.S)[0]


prepare = get(dai, 'q6apm_fullio_reference_prepare')
anchors = ('q6apm_fullio_both_pa_off', 'wsa_macro_fullio_clock_off_for_feedback',
           'q6apm_fullio_pcm_configure', 'q6apm_fullio_prepare_pull_media', 'q6apm_fullio_prepare_cal',
           'q6apm_fullio_pcm_buffer', 'q6apm_fullio_pcm_start', 'audioreach_fullio_verify_mute',
           'q6apm_fullio_mute_is_verified', 'snd_pcm_set_runtime_buffer(substream, buffer)')
assert (indices := [prepare.index(x) for x in anchors]) == sorted(indices)
assert 'if (prtd->fullio_reference_prepared)' in prepare
assert prepare.index('q6apm_fullio_reference_recycle') < prepare.index('q6apm_fullio_pcm_start')
assert 'snd_pcm_set_runtime_buffer(substream, NULL)' not in prepare
assert 'wsa884x_fullio_start_pair' not in prepare
assert 'SNDRV_PCM_TRIGGER_START' in (trigger := get(dai, 'q6apm_dai_trigger'))
assert (trigger.index('prtd->fullio_reference_pcm') < trigger.index('q6apm_fullio_reference_start')
        < trigger.index('prtd->fullio_reference_started = true')
        < trigger.index('q6apm_pcm_watermark_enable(prtd, true)'))
assert 'fullio_reference_reopen = true' not in trigger
assert re.search(r'else if \(audioreach_fullio_graph\(prtd->graph->info\)\) \{\s*return -EOPNOTSUPP;', trigger)
assert get(dai, 'q6apm_fullio_reference_start').count('wsa884x_fullio_start_pair') == 1
close = get(dai, 'q6apm_dai_close')
assert close.index('q6apm_fullio_pcm_stop') < close.index('q6apm_graph_close')
assert close.index('!prtd->fullio_reference_pcm && prtd->state') < close.index('q6apm_graph_stop')
assert 'snd_pcm_set_runtime_buffer(substream, NULL)' in get(dai, 'q6apm_dai_hw_free')

state = re.search(r'^enum q6apm_fullio_pull_state \{.*?^\};', apm, re.M | re.S)[0]
source = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stddef.h>
#define guard(mutex) (void)
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x, v) ((x) = (v))
#define APM_CMD_GRAPH_START 1
#define APM_CMD_GRAPH_STOP 2
''' + state + r'''
struct q6apm_fullio_ring { bool pcm_native; enum q6apm_fullio_pull_state state;
    struct { size_t bytes; } pcm_buffer; };
struct audioreach_graph { struct q6apm_fullio_ring *fullio_ring; int start_count; };
struct q6apm { int graph_lock; };
struct q6apm_graph { struct audioreach_graph *ar_graph; struct q6apm *apm; int id; bool info, mute; };
static int start_result, stop_result, starts, stops;
static bool withdraw;
static struct q6apm_graph graph;
static bool audioreach_fullio_graph(bool info) { return info; }
static bool q6apm_fullio_mute_is_verified(struct q6apm_graph *g) { return g->mute; }
static void q6apm_fullio_mute_invalidate(struct q6apm_graph *g) { g->mute = false; }
static int audioreach_graph_mgmt_transaction(struct audioreach_graph *ar, int cmd, bool token)
{
    assert(token && ar == graph.ar_graph);
    /* STOP also contains a START whose transaction was ambiguous. */
    assert(ar->start_count == (cmd == APM_CMD_GRAPH_START ? 0 : 1) ||
           (cmd == APM_CMD_GRAPH_STOP && !ar->start_count));
    if (cmd == APM_CMD_GRAPH_START) {
        assert(ar->fullio_ring->state == FULLIO_PULL_UNCERTAIN && graph.mute);
        starts++;
        if (withdraw) graph.mute = false;
        return start_result;
    }
    assert(cmd == APM_CMD_GRAPH_STOP && ar->fullio_ring->state == FULLIO_PULL_STOP_UNVERIFIED && !graph.mute);
    stops++;
    return stop_result;
}
''' + get(apm, 'q6apm_fullio_pcm_start') + '\n' + get(apm, 'q6apm_fullio_pcm_stop') + r'''
int main(void)
{
    struct q6apm_fullio_ring ring = {.pcm_buffer = {3840}};
    struct audioreach_graph ar = {&ring, 0};
    struct q6apm apm = {0};
    graph = (struct q6apm_graph){&ar, &apm, 0, true, true};
    assert(q6apm_fullio_pcm_start(&graph) == -EPERM && !starts);
    ring.pcm_native = true;
    assert(!q6apm_fullio_pcm_start(&graph) && starts == 1 && ring.state == FULLIO_PULL_RUNNING);
    assert(ar.start_count == 1);
    assert(!q6apm_fullio_pcm_start(&graph) && starts == 1 && ar.start_count == 1);
    assert(!q6apm_fullio_pcm_stop(&graph) && stops == 1 && ring.state == FULLIO_PULL_STOPPED);
    assert(ar.start_count == 0);
    assert(!q6apm_fullio_pcm_stop(&graph) && stops == 1);
    ring.state = FULLIO_PULL_NEW;
    graph.mute = true;
    start_result = -ETIMEDOUT;
    assert(q6apm_fullio_pcm_start(&graph) == -ETIMEDOUT && starts == 2);
    assert(!ar.start_count && ring.state == FULLIO_PULL_UNCERTAIN);
    assert(q6apm_fullio_pcm_start(&graph) == -ENOTRECOVERABLE && starts == 2);
    stop_result = -EIO;
    assert(q6apm_fullio_pcm_stop(&graph) == -EIO && stops == 2);
    assert(q6apm_fullio_pcm_stop(&graph) == -ENOTRECOVERABLE && stops == 2);
    ring.state = FULLIO_PULL_NEW;
    start_result = stop_result = 0;
    graph.mute = true; withdraw = true;
    assert(q6apm_fullio_pcm_start(&graph) == -ESTALE && starts == 3);
    assert(ar.start_count == 1 && ring.state == FULLIO_PULL_RUNNING);
    assert(!q6apm_fullio_pcm_stop(&graph) && stops == 3);
    assert(ar.start_count == 0);
}
'''
with tempfile.TemporaryDirectory() as td:
    src = Path(td) / 'prepare.c'
    binary = src.with_suffix('')
    src.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', src, '-o', binary], check=True)
    subprocess.run([binary], check=True)
print('Native PREPARE: mute proof, one DSP START, scoped STOP and no re-arm after ambiguous STOP.')
