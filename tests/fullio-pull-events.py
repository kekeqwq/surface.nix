#!/usr/bin/env python3
"""Exercise the extracted Golden registration path and its wire framing."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()


def function(name):
    return re.search(rf'^(?:static )?(?:int|bool) {name}\(.*?^\}}', text, re.M | re.S)[0]


callback = function('graph_callback')
assert re.search(r'result->opcode == APM_CMD_REGISTER_MODULE_EVENTS\) &&\s+q6apm_fullio_oob_reply', callback)
source = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;
typedef uint32_t __le32;
#define ALIGN(x, a) (((x) + (a)-1) & ~((a)-1))
#define cpu_to_le32(x) (x)
#define EXPORT_SYMBOL_GPL(x)
#define __free(x)
#define IS_ERR(x) (!(x))
#define PTR_ERR(x) (-ENOMEM)
#define GPR_HDR_SIZE 24
#define APM_CMD_HDR_SIZE 16
#define APM_CMD_REGISTER_MODULE_EVENTS 0x0100100e
#define EVENT_ID_SH_MEM_PULL_PUSH_MODE_WATERMARK 0x0800101c
#define GPR_DOMAIN_ID_ADSP 2
struct apm_module_event { u32 event_id, event_payload_size; };
struct gpr_resp_pkt {
    const void *payload;
    int payload_size;
    struct { u32 src_domain, src_port, dest_port; } hdr;
};
static u32 get_unaligned_le32(const void *p)
{
    const unsigned char *b = p;
    return b[0] | (u32)b[1] << 8 | (u32)b[2] << 16 | (u32)b[3] << 24;
}
struct apm_module_register_events { u32 module_instance_id, event_id, is_register,
    error_code, event_config_payload_size, reserved; };
struct gpr_pkt { unsigned char data[128]; };
struct audioreach_module { u32 instance_id; };
struct q6apm_fullio_ring { u32 config_bytes; };
struct graph_owner { const struct q6apm_fullio_ring *fullio_ring; };
struct q6apm_graph { struct graph_owner *ar_graph; struct { u32 id; } *port;
    bool *info; u32 shm_iid; void *apm; };
static struct gpr_pkt pkt;
static struct audioreach_module pause = {0x466b};
static unsigned stage, fail_stage, last_size, last_dest;
static void *audioreach_alloc_cmd_pkt(size_t size, u32 opcode, u32 token, u32 src, u32 dst)
{
    assert(opcode == APM_CMD_REGISTER_MODULE_EVENTS && token == 0 && src == 42);
    last_size = size;
    last_dest = dst;
    memset(&pkt, 0xff, sizeof(pkt));
    return &pkt;
}
static bool audioreach_fullio_graph(const bool *info) { return *info; }
static const struct audioreach_module *q6apm_find_module_by_mid(struct q6apm_graph *graph, u32 mid)
{ assert(graph && mid == 0x07001019); return &pause; }
static int q6apm_fullio_oob_rpc(void *apm, void *port, struct gpr_pkt *p, void *h, void *g)
{
    u32 bytes[10];
    const u32 ids[] = {EVENT_ID_SH_MEM_PULL_PUSH_MODE_WATERMARK, 0x0800103f, 0x08001043};
    assert(apm && port && !h && !g && p == &pkt && stage < 3);
    memcpy(bytes, p->data + GPR_HDR_SIZE + APM_CMD_HDR_SIZE, last_size);
    assert(last_dest == (stage == 0 ? 0x4660 : 0x466b));
    assert(last_size == (stage == 0 ? 40 : 24));
    assert(bytes[0] == last_dest && bytes[1] == ids[stage] && bytes[2] == 1);
    assert(bytes[3] == 0 && bytes[4] == (stage == 0 ? 12 : 0) && bytes[5] == 0);
    if (stage == 0)
        assert(bytes[6] == 2 && bytes[7] == 1920 && bytes[8] == 3840 && bytes[9] == 0);
    ++stage;
    return stage == fail_stage ? -ETIMEDOUT : 0;
}
''' + '\n'.join(line for line in text.splitlines() if line.startswith(('#define FULLIO_SOFT_', '#define FULLIO_PULL_PERIOD_BYTES'))) + '\n' + '\n'.join(map(function, (
    'q6apm_fullio_register_event', 'q6apm_fullio_register_pull_events', 'q6apm_fullio_pull_watermark',
))) + r'''
int main(void)
{
    struct q6apm_fullio_ring ring = {3840};
    struct graph_owner owner = {&ring};
    bool fullio = true;
    struct q6apm_graph graph = { .ar_graph = &owner, .info = &fullio, .shm_iid = 0x4660 };
    graph.port = malloc(sizeof(*graph.port));
    assert(graph.port);
    graph.port->id = 42;
    graph.apm = &graph;
    for (fail_stage = 0; fail_stage <= 3; ++fail_stage) {
        stage = 0;
        assert(q6apm_fullio_register_pull_events(&graph, 1920) == (fail_stage ? -ETIMEDOUT : 0));
        assert(stage == (fail_stage ? fail_stage : 3));
    }
    stage = 0;
    assert(q6apm_fullio_register_pull_events(&graph, 960) == -EINVAL);
    pause.instance_id = 0x466c;
    assert(q6apm_fullio_register_pull_events(&graph, 1920) == -EINVAL);
    pause.instance_id = 0x466b;
    ring.config_bytes = 7680;
    assert(q6apm_fullio_register_pull_events(&graph, 1920) == -EINVAL);
    ring.config_bytes = 3840;
    fullio = false;
    assert(q6apm_fullio_register_pull_events(&graph, 1920) == -EINVAL);
    assert(stage == 0);

    struct { struct apm_module_event event; unsigned char level[4]; } wm = {
        {EVENT_ID_SH_MEM_PULL_PUSH_MODE_WATERMARK, 4}, {0x80, 0x07, 0, 0},
    };
    struct gpr_resp_pkt data = {&wm, sizeof(wm), {GPR_DOMAIN_ID_ADSP, 0x4660, 42}};
    assert(q6apm_fullio_pull_watermark(&graph, &data));
    wm.level[0] = 0; wm.level[1] = 0x0f;
    assert(q6apm_fullio_pull_watermark(&graph, &data));
    wm.level[0] = 1;
    assert(!q6apm_fullio_pull_watermark(&graph, &data));
    wm.level[0] = 0;
    wm.event.event_payload_size = 8;
    assert(!q6apm_fullio_pull_watermark(&graph, &data));
    wm.event.event_payload_size = 4;
    wm.event.event_id++;
    assert(!q6apm_fullio_pull_watermark(&graph, &data));
    wm.event.event_id--;
    for (int bad = 0; bad < 6; ++bad) {
        struct gpr_resp_pkt wrong = data;
        switch (bad) {
        case 0: wrong.payload = NULL; break;
        case 1: wrong.payload_size--; break;
        case 2: wrong.hdr.src_domain++; break;
        case 3: wrong.hdr.src_port++; break;
        case 4: wrong.hdr.dest_port++; break;
        case 5: wrong.payload_size = -1; break;
        }
        assert(!q6apm_fullio_pull_watermark(&graph, &wrong));
    }
    graph.shm_iid++;
    assert(!q6apm_fullio_pull_watermark(&graph, &data));
    free(graph.port);
}
'''
with tempfile.TemporaryDirectory() as td:
    path = Path(td) / 'events.c'
    binary = path.with_suffix('')
    path.write_text(source)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', path, '-o', binary], check=True)
    subprocess.run([binary], check=True)
print('Golden pull registration order, timeout containment and graph-scoped watermark decoding verified.')
