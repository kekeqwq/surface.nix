#!/usr/bin/env python3
"""Exercise last-reference Close proof and admission with the extracted helpers."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()


def extract(name):
    return re.search(rf'^static [^\n]+\b{name}\([^{{]*\{{.*?^\}}', text, re.M | re.S).group()


admission = extract('q6apm_get_audioreach_graph')
assert admission.index('q6apm_fullio_close_blocks_open(apm, graph->info)') < admission.index('kref_get(')
assert admission.index('q6apm_fullio_close_blocks_open(apm, info)') < admission.index('idr_alloc(')
state = re.search(r'^enum q6apm_fullio_pull_state \{.*?^\};', text, re.M | re.S)[0]
source = r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <assert.h>
#include <errno.h>
#define APM_CMD_GRAPH_CLOSE 1
#define guard(mutex) (void)
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define lockdep_assert_held(lock) assert(*(lock))
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define kfree(p) free(p)
struct kref { int count; };
struct q6apm { int graph_lock, graph_idr; bool fullio_close_failed; };
struct audioreach_graph_info { bool fullio; };
struct audioreach_graph {
    struct kref refcount;
    struct q6apm *apm;
    struct audioreach_graph_info *info;
    int id, start_count;
    struct q6apm_fullio_ring *fullio_ring;
    void *graph;
};
''' + state + r'''
struct q6apm_fullio_ring { enum q6apm_fullio_pull_state state; void *gainstep_cpu; };
static int external_start_count;
static int token_commands, generic_commands, idr_removed, injected_error;
static int safe_drop, quarantined, unmap_error;
static int q6apm_fullio_ring_drop(struct q6apm *apm, struct q6apm_fullio_ring **r, bool quiescent)
{
    assert(apm->graph_lock && token_commands > safe_drop + quarantined);
    assert(quiescent == (!injected_error && !external_start_count &&
                         ((*r)->state == FULLIO_PULL_NEW || (*r)->state == FULLIO_PULL_STOPPED)));
    *r = NULL;
    if (!quiescent || unmap_error) { quarantined++; return -ENOTRECOVERABLE; }
    safe_drop++;
    return 0;
}
static bool audioreach_fullio_graph(struct audioreach_graph_info *info) { return info->fullio; }
static int audioreach_graph_mgmt_transaction(struct audioreach_graph *g, int op, bool token)
{ assert(g && op == APM_CMD_GRAPH_CLOSE && token && g->apm->graph_lock); token_commands++; return injected_error; }
static int audioreach_graph_mgmt_cmd(struct audioreach_graph *g, int op)
{ assert(g && op == APM_CMD_GRAPH_CLOSE && g->apm->graph_lock); generic_commands++; return injected_error; }
static void idr_remove(int *h, int id) { assert(h && id == 0); idr_removed++; }
static int kref_put(struct kref *ref, void (*release)(struct kref *))
{
    if (--ref->count) return 0;
    release(ref);
    return 1;
}
''' + '\n'.join(extract(name) for name in ('q6apm_fullio_close_blocks_open',
    'q6apm_put_audioreach_graph', 'q6apm_release_audioreach_graph')) + r'''
static int close_graph_with_ring(struct q6apm *apm, struct audioreach_graph_info *info,
                                  struct q6apm_fullio_ring *ring)
{
    struct audioreach_graph *g = calloc(1, sizeof(*g));
    assert(g);
    g->apm = apm;
    g->info = info;
    g->fullio_ring = ring;
    g->start_count = external_start_count;
    g->refcount.count = 1;
    return q6apm_release_audioreach_graph(g);
}
static int close_graph(struct q6apm *apm, struct audioreach_graph_info *info)
{ return close_graph_with_ring(apm, info, NULL); }
int main(void)
{
    struct q6apm apm = { .graph_lock = 1 }, unrelated = { .graph_lock = 1 };
    struct audioreach_graph_info speaker = {true}, mic = {false};
    struct audioreach_graph *shared = calloc(1, sizeof(*shared));
    assert(shared);
    *shared = (struct audioreach_graph){.refcount = {2}, .apm = &apm, .info = &speaker};
    assert(q6apm_release_audioreach_graph(shared) == -EBUSY);
    assert(!token_commands && !apm.fullio_close_failed);
    assert(!q6apm_release_audioreach_graph(shared));
    assert(token_commands == 1 && generic_commands == 0 && idr_removed == 1);
    assert(!q6apm_fullio_close_blocks_open(&apm, &speaker));
    injected_error = -ETIMEDOUT;
    close_graph(&apm, &mic);
    assert(token_commands == 1 && generic_commands == 1 && idr_removed == 2);
    assert(!q6apm_fullio_close_blocks_open(&apm, &speaker));
    assert(close_graph(&apm, &speaker) == -ENOTRECOVERABLE);
    assert(token_commands == 2 && generic_commands == 1 && idr_removed == 3);
    assert(q6apm_fullio_close_blocks_open(&apm, &speaker));
    assert(!q6apm_fullio_close_blocks_open(&apm, &mic));
    assert(!q6apm_fullio_close_blocks_open(&unrelated, &speaker));
    injected_error = 0;
    close_graph(&apm, &mic);
    assert(q6apm_fullio_close_blocks_open(&apm, &speaker));
    struct q6apm_fullio_ring ring = {0};
    close_graph_with_ring(&unrelated, &speaker, &ring);
    assert(safe_drop == 1 && !quarantined && !unrelated.fullio_close_failed);
    injected_error = -ETIMEDOUT;
    close_graph_with_ring(&unrelated, &speaker, &ring);
    assert(safe_drop == 1 && quarantined == 1 && unrelated.fullio_close_failed);
    injected_error = 0;
    unmap_error = -EIO;
    struct q6apm third = {.graph_lock = 1};
    assert(close_graph_with_ring(&third, &speaker, &ring) == -ENOTRECOVERABLE);
    assert(safe_drop == 1 && quarantined == 2 && third.fullio_close_failed);
    unmap_error = 0;
    for (int state = FULLIO_PULL_RUNNING; state <= FULLIO_PULL_UNCERTAIN; state++) {
        ring.state = state;
        close_graph_with_ring(&third, &speaker, &ring);
        assert(safe_drop == 1 && quarantined == 2 + state);
    }
    ring.state = FULLIO_PULL_STOPPED;
    close_graph_with_ring(&third, &speaker, &ring);
    assert(safe_drop == 2 && quarantined == 5);
    external_start_count = 1;
    close_graph_with_ring(&third, &speaker, &ring);
    assert(safe_drop == 2 && quarantined == 6);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'proof.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('GRAPH_CLOSE: token required for FullIO; failed proof sticks on that APM, without blocking MicArray.')
