#!/usr/bin/env python3
"""Exercise the patched PA-off START/STOP control flow with a modeled DSP."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile

STUBS = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#define EXPORT_SYMBOL_GPL(sym)
#define READ_ONCE(x) (x)
#define guard(kind) lock_mock
#define lock_mock(lock) ((void)(lock))
#define APM_CMD_GRAPH_START 1
#define APM_CMD_GRAPH_STOP 2
struct device_node { bool muted, clocks_off, prepare, start, post_pa, inject, taps, dma; };
struct device { struct device_node *of_node; };
struct snd_soc_card { struct device *dev; };
@PULL_STATE@
struct fullio_ring { enum q6apm_fullio_pull_state state; };
struct audioreach_graph { bool *info; int start_count; struct fullio_ring *fullio_ring; };
struct q6apm { bool fullio_start_audit_attempted; int graph_lock; };
struct q6apm_graph {
    struct audioreach_graph *ar_graph;
    struct q6apm *apm;
    struct device *dev;
    bool mute;
};

static int start_calls, stop_calls, start_error, stop_error;
static bool of_machine_is_compatible(const char *name) { return !strcmp(name, "microsoft,denali"); }
static bool of_property_read_bool(const struct device_node *n, const char *name)
{
    if (!strcmp(name, "microsoft,denali-fullio-muted-test")) return n->muted;
    if (!strcmp(name, "microsoft,denali-fullio-clock-off-audit")) return n->clocks_off;
    if (!strcmp(name, "microsoft,denali-fullio-dsp-prepare-audit")) return n->prepare;
    if (!strcmp(name, "microsoft,denali-fullio-dsp-start-audit")) return n->start;
    if (!strcmp(name, "microsoft,denali-fullio-post-pa-test")) return n->post_pa;
    if (!strcmp(name, "microsoft,denali-fullio-dsp-stop-fault-audit")) return n->inject;
    if (!strcmp(name, "microsoft,denali-fullio-immediate-taps-audit")) return n->taps;
    if (!strcmp(name, "microsoft,denali-fullio-ring-dma-audit")) return n->dma;
    assert(false);
    return false;
}
static bool audioreach_fullio_graph(const bool *info) { return *info; }
static bool q6apm_fullio_mute_is_verified(const struct q6apm_graph *g) { return g->mute; }
static void q6apm_fullio_mute_invalidate(struct q6apm_graph *g) { g->mute = false; }
static int audioreach_graph_mgmt_transaction(struct audioreach_graph *g, int opcode, bool token)
{
    assert(g && token);
    if (opcode == APM_CMD_GRAPH_START) {
        assert(!g->fullio_ring || g->fullio_ring->state == FULLIO_PULL_UNCERTAIN);
        start_calls++;
        return start_error;
    }
    assert(opcode == APM_CMD_GRAPH_STOP && start_calls == stop_calls + 1);
    assert(!g->fullio_ring || g->fullio_ring->state == FULLIO_PULL_UNCERTAIN);
    stop_calls++;
    return stop_error;
}
#define dev_err_probe(dev, err, fmt) ((void)(dev), (err))
typedef unsigned long long u64;
static u64 ktime_get_ns(void) { static u64 now; return ++now; }
static void dev_info(struct device *dev, const char *fmt, ...) { assert(dev && fmt); }
"""

