#!/usr/bin/env python3
"""Compile the real WSA PM callbacks against a modeled devres release."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile


STUBS = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>

struct regmap { bool cache_only, dirty; int sync_error; };
struct wsa884x_priv { struct regmap *regmap; };
struct device { struct wsa884x_priv *priv; bool enabled, autosuspend; };
static struct wsa884x_priv *dev_get_drvdata(struct device *dev) { return dev->priv; }
static void regcache_cache_only(struct regmap *map, bool only) { map->cache_only = only; }
static void regcache_mark_dirty(struct regmap *map) { map->dirty = true; }
static int regcache_sync(struct regmap *map)
{
    assert(!map->cache_only);
    return map->sync_error;
}
static void pm_runtime_disable(struct device *dev)
{
    assert(dev->enabled && dev->autosuspend);
    dev->enabled = false;
}
static void pm_runtime_dont_use_autosuspend(struct device *dev)
{
    /* Clearing autosuspend with runtime PM enabled could dispatch an idle callback. */
    assert(!dev->enabled);
    dev->autosuspend = false;
}
"""

CHECKS = r"""
int main(void)
{
    struct regmap left = {0}, right = {0};
    struct wsa884x_priv left_priv = {&left}, right_priv = {&right};
    struct device a = {&left_priv, true, true}, b = {&right_priv, true, true};

    /* No devres lookup exists here; the driver's pointer owns the access. */
    assert(!wsa884x_runtime_suspend(&a));
    assert(left.cache_only && left.dirty && !right.cache_only && !right.dirty);
    assert(!wsa884x_runtime_resume(&a) && !left.cache_only);
    assert(!wsa884x_runtime_suspend(&b));
    right.dirty = false;
    right.sync_error = -EIO;
    assert(wsa884x_runtime_resume(&b) == -EIO && right.cache_only && right.dirty);
    assert(!left.cache_only);

    /* The managed action runs both on detach and on registration failure. */
    wsa884x_runtime_disable(&a);
    assert(!a.enabled && !a.autosuspend && b.enabled && b.autosuspend);
    wsa884x_runtime_disable(&b);
    assert(!b.enabled && !b.autosuspend);
    return 0;
}
"""


def function(source: str, name: str) -> str:
    match = re.search(rf"^static (?:void|int) {name}\([^\n]*\)\n\{{.*?^\}}", source, re.M | re.S)
    if match is None:
        raise ValueError(f"missing {name}")
    return match.group()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path, help="patched sound/soc/codecs/wsa884x.c")
    args = parser.parse_args()
    text = args.codec.read_text()
    probe = text[text.index("static int wsa884x_probe(") : text.index("static int wsa884x_runtime_suspend(")]
    actions = (
        "devm_regmap_init_sdw(",
        "pm_runtime_enable(dev);",
        "devm_add_action_or_reset(dev, wsa884x_runtime_disable, dev);",
        "devm_snd_soc_register_component(",
    )
    positions = [probe.index(action) for action in actions]
    if positions != sorted(positions):
        raise ValueError("unsafe regmap, PM or component registration order")
    callbacks = ("wsa884x_runtime_disable", "wsa884x_runtime_suspend", "wsa884x_runtime_resume")
    with tempfile.TemporaryDirectory() as work:
        test = Path(work) / "lifetime.c"
        test.write_text(STUBS + "\n\n".join(function(text, name) for name in callbacks) + CHECKS)
        exe = test.with_suffix("")
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(test), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("WSA runtime PM: private regmap, per-device state, sync failure and disable-before-idle verified")


if __name__ == "__main__":
    main()
