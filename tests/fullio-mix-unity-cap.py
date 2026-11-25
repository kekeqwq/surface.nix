#!/usr/bin/env python3
"""Exercise the scoped FullIO mixer cap and the pinned ASoC write gate."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def extract(path, name):
    text = Path(path).read_text()
    return re.search(rf'^static int {name}\([^{{]*\{{.*?^\}}', text, re.M | re.S)[0]


init = extract(sys.argv[1], 'x1e80100_snd_init')
wsa = init.split('case WSA_CODEC_DMA_RX_1:', 1)[1].split('case DISPLAY_PORT_RX_0:', 1)[0]
assert 'ret = x1e80100_fullio_mix_cap(card);\n\t\tif (ret)\n\t\t\treturn ret;' in wsa
code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
struct device { void *of_node; };
struct snd_soc_card { struct device *dev; };
struct soc_mixer_control { int platform_max; };
static bool board, enabled;
static unsigned calls, failure;
static struct soc_mixer_control channels[2];
static bool of_machine_is_compatible(const char *id)
{ assert(!strcmp(id, "microsoft,denali")); return board; }
static bool of_property_read_bool(void *node, const char *prop)
{ assert(node && !strcmp(prop, "microsoft,denali-fullio-muted-test")); return enabled; }
static int dev_err_probe(struct device *dev, int err, const char *msg, const char *name)
{ assert(dev && msg && name); return err; }
static int snd_soc_limit_volume(struct snd_soc_card *card, const char *name, int max)
{
    const char *names[] = {"WSA WSA_RX0_MIX Digital Volume", "WSA WSA_RX1_MIX Digital Volume"};
    assert(card && calls < 2 && !strcmp(names[calls], name));
    if (++calls == failure)
        return -EIO;
    channels[calls-1].platform_max = max;
    return 0;
}
''' + extract(sys.argv[1], 'x1e80100_fullio_mix_cap') + '\n' + extract(sys.argv[2], 'soc_mixer_valid_ctl') + r'''
int main(void)
{
    struct device d = { &d };
    struct snd_soc_card card = { &d };
    enabled = true;
    assert(x1e80100_fullio_mix_cap(&card) == 0 && !calls);
    board = true; enabled = false;
    assert(x1e80100_fullio_mix_cap(&card) == 0 && !calls);
    enabled = true;
    for (failure = 1; failure <= 2; failure++) {
        calls = 0;
        assert(x1e80100_fullio_mix_cap(&card) == -EIO && calls == failure);
    }
    calls = 0;
    assert(x1e80100_fullio_mix_cap(&card) == 0 && calls == 2);
    for (unsigned i = 0; i < ARRAY_SIZE(channels); i++) {
        assert(soc_mixer_valid_ctl(&channels[i], 0, 124) == 0);
        assert(soc_mixer_valid_ctl(&channels[i], 84, 124) == 0);
        assert(soc_mixer_valid_ctl(&channels[i], 85, 124) == -EINVAL);
        assert(soc_mixer_valid_ctl(&channels[i], 124, 124) == -EINVAL);
    }
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'cap.c'
    exe = c.with_suffix('')
    c.write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Both scoped MIX caps admit at most code 84 (unity); errors propagate and ordinary cards are unchanged.')
