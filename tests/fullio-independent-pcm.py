#!/usr/bin/env python3
"""The independent diagnostic PCM must never send legacy DMA mappings."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()


def extract(name):
    return re.search(rf'^static [^\n]+\b{name}\([^{{]*\{{.*?^\}}', text, re.M | re.S).group()


new = extract('q6apm_dai_pcm_new')
assert new.index('q6apm_fullio_independent_pcm') < new.index('snd_pcm_set_fixed_buffer_all')
gate = new[new.index('if (q6apm_fullio_independent_pcm'):new.index('ret = q6apm_dai_memory_map')]
assert gate.index('return 0;') < gate.index('snd_pcm_set_fixed_buffer_all') < gate.index('q6apm_dai_scm_assign')
assert 'SNDRV_PCM_STREAM_CAPTURE' in gate and 'return -EPERM;' in gate
free = extract('q6apm_dai_pcm_free')
assert free.index('q6apm_dai_memory_unmap') < free.index('q6apm_fullio_independent_pcm') < free.rindex('q6apm_dai_memory_unmap')
prepare = extract('q6apm_dai_prepare')
assert (prepare.index('q6apm_fullio_independent_pcm') < prepare.index('q6apm_fullio_ring_map_audit')
        < prepare.index('q6apm_fullio_prepare_pull_media') < prepare.index('q6apm_fullio_pcm_buffer')
        < prepare.index('snd_pcm_set_runtime_buffer(substream, buffer)') < prepare.index('q6apm_fullio_prepare_cal')
        < prepare.index('snd_pcm_set_runtime_buffer(substream, NULL)') < prepare.index('q6apm_push_pull_config'))
close = extract('q6apm_dai_close')
assert close.index('snd_pcm_set_runtime_buffer(substream, NULL)') < close.index('q6apm_graph_close')
compressed = extract('q6apm_dai_compr_open')
assert compressed.index('q6apm_fullio_independent_pcm') < compressed.index('q6apm_graph_open')

source = r'''
#include <stdbool.h>
#include <assert.h>
#include <errno.h>
#include <string.h>
#define SNDRV_PCM_STREAM_PLAYBACK 0
struct device { bool *of_node; };
struct card { struct device *dev; };
struct snd_soc_component { struct card *card; };
static bool denali = true, native;
static bool q6apm_fullio_reference_render(struct card *card) { return card && denali && native; }
static bool of_machine_is_compatible(const char *name) { assert(!strcmp(name, "microsoft,denali")); return denali; }
static bool of_property_read_bool(const bool *node, const char *name)
{ assert(!strcmp(name, "microsoft,denali-fullio-ring-map-audit")); return *node; }
struct q6apm_graph { int dev; };
struct audioreach_module_config { int valid; };
#define dev_info(dev, ...) assert(dev)
#define dev_err_probe(dev, ret, ...) (assert(dev), (ret))
static int stage, fail_stage;
static int q6apm_fullio_register_pull_events(struct q6apm_graph *g, unsigned int bytes)
{
    assert(g && bytes == 1920 && stage++ == 0);
    return fail_stage == 1 ? -ETIMEDOUT : 0;
}
static int q6apm_graph_media_format_shmem(struct q6apm_graph *g, struct audioreach_module_config *cfg)
{
    assert(g && cfg->valid && stage++ == 1);
    return fail_stage == 2 ? -EIO : 0;
}
''' + extract('q6apm_fullio_independent_pcm') + '\n' + extract('q6apm_fullio_prepare_pull_media') + r'''
int main(void)
{
    bool audit = true;
    struct device d = {&audit};
    struct card card = {&d};
    struct snd_soc_component c = {&card};
    for (int m = 0; m < 2; m++) for (int a = 0; a < 2; a++)
        for (int i = 0; i < 3; i++) for (int stream = 0; stream < 2; stream++) {
            denali = m; audit = a;
            assert(q6apm_fullio_independent_pcm(&c, i, stream) == (m && a && !i && !stream));
        }
    native = true;
    denali = true;
    audit = false;
    assert(q6apm_fullio_independent_pcm(&c, 0, 0));
    assert(!q6apm_fullio_independent_pcm(&c, 0, 1));
    c.card = 0;
    assert(!q6apm_fullio_independent_pcm(&c, 0, 0));
    struct q6apm_graph g = {1};
    struct audioreach_module_config cfg = {1};
    for (fail_stage = 0; fail_stage <= 2; fail_stage++) {
        stage = 0;
        int ret = q6apm_fullio_prepare_pull_media(&g, &cfg, 1920);
        assert(ret == (fail_stage == 1 ? -ETIMEDOUT : fail_stage == 2 ? -EIO : 0));
        assert(stage == (fail_stage == 1 ? 1 : 2));
    }
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'proof.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Independent DMA owner stays on Denali graph 0; pull registrations precede SHMEM and first failures propagate.')
