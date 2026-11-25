#!/usr/bin/env python3
"""Run the composed clock-stop resume branch against offline PM and slot stubs."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
start = text.index('\t\tint ee_ret = 0, start_ret, mask_ret = 0;')
end = text.index('\n}\n', start)
branch = text[start:end].replace('\n\t}\n\n\treturn 0;', '\n\n\treturn 0;')
suspend = text[text.index('static int __maybe_unused swrm_runtime_suspend('):]
assert suspend.index('if (READ_ONCE(ctrl->fullio_pm_incomplete))\n\t\treturn -EBUSY;') < suspend.index('swrm_wait_for_wr_fifo_done')
slot_helpers = '\n'.join(
    re.search(rf'^static void {name}\([^{{]+\{{.*?^\}}', text, re.M | re.S)[0]
    for name in ('qcom_swrm_fullio_latch_link_error', 'qcom_swrm_fullio_observe_slots',
                 'qcom_swrm_fullio_check_resumed_slots')
)
xfer = re.search(r'^static enum sdw_command_response qcom_swrm_xfer_msg\([^\{]+\{.*?^\}',
                 text, re.M | re.S)[0]
code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
typedef unsigned int u32;
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x, v) ((x) = (v))
#define SDW_MAX_DEVICES 11
#define SWRM_MCP_SLV_STATUS_SZ 2
#define SWRM_MCP_SLV_STATUS_MASK 3
#define SWRM_MCP_SLV_STATUS 0x18
#define SDW_SLAVE_UNATTACHED 0
#define SDW_SLAVE_ATTACHED 1
#define SDW_CMD_OK 0
#define set_bit(i, p) (*(p) |= 1UL << (i))
#define test_bit(i, p) (!!(*(p) & (1UL << (i))))
#define cmpxchg(p, o, n) __sync_val_compare_and_swap(p, o, n)
#define SWRM_VERSION_1_7_0 7
#define SWRM_VERSION_2_0_0 8
#define SWRM_LINK_MANAGER_EE 0
#define SWRM_MCP_BUS_CTRL 1
#define SWRM_MCP_BUS_CLK_START 2
#define SWRM_V2_0_CLK_CTRL 1
#define SWRM_EE_CPU 1
#define SWRM_V2_REG_EE_STRIDE 4
#define SWRM_V2_0_CLK_CTRL_CLK_START 1
#define SWRM_INTERRUPT_STATUS_MASTER_CLASH_DET 8
#define SWRM_REG_INTERRUPT_CLEAR 0
#define SWRM_REG_INTERRUPT_MASK_ADDR 1
#define SWRM_REG_INTERRUPT_CPU_EN 2
struct qcom_swrm_ctrl {
    bool fullio_link_gate, fullio_pm_incomplete;
    int fullio_link_error, audio_cgcr, version, ee, intr_mask, bus, dev;
    int reg_layout[3];
    int page1_cache[12], page2_cache[12];
    unsigned long fullio_seen_attached;
    int (*reg_write)(struct qcom_swrm_ctrl *, int, int);
    int (*reg_read)(struct qcom_swrm_ctrl *, int, u32 *);
};
static int fail, step, writes, slot_reads, exits;
static int reset_control_reset(int r) { assert(!r && !step++); return fail == 1 ? -EIO : 0; }
static int write_reg(struct qcom_swrm_ctrl *c, int reg, int value)
{ assert(c && value >= 0 && reg == writes++); return fail == ++step ? 1 : 0; }
static void swrm_fullio_pm_snapshot(struct qcom_swrm_ctrl *c, const char *s, int r)
{ assert(c && s); (void)r; }
static void dev_err(int dev, const char *s, ...) { assert(!dev && s); }
static void usleep_range(int a, int b) { assert(a == 100 && b == 105); }
static bool swrm_wait_for_frame_gen_enabled(struct qcom_swrm_ctrl *c) { assert(c); return fail != ++step; }
static int read_slot_reg(struct qcom_swrm_ctrl *ctrl, int reg, u32 *value)
{
    assert(ctrl && reg == SWRM_MCP_SLV_STATUS);
    unsigned int count = ++slot_reads;
    *value = ((fail == 7 && count == 1) || (fail == 8 && count == 2)) ? 0 : 0x14;
    return (fail == 10 && count == 1) || (fail == 11 && count == 2) ? 1 : SDW_CMD_OK;
}
static int sdw_bus_exit_clk_stop(int *bus) { assert(bus); exits++; return fail == 9 ? -ETIMEDOUT : 0; }
enum sdw_command_response { SDW_CMD_FAIL_OTHER = 1, SDW_CMD_IGNORED };
#define QCOM_SWRM_MAX_RD_LEN 2
#define SDW_SCP_ADDRPAGE1 10
#define SDW_SCP_ADDRPAGE2 11
#define SDW_MSG_FLAG_READ 1
#define SDW_MSG_FLAG_WRITE 2
#define min(a, b) ((a) < (b) ? (a) : (b))
struct sdw_bus { struct qcom_swrm_ctrl *ctrl; };
struct sdw_msg { int page, dev_num, addr_page1, addr_page2, flags, len, addr; unsigned char *buf; };
#define to_qcom_sdw(bus) ((bus)->ctrl)
static int fifo_reads, fifo_writes;
static int qcom_swrm_cmd_fifo_rd_cmd(struct qcom_swrm_ctrl *c, int dev, int addr,
                                    int len, unsigned char *data)
{ assert(c && dev == 2 && addr == 32 && len == 1); fifo_reads++; *data = 7; return 0; }
static int qcom_swrm_cmd_fifo_wr_cmd(struct qcom_swrm_ctrl *c, int data, int dev, int addr)
{ assert(c && data >= 0 && dev == 2 && (addr == 10 || addr == 11 || addr == 32)); fifo_writes++; return 0; }
''' + slot_helpers + '\n' + xfer + r'''
static int resume(struct qcom_swrm_ctrl *ctrl)
{
    int ret;
''' + branch + r'''
}
int main(void)
{
    for (fail = 0; fail <= 11; fail++) {
        struct qcom_swrm_ctrl c = {.fullio_link_gate = true, .version = 8, .ee = 1,
            .reg_layout = {2, -1, 3}, .reg_write = write_reg, .reg_read = read_slot_reg};
        step = writes = slot_reads = exits = 0;
        qcom_swrm_fullio_observe_slots(&c, 0x14);
        assert(!resume(&c));
        assert(c.fullio_pm_incomplete == !!fail);
        assert(exits == (fail == 0 || fail == 8 || fail == 9 || fail == 11));
        assert(c.fullio_link_error == (fail == 0 ? 0 : fail == 6 || fail == 9 ? -ETIMEDOUT :
                                       fail == 7 || fail == 8 ? -ENODEV : -EIO));
        if (fail >= 1 && fail <= 5) assert(writes == fail - 1 && !slot_reads);
        if (fail == 7 || fail == 9 || fail == 10) assert(slot_reads == 1);
        if (fail == 0 || fail == 8 || fail == 11) assert(slot_reads == 2);
        struct sdw_bus bus = {&c};
        unsigned char data = 11;
        struct sdw_msg msg = {.page = 1, .dev_num = 2, .addr_page1 = 2, .addr_page2 = 3,
                              .flags = SDW_MSG_FLAG_READ, .len = 1, .addr = 32, .buf = &data};
        fifo_reads = fifo_writes = 0;
        assert(qcom_swrm_xfer_msg(&bus, &msg) == (fail ? SDW_CMD_FAIL_OTHER : SDW_CMD_OK));
        msg.flags = SDW_MSG_FLAG_WRITE;
        assert(qcom_swrm_xfer_msg(&bus, &msg) == (fail ? SDW_CMD_FAIL_OTHER : SDW_CMD_OK));
        assert(fifo_reads == !fail && fifo_writes == (fail ? 0 : 3));
        assert(c.page1_cache[2] == (fail ? 0 : 2) && c.page2_cache[2] == (fail ? 0 : 3));
        assert(data == (fail ? 11 : 7));
    }
    fail = 0; step = writes = slot_reads = exits = 0;
    struct qcom_swrm_ctrl c = {.fullio_link_gate = true, .fullio_link_error = -EPROTO,
        .version = 8, .ee = 1, .reg_layout = {2, -1, 3}, .reg_write = write_reg, .reg_read = read_slot_reg};
    assert(!resume(&c) && c.fullio_link_error == -EPROTO && c.fullio_pm_incomplete && !exits);
}
'''
with tempfile.TemporaryDirectory() as folder:
    src = Path(folder) / 'resume.c'
    exe = src.with_suffix('')
    src.write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('FullIO clock resume: reject incomplete phases, keep first errno and PM ownership, and prevent another clock-stop or slave-message FIFO access.')
