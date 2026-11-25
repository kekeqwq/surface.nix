#!/usr/bin/env python3
"""Verify capture-only open and playback backing gates in the real driver."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile

STUBS = r"""
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <string.h>
#define SNDRV_PCM_STREAM_PLAYBACK 0
#define SNDRV_PCM_STREAM_CAPTURE 1
struct device_node { bool capture_only; };
struct device { struct device_node *of_node; };
struct snd_soc_card { struct device *dev; };
struct snd_soc_component { struct snd_soc_card *card; };
struct snd_pcm_substream { int stream; };
struct snd_pcm { struct { struct snd_pcm_substream *substream; } streams[2]; };
static bool denali = true;
static bool of_machine_is_compatible(const char *name) { assert(!strcmp(name, "microsoft,denali")); return denali; }
static bool of_property_read_bool(struct device_node *n, const char *name)
{
    assert(!strcmp(name, "microsoft,denali-fullio-capture-only"));
    return n && n->capture_only;
}
"""

CHECKS = r"""
int main(void)
{
    struct device_node dt = {.capture_only = true};
    struct device dev = {&dt};
    struct snd_soc_card card = {&dev};
    struct snd_soc_component component = {&card};
    struct snd_pcm_substream out = {SNDRV_PCM_STREAM_PLAYBACK}, in = {SNDRV_PCM_STREAM_CAPTURE};
    struct snd_pcm pcm = {0};
    for (int m = 0; m <= 1; m++) for (int a = 0; a <= 1; a++)
        for (int graph = 0; graph <= 2; graph++) for (int streams = 0; streams <= 3; streams++) {
            denali = m; dt.capture_only = a;
            pcm.streams[SNDRV_PCM_STREAM_PLAYBACK].substream = (streams & 1) ? &out : 0;
            pcm.streams[SNDRV_PCM_STREAM_CAPTURE].substream = (streams & 2) ? &in : 0;
            assert(q6apm_fullio_no_render_backing(&component, &pcm, graph) ==
                   (m && a && graph == 0 && streams == 1));
        }
    assert(pcm_gate(&component, &out) == -EOPNOTSUPP);
    assert(!pcm_gate(&component, &in));
    assert(compr_gate(&component) == -EOPNOTSUPP);
    denali = false;
    assert(!pcm_gate(&component, &out) && !compr_gate(&component));
    denali = true;
    dt.capture_only = false;
    assert(!pcm_gate(&component, &out) && !compr_gate(&component));
    component.card = 0;
    assert(!compr_gate(&component));
}
"""


def function(text, name):
    match = re.search(rf"^static (?:int|bool|void) {name}\([^{{]*\{{.*?^\}}", text, re.M | re.S)
    if match is None:
        raise ValueError(f"could not extract {name}")
    return match.group()


def gate(body, signature):
    match = re.search(r"\tif \([^\n]*q6apm_fullio_capture_only\(component\)\)\n\t\treturn -EOPNOTSUPP;", body)
    if not match or match.start() >= body.index("q6apm_graph_open(") or match.start() >= body.index("kzalloc_obj("):
        raise ValueError("render gate missing or after allocation")
    return signature + "\n{\n" + match.group() + "\n\treturn 0;\n}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="patched q6apm-dai.c")
    text = parser.parse_args().source.read_text()
    pcm_new = function(text, "q6apm_dai_pcm_new")
    skip = pcm_new[pcm_new.index('if (q6apm_fullio_no_render_backing'):pcm_new.index('snd_pcm_set_fixed_buffer_all')]
    assert 'return 0;' in skip and 'q6apm_dai_memory_map' not in skip
    pcm_free = function(text, "q6apm_dai_pcm_free")
    skip = pcm_free[pcm_free.index('if (cpu && (q6apm_fullio_no_render_backing'):pcm_free.rindex('q6apm_dai_memory_unmap')]
    assert 'return;' in skip
    checks = (
        function(text, "q6apm_fullio_capture_only"),
        function(text, "q6apm_fullio_no_render_backing"),
        gate(function(text, "q6apm_dai_open"), "static int pcm_gate(struct snd_soc_component *component, struct snd_pcm_substream *substream)"),
        gate(function(text, "q6apm_dai_compr_open"), "static int compr_gate(struct snd_soc_component *component)"),
    )
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "open.c"
        exe = source.with_suffix("")
        source.write_text(STUBS + "\n".join(checks) + CHECKS)
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("Capture-only: no render open or MultiMedia1 backing; capture and other fixtures unchanged.")


if __name__ == "__main__":
    main()
