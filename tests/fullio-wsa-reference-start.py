#!/usr/bin/env python3
"""Exercise the checked reference PA-pair START against modeled hardware."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
begin = text.index('static int wsa884x_fullio_reference_start(')
start = text[begin:text.index('EXPORT_SYMBOL_GPL(wsa884x_fullio_start_pair)', begin)]
assert 'if (!mute && wsa884x->feedback_enabled)' in text
preamble = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stddef.h>
#include <string.h>
typedef long long s64;
#define IS_REACHABLE(x) 1
#define READ_ONCE(x) (x)
#define atomic64_read_acquire(p) (*(p))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK 1
#define SDW_SLAVE_ATTACHED 1
#define SDW_STREAM_ENABLED 2
#define SINGLE_DEPTH_NESTING 1
#define guard(type) (void)
static void mutex_lock_nested(int *lock, int nesting) { assert(!*lock && nesting == 1); *lock = 1; }
static void mutex_unlock(int *lock) { assert(*lock); *lock = 0; }
enum { WSA884X_DAI_PLAYBACK, WSA884X_DAI_VI, WSA884X_DAI_CPS };
enum { WSA884X_ISENSE2, WSA884X_VSENSE1, WSA884X_INTR_MASK0, WSA884X_INTR_MASK1,
       WSA884X_CLSH_CTL_0, WSA884X_PWRSTG_DBG, WSA884X_PDRV_HS_CTL, WSA884X_PA_FSM_EN };
struct reg_sequence { unsigned int reg, def; };
struct sdw_stream_runtime { int state; };
struct sdw_slave { int status; };
struct wsa884x_priv;
struct device_node { bool enabled, muted; };
struct device { struct wsa884x_priv *amp; struct device_node *of_node; int refs; };
struct snd_soc_card { struct device *dev; };
struct snd_soc_component { struct snd_soc_card *card; struct device *dev; void *driver; const char *name_prefix; };
struct wsa884x_priv {
    struct device *dev;
    struct wsa884x_priv *regmap;
    struct sdw_slave *slave;
    struct sdw_stream_runtime *attached[3];
    s64 fullio_pa_epoch;
    bool hw_init, fullio_reference_codec;
    int sp_lock, side;
};
struct wsa884x_fullio_pa_snapshot { unsigned int enable, sta1, err0, err1, vphx; s64 epoch; };
static int wsa884x_component_drv;
static int writes[2], paused, stopped[2], graph_checks, graph_failure, fail_side, fail_at;
static int settle, settle_sleeps, pre_pa_sleeps;
static unsigned int wsa884x_pa_settle_us = 20000;
static bool ready_error, clocks_error, clock_verify_stale, preflight_error;
static int clock_attempts;
static bool of_machine_is_compatible(const char *name) { return !strcmp(name, "microsoft,denali"); }
static bool of_property_read_bool(struct device_node *n, const char *name)
{
    if (!strcmp(name, "microsoft,denali-fullio-reference-render")) return n->enabled;
    assert(!strcmp(name, "microsoft,denali-fullio-muted-test"));
    return n->muted;
}
static struct wsa884x_priv *dev_get_drvdata(struct device *d) { return d->amp; }
static int pm_runtime_resume_and_get(struct device *d) { assert(d); d->refs++; return 0; }
static void pm_runtime_mark_last_busy(struct device *d) { assert(d->refs == 1); }
static void pm_runtime_put_autosuspend(struct device *d) { assert(d->refs-- == 1); }
static int graph(void *p) { assert(p); return ++graph_checks == graph_failure ? -ESTALE : 0; }
static int wsa884x_fullio_read_pa(struct snd_soc_component *c, bool faults, struct wsa884x_fullio_pa_snapshot *snapshot)
{
    assert(c->dev->refs && faults && !writes[0] && !writes[1]);
    *snapshot = (struct wsa884x_fullio_pa_snapshot){.vphx = 2, .epoch = c->dev->amp->fullio_pa_epoch};
    return 0;
}
static int wsa884x_fullio_pa_ready(struct snd_soc_component *c, s64 *epoch)
{
    assert(c->dev->refs == 1 && writes[0] == 10 && writes[1] == 10 && paused == 2);
    if (settle > 0) { settle--; return -EAGAIN; }
    *epoch = c->dev->amp->fullio_pa_epoch;
    return ready_error ? -EIO : 0;
}
static int regmap_write(struct wsa884x_priv *amp, unsigned int address, unsigned int value)
{
    static const unsigned int reg[] = {0, 1, 2, 3, 4, 5, 6, 7, 5, 6};
    static const unsigned int data[] = {7, 0x67, 0x90, 0, 0x67, 8, 0x52, 1, 0xc, 0x5a};
    int index = writes[amp->side]++;
    assert(amp->dev->refs == 1 && index < 10 && reg[index] == address && data[index] == value);
    if (address == WSA884X_PA_FSM_EN)
        assert(pre_pa_sleeps == amp->side + 1); /* settle precedes PA enable */
    assert(!amp->side || (writes[0] == 10 && paused == 1));
    return amp->side == fail_side && index == fail_at ? -EIO : 0;
}
static void usleep_range(int min, int max)
{
    if (min == 1000) { assert(max == 1100); paused++; }
    else if (min == 2000 && max == 3000) { settle_sleeps++; }
    else {
        assert((unsigned int)min == wsa884x_pa_settle_us);
        assert((unsigned int)max == wsa884x_pa_settle_us + 500);
        pre_pa_sleeps++;
    }
}
#define min(a, b) ((a) < (b) ? (a) : (b))
static int wsa_macro_fullio_verify_pair_clocks_off(struct snd_soc_component *l, struct snd_soc_component *r)
{ assert(l != r && !writes[0] && !writes[1]); return preflight_error ? -EBUSY : 0; }
static int wsa_macro_fullio_clock_on_for_pair(struct snd_soc_component *l, struct snd_soc_component *r,
                                           int (*verify)(void *), void *ctx)
{
    ++clock_attempts;
    assert(l != r && paused == 2 && !stopped[0] && !stopped[1] && !verify(ctx));
    if (clock_verify_stale) {
        r->dev->amp->fullio_pa_epoch++;
        return verify(ctx);
    }
    return clocks_error ? -EIO : 0;
}
static int wsa884x_fullio_verified_stop(struct snd_soc_component *c, struct wsa884x_priv *a)
{ assert(c->dev->amp == a && a->dev->refs == 1); stopped[a->side]++; return -ETIMEDOUT; }
'''
tests = r'''
int main(void)
{
    struct device_node node = {.enabled = true};
    struct sdw_slave slave = {SDW_SLAVE_ATTACHED};
    struct sdw_stream_runtime live = {SDW_STREAM_ENABLED};
    struct device devices[2] = {{.of_node = &node}, {.of_node = &node}};
    struct snd_soc_card card = {&devices[0]};
    struct snd_soc_component l = {&card, &devices[0], &wsa884x_component_drv, "SpkrLeft"};
    struct snd_soc_component r = {&card, &devices[1], &wsa884x_component_drv, "SpkrRight"};
    struct wsa884x_priv amps[2];
    int stop_error;
#define RUN() wsa884x_fullio_start_pair(&l, &r, graph, &card, &stop_error)
    for (int trial = -5; trial <= 25; ++trial) {
        for (int i = 0; i < 2; ++i) {
            amps[i] = (struct wsa884x_priv){.dev = &devices[i], .regmap = &amps[i], .slave = &slave,
                .attached = {&live, &live, &live}, .hw_init = true, .fullio_reference_codec = true, .side = i};
            devices[i].amp = &amps[i];
            writes[i] = stopped[i] = 0;
        }
        node.muted = trial == -5;
        amps[1].attached[2] = trial == -4 ? NULL : &live;
        preflight_error = trial == -3;
        graph_checks = clock_attempts = paused = settle_sleeps = pre_pa_sleeps = 0;
        wsa884x_pa_settle_us = trial == 24 ? 300000 : 20000;
        settle = trial == 25 ? 4 : 0;
        graph_failure = trial == -2 ? 1 : trial == 20 ? 2 : 0;
        fail_side = trial >= 0 && trial < 20 ? trial / 10 : -1;
        fail_at = trial >= 0 ? trial % 10 : -1;
        ready_error = trial == 21;
        clocks_error = trial == 22;
        clock_verify_stale = trial == 23;
        stop_error = -EAGAIN;
        int result = RUN();
        assert(stop_error == (trial >= 0 && trial < 24 ? -ETIMEDOUT : 0));
        if (trial >= -5 && trial <= -2) {
            assert(result < 0 && !writes[0] && !writes[1] && !clock_attempts && !stopped[0] && !stopped[1]);
        } else if (trial == -1 || trial == 24 || trial == 25) {
            assert(!result && writes[0] == 10 && writes[1] == 10 && clock_attempts == 1 && !stopped[0] && !stopped[1]);
            assert(settle_sleeps == (trial == 25 ? 4 : 0));
            assert(pre_pa_sleeps == 2);
        } else {
            assert(result == (trial == 20 || trial == 23 ? -ESTALE : -EIO));
            assert(stopped[0] == 1 && stopped[1] == 1);
            assert(clock_attempts == (trial >= 22 ? 1 : 0));
            if (trial < 10 || trial == 20) assert(!writes[1]);
        }
        assert(!devices[0].refs && !devices[1].refs && !amps[1].sp_lock);
    }
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / 'pair.c'
    binary = src.with_suffix('')
    src.write_text(preamble + start + tests)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', src, '-o', binary], check=True)
    subprocess.run([binary], check=True)
print('Reference paired START: both verified PAs precede clocks, every write failure stops both, first error retained.')
