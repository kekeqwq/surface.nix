#!/usr/bin/env python3
"""Exercise the native kernel shared reset and GPIO provider on a fake line only."""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile

STUBS = r"""
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stddef.h>
#include <stdlib.h>
#define ENOTSUPP EOPNOTSUPP
#define WARN_ON(x) (!!(x))
#define WARN(x, ...) ((void)(x))
typedef int atomic_t;
#define atomic_read(p) (*(p))
#define atomic_inc_return(p) (++*(p))
#define atomic_dec_return(p) (--*(p))
struct reset_controller_dev;
struct reset_control_ops {
    int (*assert)(struct reset_controller_dev *, unsigned long);
    int (*deassert)(struct reset_controller_dev *, unsigned long);
    int (*status)(struct reset_controller_dev *, unsigned long);
};
struct reset_controller_dev { const struct reset_control_ops *ops; };
struct gpio_desc { bool raw_level, active_low; int write_error, read_error, writes, reads; };
struct reset_gpio_priv { struct reset_controller_dev rc; struct gpio_desc *reset; };
struct reset_control { bool shared, acquired; atomic_t triggered_count, deassert_count; unsigned long id; };
static struct reset_gpio_priv *rc_to_reset_gpio(struct reset_controller_dev *rc)
{
    return (void *)((char *)rc - offsetof(struct reset_gpio_priv, rc));
}
static const char *rcdev_name(struct reset_controller_dev *rc) __attribute__((unused));
static const char *rcdev_name(struct reset_controller_dev *rc) { assert(rc); return "mock-gpio"; }
static int gpiod_set_value_cansleep(struct gpio_desc *gpio, int logical)
{
    gpio->writes++;
    if (gpio->write_error) return gpio->write_error;
    gpio->raw_level = !!logical ^ gpio->active_low;
    return 0;
}
static int gpiod_get_value_cansleep(struct gpio_desc *gpio)
{
    gpio->reads++;
    if (gpio->read_error) return gpio->read_error;
    return gpio->raw_level ^ gpio->active_low;
}
"""

CHECKS = r"""
#define assert(expr) do { if (!(expr)) abort(); } while (0)
static const struct reset_control_ops ops = {reset_gpio_assert, reset_gpio_deassert, reset_gpio_status};
int main(void)
{
    struct gpio_desc pin = { .active_low = true };
    struct reset_gpio_priv provider = { {&ops}, &pin };
    struct reset_controller_dev *ctrl = &provider.rc;
    struct reset_control shared = { .shared = true };

    /* Two codec consumer votes; only the last release acts on the line. */
    assert(!__reset_control_deassert(&shared, ctrl));
    assert(!__reset_control_deassert(&shared, ctrl));
    assert(pin.raw_level && shared.deassert_count == 2 && pin.writes == 1);
    assert(!__reset_control_assert(&shared, ctrl));
    assert(reset_gpio_status(ctrl, 0) == 0 && pin.writes == 1);
    assert(!__reset_control_assert(&shared, ctrl));
    assert(reset_gpio_status(ctrl, 0) == 1 && !pin.raw_level && pin.writes == 2);

    /* Extra caller: two successful 'asserts' don't imply physical shutdown. */
    assert(!__reset_control_deassert(&shared, ctrl));
    assert(!__reset_control_deassert(&shared, ctrl));
    assert(!__reset_control_deassert(&shared, ctrl));
    assert(!__reset_control_assert(&shared, ctrl));
    assert(!__reset_control_assert(&shared, ctrl));
    assert(reset_gpio_status(ctrl, 0) == 0 && shared.deassert_count == 1);

    /* A provider failure still consumed the last shared vote on this kernel. */
    pin.write_error = -EIO;
    assert(__reset_control_assert(&shared, ctrl) == -EIO);
    assert(reset_gpio_status(ctrl, 0) == 0 && shared.deassert_count == 0);
    int prior = pin.writes;
    assert(__reset_control_assert(&shared, ctrl) == -EINVAL && pin.writes == prior);
    pin.read_error = -ENODEV;
    assert(reset_gpio_status(ctrl, 0) == -ENODEV);

    /* The deassert count also changes before a failing provider write. */
    pin.read_error = 0;
    assert(__reset_control_deassert(&shared, ctrl) == -EIO);
    assert(shared.deassert_count == 1 && pin.raw_level);
}
"""


def function(text, name):
    match = re.search(rf"^static int {name}\([^{{]*\{{.*?^\}}", text, re.M | re.S)
    if match is None:
        raise ValueError(f"could not extract {name}")
    return match.group()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reset_dir", type=Path, help="drivers/reset from pinned Surface-next sources")
    args = parser.parse_args()
    core = (args.reset_dir / "core.c").read_text()
    gpio = (args.reset_dir / "reset-gpio.c").read_text()
    helpers = [function(core, n) for n in ("__reset_control_assert", "__reset_control_deassert")]
    helpers += [function(gpio, n) for n in ("reset_gpio_assert", "reset_gpio_deassert", "reset_gpio_status")]
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "shared-sd-n.c"
        exe = src.with_suffix("")
        src.write_text(STUBS + "\n#undef assert\n" + "\n".join(helpers) + CHECKS)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", src, "-o", exe], check=True)
        subprocess.run([str(exe)], check=True)
    print("Shared SD_N model: one/extra votes do not assert pin; provider error consumes vote; raw retry rejected.")


if __name__ == "__main__":
    main()
