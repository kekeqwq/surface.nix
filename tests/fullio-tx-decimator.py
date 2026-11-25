#!/usr/bin/env python3
"""Compile the TX driver's real stereo route, channel map and mute handlers."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile

STUBS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <errno.h>
typedef uint32_t u32;
#define TX_MACRO_AIF1_CAP 1
#define TX_MACRO_AIF2_CAP 2
#define TX_MACRO_AIF3_CAP 3
#define TX_MACRO_DEC_MAX 8
#define CDC_TXn_TX_PATH_CTL(dec) (dec)
#define CDC_TXn_PGA_MUTE_MASK 2
#define READ_ONCE(x) (x)
#define hweight32(x) __builtin_popcount(x)
#define for_each_set_bit(i, mask, max) for ((i) = 0; (i) < (max); (i)++) if (test_bit((i), (mask)))
struct tx_macro { unsigned long active_ch_mask[4]; };
struct snd_soc_component { struct tx_macro tx; };
struct snd_soc_dapm_context { struct snd_soc_component *component; };
struct snd_soc_dapm_widget { unsigned int shift; struct snd_soc_dapm_context *dapm; };
struct soc_mixer_control { unsigned int shift; };
struct snd_kcontrol { struct snd_soc_dapm_widget *widget; unsigned long private_value; };
struct snd_ctl_elem_value { struct { struct { long value[1]; } integer; } value; };
struct snd_soc_dai { struct snd_soc_component *component; int id; };
struct snd_soc_dapm_update;
static unsigned int dapm_calls, muted, mute_attempts;
static int write_failure = -1;
static bool test_bit(unsigned int n, unsigned long *bits) { return (*bits >> n) & 1; }
static bool test_and_set_bit(unsigned int n, unsigned long *bits)
{
    bool before = test_bit(n, bits);
    *bits |= 1ul << n;
    return before;
}
static bool test_and_clear_bit(unsigned int n, unsigned long *bits)
{
    bool before = test_bit(n, bits);
    *bits &= ~(1ul << n);
    return before;
}
static struct snd_soc_component *snd_soc_dapm_to_component(struct snd_soc_dapm_context *d) { return d->component; }
static struct snd_soc_dapm_widget *snd_soc_dapm_kcontrol_to_widget(struct snd_kcontrol *ctl) { return ctl->widget; }
static struct tx_macro *snd_soc_component_get_drvdata(struct snd_soc_component *c) { return &c->tx; }
static int snd_soc_dapm_mixer_update_power(struct snd_soc_dapm_context *d, struct snd_kcontrol *ctl,
                                        unsigned int enabled, struct snd_soc_dapm_update *update)
{
    struct soc_mixer_control *mc = (void *)ctl->private_value;
    assert(!update && enabled == test_bit(mc->shift, &d->component->tx.active_ch_mask[ctl->widget->shift]));
    dapm_calls++;
    return 1;
}
static int snd_soc_component_write_field(struct snd_soc_component *c, unsigned int dec,
                                        unsigned int mask, bool value)
{
    assert(c && dec < TX_MACRO_DEC_MAX && mask == CDC_TXn_PGA_MUTE_MASK);
    mute_attempts |= 1u << dec;
    if (write_failure == (int)dec) return -EIO;
    if (value) muted |= 1u << dec;
    else muted &= ~(1u << dec);
    return 0;
}
"""

CHECKS = r"""
static void check_map(struct snd_soc_dai *dai, unsigned int expected_mask, unsigned int expected_n)
{
    unsigned int count = 0, mask = 0;
    assert(!tx_macro_get_channel_map(dai, &count, &mask, 0, 0));
    assert(count == expected_n && mask == expected_mask);
}
static int put(struct snd_kcontrol *ctl, long on)
{
    struct snd_ctl_elem_value value = { .value.integer.value = {on} };
    return tx_macro_tx_mixer_put(ctl, &value);
}
int main(void)
{
    struct snd_soc_component c = {0};
    struct snd_soc_dapm_context d = {&c};
    struct snd_soc_dapm_widget w1 = {TX_MACRO_AIF1_CAP, &d}, w2 = {TX_MACRO_AIF2_CAP, &d};
    struct soc_mixer_control mc0 = {0}, mc1 = {1};
    struct snd_kcontrol dec0 = {&w1, (unsigned long)&mc0};
    struct snd_kcontrol dec1 = {&w1, (unsigned long)&mc1};
    struct snd_kcontrol other = {&w2, (unsigned long)&mc1};
    struct snd_soc_dai aif1 = {&c, TX_MACRO_AIF1_CAP}, aif2 = {&c, TX_MACRO_AIF2_CAP};
    struct snd_ctl_elem_value state = {0};

    assert(!put(&dec0, 0) && dapm_calls == 0);
    for (unsigned int pass = 0; pass < 2; pass++) {
        unsigned int before = dapm_calls;
        assert(put(&dec0, 1) == 1 && put(&dec1, 1) == 1 && !put(&dec0, 1));
        check_map(&aif1, 3, 2);
        check_map(&aif2, 0, 0);
        mute_attempts = 0;
        assert(!tx_macro_digital_mute(&aif1, 1, 0) && mute_attempts == 3 && muted == 3);
        write_failure = 0;
        mute_attempts = 0;
        assert(tx_macro_digital_mute(&aif1, 0, 0) == -EIO && mute_attempts == 3 && muted == 1);
        write_failure = -1;
        assert(!tx_macro_digital_mute(&aif1, 0, 0) && !muted);
        assert(put(&dec1, 0) == 1 && !put(&dec1, 0));
        check_map(&aif1, 1, 1);
        assert(put(&dec0, 0) == 1 && !put(&dec0, 0) && dapm_calls == before + 4);
        assert(!tx_macro_tx_mixer_get(&dec0, &state) && !state.value.integer.value[0]);
        check_map(&aif1, 0, 0);
    }
    assert(put(&other, 1) == 1);
    check_map(&aif2, 2, 1);
    check_map(&aif1, 0, 0);
    return 0;
}
"""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path, help="patched lpass-tx-macro.c")
    text = p.parse_args().source.read_text()
    functions = []
    for name in ("tx_mixer_get", "tx_mixer_put", "get_channel_map", "digital_mute"):
        match = re.search(rf"^static int tx_macro_{name}\([^{{]*\{{.*?^\}}", text, re.M | re.S)
        if match is None:
            p.error(f"cannot extract tx_macro_{name}")
        functions.append(match.group())
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "tx.c"
        exe = source.with_suffix("")
        source.write_text(STUBS + "\n".join(functions) + CHECKS)
        subprocess.run(["cc", "-std=c11", "-Werror", "-Wall", "-Wextra", "-Wno-unused-parameter", str(source), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("TX stereo decimators: repeat enable, reverse teardown, channel map, per-DAI isolation and paired mute verified")


if __name__ == "__main__":
    main()
