#!/usr/bin/env python3
"""Test the extracted diagnostic SOFT_PAUSE transaction, not an ALSA trigger."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
dai = Path(sys.argv[2]).read_text()
verify = re.search(r'^static int q6apm_fullio_verify_silent_audit\(.*?^\}', dai, re.M | re.S)[0]
assert re.search(r'if \(ret \|\| !started \|\| !of_property_read_bool\(node, '
                 r'"microsoft,denali-fullio-soft-cycle-audit"\)\)\s*return ret;\s*'
                 r'ret = q6apm_fullio_soft_cycle_audit\(audit->graph\);', verify)
parts = ('q6apm_fullio_soft_event', 'q6apm_fullio_soft_transition', 'q6apm_fullio_soft_cycle_audit')
functions = [re.search(rf'^(?:static )?(?:int|bool) {name}\(.*?^\}}', text, re.M | re.S)[0]
             for name in parts]
state = re.search(r'^enum q6apm_fullio_pull_state \{.*?^\};', text, re.M | re.S)[0]
assert re.search(r'case APM_EVENT_MODULE_TO_CLIENT:\s*if \(q6apm_fullio_soft_event\(graph, data\) \|\| !graph->cb\)', text)
source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <stddef.h>
typedef uint32_t u32;
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x, v) ((x) = (v))
#define cmpxchg(p, o, n) __sync_val_compare_and_swap(p, o, n)
#define dev_info(...) ((void)0)
#define dev_err_probe(dev, err, ...) (err)
#define lockdep_assert_held(p) assert(*(p))
#define GPR_DOMAIN_ID_ADSP 2
#define APM_CMD_SET_CFG 0x01001006
#define GPR_HDR_SIZE 24
#define APM_CMD_HDR_SIZE 16
#define APM_MODULE_PARAM_DATA_SIZE 16
#define __free(x)
#define msecs_to_jiffies(x) (x)
#define IS_ERR(x) (!(x))
#define PTR_ERR(x) (-ENOMEM)
struct apm_module_event { u32 event_id, event_payload_size; };
struct gpr_resp_pkt {
    const void *payload;
    size_t payload_size;
    struct { u32 src_domain, src_port, dest_port; } hdr;
};
struct apm_module_param_data { u32 module_instance_id, param_id, param_size, error_code; };
struct gpr_pkt { u32 headers[(GPR_HDR_SIZE + APM_CMD_HDR_SIZE)/4]; struct apm_module_param_data param; };
''' + state + r'''
struct q6apm_fullio_ring { enum q6apm_fullio_pull_state state; };
struct audioreach_module { u32 instance_id; };
struct apm { bool graph_lock; };
struct port { u32 id; };
struct graph_owner { struct q6apm_fullio_ring *fullio_ring; };
struct q6apm_graph { struct apm *apm; struct port *port; struct graph_owner *ar_graph;
    u32 fullio_soft_event; bool fullio_soft_cycle_attempted, cb; int cmd_wait; };
static struct q6apm_graph g;
static struct gpr_pkt packet;
static struct audioreach_module mod = {0x466b};
static int attempt, waits, ack_failure, no_event, before_ack, wakes;
static bool revoke_mute;
static void wake_up(int *w) { assert(w == &g.cmd_wait); wakes++; }
static bool q6apm_fullio_mute_is_verified(struct q6apm_graph *graph)
{ return graph == &g && !(revoke_mute && attempt); }
static struct audioreach_module *q6apm_find_module_by_mid(struct q6apm_graph *graph, u32 mid)
{ assert(graph == &g && mid == 0x07001019); return &mod; }
static struct gpr_pkt *audioreach_alloc_cmd_pkt(size_t size, u32 opcode, u32 token, u32 src, u32 dst)
{
    assert(size == 16 && opcode == APM_CMD_SET_CFG && !token && src == 42 && dst == 0x466b);
    return &packet;
}
static bool q6apm_fullio_soft_event(struct q6apm_graph *, const struct gpr_resp_pkt *);
static void notify(void)
{
    struct apm_module_event data = {g.fullio_soft_event, 0};
    struct gpr_resp_pkt evt = {.payload = &data, .payload_size = sizeof(data), .hdr = {2, 0x466b, 42}};
    assert(data.event_id == (attempt == 1 ? 0x0800103f : 0x08001043));
    evt.hdr.dest_port++;
    assert(!q6apm_fullio_soft_event(&g, &evt));
    evt.hdr.dest_port--;
    evt.hdr.src_port++;
    assert(!q6apm_fullio_soft_event(&g, &evt));
    evt.hdr.src_port--;
    evt.hdr.src_domain++;
    assert(!q6apm_fullio_soft_event(&g, &evt));
    evt.hdr.src_domain--;
    evt.payload_size--;
    assert(!q6apm_fullio_soft_event(&g, &evt));
    evt.payload_size++;
    data.event_payload_size++;
    assert(!q6apm_fullio_soft_event(&g, &evt));
    data.event_payload_size--;
    data.event_id ^= 1;
    assert(!q6apm_fullio_soft_event(&g, &evt));
    data.event_id ^= 1;
    assert(q6apm_fullio_soft_event(&g, &evt));
    assert(!q6apm_fullio_soft_event(&g, &evt));
}
static int q6apm_fullio_oob_rpc(struct apm *a, struct port *p, struct gpr_pkt *pkt, void *x, void *y)
{
    assert(a == g.apm && p == g.port && pkt == &packet && !x && !y);
    assert(pkt->param.module_instance_id == 0x466b && !pkt->param.param_size && !pkt->param.error_code);
    assert(pkt->param.param_id == (++attempt == 1 ? 0x0800102e : 0x0800102f));
    if (before_ack && attempt != no_event) notify();
    return attempt == ack_failure ? -EIO : 0;
}
static void wait_hook(int *w, int limit)
{
    assert(w == &g.cmd_wait && limit == 50);
    waits++;
    if (!before_ack && attempt != no_event) notify();
}
#define wait_event_timeout(w, condition, time) (wait_hook(&(w), (time)), (condition))
''' + '\n'.join(line for line in text.splitlines() if line.startswith('#define FULLIO_SOFT_')) + '\n' + '\n'.join(functions) + r'''
int main(void)
{
    struct apm apm = {true};
    struct port port = {42};
    struct q6apm_fullio_ring ring = {FULLIO_PULL_RUNNING};
    struct graph_owner owner = {&ring};
    for (before_ack = 0; before_ack <= 1; before_ack++) {
        for (int fault = 0; fault < 5; fault++) {
            g = (struct q6apm_graph){ .apm = &apm, .port = &port, .ar_graph = &owner };
            ring.state = FULLIO_PULL_RUNNING;
            assert(q6apm_fullio_soft_transition(&g, false) == -EPERM);
            attempt = waits = wakes = 0;
            ack_failure = fault == 1 ? 1 : fault == 2 ? 2 : 0;
            no_event = fault == 3 ? 1 : fault == 4 ? 2 : 0;
            assert(q6apm_fullio_soft_cycle_audit(&g) == (ack_failure ? -EIO : no_event ? -ETIMEDOUT : 0));
            assert(attempt == (fault == 1 || fault == 3 ? 1 : 2));
            assert(waits == attempt - !!ack_failure);
            assert(wakes == attempt - !!no_event - (!before_ack && !!ack_failure));
            assert(ring.state == (fault ? FULLIO_PULL_UNCERTAIN : FULLIO_PULL_RUNNING));
            assert(!g.fullio_soft_event && q6apm_fullio_soft_cycle_audit(&g) == -EPERM);
            if (fault) {
                assert(q6apm_fullio_soft_transition(&g, false) == -EPERM);
                assert(q6apm_fullio_soft_transition(&g, true) == -EPERM);
            }
        }
    }
    g.fullio_soft_cycle_attempted = false;
    ring.state = FULLIO_PULL_RUNNING;
    attempt = ack_failure = no_event = 0;
    revoke_mute = true;
    assert(q6apm_fullio_soft_cycle_audit(&g) == -ESTALE);
    assert(attempt == 1 && ring.state == FULLIO_PULL_PAUSED);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / 'cycle.c'
    exe = src.with_suffix('')
    src.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('SOFT_PAUSE audit: exact zero-body transactions, both event orderings, scoped completion and no retry after ambiguity.')
