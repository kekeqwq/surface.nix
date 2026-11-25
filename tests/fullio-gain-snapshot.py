#!/usr/bin/env python3
"""Check that the actual WSA PA snapshot only exposes stable PA-off gain data."""

import argparse
from pathlib import Path
import subprocess
import tempfile


STUBS = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <string.h>

typedef long long s64;
#define READ_ONCE(v) (v)
#define SDW_SLAVE_ATTACHED 1
#define WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK 1

enum {
    WSA884X_PA_FSM_EN, WSA884X_PA_FSM_STA0, WSA884X_PA_FSM_STA1,
    WSA884X_PA_FSM_ERR_COND0, WSA884X_PA_FSM_ERR_COND1, WSA884X_DRE_CTL_0, WSA884X_DRE_CTL_1,
};
struct device_node { bool muted, off, audit, post_pa; };
struct device { struct device_node *of_node; void *drvdata; };
struct snd_soc_card { struct device *dev; };
struct snd_soc_component { const int *driver; struct device *dev; struct snd_soc_card *card; };
struct sdw_slave { int status; };
struct wsa884x_priv {
    struct device *dev;
    struct sdw_slave *slave;
    struct wsa884x_priv *regmap;
    bool feedback_enabled;
    s64 fullio_pa_epoch;
    int fullio_pa_teardowns;
};
static const int wsa884x_component_drv;
static unsigned int pa, gain_reads, fault_reads;
static bool bump_epoch;
static int pm_users, bad_reg = -1;
static void *dev_get_drvdata(struct device *d) { return d->drvdata; }
static int pm_runtime_resume_and_get(struct device *d) { assert(d); pm_users++; return 0; }
static void pm_runtime_mark_last_busy(struct device *d) { assert(d && pm_users == 1); }
static void pm_runtime_put_autosuspend(struct device *d) { assert(d && --pm_users == 0); }
static s64 atomic64_read_acquire(const s64 *epoch) { return *epoch; }
static int atomic_read_acquire(const int *active) { return *active; }
static bool of_machine_is_compatible(const char *name) { return !strcmp(name, "microsoft,denali"); }
static bool of_property_read_bool(struct device_node *n, const char *name)
{
    if (!n) return false;
    if (!strcmp(name, "microsoft,denali-fullio-muted-test")) return n->muted;
    if (!strcmp(name, "microsoft,denali-fullio-clock-off-audit")) return n->off;
    if (!strcmp(name, "microsoft,denali-fullio-pa-off-gain-audit")) return n->audit;
    if (!strcmp(name, "microsoft,denali-fullio-post-pa-test")) return n->post_pa;
    assert(false);
    return false;
}
static int regmap_read_bypassed(struct wsa884x_priv *amp, int reg, unsigned int *value)
{
    assert(amp && pm_users == 1);
    if (reg == bad_reg) return -EIO;
    switch (reg) {
    case WSA884X_PA_FSM_EN: *value = pa; break;
    case WSA884X_DRE_CTL_0: gain_reads++; *value = 0xf2; break;
    case WSA884X_DRE_CTL_1:
        gain_reads++;
        *value = 0x32;
        if (bump_epoch) amp->fullio_pa_epoch++;
        break;
    case WSA884X_PA_FSM_ERR_COND0:
    case WSA884X_PA_FSM_ERR_COND1:
        fault_reads++;
        /* fall through */
    default: *value = 0; break;
    }
    return 0;
}
"""

CHECKS = r"""
int main(void)
{
    struct device_node dt = { .muted = true, .off = true };
    struct device carddev = { .of_node = &dt }, codecdev = {0};
    struct snd_soc_card card = { .dev = &carddev };
    struct snd_soc_component codec = { &wsa884x_component_drv, &codecdev, &card };
    struct sdw_slave slave = { SDW_SLAVE_ATTACHED };
    struct wsa884x_priv amp = { .dev = &codecdev, .slave = &slave, .feedback_enabled = true };
    struct wsa884x_fullio_pa_snapshot sample = {0};
    codecdev.drvdata = amp.regmap = &amp;
#define SAMPLE(faults) wsa884x_fullio_read_pa(&codec, (faults), &sample)
    assert(SAMPLE(false) == 0 && !sample.gain_sampled && gain_reads == 0);
    dt.audit = dt.post_pa = true;
    assert(SAMPLE(false) == 0 && !sample.gain_sampled && gain_reads == 0);
    dt.post_pa = false;
    pa = 1;
    assert(SAMPLE(false) == 0 && !sample.gain_sampled && gain_reads == 0);
    pa = 0;
    assert(SAMPLE(true) == 0 && !sample.gain_sampled && gain_reads == 0 && fault_reads == 2);
    assert(SAMPLE(false) == 0 && sample.gain_sampled && gain_reads == 2);
    assert(sample.dre0 == 0xf2 && sample.dre1 == 0x32);
    memset(&sample, 0, sizeof(sample));
    bump_epoch = true;
    assert(SAMPLE(false) == -EAGAIN && !sample.gain_sampled);
    bump_epoch = false;
    bad_reg = WSA884X_DRE_CTL_1;
    assert(SAMPLE(false) == -EIO && !sample.gain_sampled && pm_users == 0);
#undef SAMPLE
}
"""


GUARD_STUBS = r"""
#define WSA884X_PDM_WD_CTL 20
#define WSA884X_CURRENT_LIMIT 21
#define WSA884X_PDM_WD_CTL_PDM_WD_EN_MASK 1
static int guard_ok, guard_bad, pm_active = 1, guard_reads, wd;
static bool guard_enabled, detach_after_limit;
static int pm_runtime_get_if_active(struct device *dev)
{
    assert(dev);
    if (pm_active > 0) pm_users++;
    return pm_active;
}
static bool audit_property(struct device_node *node, const char *name)
{
    if (!strcmp(name, "microsoft,denali-fullio-pa-off-guard-audit"))
        return guard_enabled;
    return of_property_read_bool(node, name);
}
static int guard_read(struct wsa884x_priv *amp, int reg, unsigned int *value)
{
    assert(amp && pm_users == 1);
    guard_reads++;
    if (reg == bad_reg) return -EIO;
    switch (reg) {
    case WSA884X_PDM_WD_CTL: *value = wd; break;
    case WSA884X_CURRENT_LIMIT:
        *value = 0xd4;
        if (detach_after_limit) amp->slave->status = 0;
        break;
    default: return regmap_read_bypassed(amp, reg, value);
    }
    return 0;
}
static void dev_info(struct device *d, const char *fmt, ...)
{
    assert(d && fmt);
    guard_ok++;
}
static void dev_warn(struct device *d, const char *fmt, ...)
{
    assert(d && fmt);
    guard_bad++;
}
#define of_property_read_bool audit_property
#define regmap_read_bypassed guard_read
"""

GUARD_CHECKS = r"""
int main(void)
{
    struct device_node dt = {.muted = true, .off = true};
    struct device carddev = {.of_node = &dt}, codecdev = {0};
    struct snd_soc_card card = {.dev = &carddev};
    struct snd_soc_component codec = {&wsa884x_component_drv, &codecdev, &card};
    struct sdw_slave slave = {SDW_SLAVE_ATTACHED};
    struct wsa884x_priv amp = {.dev = &codecdev, .slave = &slave, .feedback_enabled = true};
    codecdev.drvdata = amp.regmap = &amp;
    wsa884x_fullio_audit_guard(&codec, &amp, true);
    assert(!guard_reads && !guard_ok && !guard_bad);
    guard_enabled = dt.post_pa = true;
    wsa884x_fullio_audit_guard(&codec, &amp, false);
    assert(!guard_reads);
    dt.post_pa = false;
    wd = 1;
    wsa884x_fullio_audit_guard(&codec, &amp, true);
    assert(guard_reads == 4 && guard_ok == 1 && !guard_bad && !pm_users);
    wd = 0;
    wsa884x_fullio_audit_guard(&codec, &amp, false);
    assert(guard_ok == 2 && !guard_bad);
    wsa884x_fullio_audit_guard(&codec, &amp, true);
    assert(guard_ok == 2 && guard_bad == 1);
    detach_after_limit = true;
    wsa884x_fullio_audit_guard(&codec, &amp, false);
    assert(guard_ok == 2 && guard_bad == 2 && !pm_users);
    slave.status = SDW_SLAVE_ATTACHED;
    pa = 1;
    int prior = guard_reads;
    wsa884x_fullio_audit_guard(&codec, &amp, false);
    assert(guard_ok == 2 && guard_bad == 3 && guard_reads == prior + 1);
    pm_active = 0;
    prior = guard_reads;
    wsa884x_fullio_audit_guard(&codec, &amp, false);
    assert(guard_reads == prior && guard_bad == 4 && !pm_users);
    pm_active = 1;
    pa = 0;
    bad_reg = WSA884X_CURRENT_LIMIT;
    wsa884x_fullio_audit_guard(&codec, &amp, false);
    assert(guard_reads == prior + 3 && guard_bad == 5 && guard_ok == 2 && !pm_users);
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_tree", type=Path)
    parser.add_argument("--guard", action="store_true", help="exercise the PA-off watchdog/limit observer")
    args = parser.parse_args()
    path = args.kernel_tree / "sound/soc/codecs/wsa884x.c"
    text = path.read_text()
    if args.guard:
        start = text.index("static void wsa884x_fullio_audit_guard(")
        end = text.index("static int wsa884x_spkr_event(", start)
        source = STUBS + GUARD_STUBS + text[start:end] + GUARD_CHECKS
    else:
        start = text.index("struct wsa884x_fullio_pa_snapshot {")
        end = text.index("/* The pinned reference observed", start)
        source = STUBS + text[start:end] + CHECKS
    with tempfile.TemporaryDirectory(prefix="fullio-gain-snapshot-") as tmp:
        c, exe = Path(tmp) / "snapshot.c", Path(tmp) / "snapshot"
        c.write_text(source)
        flags = ["-Wno-unused-function"] if args.guard else []
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", *flags, c, "-o", exe], check=True)
        subprocess.run([exe], check=True)
    if args.guard:
        print("FullIO PA-off codec guard: fixture/PM/PA-off gates, watchdog mismatch and detach passed")
    else:
        print("FullIO PA-off gain: fixture gates, no PA-on reads, epoch and read errors passed")


if __name__ == "__main__":
    main()
