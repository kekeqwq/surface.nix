#!/usr/bin/env python3
"""Exercise Denali sidechain register gates and restoration from kernel source."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile

STUBS = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

typedef uint32_t u32;
#define MASTER_ID_WSA 1
#define dev_err(...) ((void)0)
#define dev_info_ratelimited(...) ((void)0)
struct device_node { bool feedback, capture, integrated, wake, offset; };
struct device { struct device_node *of_node; };
struct qcom_swrm_ctrl {
    struct device *dev;
    struct { unsigned int controller_id; } bus;
    bool cps_wake_active;
    u32 cps_saved_route, cps_saved_pcm;
    int (*reg_read)(struct qcom_swrm_ctrl *, u32, u32 *);
    int (*reg_write)(struct qcom_swrm_ctrl *, u32, u32);
};
static bool denali = true;
static bool of_machine_is_compatible(const char *s) { return denali && !strcmp(s, "microsoft,denali"); }
static bool of_property_read_bool(const struct device_node *n, const char *s)
{
    if (!strcmp(s, "qcom,denali-fullio-feedback")) return n->feedback;
    if (!strcmp(s, "qcom,denali-fullio-feedback-capture-test")) return n->capture;
    if (!strcmp(s, "qcom,denali-fullio-sidechain-audit")) return n->integrated;
    if (!strcmp(s, "qcom,denali-cps-probe-wake-test")) return n->wake;
    if (!strcmp(s, "qcom,denali-cps-probe-active-offset2-test")) return n->offset;
    assert(false);
    return false;
}
"""

CHECKS = r"""
static u32 regs[2] = {0x1020, 0x31};
static unsigned int writes;
static bool drop_pcm;
static unsigned int reg_index(u32 reg)
{
    assert(reg == DENALI_CPS_WAKE_ROUTE_REG || reg == DENALI_CPS_WAKE_PCM_REG);
    return reg == DENALI_CPS_WAKE_PCM_REG;
}
static int read_register(struct qcom_swrm_ctrl *c, u32 reg, u32 *v)
{
    assert(c);
    *v = regs[reg_index(reg)];
    return 0;
}
static int write_register(struct qcom_swrm_ctrl *c, u32 reg, u32 v)
{
    assert(c);
    writes++;
    if (!drop_pcm || !reg_index(reg)) regs[reg_index(reg)] = v;
    return 0;
}

int main(void)
{
    struct device_node dt = {.feedback = true};
    struct device dev = {&dt};
    struct qcom_swrm_ctrl c = {.dev = &dev, .bus = {MASTER_ID_WSA},
                              .reg_read = read_register, .reg_write = write_register};
    assert(!qcom_swrm_cps_wake_probe(&c));
    dt.integrated = true;
    assert(qcom_swrm_cps_wake_probe(&c));
    for (unsigned int i = 0; i <= 14; i++)
        assert(qcom_swrm_audit_active_offset2(&c, i) == (i == 10 || i == 11 || i == 13));
    c.bus.controller_id++;
    assert(!qcom_swrm_cps_wake_probe(&c));
    c.bus.controller_id--;
    denali = false;
    assert(!qcom_swrm_audit_active_offset2(&c, 13));
    denali = true;
    dt.capture = true;
    assert(!qcom_swrm_cps_wake_probe(&c));
    dt.wake = dt.offset = true;
    assert(qcom_swrm_audit_active_offset2(&c, 13));
    assert(!qcom_swrm_audit_active_offset2(&c, 10));
    dt.capture = false;

    assert(qcom_swrm_apply_cps_wake(&c) == 0 && c.cps_wake_active);
    assert(regs[0] == 0x0005000f && regs[1] == 3);
    assert(qcom_swrm_apply_cps_wake(&c) == 0);
    assert(c.cps_saved_route == 0x1020 && c.cps_saved_pcm == 0x31);
    drop_pcm = true;
    assert(qcom_swrm_restore_cps_wake(&c) == -EIO && c.cps_wake_active);
    assert(regs[0] == 0x1020 && regs[1] == 3);
    drop_pcm = false;
    assert(qcom_swrm_restore_cps_wake(&c) == 0 && !c.cps_wake_active);
    assert(regs[0] == 0x1020 && regs[1] == 0x31);
    unsigned int before = writes;
    assert(qcom_swrm_restore_cps_wake(&c) == 0 && writes == before);
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_tree", type=Path)
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    args = parser.parse_args()
    source = (args.kernel_tree / "drivers/soundwire/qcom.c").read_text()
    start = source.index("#define DENALI_CPS_WAKE_ROUTE_REG")
    end = source.index("static int qcom_swrm_transport_params(", start)
    with tempfile.TemporaryDirectory(prefix="fullio-sidechain-") as td:
        src = Path(td) / "verify.c"
        exe = Path(td) / "verify"
        src.write_text(STUBS + source[start:end] + CHECKS)
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                        str(src), "-o", str(exe)], check=True)
        subprocess.run([exe], check=True)
    print("FullIO sidechain: controller/port gates, CPS wake, recovery and restored readback passed")


if __name__ == "__main__":
    main()
