#!/usr/bin/env python3
"""Exercise the dormant post-PA clock lifecycle with the actual helpers."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()


def extract(name):
    return re.search(rf'^(?:static )?int {name}\([^;{{]*\{{.*?^\}}', source, re.M | re.S).group()


code = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stddef.h>
#define guard(x) (void)
#define lockdep_assert_held(x) assert(x)
#define dev_info_ratelimited(...) ((void)0)
#define dev_err_ratelimited(...) ((void)0)
#define dev_err(...) ((void)0)
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define BIT(i) (1u << (i))
#define CDC_WSA_TX_SPKR_PROT_RESET_MASK 2
#define CDC_WSA_TX_SPKR_PROT_RESET 2
#define CDC_WSA_TX_SPKR_PROT_CLK_EN_MASK 1
struct wsa_macro { void *dev, *regmap; bool fullio_clock_lock, fullio_clock_pm, fullio_clock_fault; };
struct snd_soc_component { void *driver, *card; struct wsa_macro *wsa; };
static int wsa_macro_component_drv;
static const unsigned int fullio_tx_regs[] = {0,1,2,3};
static int refs, reads, writes, vcount, fail_v, pm_fail, cleanup_fail, read_fail;
static unsigned int on;
static bool wsa_macro_fullio_post_pa_probe(struct snd_soc_component *c) { return c->card != NULL; }
static bool wsa_macro_fullio_clock_audit(void *card) { assert(card); return false; }
static struct wsa_macro *snd_soc_component_get_drvdata(struct snd_soc_component *c) { return c->wsa; }
static int pm_runtime_resume_and_get(void *d) { assert(d); if (pm_fail) return -EIO; ++refs; return 0; }
static void pm_runtime_mark_last_busy(void *d) { assert(d && refs); }
static void pm_runtime_put_autosuspend(void *d) { assert(d && refs-- > 0); }
static int regmap_read_bypassed(void *map, unsigned int reg, unsigned int *val)
{ assert(map && refs && reg < 4); ++reads; *val = !!(on & BIT(reg)); return read_fail; }
static int wsa_macro_fullio_start_pair(struct wsa_macro *w, int start)
{ assert(w->fullio_clock_pm && refs && (start == 0 || start == 2)); ++writes; return 0; }
static int wsa_macro_fullio_tx_update(struct wsa_macro *w, int first, int n, int mask, int val, bool all)
{ assert(w && refs && first == 0 && n == 4 && mask == 3 && val == 2 && all); ++writes; return cleanup_fail; }
static int verify(void *ctx) { assert(ctx); return ++vcount == fail_v ? -ESTALE : 0; }
''' + '\n'.join(extract(n) for n in (
    'wsa_macro_fullio_verify_clocks_off_locked', 'wsa_macro_fullio_tx_clocks', 'wsa_macro_fullio_protclk',
)) + r'''
int main(void)
{
    struct wsa_macro w = { &w, &w, true, false, false };
    struct snd_soc_component c = { &wsa_macro_component_drv, &w, &w };
#define STOP() wsa_macro_fullio_protclk(&c, false, NULL, NULL)
#define START() wsa_macro_fullio_protclk(&c, true, verify, &w)
    assert(!STOP() && reads == 4 && !writes && !refs);
    on = 8;
    assert(STOP() == -EBUSY && reads == 8 && !writes && !refs);
    read_fail = -EIO;
    assert(STOP() == -EIO && reads == 9 && !writes && !refs);
    pm_fail = 1;
    assert(STOP() == -EIO && reads == 9 && !writes && !refs);
    pm_fail = 0;
    fail_v = 2;
    assert(START() == -ESTALE && vcount == 2 && !writes && !refs && !w.fullio_clock_pm);
    vcount = 0;
    fail_v = 3;
    assert(START() == -ESTALE && writes == 2 && !refs && !w.fullio_clock_pm);
    vcount = 0;
    cleanup_fail = -EIO;
    assert(START() == -ESTALE && writes == 4 && refs == 1 && w.fullio_clock_pm && w.fullio_clock_fault);
    assert(START() == -EPERM && writes == 4 && refs == 1);
}
'''
with tempfile.TemporaryDirectory() as d:
    c = Path(d) / 'test.c'
    c.write_text(code)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', c, '-o', c.with_suffix('')], check=True)
    subprocess.run([c.with_suffix('')], check=True)
print('Clock proof: no-vote STOP reads hardware; stale post-resume readiness issues no TX writes; partial activation rolls back.')
