#!/usr/bin/env python3
"""Compile and exercise the actual FullIO shutdown verdict helpers offline."""

import argparse
import re
from pathlib import Path
import subprocess
import tempfile

STUBS = r"""
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <string.h>
struct device_node { bool require_proof, withhold_proof; };
struct device { struct device_node *of_node; };
struct snd_soc_component { int result, calls; };
struct snd_soc_card { struct device *dev; struct snd_soc_component *left, *right; };
struct q6apm_fullio_amp_pair { struct snd_soc_component *left, *right; };
struct q6apm_dai_data { bool fullio_render_locked; };
#define SNDRV_PCM_STREAM_PLAYBACK 0
#define SNDRV_PCM_STREAM_CAPTURE 1
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x, v) ((x) = (v))
static int pair_error;
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
static int q6apm_fullio_amp_pair(struct snd_soc_card *card, const char *name, struct q6apm_fullio_amp_pair *pair)
{
    assert(!strcmp(name, "WSA Playback") && card->left != card->right);
    if (pair_error) return pair_error;
    *pair = (struct q6apm_fullio_amp_pair){card->left, card->right};
    return 0;
}
static int wsa884x_fullio_stop_audit(struct snd_soc_component *codec)
{
    codec->calls++;
    return codec->result;
}
static bool of_property_read_bool(struct device_node *node, const char *name)
{
    if (!strcmp(name, "microsoft,denali-fullio-pa-stop-audit")) return node->require_proof;
    assert(!strcmp(name, "microsoft,denali-fullio-pa-off-missing-stop-proof"));
    return node->withhold_proof;
}
"""

CHECKS = r"""
int main(void)
{
    struct device_node dt = {0};
    struct device dev = { &dt };
    struct snd_soc_component l = {0}, r = {0};
    struct snd_soc_card card = {&dev, &l, &r};
    struct q6apm_dai_data pdata = {0}, unrelated = {0};
#define FINISH(result, worker) q6apm_fullio_finish_audit(&pdata, &card, result, 0, worker)
#define PLAYBACK() q6apm_fullio_check_render(&pdata, SNDRV_PCM_STREAM_PLAYBACK)
    assert(FINISH(-ECANCELED, false) == -ECANCELED && !l.calls && !r.calls);
    dt.require_proof = true;
    assert(FINISH(-ECANCELED, true) == -ECANCELED && !l.calls && !r.calls);
    assert(FINISH(-ETIMEDOUT, false) == -ETIMEDOUT && l.calls == 1 && r.calls == 1);
    assert(!PLAYBACK());
    l.result = -ENODEV;
    assert(FINISH(-ECANCELED, false) == -ENOTRECOVERABLE);
    assert(l.calls == 2 && r.calls == 2 && PLAYBACK() == -ENOTRECOVERABLE);
    l.result = 0;
    r.result = -EIO;
    assert(FINISH(0, false) == -ENOTRECOVERABLE);
    assert(l.calls == 3 && r.calls == 3);
    r.result = 0;
    dt.withhold_proof = true;
    assert(q6apm_fullio_stop_pair_audit(&card) == -ENODATA && l.calls == 4 && r.calls == 4);
    assert(FINISH(-ENODATA, false) == -ENOTRECOVERABLE && l.calls == 5 && r.calls == 5);
    pair_error = -EINVAL;
    assert(FINISH(0, false) == -ENOTRECOVERABLE && l.calls == 5 && r.calls == 5);
    pair_error = 0;
    dt.withhold_proof = false;
    assert(!FINISH(0, false) && PLAYBACK() == -ENOTRECOVERABLE);
    assert(!q6apm_fullio_check_render(&pdata, SNDRV_PCM_STREAM_CAPTURE));
    assert(!q6apm_fullio_check_render(&unrelated, SNDRV_PCM_STREAM_PLAYBACK));
    struct q6apm_dai_data dsp_only = {0}, no_pa_audit = {0}, both = {0};
    assert(q6apm_fullio_finish_audit(&dsp_only, &card, -ETIMEDOUT, -ETIMEDOUT, true) == -ENOTRECOVERABLE);
    assert(l.calls == 6 && r.calls == 6 && dsp_only.fullio_render_locked);
    dt.require_proof = false;
    assert(q6apm_fullio_finish_audit(&no_pa_audit, &card, -ETIMEDOUT, -ETIMEDOUT, false) == -ENOTRECOVERABLE);
    assert(l.calls == 6 && r.calls == 6 && no_pa_audit.fullio_render_locked);
    dt.require_proof = true;
    r.result = -ENODEV;
    assert(q6apm_fullio_finish_audit(&both, &card, -ETIMEDOUT, -ETIMEDOUT, false) == -ENOTRECOVERABLE);
    assert(l.calls == 7 && r.calls == 7 && both.fullio_render_locked);
    struct q6apm_dai_data positive = {0};
    r.result = 0;
    assert(q6apm_fullio_finish_audit(&positive, &card, 1, 0, false) == -ENOTRECOVERABLE);
    assert(l.calls == 8 && r.calls == 8 && positive.fullio_render_locked);
    dt.require_proof = false;
    struct q6apm_dai_data positive_no_stop = {0};
    assert(q6apm_fullio_finish_audit(&positive_no_stop, &card, 1, 0, false) == -ENOTRECOVERABLE);
    assert(l.calls == 8 && r.calls == 8 && positive_no_stop.fullio_render_locked);
    assert(!q6apm_fullio_check_render(&positive_no_stop, SNDRV_PCM_STREAM_CAPTURE));
}
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path, help="patched q6apm-dai.c")
    text = p.parse_args().source.read_text()
    helpers = []
    for name in ("q6apm_fullio_stop_pair_audit", "q6apm_fullio_check_render",
                 "q6apm_fullio_finish_audit"):
        match = re.search(rf"^static int {name}\([^{{]*\{{.*?^\}}", text, re.M | re.S)
        if match is None:
            p.error(f"missing {name}")
        helpers.append(match.group())
    for name in ('q6apm_dai_open', 'q6apm_dai_compr_open'):
        opening = re.search(rf'^static int {name}\([^{{]*\{{.*?^\}}', text, re.M | re.S).group()
        assert opening.index('q6apm_fullio_check_render') < opening.index('q6apm_graph_open')
    with tempfile.TemporaryDirectory() as work:
        source = Path(work) / "proof.c"
        binary = source.with_suffix("")
        source.write_text(STUBS + "\n".join(helpers) + CHECKS)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", source, "-o", binary], check=True)
        subprocess.run([binary], check=True)
    print('Shutdown proof: positive audit result, unverified PA or DSP STOP locks render, not capture.')


if __name__ == "__main__":
    main()
