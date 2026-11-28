#!/usr/bin/env python3
"""Exercise the patched bus-halt code against fake registers, never hardware."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def function(src, name):
    text = (src / name).read_text()
    match = re.search(r'^int a[68]xx_bus_clear_pending_transactions\([^\n]*\)\n\{', text, re.M)
    if not match:
        raise ValueError(f'patched bus helper not found in {name}')
    return text[match.start():text.index('\n}', match.end()) + 2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('adreno_source', type=Path)
    parser.add_argument('cc')
    args = parser.parse_args()
    code = '\n'.join(function(args.adreno_source, f'a{gen}xx_gpu.c') for gen in (6, 8))
    registers = sorted(set(re.findall(r'\bREG_A[68]XX_\w+', code)))
    regs = 'enum { ' + ', '.join(registers) + ' };'
    with tempfile.TemporaryDirectory() as temp:
        harness = Path(temp) / 'harness.c'
        exe = Path(temp) / 'harness'
        harness.write_text(PREFIX + regs + '\n' + code + '\n' + CASES)
        subprocess.run([args.cc, '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(harness), '-o', str(exe)], check=True)
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


if __name__ == '__main__':
    main()
