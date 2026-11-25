#!/usr/bin/env python3
"""Offline test of the patched slot observer and real sticky admission gate."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()


def extract(name):
    return re.search(rf'^static (?:void|int) {name}\([^\{{]+\{{.*?^\}}', text, re.M | re.S).group()


source = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdint.h>
typedef uint32_t u32;
#define SDW_MAX_DEVICES 11
#define SWRM_MCP_SLV_STATUS_SZ 2
#define SWRM_MCP_SLV_STATUS_MASK 3
#define SDW_SLAVE_UNATTACHED 0
#define SDW_SLAVE_ATTACHED 1
#define SDW_SLAVE_ALERT 2
#define SWRM_MCP_SLV_STATUS 0x18
#define SDW_CMD_OK 0
#define READ_ONCE(x) (x)
#define dev_err(...) ((void)0)
#define cmpxchg(p, o, n) __sync_val_compare_and_swap(p, o, n)
#define set_bit(i, p) (*(p) |= 1UL << (i))
#define test_bit(i, p) (!!(*(p) & (1UL << (i))))
struct qcom_swrm_ctrl {
    bool fullio_link_gate;
    int fullio_link_error;
    unsigned long fullio_seen_attached;
    int (*reg_read)(struct qcom_swrm_ctrl *, int, u32 *);
};
static int count, read_result;
static u32 reported;
static int read_slots(struct qcom_swrm_ctrl *ctrl, int reg, u32 *val)
{
    assert(ctrl && reg == SWRM_MCP_SLV_STATUS);
    count++;
    *val = reported;
    return read_result;
}
''' + '\n'.join(extract(n) for n in ('qcom_swrm_fullio_latch_link_error',
                                     'qcom_swrm_fullio_new_stream_ok',
                                     'qcom_swrm_fullio_observe_slots',
                                     'qcom_swrm_fullio_check_resumed_slots')) + r'''
int main(void)
{
    struct qcom_swrm_ctrl ctrl = { .fullio_link_gate = true }, other = {0};
    qcom_swrm_fullio_observe_slots(&ctrl, 0);
    assert(!ctrl.fullio_seen_attached && !qcom_swrm_fullio_new_stream_ok(&ctrl));
    qcom_swrm_fullio_observe_slots(&ctrl, 0x14);
    assert(ctrl.fullio_seen_attached == 6 && !qcom_swrm_fullio_new_stream_ok(&ctrl));
    qcom_swrm_fullio_observe_slots(&ctrl, 0x18); /* ALERT on device 1 */
    assert(!qcom_swrm_fullio_new_stream_ok(&ctrl));
    qcom_swrm_fullio_observe_slots(&ctrl, 0x10); /* device 1 unattached */
    assert(ctrl.fullio_link_error == -ENODEV && qcom_swrm_fullio_new_stream_ok(&ctrl) == -ENOTRECOVERABLE);
    qcom_swrm_fullio_observe_slots(&ctrl, 0x14);
    qcom_swrm_fullio_latch_link_error(&ctrl, -EIO);
    assert(ctrl.fullio_link_error == -ENODEV && qcom_swrm_fullio_new_stream_ok(&ctrl) == -ENOTRECOVERABLE);
    qcom_swrm_fullio_observe_slots(&other, 0x14);
    qcom_swrm_fullio_observe_slots(&other, 0);
    assert(!other.fullio_seen_attached && !qcom_swrm_fullio_new_stream_ok(&other));
    qcom_swrm_fullio_check_resumed_slots(&other); /* no register access */
    assert(!count);
    struct qcom_swrm_ctrl resumed = { .fullio_link_gate = true, .reg_read = read_slots };
    reported = 0x14;
    qcom_swrm_fullio_check_resumed_slots(&resumed);
    assert(count == 1 && !qcom_swrm_fullio_new_stream_ok(&resumed));
    reported = 0;
    qcom_swrm_fullio_check_resumed_slots(&resumed);
    assert(count == 2 && resumed.fullio_link_error == -ENODEV);
    struct qcom_swrm_ctrl unreadable = { .fullio_link_gate = true, .reg_read = read_slots };
    read_result = 1;
    qcom_swrm_fullio_check_resumed_slots(&unreadable);
    assert(count == 3 && unreadable.fullio_link_error == -EIO);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / 'slots.c'
    exe = src.with_suffix('')
    src.write_text(source)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Detach model: startup/ALERT allowed; loss or unreadable slots after resume fail closed, unmarked controller untouched.')
