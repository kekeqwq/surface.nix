#!/usr/bin/env python3
"""Compile the real push/pull encoder and verify the attached-ring wire payload."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
encoder = re.search(r'^struct gpr_pkt \*audioreach_alloc_push_pull_pkt\([^\{]*\{.*?^\}',
                    text, re.M | re.S).group()
source = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t phys_addr_t;
#define GPR_HDR_SIZE 24
#define APM_CMD_HDR_SIZE 16
#define APM_MODULE_PARAM_DATA_SIZE 16
#define APM_CMD_SET_CFG 0x01001006
#define PARAM_ID_SH_MEM_PULL_PUSH_MODE_CFG 0x0800100a
#define lower_32_bits(x) ((u32)(x))
#define upper_32_bits(x) ((u32)((x) >> 32))
#define IS_ERR(x) ((uintptr_t)(x) >= (uintptr_t)-4095)
#define ALIGN(n, a) (((n) + (a) - 1) & ~((a) - 1))
struct port { u32 id; };
struct q6apm_graph { u32 shm_iid; struct port *port; };
struct gpr_pkt { u32 words[32]; };
struct apm_module_param_data { u32 module_instance_id, param_id, param_size, error_code; };
struct param_id_sh_mem_pull_push_mode_cfg {
    u32 shared_circ_buf_addr_lsw, shared_circ_buf_addr_msw, shared_circ_buf_size, circ_buf_mem_map_handle;
    u32 shared_pos_buf_addr_lsw, shared_pos_buf_addr_msw, pos_buf_mem_map_handle;
};
static struct gpr_pkt pkt;
static int fail;
static struct gpr_pkt *audioreach_alloc_apm_cmd_pkt(int size, int opcode, int token)
{
    assert(size == 44 && opcode == APM_CMD_SET_CFG && !token);
    memset(&pkt, 0xa5, sizeof(pkt));
    return fail ? (void *)(intptr_t)-ENOMEM : &pkt;
}
static struct gpr_pkt *audioreach_alloc_cmd_pkt(int size, int opcode, int token, u32 src, u32 dst)
{
    assert(size == 48 && opcode == APM_CMD_SET_CFG && !token && src == 42 && dst == 0x4660);
    memset(&pkt, 0, sizeof(pkt));
    return fail ? (void *)(intptr_t)-ENOMEM : &pkt;
}
''' + encoder + r'''
int main(void)
{
    struct port port = {42};
    struct q6apm_graph graph = {0x4660, &port};
    struct gpr_pkt *r = audioreach_alloc_push_pull_pkt(&graph, 0x0145678000ULL, 0x0234567000ULL,
                                                       0x1234, 0x5678, 0x7200, false);
    const u32 expected[] = {0x4660, PARAM_ID_SH_MEM_PULL_PUSH_MODE_CFG, 28, 0,
                            0x45678000, 1, 0x7200, 0x1234, 0x34567000, 2, 0x5678};
    assert(r == &pkt && !memcmp(&pkt.words[10], expected, sizeof(expected)));
    assert(pkt.words[9] == 0xa5a5a5a5 && pkt.words[21] == 0xa5a5a5a5);
    r = audioreach_alloc_push_pull_pkt(&graph, 0x0145678000ULL, 0x0234567000ULL,
                                      0x1234, 0x5678, 0x7200, true);
    assert(r == &pkt && !memcmp(&pkt.words[10], expected, sizeof(expected)));
    assert(pkt.words[21] == 0); /* Direct packet adds exactly one padding word. */
    fail = 1;
    assert((intptr_t)audioreach_alloc_push_pull_pkt(&graph, 0, 0, 0, 0, 0, false) == -ENOMEM);
    assert((intptr_t)audioreach_alloc_push_pull_pkt(&graph, 0, 0, 0, 0, 0, true) == -ENOMEM);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'cfg.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Ring SET_CFG: exact addresses, sizes and handles in reused push/pull encoder.')
