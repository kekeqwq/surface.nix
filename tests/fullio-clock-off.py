#!/usr/bin/env python3
"""Verify the patched FullIO clock-off/PA-mute ordering without hardware writes."""

from pathlib import Path
import argparse
import os
import subprocess
import tempfile


STUBS = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#define EXPORT_SYMBOL_GPL(x)
#define WSA884X_DAI_PLAYBACK 0
#define WSA884X_DRE_CTL_1 1
#define WSA884X_DRE_CTL_1_CSR_GAIN_EN_MASK 1
#define WSA884X_PA_FSM_EN 2
#define WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK 1
#define WSA884X_INTR_MASK0 10
#define WSA884X_INTR_MASK1 11
#define WSA884X_INTR_CLEAR0 12
#define WSA884X_INTR_CLEAR1 13
#define WSA884X_CLSH_CTL_0 14
#define SDW_SLAVE_ATTACHED 1
#define READ_ONCE(x) (x)
#define WRITE_ONCE(p, v) ((p) = (v))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define guard(type) (void)
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define IS_ERR(p) (PTR_ERR(p) < 0 && PTR_ERR(p) >= -4095)
#include <stdint.h>
struct reg_sequence { unsigned int reg, def; };
struct sdw_slave { int status; };
struct device;
struct wsa884x_priv {
    struct device *dev;
    bool feedback_enabled, fullio_reference_codec, hw_init;
    int fullio_pa_epoch, fullio_pa_teardowns, sp_lock;
    struct wsa884x_priv *regmap;
    struct sdw_slave *slave;
};
struct snd_soc_card;
struct device_node { bool post_pa; };
struct device { struct device_node *of_node; struct wsa884x_priv *amp; };
struct snd_soc_component { struct snd_soc_card *card; struct device *dev; const void *driver; };
struct snd_soc_dai { struct snd_soc_component *component; struct device *dev; int id; };
struct snd_soc_dai_link { const char *name; };
struct snd_soc_pcm_runtime {
    struct snd_soc_dai_link *dai_link;
    struct snd_soc_dai *dais[4];
    int ndais;
    struct snd_soc_card *card;
    struct snd_soc_dai *cpu;
};
struct snd_soc_card { struct device *dev; struct snd_soc_pcm_runtime *links; int nlinks; };
#define for_each_card_rtds(card, rtd) \
    for ((rtd) = (card)->links; (rtd) < (card)->links + (card)->nlinks; (rtd)++)
#define for_each_rtd_codec_dais(rtd, i, codec) \
    for ((i) = 0; (i) < (rtd)->ndais && ((codec) = (rtd)->dais[i]); (i)++)
#define of_machine_is_compatible(s) (!strcmp(s, "microsoft,denali"))
static bool audit_mode, muted, pa_stop_audit, gain_audit, reference_route;
#define of_property_read_bool(n, s) \
    ((!strcmp(s, "microsoft,denali-fullio-post-pa-test") && (n) && (n)->post_pa) || \
     (!strcmp(s, "microsoft,denali-fullio-clock-off-audit") && audit_mode) || \
     (!strcmp(s, "microsoft,denali-fullio-muted-test") && muted) || \
     (!strcmp(s, "microsoft,denali-fullio-pa-stop-audit") && pa_stop_audit) || \
     (!strcmp(s, "microsoft,denali-fullio-pa-off-gain-audit") && gain_audit) || \
     (!strcmp(s, "microsoft,denali-fullio-reference-render") && reference_route))
#define dev_get_drvdata(d) ((d)->amp)
#define atomic_inc_return(p) (++*(p))
#define atomic64_inc_return(p) (++*(p))
#define atomic64_read_acquire(p) (*(p))
typedef long long s64;
typedef unsigned long long u64;
#define atomic_dec_return(p) (--*(p))
#define dev_err_ratelimited(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_err(...) ((void)0)
static int wsa_macro_component_drv, wsa884x_component_drv, steps[8], nsteps;
static int inject, fail_pa, fail_read, fail_before, pm_users, fail_table_reg;
static bool bump_epoch, change_cap;
static int dre_reads;
static int pm_runtime_resume_and_get(struct device *d) { assert(d); pm_users++; return 0; }
static void pm_runtime_mark_last_busy(struct device *d) { assert(d && pm_users == 1); }
static void pm_runtime_put_autosuspend(struct device *d) { assert(d && --pm_users == 0); }
static int wsa884x_fullio_pa_off(struct snd_soc_component *c) { assert(c && pm_users == 1); return fail_before; }
static unsigned int pa_enabled;
static struct snd_soc_component *expected_macro;

