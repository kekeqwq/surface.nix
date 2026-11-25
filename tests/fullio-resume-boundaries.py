#!/usr/bin/env python3
"""Check the actual clock-start prefix without operating a SoundWire device."""
from pathlib import Path
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
start = text.index('static int __maybe_unused swrm_runtime_resume(')
begin = text.index('\t\tint ee_ret = 0, start_ret, mask_ret = 0;', start)
end = text.index('\n\n\t\tusleep_range(100, 105);', begin)
c = r'''
#include <assert.h>
#include <string.h>
#define SWRM_VERSION_1_7_0 7
#define SWRM_VERSION_2_0_0 8
#define SWRM_LINK_MANAGER_EE 20
#define SWRM_MCP_BUS_CTRL 24
#define SWRM_MCP_BUS_CLK_START 2
#define SWRM_V2_0_CLK_CTRL 32
#define SWRM_EE_CPU 1
#define SWRM_V2_REG_EE_STRIDE 4
#define SWRM_V2_0_CLK_CTRL_CLK_START 1
#define SWRM_INTERRUPT_STATUS_MASTER_CLASH_DET 8
#define SWRM_REG_INTERRUPT_CLEAR 0
#define SWRM_REG_INTERRUPT_MASK_ADDR 1
#define SWRM_REG_INTERRUPT_CPU_EN 2
struct qcom_swrm_ctrl {
    int version, ee, audio_cgcr, intr_mask, fullio_link_gate;
    const int *reg_layout;
    int (*reg_write)(struct qcom_swrm_ctrl *, int, int);
};
static int phase, reset_rc, ee_rc, start_rc, clear_rc, mask_rc, enable_rc;
static int clock_snapshot(const struct qcom_swrm_ctrl *ctrl) { return ctrl->version < 7 ? 4 : 5; }
static int reset_control_reset(int id) { assert(id == 42 && phase++ == 1); return reset_rc; }
static void swrm_fullio_pm_snapshot(struct qcom_swrm_ctrl *ctrl, const char *stage, int result)
{
    assert(ctrl->audio_cgcr == 42);
    if (phase == 0) { assert(!strcmp(stage, "before-cgcr-reset") && !result); }
    else if (phase == 2) { assert(!strcmp(stage, "after-cgcr-reset-before-clock-start") && result == reset_rc); }
    else if (phase == clock_snapshot(ctrl)) {
        assert(!strcmp(stage, "clock-start-before-clash-clear"));
        assert(result == (ctrl->version >= 7 && ee_rc ? ee_rc : start_rc));
    } else if (phase == clock_snapshot(ctrl) + 2) {
        assert(!strcmp(stage, "after-clash-clear-before-irq-restore") && result == clear_rc);
    } else {
        assert(phase == clock_snapshot(ctrl) + (ctrl->version < 8 ? 5 : 4));
        assert(!strcmp(stage, "after-irq-restore-before-frame-wait"));
        assert(result == (ctrl->version < 8 && mask_rc ? mask_rc : enable_rc));
    }
    phase++;
}
static int reg_write(struct qcom_swrm_ctrl *ctrl, int reg, int value)
{
    if (reg == SWRM_LINK_MANAGER_EE) {
        assert(ctrl->version >= 7 && value == 2 && phase++ == 3);
        return ee_rc;
    }
    if (reg == 80) {
        assert(phase++ == clock_snapshot(ctrl) + 1 && value == 8);
        return clear_rc;
    }
    if (reg == 84) {
        assert(ctrl->version < 8 && phase++ == clock_snapshot(ctrl) + 3 && value == 9);
        return mask_rc;
    }
    if (reg == 88) {
        assert(phase++ == clock_snapshot(ctrl) + (ctrl->version < 8 ? 4 : 3) && value == 9);
        return enable_rc;
    }
    assert(phase++ == (ctrl->version < 7 ? 3 : 4));
    if (ctrl->version == 8) assert(reg == 36 && value == 1);
    else assert(reg == 24 && value == (ctrl->version == 7 ? 8 : 2));
    return start_rc;
}
static void exercise(struct qcom_swrm_ctrl *ctrl)
{
    int ret;
''' + text[begin:end] + (r'''
    return;
incomplete:
    assert(0 && "non-FullIO must keep the original prefix");
''' if 'goto incomplete;' in text[begin:end] else '') + r'''
}
int main(void)
{
    const int layout[] = {80, 84, 88};
    struct qcom_swrm_ctrl ctrl = {.ee = 2, .audio_cgcr = 42, .reg_write = reg_write, .reg_layout = layout};
    for (ctrl.version = 6; ctrl.version <= 8; ++ctrl.version) {
        for (int errors = 0; errors < 64; ++errors) {
            phase = 0;
            ctrl.intr_mask = 1;
            reset_rc = errors & 1 ? -5 : 0;
            ee_rc = errors & 2 ? 2 : 0;
            start_rc = errors & 4 ? 3 : 0;
            clear_rc = errors & 8 ? 4 : 0;
            mask_rc = errors & 16 ? 5 : 0;
            enable_rc = errors & 32 ? 6 : 0;
            exercise(&ctrl);
            assert(phase == clock_snapshot(&ctrl) + (ctrl.version < 8 ? 6 : 5));
        }
    }
}
'''
with tempfile.TemporaryDirectory() as d:
    src = Path(d) / 'probe.c'
    src.write_text(c)
    exe = src.with_suffix('')
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Resume snapshots bracket reset, clock start, clash clear and IRQ restore across all layouts without extra writes.')
