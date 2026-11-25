#!/usr/bin/env python3
"""Exercise the real scoped timeout branch offline, never on SoundWire."""
import re
from pathlib import Path
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()

def func(name):
    return re.search(rf'^static (?:int|void) {name}\([^{{;]*\{{.*?^\}}', text, re.M | re.S).group()

code = r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define SDW_BROADCAST_DEV_NUM 15
#define SWR_BROADCAST_CMD_ID 15
#define SDW_CMD_OK 0
#define SDW_CMD_IGNORED 1
#define SDW_CMD_FAIL_OTHER 2
#define SWRM_REG_CMD_FIFO_WR_CMD 0
#define SWRM_VERSION_1_3_0 1
#define TIMEOUT_MS 100
#define msecs_to_jiffies(ms) (ms)
#define dev_err(...) ((void)0)
#define dev_warn_ratelimited(dev, fmt, reg, drained) ((void)(reg), (void)(drained), reports++)
#define cmpxchg(p, o, v) __sync_val_compare_and_swap(p, o, v)
struct qcom_swrm_ctrl {
    bool fullio_link_gate;
    int fullio_link_error, broadcast, version, reg_layout[1];
    u8 wcmd_id;
    void (*reg_write)(struct qcom_swrm_ctrl *, int, u32);
};
static int ack, reports, writes, waits;
static u32 swrm_get_packed_reg_val(u8 *id, u8 data, u8 addr, u16 reg)
{ return *id + data + addr + reg; }
static int swrm_wait_for_wr_fifo_avail(struct qcom_swrm_ctrl *p) { assert(p); return 0; }
static bool swrm_wait_for_wr_fifo_done(struct qcom_swrm_ctrl *p) { assert(p); return true; }
static void reinit_completion(int *c) { *c = 0; }
static unsigned wait_for_completion_timeout(int *c, int ms) { assert(!*c && ms == 100); waits++; return ack; }
static void usleep_range(int min, int max) { assert(min < max); }
static void fake_write(struct qcom_swrm_ctrl *p, int r, u32 val) { assert(p && r == 0 && val); writes++; }
''' + func('qcom_swrm_fullio_latch_link_error') + '\n' + func('qcom_swrm_cmd_fifo_wr_cmd') + r'''
int main(void)
{
    struct qcom_swrm_ctrl ctrl = { .fullio_link_gate = true, .reg_write = fake_write };
    assert(qcom_swrm_cmd_fifo_wr_cmd(&ctrl, 1, 15, 1) == SDW_CMD_IGNORED);
    assert(ctrl.fullio_link_error == -ETIMEDOUT && reports == 1 && writes == 1 && waits == 1);
    ack = 1;
    assert(qcom_swrm_cmd_fifo_wr_cmd(&ctrl, 1, 15, 2) == SDW_CMD_OK);
    assert(ctrl.fullio_link_error == -ETIMEDOUT && reports == 1 && writes == 2 && waits == 2);
    assert(qcom_swrm_cmd_fifo_wr_cmd(&ctrl, 1, 2, 3) == SDW_CMD_OK && writes == 3 && waits == 2);
    ctrl.fullio_link_gate = false; ctrl.fullio_link_error = 0; ack = 0;
    assert(qcom_swrm_cmd_fifo_wr_cmd(&ctrl, 1, 15, 1) == SDW_CMD_IGNORED);
    assert(!ctrl.fullio_link_error && reports == 1 && writes == 4 && waits == 3);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'bcast.c'
    exe = path.with_suffix('')
    path.write_text(code)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', path, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Broadcast timeout: opted-in lock sticks after success; cleanup commands and stock return codes unchanged.')
