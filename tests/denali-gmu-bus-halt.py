#!/usr/bin/env python3
"""Exercise patched bus-halt and GMU stop code with fake registers only."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def function(src, name, symbol):
    text = (src / name).read_text()
    match = re.search(rf'^(?:static )?int {re.escape(symbol)}\([^\n]*\)\n\{{', text, re.M)
    if not match:
        raise ValueError(f'patched function {symbol} not found in {name}')
    return text[match.start():text.index('\n}', match.end()) + 2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('adreno_source', type=Path)
    parser.add_argument('cc')
    args = parser.parse_args()
    bus = '\n'.join(function(args.adreno_source, f'a{gen}xx_gpu.c',
                             f'a{gen}xx_bus_clear_pending_transactions') for gen in (6, 8))
    stop = '\n'.join(function(args.adreno_source, 'a6xx_gmu.c', symbol) for symbol in
                     ('a6xx_rpmh_stop', 'a6xx_gmu_force_off', 'a6xx_gmu_shutdown'))
    run(args.cc, PREFIX, bus, CASES)
    run(args.cc, STOP_PREFIX, stop, STOP_CASES)


def run(cc, prefix, code, cases):
    registers = sorted(set(re.findall(r'\bREG_A[68]XX_\w+', code)))
    regs = 'enum { ' + ', '.join(registers) + ' };'
    with tempfile.TemporaryDirectory() as temp:
        harness = Path(temp) / 'harness.c'
        exe = Path(temp) / 'harness'
        harness.write_text(prefix + regs + '\n' + code + '\n' + cases)
        subprocess.run([cc, '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(harness), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <errno.h>
#include <stddef.h>

#define VBIF_RESET_ACK_MASK 0xf0
#define VBIF_XIN_HALT_CTRL0_MASK 0xf
#define GPR0_GBIF_HALT_REQUEST 0x1e0
#define GBIF_CLIENT_HALT_MASK 1
#define GBIF_ARB_HALT_MASK 2
struct msm_gpu { void *pdev; };
struct adreno_gpu { struct msm_gpu base; bool holi, gbif; };
#define adreno_is_a619_holi(gpu) ((gpu)->holi)
#define a6xx_has_gbif(gpu) ((gpu)->gbif)
#define dev_err_ratelimited(...) ((void)0)
#define gpu_read(gpu, reg) ((void)(gpu), (void)(reg), ~0u)
static size_t poll, fail, n;
static struct { unsigned reg, value; } writes[8];
#define spin_until(condition) (++poll == fail || !(condition) ? -ETIMEDOUT : 0)
static void gpu_write(struct msm_gpu *gpu, unsigned reg, unsigned value)
{
    (void)gpu;
    assert(n < sizeof(writes) / sizeof(writes[0]));
    writes[n++] = (typeof(writes[0])){reg, value};
}
'''

CASES = r'''
static void check(int (*halt)(struct adreno_gpu *, bool), struct adreno_gpu gpu,
                  bool gx, unsigned gx_reg, size_t expected_polls)
{
    for (fail = 0; fail <= expected_polls; fail++) {
        poll = n = 0;
        assert(halt(&gpu, gx) == (fail ? -ETIMEDOUT : 0));
        assert(poll == expected_polls);
        size_t i = 0;
        if (gpu.holi) {
            assert(writes[i].reg == REG_A6XX_RBBM_GPR0_CNTL);
            assert(writes[i++].value == GPR0_GBIF_HALT_REQUEST);
        }
        if (!gpu.gbif) {
            assert(n == 2 && expected_polls == 1);
            assert(writes[0].reg == REG_A6XX_VBIF_XIN_HALT_CTRL0);
            assert(writes[0].value == VBIF_XIN_HALT_CTRL0_MASK);
            assert(writes[1].reg == REG_A6XX_VBIF_XIN_HALT_CTRL0);
            assert(writes[1].value == 0);
            continue;
        }
        if (gx) {
            assert(writes[i].reg == gx_reg);
            assert(writes[i++].value == 1);
        }
        assert(n == i + 3);
        assert(writes[i].reg == REG_A6XX_GBIF_HALT);
        assert(writes[i++].value == GBIF_CLIENT_HALT_MASK);
        assert(writes[i].reg == REG_A6XX_GBIF_HALT);
        assert(writes[i++].value == GBIF_ARB_HALT_MASK);
        assert(writes[i].reg == REG_A6XX_GBIF_HALT);
        assert(writes[i].value == 0);
    }
}

int main(void)
{
    struct adreno_gpu gbif = {.gbif = true};
    struct adreno_gpu holi = {.holi = true, .gbif = true};
    struct adreno_gpu vbif = {0};
    check(a6xx_bus_clear_pending_transactions, gbif, false, REG_A6XX_RBBM_GBIF_HALT, 2);
    check(a6xx_bus_clear_pending_transactions, gbif, true, REG_A6XX_RBBM_GBIF_HALT, 3);
    check(a6xx_bus_clear_pending_transactions, holi, true, REG_A6XX_RBBM_GBIF_HALT, 4);
    check(a6xx_bus_clear_pending_transactions, vbif, true, 0, 1);
    check(a8xx_bus_clear_pending_transactions, gbif, false, REG_A8XX_RBBM_GBIF_HALT, 2);
    check(a8xx_bus_clear_pending_transactions, gbif, true, REG_A8XX_RBBM_GBIF_HALT, 3);
    puts("GMU bus ACK error retention and register-write order: PASS");
    return 0;
}
'''


STOP_PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <errno.h>
#include <stdint.h>
#define BIT(n) (1u << (n))
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
#define DRM_DEV_ERROR(...) ((void)0)
#define wmb() ((void)0)
#define GMU_STATUS_FW_START 0
#define GMU_STATUS_PDC_SLEEP 1
#define GMU_STATUS_OOB_PERF_SET 2
#define GMU_OOB_GPU_SET 1
#define GMU_OOB_PERFCOUNTER_SET 2
#define A6XX_GPU_GMU_AO_GPU_CX_BUSY_STATUS_CXGXCPUBUSYIGNAHB 1u
typedef uint32_t u32;
struct msm_gpu { bool needs_hw_init; };
struct a6xx_gmu { unsigned long status; };
struct adreno_gpu;
struct adreno_funcs { int (*bus_halt)(struct adreno_gpu *, bool); };
struct adreno_gpu { struct msm_gpu base; const struct adreno_funcs *funcs; };
struct a6xx_gpu { struct adreno_gpu base; struct a6xx_gmu gmu; bool hung; };
static int bus[2], cx, rscc, slumber, idle, oob;
static unsigned calls, resets, cx_polls, rscc_polls;
static int halt(struct adreno_gpu *gpu, bool gx)
{
    (void)gpu; (void)gx;
    assert(calls < 2);
    return bus[calls++];
}
static bool test_and_clear_bit(unsigned bit, unsigned long *status)
{
    bool old = *status & BIT(bit);
    *status &= ~BIT(bit);
    return old;
}
#define set_bit(bit, status) (*(status) |= BIT(bit))
#define adreno_is_a840(gpu) ((void)(gpu), false)
#define adreno_is_a850_family(gpu) ((void)(gpu), false)
#define adreno_is_a8xx(gpu) ((void)(gpu), false)
#define gmu_write(gmu, reg, value) ((void)(gmu), (void)(reg), (void)(value))
#define gmu_poll_timeout(gmu, reg, val, cond, delay, limit) \
    ((void)(gmu), (void)(reg), (val) = 0, (void)(cond), ++cx_polls, cx)
#define gmu_poll_timeout_rscc(gmu, reg, val, cond, delay, limit) \
    ((void)(gmu), (void)(reg), (val) = ~0u, (void)(cond), ++rscc_polls, rscc)
#define a6xx_hfi_stop(gmu) ((void)(gmu))
#define a6xx_gmu_irq_disable(gmu) ((void)(gmu))
#define a6xx_sptprac_disable(gmu) ((void)(gmu))
#define a6xx_gemnoc_workaround(gmu) ((void)(gmu))
#define a6xx_gmu_rpmh_off(gmu) ((void)(gmu))
#define a6xx_gpu_sw_reset(gpu, state) ((void)(gpu), (void)(state), ++resets)
#define a6xx_gmu_set_oob(gmu, type) ((void)(gmu), (void)(type), oob)
#define a6xx_gmu_clear_oob(gmu, type) ((void)(gmu), (void)(type))
#define a6xx_gmu_wait_for_idle(gmu) ((void)(gmu), idle)
#define a6xx_gmu_notify_slumber(gmu) ((void)(gmu), slumber)
'''

STOP_CASES = r'''
static const struct adreno_funcs funcs = {.bus_halt = halt};
static struct a6xx_gpu init(void)
{
    bus[0] = bus[1] = cx = rscc = slumber = idle = oob = 0;
    calls = resets = cx_polls = rscc_polls = 0;
    return (struct a6xx_gpu){.base.funcs = &funcs,
                            .gmu.status = BIT(GMU_STATUS_FW_START)};
}

int main(void)
{
    struct a6xx_gpu gpu;
    for (unsigned failures = 0; failures < 8; failures++) {
        gpu = init();
        bus[0] = failures & 1 ? -EIO : 0;
        cx = failures & 2 ? -EBUSY : 0;
        rscc = failures & 4 ? -ETIMEDOUT : 0;
        assert(a6xx_gmu_shutdown(&gpu.gmu) == (bus[0] ?: (cx ?: rscc)));
        assert(calls == 1 && !resets && cx_polls == 1 && rscc_polls == 1);
    }
    for (unsigned failures = 0; failures < 4; failures++) {
        gpu = init();
        bus[0] = failures & 1 ? -EIO : 0;
        rscc = failures & 2 ? -ETIMEDOUT : 0;
        assert(a6xx_gmu_force_off(&gpu.gmu) == (bus[0] ?: rscc));
        assert(calls == 1 && resets == 1 && !cx_polls && rscc_polls == 1);
    }
    gpu = init();
    slumber = -EIO;
    bus[0] = -ETIMEDOUT;
    assert(a6xx_gmu_shutdown(&gpu.gmu) == -ETIMEDOUT);
    assert(calls == 2 && resets == 1 && !cx_polls && rscc_polls == 1);
    gpu = init();
    idle = -EIO;
    rscc = -ETIMEDOUT;
    assert(a6xx_gmu_shutdown(&gpu.gmu) == -ETIMEDOUT);
    assert(calls == 1 && resets == 1 && !cx_polls && rscc_polls == 1);
    gpu = init();
    gpu.gmu.status = 0;
    rscc = -ETIMEDOUT;
    assert(a6xx_gmu_force_off(&gpu.gmu) == -ENODATA);
    assert(!rscc_polls); /* No firmware-start bit; no RSCC ACK observed. */
    gpu = init();
    gpu.gmu.status = 0;
    assert(a6xx_gmu_shutdown(&gpu.gmu) == -ENODATA);
    assert(cx_polls == 1 && !rscc_polls);
    gpu = init();
    gpu.gmu.status = 0;
    bus[0] = -ETIMEDOUT;
    assert(a6xx_gmu_force_off(&gpu.gmu) == -ETIMEDOUT);
    assert(!rscc_polls);
    puts("GMU shutdown and fallback acknowledgement handling: PASS");
    return 0;
}
'''

if __name__ == '__main__':
    main()
