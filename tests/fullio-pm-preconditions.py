#!/usr/bin/env python3
"""Test SoundWire suspend and resume prerequisites with offline stubs."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()


def extract(name):
    return re.search(rf'^static [^\n]+\b{name}\([^{{]*\{{.*?^\}}', source, re.M | re.S).group()


resume = extract('swrm_runtime_resume').split('\n\tif (ctrl->clock_stop_not_supported)', 1)[0]
resume += '\n\treturn 0;\n}\n'


c = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#define __maybe_unused
#define READ_ONCE(v) (v)
#define WRITE_ONCE(v, value) ((v) = (value))
#define cmpxchg(p, o, n) __sync_val_compare_and_swap(p, o, n)
#define dev_err(...) ((void)0)
#define dev_info_ratelimited(...) (++confirmed)
#define SDW_CMD_OK 0
#define SWRM_COMP_STATUS 0x14
#define SWRM_FRM_GEN_ENABLED 1u
typedef unsigned int u32;
#define SWRM_INTERRUPT_STATUS_MASTER_CLASH_DET 16u
#define SWRM_VERSION_2_0_0 2
#define SWRM_REG_INTERRUPT_MASK_ADDR 0
#define SWRM_REG_INTERRUPT_CPU_EN 1
struct qcom_swrm_ctrl {
    bool fullio_link_gate, clock_stop_not_supported, fullio_pm_incomplete;
    unsigned long fullio_seen_attached;
    int fullio_link_error, wake_irq, irq, version, reg_layout[2], bus;
    unsigned int intr_mask;
    int (*reg_write)(struct qcom_swrm_ctrl *, int, unsigned int);
    int (*reg_read)(struct qcom_swrm_ctrl *, int, u32 *);
    void *hclk;
};
struct device { struct qcom_swrm_ctrl *ctrl; const bool *of_node; };
static int clock_result, irq_op, clock_op, writes, stop_calls, snapshot_calls, prep_result, stop_result;
static int frame_reads, frame_sleeps, stop_at, read_bad_at, read_error, confirmed;
static bool drained, wait_frame, lose_broadcast;
static int fifo_checks;
static bool of_property_read_bool(const bool *node, const char *property) { assert(property); return *node; }
static struct qcom_swrm_ctrl *dev_get_drvdata(struct device *d) { return d->ctrl; }
static int clk_prepare_enable(void *clk) { (void)clk; clock_op++; return clock_result; }
static int irq_get_irq_data(int irq) { return irq; }
static bool irqd_irq_disabled(int irq) { (void)irq; return false; }
static void disable_irq_nosync(int irq) { assert(irq > 0); irq_op++; }
static void enable_irq(int irq) { assert(irq > 0); irq_op++; }
static bool swrm_wait_for_wr_fifo_done(struct qcom_swrm_ctrl *ctrl) { assert(ctrl); ++fifo_checks; return drained; }
static int write_reg(struct qcom_swrm_ctrl *c, int reg, unsigned int mask)
{ assert(c && reg == 1 && mask == 0); writes++; return 0; }
static int sdw_bus_prep_clk_stop(int *bus) { assert(bus); return prep_result; }
static struct qcom_swrm_ctrl *active_ctrl;
static int sdw_bus_clk_stop(int *bus);
static void swrm_fullio_pm_snapshot(struct qcom_swrm_ctrl *c, const char *stage, int ret)
{ assert(c && stage && ret == stop_result); snapshot_calls++; }
static void disable_irq(int irq) { assert(irq > 0); irq_op++; }
static void clk_disable_unprepare(void *clk) { (void)clk; clock_op++; }
static void usleep_range(int min, int max)
{
    if (min == 1000) { assert(max == 1100); ++frame_sleeps; }
    else assert(min == 300 && max == 305);
}
static int read_frame(struct qcom_swrm_ctrl *c, int reg, u32 *state)
{
    assert(c && reg == SWRM_COMP_STATUS && !irq_op && !clock_op && stop_calls == 1 && snapshot_calls == 1);
    *state = ++frame_reads >= stop_at ? 0 : SWRM_FRM_GEN_ENABLED;
    return frame_reads == read_bad_at ? read_error : SDW_CMD_OK;
}
''' + '\n'.join(extract(f'qcom_swrm_fullio_{suffix}') for suffix in
                       ('latch_link_error', 'new_stream_ok')) + '\n' + extract('swrm_fullio_wait_for_frame_stop') + '\n' + resume + '\n' + extract('swrm_fullio_clock_stop_result') + '\n' + extract('swrm_runtime_suspend') + r'''
static int sdw_bus_clk_stop(int *bus)
{
    assert(bus == &active_ctrl->bus);
    stop_calls++;
    if (lose_broadcast)
        qcom_swrm_fullio_latch_link_error(active_ctrl, -ETIMEDOUT);
    return stop_result;
}
int main(void)
{
    struct qcom_swrm_ctrl ctrl = {
        .fullio_link_gate = true, .wake_irq = 2, .irq = 3, .version = SWRM_VERSION_2_0_0,
        .reg_layout = {0, 1}, .reg_write = write_reg, .intr_mask = SWRM_INTERRUPT_STATUS_MASTER_CLASH_DET,
    };
    struct device dev = { &ctrl, &wait_frame };
    active_ctrl = &ctrl;
    clock_result = -EIO;
    assert(swrm_runtime_resume(&dev) == -EIO && ctrl.fullio_link_error == -EIO && clock_op == 1 && !irq_op);
    clock_result = ctrl.fullio_link_error = 0;
    assert(!swrm_runtime_resume(&dev) && clock_op == 2 && irq_op == 2);
    assert(swrm_runtime_suspend(&dev) == -ETIMEDOUT && ctrl.fullio_link_error == -ETIMEDOUT);
    assert(!writes && !stop_calls && !snapshot_calls && irq_op == 2 && clock_op == 2);
    ctrl.fullio_link_error = 0;
    drained = true;
    prep_result = -EIO;
    assert(swrm_runtime_suspend(&dev) == -EIO && ctrl.fullio_link_error == -EIO && ctrl.fullio_pm_incomplete);
    assert(writes == 1 && !stop_calls && !snapshot_calls && irq_op == 2 && clock_op == 2);
    assert(qcom_swrm_fullio_new_stream_ok(&ctrl) == -ENOTRECOVERABLE);
    for (int i = 0; i < 5; ++i) {
        // Reset stubs between independent failures, never on hardware.
        ctrl.fullio_pm_incomplete = false;
        ctrl.fullio_link_error = 0;
        ctrl.fullio_seen_attached = i == 1 || i == 2 ? 0x14 : 0;
        prep_result = i == 2 || i == 3 ? -ENODATA : 0;
        stop_result = i == 0 ? -ETIMEDOUT : -ENODATA;
        lose_broadcast = i == 4;
        int expected = i == 0 || i == 4 ? -ETIMEDOUT : i == 3 ? 0 : -ENODEV;
        writes = stop_calls = snapshot_calls = irq_op = clock_op = fifo_checks = 0;
        assert(swrm_runtime_suspend(&dev) == expected && ctrl.fullio_link_error == expected);
        assert(ctrl.fullio_pm_incomplete == !!expected);
        assert(writes == 1 && stop_calls == (i != 2) && snapshot_calls == stop_calls);
        assert(irq_op == !expected && clock_op == !expected);
        if (expected) {
            assert(swrm_runtime_suspend(&dev) == -EBUSY);
            assert(fifo_checks == 1 && writes == 1 && !irq_op && !clock_op);
        }
    }
    ctrl.fullio_pm_incomplete = lose_broadcast = false;
    ctrl.fullio_link_error = 0;
    irq_op = clock_op = 3;
    drained = ctrl.fullio_link_gate = false;
    prep_result = 0;
    stop_result = -EIO;
    assert(swrm_runtime_suspend(&dev) == -EIO && !ctrl.fullio_link_error && irq_op == 3 && clock_op == 3);
    clock_result = -EIO;
    assert(!swrm_runtime_resume(&dev) && clock_op == 4 && irq_op == 5 && !ctrl.fullio_link_error);

    ctrl.reg_read = read_frame;
    drained = wait_frame = true;
    for (int scenario = 0; scenario < 9; ++scenario) {
        ctrl.fullio_link_gate = scenario != 6;
        wait_frame = scenario != 7;
        ctrl.fullio_link_error = 0;
        ctrl.fullio_pm_incomplete = false;
        stop_calls = snapshot_calls = irq_op = clock_op = frame_reads = frame_sleeps = confirmed = 0;
        stop_at = scenario == 0 ? 1 : scenario == 1 ? 30 : 31;
        read_bad_at = scenario == 3 ? 2 : scenario == 4 || scenario == 8 ? 1 : 0;
        read_error = scenario == 3 ? -ENODEV : scenario == 8 ? -ENODATA : 1;
        stop_result = scenario == 5 ? -ENODATA : 0;
        int expected = scenario == 2 ? -ETIMEDOUT : scenario == 3 ? -ENODEV : scenario == 4 || scenario == 8 ? -EIO : 0;
        int reads[] = {1, 30, 30, 2, 1, 0, 0, 0, 1};
        assert(swrm_runtime_suspend(&dev) == expected && ctrl.fullio_link_error == expected);
        assert(ctrl.fullio_pm_incomplete == !!expected);
        assert(stop_calls == 1 && frame_reads == reads[scenario]);
        assert(frame_sleeps == (frame_reads ? frame_reads - 1 : 0));
        assert(confirmed == (scenario <= 1));
        assert(irq_op == !expected && clock_op == !expected);
    }
}
'''
with tempfile.TemporaryDirectory() as d:
    src = Path(d) / 'test.c'
    exe = src.with_suffix('')
    src.write_text(c)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('FullIO PM: distinguish unknown/empty from masked timeout or loss; unverified entry quarantines before gating or retry.')
