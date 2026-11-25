#!/usr/bin/env python3
"""Test the isolated ring's callback boundary in composed kernel sources."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile


dai, apm = (Path(p).read_text() for p in sys.argv[1:])
assert 'fullio_ring_watermark_audit' not in dai
open_pcm = re.search(r'^static int q6apm_dai_open\(.*?^\}', dai, re.M | re.S)[0]
assert 'independent = q6apm_fullio_independent_pcm(component, graph_id, substream->stream);' in open_pcm
assert re.search(r'q6apm_graph_open\(dev,\s*independent && !prtd->fullio_reference_pcm \? NULL : event_handler,\s*'
                 r'independent && !prtd->fullio_reference_pcm \? NULL : prtd,\s*graph_id, substream->stream\)', open_pcm)
assert re.search(r'if \(independent\)\s*runtime->hw.info &= ~\(SNDRV_PCM_INFO_PAUSE \| SNDRV_PCM_INFO_RESUME\);', open_pcm)
assert re.search(r'if \(independent\)\s*return 0;', open_pcm)
assert open_pcm.index('if (independent)\n\t\treturn 0;') < open_pcm.index('prtd->pos_buffer =')
pointer = re.search(r'^static snd_pcm_uframes_t q6apm_dai_pointer\(.*?^\}', dai, re.M | re.S)[0]
assert (pointer.index('if (prtd->independent_pcm)') < pointer.index('q6apm_fullio_pcm_cursor')
        < pointer.index('prtd->pos_buffer->frame_counter'))
open_graph = re.search(r'^struct q6apm_graph \*q6apm_graph_open\(.*?^\}', apm, re.M | re.S)[0]
assert open_graph.index('graph->cb = cb;') < open_graph.index('gpr_alloc_port(')
callback = re.search(r'^static int graph_callback\(.*?^\}', apm, re.M | re.S)[0]
module_event = callback[callback.index('\tcase APM_EVENT_MODULE_TO_CLIENT:'):
                        callback.index('\tcase DATA_CMD_RSP_WR_SH_MEM_EP_DATA_BUFFER_DONE_V2:')]
assert callback.index('q6apm_fullio_oob_reply') < callback.index(module_event)
assert module_event.index('!graph->cb') < module_event.index('q6apm_fullio_pull_watermark')
assert module_event.index('q6apm_fullio_pull_watermark') < module_event.index('graph->cb(client_event')
assert callback.count('if (graph->cb)') == 3

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#define APM_EVENT_MODULE_TO_CLIENT 1
#define EVENT_ID_SH_MEM_PULL_PUSH_MODE_WATERMARK 2
#define APM_CLIENT_EVENT_WATERMARK_EVENT 3
struct apm_module_event { int event_id, payload_size; };
struct packet { int payload_size; void *payload; };
struct header { int token; };
struct graph { void (*cb)(int, int, void *, void *); void *priv; bool info; };
#define q6apm_fullio_soft_event(graph, data) false
#define audioreach_fullio_graph(info) (info)
#define q6apm_fullio_pull_watermark(graph, data) false
static int delivered;
static void elapsed(int kind, int token, void *data, void *priv)
{
    assert(kind == APM_CLIENT_EVENT_WATERMARK_EVENT && token == 17 && data && priv == &delivered);
    delivered++;
}
static int receive(struct graph *graph, struct packet *data, const struct header *hdr)
{
    struct apm_module_event *event;
    int client_event;
    switch (APM_EVENT_MODULE_TO_CLIENT) {
''' + module_event + r'''
    }
    return 0;
}
int main(void)
{
    struct apm_module_event event = { EVENT_ID_SH_MEM_PULL_PUSH_MODE_WATERMARK, 0 };
    struct header header = { 17 };
    struct graph control_only = { .info = true };
    struct graph ordinary = { .cb = elapsed, .priv = &delivered };
    struct graph fullio = { .cb = elapsed, .priv = &delivered, .info = true };
    struct packet absent = { 0, NULL }, truncated = { sizeof(event) - 1, &event };
    struct packet valid = { sizeof(event), &event };
    assert(!receive(&control_only, &absent, &header));
    assert(!receive(&control_only, &truncated, &header));
    assert(!receive(&control_only, &valid, &header) && !delivered);
    assert(receive(&ordinary, &absent, &header) == -EINVAL);
    assert(receive(&ordinary, &truncated, &header) == -EINVAL);
    assert(!receive(&ordinary, &valid, &header) && delivered == 1);
    assert(!receive(&fullio, &valid, &header) && delivered == 1);
    event.event_id = 0;
    assert(!receive(&ordinary, &valid, &header) && delivered == 1);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / 'callback.c'
    exe = src.with_suffix('')
    src.write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Independent ring installs no PCM callback; ordinary watermark events still dispatch and truncated envelopes are rejected.')
