#!/usr/bin/env python3
"""Check if upstream PM cleanup covers the Denali devres lookup loss.

This source/model check takes the pinned Linux source tree and a patched WSA
codec source. It never unbinds a device or executes kernel code on hardware.
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path


def body(text, name):
    match = re.search(rf'^(?:static )?(?:int|void) {name}\([^;{{]*\{{.*?^\}}', text, re.M | re.S)
    if not match:
        raise ValueError(f'cannot find {name}')
    return match.group()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('upstream', type=Path)
    p.add_argument('patched_codec', type=Path)
    args = p.parse_args()
    read = lambda path: (args.upstream / path).read_text()
    codec = read('sound/soc/codecs/wsa884x.c')
    pm = read('drivers/base/power/runtime.c')
    devres = body(read('drivers/base/devres.c'), 'devres_release_all')
    lookup = read('drivers/base/regmap/regmap.c')
    assert devres.index('remove_nodes(') < devres.index('release_nodes(')
    assert 'devres_find(dev, dev_get_regmap_release' in lookup
    assert 'devm_pm_runtime_enable(dev)' in body(codec, 'wsa884x_probe')
    patched = args.patched_codec.read_text()
    upstream_suspend = body(codec, 'wsa884x_runtime_suspend').replace('wsa884x_runtime_suspend', 'upstream_suspend')
    patched_suspend = body(patched, 'wsa884x_runtime_suspend')
    code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
struct regmap { bool cache_only; };
struct wsa884x_priv { struct regmap *regmap; };
struct device { struct wsa884x_priv *priv; bool enabled, listed, old; };
static unsigned callbacks, failed_lookups;
static struct wsa884x_priv *dev_get_drvdata(struct device *d) { return d->priv; }
static struct regmap *dev_get_regmap(struct device *d, void *ignored)
{
    assert(!ignored);
    return d->listed ? d->priv->regmap : NULL;
}
static void regcache_cache_only(struct regmap *regmap, bool cache_only)
{
    if (regmap) regmap->cache_only = cache_only;
    else failed_lookups++;  /* Record where the kernel would dereference NULL. */
}
static void regcache_mark_dirty(struct regmap *regmap) { (void)regmap; }
''' + upstream_suspend + '\n' + patched_suspend + r'''
static void pm_runtime_dont_use_autosuspend(void *data)
{
    struct device *dev = data;
    if (dev->enabled) { /* Modeled idle dispatch from the observed teardown. */
        callbacks++;
        if (dev->old) upstream_suspend(dev);
        else wsa884x_runtime_suspend(dev);
    }
}
static void pm_runtime_disable(void *data)
{
    ((struct device *)data)->enabled = false;
}
''' + body(pm, 'pm_runtime_disable_action') + '\n' + body(patched, 'wsa884x_runtime_disable') + r'''
int main(void)
{
    struct regmap map = {0};
    struct wsa884x_priv priv = {&map};
    struct device old = {&priv, true, false, true};
    struct device fixed = {&priv, true, false, false};
    pm_runtime_disable_action(&old);
    assert(!old.enabled && callbacks == 1 && failed_lookups == 1);
    assert(!wsa884x_runtime_suspend(&fixed) && map.cache_only);
    wsa884x_runtime_disable(&fixed);
    assert(!fixed.enabled && callbacks == 1 && failed_lookups == 1);
}
'''
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / 'pm.c'
        exe = src.with_suffix('')
        src.write_text(code)
        subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
        subprocess.run([exe], check=True)
    print('Pinned upstream managed action is not equivalent: detached lookup fails in the modeled callback, local fix does not.')


if __name__ == '__main__':
    main()
