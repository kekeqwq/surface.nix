#!/usr/bin/env python3
"""Exercise the real token reply handler separately from the ring owner model."""
from pathlib import Path
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
allocate = text[text.index('static atomic_t fullio_oob_sequence'):text.index('struct q6apm_fullio_get {')]
reply = text[text.index('static bool q6apm_fullio_oob_reply('):
             text.index('static int q6apm_fullio_oob_rpc(')]
source = r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdatomic.h>
typedef uint32_t u32;
typedef uint8_t u8;
typedef atomic_int atomic_t;
#define Q6APM_FULLIO_OOB_TOKEN (1u << 31)
#define APM_CMD_RSP_GET_CFG 1
#define APM_CMD_GET_CFG 2
#define APM_CMD_RSP_SHARED_MEM_MAP_REGIONS 3
#define APM_CMD_SHARED_MEM_MAP_REGIONS 4
#define APM_CMD_SHARED_MEM_UNMAP_REGIONS 5
#define GPR_BASIC_RSP_RESULT 6
#define spin_lock_irqsave(lock, flags) ((void)(lock), (flags) = 0)
#define spin_unlock_irqrestore(lock, flags) ((void)(lock), (void)(flags))
#define dev_err_ratelimited(...) ((void)0)
#define dev_warn_ratelimited(dev, fmt, ...) ((void)p)
struct gpr_hdr { u32 token, opcode; };
struct gpr_resp_pkt { struct gpr_hdr hdr; const void *payload; int payload_size; };
struct apm_cmd_rsp_shared_mem_map_regions { u32 mem_map_handle; };
struct gpr_ibasic_rsp_result_t { u32 opcode, status; };
struct q6apm_fullio_get { u32 instance, param; };
struct q6apm {
    u32 fullio_oob_token, fullio_oob_op, fullio_oob_handle;
    int fullio_oob_status, fullio_oob_lock, fullio_oob_done;
    struct q6apm_fullio_get *fullio_get;
};
static void complete(int *n) { ++*n; }
static int q6apm_fullio_readback(const struct gpr_resp_pkt *d, struct q6apm_fullio_get *g)
{ (void)d; (void)g; assert(0); return -EINVAL; }
#define APM_MODULE_PARAM_DATA_SIZE 16
#define ATOMIC_INIT(n) (n)
#define atomic_read(p) atomic_load(p)
#define atomic_try_cmpxchg(p, x, n) atomic_compare_exchange_strong(p, x, n)
''' + allocate + reply + r'''
#define WORKERS 4
#define TOKENS 1024
static atomic_int seen[WORKERS * TOKENS];
static void *request_tokens(void *arg)
{
    (void)arg;
    for (int i = 0; i < TOKENS; i++) {
        u32 token;
        assert(!q6apm_fullio_next_token(&token) && (token & Q6APM_FULLIO_OOB_TOKEN));
        u32 n = token & ~Q6APM_FULLIO_OOB_TOKEN;
        assert(n >= 1 && n <= WORKERS * TOKENS);
        assert(!atomic_exchange(&seen[n - 1], 1));
    }
    return NULL;
}

int main(void)
{
    u32 first, second, final;
    assert(!q6apm_fullio_next_token(&first) && first == (Q6APM_FULLIO_OOB_TOKEN | 1));
    assert(!q6apm_fullio_next_token(&second) && second == first + 1);
    atomic_store(&fullio_oob_sequence, INT_MAX - 1);
    assert(!q6apm_fullio_next_token(&final) && final == UINT32_MAX);
    assert(q6apm_fullio_next_token(&final) == -EOVERFLOW && final == UINT32_MAX);
    struct q6apm a = { .fullio_oob_token = first, .fullio_oob_op = APM_CMD_SHARED_MEM_MAP_REGIONS };
    struct gpr_ibasic_rsp_result_t basic = {APM_CMD_SHARED_MEM_MAP_REGIONS, 0};
    struct apm_cmd_rsp_shared_mem_map_regions map = {42};
    struct gpr_resp_pkt r = {{1, GPR_BASIC_RSP_RESULT}, &basic, sizeof(basic)};
    assert(!q6apm_fullio_oob_reply(&a, &r) && !a.fullio_oob_done);
    r.hdr.token = first;
    assert(q6apm_fullio_oob_reply(&a, &r) && !a.fullio_oob_done);
    r = (struct gpr_resp_pkt){{first, APM_CMD_RSP_SHARED_MEM_MAP_REGIONS}, &map, sizeof(map)};
    assert(q6apm_fullio_oob_reply(&a, &r) && a.fullio_oob_done == 1);
    assert(a.fullio_oob_handle == 42 && a.fullio_oob_status == 0);
    /* A replacement APM starts with a new waiter but the same token allocator. */
    a = (struct q6apm){ .fullio_oob_token = second, .fullio_oob_op = APM_CMD_SHARED_MEM_UNMAP_REGIONS };
    assert(q6apm_fullio_oob_reply(&a, &r) && !a.fullio_oob_done); /* delayed duplicate MAP */
    r = (struct gpr_resp_pkt){{second, GPR_BASIC_RSP_RESULT}, &basic, sizeof(basic)};
    assert(q6apm_fullio_oob_reply(&a, &r) && !a.fullio_oob_done); /* wrong echoed opcode */
    basic.opcode = APM_CMD_SHARED_MEM_UNMAP_REGIONS;
    assert(q6apm_fullio_oob_reply(&a, &r) && a.fullio_oob_done == 1 && !a.fullio_oob_status);
    for (int i = 0; i < 2; i++) {
        a.fullio_oob_token = ++r.hdr.token;
        a.fullio_oob_op = APM_CMD_SHARED_MEM_MAP_REGIONS;
        map.mem_map_handle = i ? 42 : 0;
        r.hdr.opcode = APM_CMD_RSP_SHARED_MEM_MAP_REGIONS;
        r.payload = &map;
        r.payload_size = sizeof(map) - i;
        assert(q6apm_fullio_oob_reply(&a, &r) && a.fullio_oob_status == -EPROTO);
        assert(!a.fullio_oob_handle);
    }
    /* Independent run of the allocator from multiple simulated APMs. */
    atomic_store(&fullio_oob_sequence, 0);
    pthread_t workers[WORKERS];
    for (int i = 0; i < WORKERS; i++) assert(!pthread_create(&workers[i], NULL, request_tokens, NULL));
    for (int i = 0; i < WORKERS; i++) assert(!pthread_join(workers[i], NULL));
    assert(atomic_load(&fullio_oob_sequence) == WORKERS * TOKENS);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'replies.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-pthread', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Ring replies: token uniqueness under contention, no wrap, and stale/wrong MAP or UNMAP replies rejected.')