static bool wsa_macro_fullio_post_pa_probe(struct snd_soc_component *amp)
{
    return amp->card && amp->card->dev->of_node->post_pa;
}
static bool wsa_macro_fullio_clock_audit(struct snd_soc_card *card)
{
    return card && audit_mode;
}
static int wsa_macro_fullio_verify_clocks_off(struct snd_soc_component *owner)
{
    assert(owner == expected_macro);
    steps[nsteps++] = 5;
    return inject;
}
static int wsa_macro_fullio_tx_clocks(struct snd_soc_component *macro, bool enable,
                                  int (*verify)(void *), void *ctx)
{
    assert(macro == expected_macro && !enable && !verify && !ctx);
    steps[nsteps++] = 0;
    return inject;
}
static void snd_soc_component_write_field(struct snd_soc_component *amp, int reg, int mask, int value)
{
    assert(mask == 1 && value == 0 && amp->dev->amp->fullio_pa_teardowns == 1);
    steps[nsteps++] = reg;
}
static int regmap_write_bits(struct wsa884x_priv *amp, int reg, int mask, int value)
{
    snd_soc_component_write_field(&(struct snd_soc_component){.dev = &(struct device){.amp = amp}},
                                  reg, mask, value);
    assert(reg == WSA884X_PA_FSM_EN);
    if (!fail_pa) pa_enabled = 0;
    return fail_pa;
}
static int regmap_write(struct wsa884x_priv *amp, unsigned int reg, unsigned int value)
{
    static const unsigned int address[] = {2, 10, 11, 12, 13, 14};
    static const unsigned int values[] = {0, 0xff, 3, 0xff, 3, 0};
    assert(amp->fullio_reference_codec && amp->fullio_pa_teardowns == 1);
    assert(nsteps > 0 && nsteps <= 6 && address[nsteps - 1] == reg && values[nsteps - 1] == value);
    steps[nsteps++] = reg;
    if (reg == WSA884X_PA_FSM_EN && !fail_pa)
        pa_enabled = 0;
    return reg == WSA884X_PA_FSM_EN ? fail_pa : (int)reg == fail_table_reg ? -EINVAL : 0;
}
static int regmap_read_bypassed(struct wsa884x_priv *amp, int reg, unsigned int *value)
{
    if (reg == WSA884X_DRE_CTL_1) {
        assert(!amp->fullio_pa_teardowns && gain_audit && !pa_enabled);
        *value = (change_cap && ++dre_reads == 2) ? 0 : 0x33;
        steps[nsteps++] = 7;
        return 0;
    }
    assert(amp->fullio_pa_teardowns == 1 && reg == WSA884X_PA_FSM_EN);
    *value = pa_enabled;
    if (bump_epoch) amp->fullio_pa_epoch++;
    steps[nsteps++] = 6;
    return fail_read;
}
"""

FEEDBACK_STUB = r"""
struct q6apm_fullio_amp_pair { struct snd_soc_component *left, *right; };
static struct q6apm_fullio_amp_pair fixture_pair;
static int q6apm_fullio_amp_pair(struct snd_soc_card *card, const char *link,
                               struct q6apm_fullio_amp_pair *pair)
{
    assert(!strcmp(link, "WSA Playback"));
    assert(fixture_pair.left->card == card && fixture_pair.right->card == card);
    *pair = fixture_pair;
    return 0;
}
#define WSA_CODEC_DMA_TX_0 20
#define WSA_CODEC_DMA_TX_1 21
#define Q6APM_FULLIO_VI 0
#define Q6APM_FULLIO_CPS 1
struct snd_pcm_substream { struct snd_soc_card *card; struct snd_soc_dai *cpu; };
static struct snd_soc_pcm_runtime fake_rtd;
static struct snd_soc_pcm_runtime *snd_soc_substream_to_rtd(struct snd_pcm_substream *substream)
{
    fake_rtd = (struct snd_soc_pcm_runtime){.card = substream->card, .cpu = substream->cpu};
    return &fake_rtd;
}
#define snd_soc_rtd_to_cpu(rtd, i) ((rtd)->cpu)
#define of_property_read_string(n, key, out) (*(out) = "X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0", 0)
static void q6apm_fullio_set_transport(struct device *dev, int path, bool enabled)
{
    assert(path == (dev->amp ? Q6APM_FULLIO_VI : Q6APM_FULLIO_CPS));
    steps[nsteps++] = enabled ? 4 : 3;
}
"""

TEST = r"""
int main(void)
{
    struct device_node node = {false};
    struct snd_soc_card card, foreign;
    struct sdw_slave slave = {SDW_SLAVE_ATTACHED};
    struct wsa884x_priv priv = {.feedback_enabled = true, .regmap = &priv, .slave = &slave};
    struct device dev = {.of_node = &node, .amp = &priv};
    struct snd_soc_component amp = {&card, &dev, &wsa884x_component_drv};
    struct snd_soc_component macro = {&card, &dev, &wsa_macro_component_drv};
    struct snd_soc_dai amp_dai = {&amp, &dev, WSA884X_DAI_PLAYBACK};
    struct snd_soc_dai macro_dai = {&macro, &dev, 10};
    struct snd_soc_dai_link playback = {"WSA Playback"};
    struct snd_soc_pcm_runtime rtds[2] = {{.dai_link = &playback, .dais = {&amp_dai, &macro_dai}, .ndais = 2}};
    rtds[1] = rtds[0];
    card = (struct snd_soc_card){&dev, rtds, 1};
    expected_macro = &macro;
    priv.dev = &dev;

    assert(wsa884x_mute_stream(&amp_dai, 0, 0) == -EPERM && nsteps == 0);
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == 0 && nsteps == 1 && steps[0] == 2);
    assert(wsa_macro_fullio_clock_off_for_feedback(&card) == -EOPNOTSUPP && nsteps == 1);
    node.post_pa = true;
    nsteps = 0;
    assert(wsa_macro_fullio_clock_off_for_feedback(&card) == 0 && nsteps == 1 && steps[0] == 0);
    nsteps = 0;
    pa_enabled = 1;
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == 0 && nsteps == 3 && !pa_enabled);
    assert(steps[0] == 0 && steps[1] == 2 && steps[2] == 6);
    assert(priv.fullio_pa_teardowns == 0 && priv.fullio_pa_epoch == 2);
    nsteps = 0;
    inject = -EIO;
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == -EIO && nsteps == 3);
    assert(steps[1] == 2 && steps[2] == 6 && priv.fullio_pa_teardowns == 0);
    nsteps = 0;
    inject = 0;
    bump_epoch = true;
    pa_enabled = 1;
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == -ESTALE && nsteps == 3 && !pa_enabled);
    nsteps = 0;
    bump_epoch = false;
    fail_pa = -EIO;
    pa_enabled = 1;
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == -EBUSY && nsteps == 3 && pa_enabled);
    nsteps = 0;
    fail_pa = 0;
    fail_read = -EIO;
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == -EIO && nsteps == 3 && !pa_enabled);
    nsteps = 0;
    fail_read = 0;
    slave.status = 0;
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == -ENODEV && nsteps == 3);
    slave.status = SDW_SLAVE_ATTACHED;
    nsteps = 0;
    card.nlinks = 2;
    assert(wsa_macro_fullio_clock_off_for_pa(&amp) == -EEXIST && nsteps == 0);
    assert(wsa_macro_fullio_clock_off_for_feedback(&card) == -EEXIST && nsteps == 0);
    card.nlinks = 1;
    macro.card = &foreign;
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == -ENODEV && nsteps == 2);

    macro.card = &card;
    inject = 0;
    struct snd_soc_dai cpu = {NULL, &dev, WSA_CODEC_DMA_TX_0};
    struct snd_pcm_substream substream = {&card, &cpu};
    nsteps = 0;
    x1e80100_fullio_feedback(&substream, true);
    assert(nsteps == 1 && steps[0] == 4);
    nsteps = 0;
    x1e80100_fullio_feedback(&substream, false);
    assert(nsteps == 2 && steps[0] == 3 && steps[1] == 0);
    nsteps = 0;
    cpu.id = WSA_CODEC_DMA_TX_1;
    dev.amp = NULL;
    x1e80100_fullio_feedback(&substream, false);
    assert(nsteps == 2 && steps[0] == 3 && steps[1] == 0);
    nsteps = 0;
    node.post_pa = false;
    x1e80100_fullio_feedback(&substream, false);
    assert(nsteps == 1 && steps[0] == 3);
    audit_mode = true;
    nsteps = 0;
    x1e80100_fullio_feedback(&substream, false);
    assert(nsteps == 2 && steps[0] == 3 && steps[1] == 5);

    nsteps = 0;
    dev.amp = &priv;
    pa_stop_audit = true;
    assert(wsa884x_fullio_stop_audit(&amp) == -EOPNOTSUPP && nsteps == 0);
    muted = true;
    assert(wsa884x_mute_stream(&amp_dai, 0, 0) == -EPERM && nsteps == 0);
    assert(wsa884x_fullio_stop_audit(&amp) == 0 && nsteps == 3 && !pm_users);
    assert(steps[0] == 5 && steps[1] == 2 && steps[2] == 6);
    nsteps = 0;
    inject = -EIO;
    assert(wsa884x_fullio_stop_audit(&amp) == -EIO && nsteps == 3 && !pm_users);
    assert(steps[0] == 5 && steps[1] == 2 && steps[2] == 6);
    nsteps = 0;
    inject = 0;
    fail_before = -EBUSY;
    pa_enabled = 1;
    assert(wsa884x_fullio_stop_audit(&amp) == -EBUSY && nsteps == 3 && !pm_users && !pa_enabled);

    struct device dev_right = dev;
    struct snd_soc_component amp_right = {&card, &dev_right, &wsa884x_component_drv};
    struct snd_soc_dai dai_right = {&amp_right, &dev_right, WSA884X_DAI_PLAYBACK};
    rtds[0].dais[2] = &dai_right;
    rtds[0].ndais = 3;
    fixture_pair = (struct q6apm_fullio_amp_pair){&amp, &amp_right};
    nsteps = 0;
    assert(q6apm_fullio_stop_pair_audit(&card) == -EBUSY && nsteps == 6 && !pm_users);
    assert(steps[0] == 5 && steps[2] == 6 && steps[3] == 5 && steps[5] == 6);
    gain_audit = true;
    fail_before = 0;
    nsteps = 0;
    assert(wsa884x_fullio_stop_audit(&amp) == 0 && nsteps == 5 && !pm_users);
    assert(steps[0] == 7 && steps[1] == 5 && steps[2] == 2 && steps[3] == 6 && steps[4] == 7);
    change_cap = true;
    nsteps = 0;
    assert(wsa884x_fullio_stop_audit(&amp) == -EIO && nsteps == 5 && !pm_users);

    audit_mode = muted = false;
    reference_route = priv.fullio_reference_codec = priv.hw_init = true;
    nsteps = 0;
    pa_enabled = 1;
    /* Per-amp unmute defers to the card coordinator: no PA write here. */
    assert(wsa884x_mute_stream(&amp_dai, 0, 0) == 0 && nsteps == 0 && pa_enabled);
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == 0 && priv.hw_init && !pa_enabled);
    assert(nsteps == 8 && steps[0] == 0 && steps[1] == 2 && steps[7] == 6);
    inject = -ETIMEDOUT;
    fail_pa = -EIO;
    fail_table_reg = WSA884X_INTR_MASK1;
    nsteps = 0;
    pa_enabled = 1;
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == -ETIMEDOUT && !priv.hw_init && pa_enabled);
    assert(nsteps == 8 && steps[0] == 0 && steps[7] == 6);
    inject = fail_pa = 0;
    priv.hw_init = true;
    nsteps = 0;
    assert(wsa884x_mute_stream(&amp_dai, 1, 0) == -EINVAL && !priv.hw_init && !pa_enabled);
    assert(nsteps == 8 && steps[7] == 6);
}
"""


def extract(file, start, end):
    text = file.read_text()
    first = text.index(start)
    return text[first:text.index(end, first)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_tree", type=Path)
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    args = parser.parse_args()
    codecs = args.kernel_tree / "sound/soc/codecs"
    macro = codecs / "lpass-wsa-macro.c"
    off = extract(macro, "static bool wsa_macro_fullio_reference_route(",
                  "static bool wsa_macro_fullio_clock_audit(")
    off += extract(macro, "static struct snd_soc_component *\nwsa_macro_fullio_clock_owner(",
                   "static struct snd_soc_component *\nwsa_macro_fullio_reference_owner(")
    off += extract(macro, "static int wsa_macro_fullio_clock_off_on_card(",
                   "EXPORT_SYMBOL_GPL(wsa_macro_fullio_clock_off_for_feedback)")
    wsa = codecs / "wsa884x.c"
    mute = extract(wsa, "static int wsa884x_fullio_reference_stop(",
                   "static int wsa884x_fullio_reference_start(")
    mute += extract(wsa, "static bool wsa884x_fullio_pa_stop_audit(",
                    "EXPORT_SYMBOL_GPL(wsa884x_fullio_stop_audit)")
    mute += extract(wsa, "static int wsa884x_mute_stream(", "static int wsa884x_set_stream(")
    pair = extract(codecs.parent / "qcom/qdsp6/q6apm-dai.c", "static int q6apm_fullio_stop_pair_audit(",
                   "\n}\n") + "\n}\n"
    feedback = extract(codecs.parent / "qcom/x1e80100.c", "static void x1e80100_fullio_feedback(",
                       "static int x1e80100_snd_prepare(")
    with tempfile.TemporaryDirectory(prefix="fullio-clock-off-") as tmp:
        src, binary = Path(tmp) / "test.c", Path(tmp) / "test"
        src.write_text(STUBS + off + mute + FEEDBACK_STUB + pair + feedback + TEST)
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-parameter", str(src), "-o", str(binary)], check=True)
        subprocess.run([binary], check=True)
    print("FullIO: clock shutdown before PA mute, and VI/CPS transport revocation passed")


if __name__ == "__main__":
    main()