TESTS = r"""
struct verifier { struct q6apm_graph *graph; int pre, post; bool revoke; };
static int verify(void *ctx, bool started)
{
    struct verifier *v = ctx;
    assert(v->graph->mute);
    if (!started) return v->pre;
    assert(!v->graph->ar_graph->fullio_ring || v->graph->ar_graph->fullio_ring->state == FULLIO_PULL_RUNNING);
    if (v->revoke) v->graph->mute = false;
    return v->post;
}

int main(void)
{
    struct device_node dt = { .muted = true, .clocks_off = true, .prepare = true };
    struct device dev = {&dt};
    struct snd_soc_card card = {&dev};
    struct q6apm apm = {0};
    bool fullio = true;
    struct audioreach_graph ar = {.info = &fullio};
    struct q6apm_graph graph = {&ar, &apm, &dev, true};
    struct verifier v = {&graph, 0, 0, false};
    int reported_stop = -1;
#define RUN() q6apm_fullio_audit_start_stop(&graph, &card, verify, &v, &reported_stop)
    assert(RUN() == -EPERM && !start_calls && reported_stop == 0);
    dt.start = true;
    dt.post_pa = true;
    assert(RUN() == -EPERM && !start_calls);
    dt.post_pa = false;
    graph.mute = false;
    assert(RUN() == -EPERM && !start_calls);
    graph.mute = true;
    v.pre = -EBUSY;
    assert(RUN() == -EBUSY && !start_calls && !apm.fullio_start_audit_attempted);
    v.pre = 0;
    dt.taps = true;
    assert(RUN() == 0 && start_calls == 1 && stop_calls == 1 && !graph.mute);
    graph.mute = true;
    assert(RUN() == -EALREADY && start_calls == 1);

    apm.fullio_start_audit_attempted = false;
    start_error = -ETIMEDOUT;
    assert(RUN() == -ETIMEDOUT && start_calls == 2 && stop_calls == 2 && !graph.mute);
    assert(reported_stop == 0);
    start_error = 0;
    graph.mute = true;
    apm.fullio_start_audit_attempted = false;
    v.revoke = true;
    assert(RUN() == -ESTALE && start_calls == 3 && stop_calls == 3 && !graph.mute);
    graph.mute = true;
    apm.fullio_start_audit_attempted = false;
    v.revoke = false;
    v.post = -EILSEQ;
    stop_error = -ETIMEDOUT;
    assert(RUN() == -ETIMEDOUT && start_calls == 4 && stop_calls == 4 && !graph.mute);
    assert(reported_stop == -ETIMEDOUT); /* Unlike identical START errno. */
    graph.mute = true;
    assert(RUN() == -EALREADY && start_calls == 4 && reported_stop == 0);
    stop_error = v.post = 0;
    apm.fullio_start_audit_attempted = false;
    dt.inject = true;
    assert(RUN() == -ECANCELED && start_calls == 5 && stop_calls == 5 && !graph.mute);
    graph.mute = true;
    assert(RUN() == -EALREADY && start_calls == 5);
    struct fullio_ring ring = {0};
    apm.fullio_start_audit_attempted = dt.inject = false;
    dt.dma = true;
    assert(RUN() == -EPERM && ring.state == FULLIO_PULL_NEW);
    ar.fullio_ring = &ring;
    dt.dma = false;
    assert(RUN() == -EPERM && ring.state == FULLIO_PULL_NEW);
    dt.dma = true;
    ring.state = FULLIO_PULL_STOPPED;
    assert(RUN() == -EPERM && start_calls == 5);
    ring.state = FULLIO_PULL_NEW;
    start_error = stop_error = -ETIMEDOUT;
    assert(RUN() == -ETIMEDOUT && start_calls == 6 && stop_calls == 6);
    assert(ring.state == FULLIO_PULL_UNCERTAIN);
    ring = (struct fullio_ring){0};
    graph.mute = true;
    apm.fullio_start_audit_attempted = false;
    stop_error = 0;
    assert(RUN() == -ETIMEDOUT && start_calls == 7 && stop_calls == 7);
    assert(ring.state == FULLIO_PULL_STOPPED);
#undef RUN
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_tree", type=Path)
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    args = parser.parse_args()
    path = args.kernel_tree / "sound/soc/qcom/qdsp6/q6apm.c"
    text = path.read_text()
    start = text.index("int q6apm_fullio_audit_start_stop(")
    end = text.index("EXPORT_SYMBOL_GPL(q6apm_fullio_audit_start_stop)", start)
    with tempfile.TemporaryDirectory(prefix="fullio-start-audit-") as tmp:
        src, binary = Path(tmp) / "audit.c", Path(tmp) / "audit"
        state_start = text.index('enum q6apm_fullio_pull_state {')
        state_end = text.index('};', state_start) + 2
        src.write_text(STUBS.replace('@PULL_STATE@', text[state_start:state_end]) + text[start:end] + TESTS)
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                        str(src), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)
    print("FullIO START audit: markers, PA/mute checks, STOP on failure, and no retry passed")


if __name__ == "__main__":
    main()
