#!/usr/bin/env python3
"""Exercise the dormant driver's actual allocation/rollback/quarantine code."""
from pathlib import Path
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
owner = text[text.index('enum q6apm_fullio_pull_state {'):
             text.index('/* Attach only to the never-started audit graph')]
source = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint64_t dma_addr_t, u64;
typedef uint32_t u32;
typedef int atomic_t;
#define ATOMIC_INIT(n) (n)
#define GFP_KERNEL 0
#define THIS_MODULE 1
#define SZ_4K 4096
#define SZ_512K (512 * 1024)
#define IS_ALIGNED(n, a) (!((n) & ((a)-1)))
#define upper_32_bits(n) ((n) >> 32)
#define kzalloc_obj(o) calloc(1, sizeof(o))
#define kfree(p) free(p)
#define WRITE_ONCE(a, b) ((a) = (b))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define __maybe_unused
#define dev_err(d, ...) assert(d)
struct device { int references; };
struct snd_dma_buffer { size_t bytes; };
struct q6apm { int unused; };
struct q6apm_fullio_oob_region { u64 dsp_addr; u32 size, handle; bool poisoned; };
static int mapped, unmapped, frees, module_refs, fail_map, fail_unmap;
static unsigned unmap_order;
static bool alias;
static dma_addr_t base = 0x40000;
static bool of_machine_is_compatible(const char *n) { return !strcmp(n, "microsoft,denali"); }
static int atomic_cmpxchg(int *a, int old, int new) { int before = *a; if (before == old) *a = new; return before; }
static void atomic_set(int *a, int n) { *a = n; }
static bool try_module_get(int m) { assert(m); module_refs++; return true; }
static void module_put(int m) { assert(m && module_refs == 1); module_refs--; }
static struct device *get_device(struct device *dev) { dev->references++; return dev; }
static void put_device(struct device *dev) { assert(dev->references == 1); dev->references--; }
static void *dma_alloc_coherent(struct device *d, size_t b, dma_addr_t *a, int flags)
{ assert(d && !flags); *a = base; void *p = malloc(b); assert(p); memset(p, 0xcc, b); return p; }
static void dma_free_coherent(struct device *d, size_t b, void *p, dma_addr_t a)
{ assert(d && ((b == SZ_512K + SZ_4K && a == base) ||
               (b == SZ_4K && a == base + SZ_512K + SZ_4K))); free(p); frees++; }
static void dma_wmb(void) {}
static int q6apm_fullio_oob_map_region(struct q6apm *a, struct q6apm_fullio_oob_region *r, unsigned max, u32 flag)
{
    assert(a && r->size == max && (flag == 0 || flag == 2));
    assert(r->dsp_addr == (UINT64_C(0x100000000) | (base + (flag ? SZ_512K : 0))));
    if (++mapped == fail_map) { r->poisoned = true; return -ETIMEDOUT; }
    r->handle = flag && !alias ? 2 : 1; return 0;
}
static int q6apm_fullio_oob_unmap(struct q6apm *a, struct q6apm_fullio_oob_region *r)
{
    assert(a && !r->poisoned && r->handle);
    unmap_order = unmap_order * 10 + r->handle;
    unmapped++;
    if ((int)r->handle == fail_unmap) { r->poisoned = true; return -ETIMEDOUT; }
    r->handle = 0; return 0;
}
''' + owner + r'''
int main(int argc, char **argv)
{
    assert(argc == 2);
    int mode = atoi(argv[1]);
    struct q6apm apm = {0}; struct device dev = {0};
    fail_map = mode == 1 ? 1 : mode == 2 ? 2 : 0;
    fail_unmap = mode == 3 ? 2 : mode == 4 ? 1 : mode == 9 ? 3 : 0;
    alias = mode == 6;
    if (mode == 7) base = UINT64_C(0x100000000);
    struct q6apm_fullio_ring *r = q6apm_fullio_ring_alloc(&apm, &dev, SZ_512K, 1);
    if (mode == 7) {
        assert(r == ERR_PTR(-ERANGE) && !mapped && frees == 1 && !module_refs && !dev.references);
        return 0;
    }
    if (mode == 1 || mode == 2 || mode == 6) {
        assert(r == ERR_PTR(-ENOTRECOVERABLE));
        assert(mapped == (mode == 1 ? 1 : 2));
        assert(unmapped == (mode == 2 ? 1 : 0));
    } else {
        assert(r && mapped == 2 && r->data.handle == 1 && r->pos.handle == 2);
        for (size_t i = 0; i < r->bytes; i++) assert(!((unsigned char *)r->cpu)[i]);
        assert(q6apm_fullio_ring_alloc(&apm, &dev, SZ_512K, 1) == ERR_PTR(-EBUSY));
        if (mode == 8 || mode == 9) {
            r->gainstep_cpu = malloc(SZ_4K);
            assert(r->gainstep_cpu);
            r->gainstep_dma = base + SZ_512K + SZ_4K;
            r->gainstep.handle = 3;
        }
        assert(q6apm_fullio_ring_drop(&apm, &r, mode != 5) ==
               (mode && mode != 8 ? -ENOTRECOVERABLE : 0));
        assert(!r && !q6apm_fullio_ring_drop(&apm, &r, true));
        assert(unmap_order == (mode == 5 ? 0 : mode >= 8 ? 321 : 21));
    }
    if (mode && mode != 8) {
        assert(fullio_ring_quarantine && !frees && module_refs == 1 && dev.references == 1);
        assert(q6apm_fullio_ring_alloc(&apm, &dev, SZ_512K, 1) == ERR_PTR(-EBUSY));
    } else {
        assert(!fullio_ring_quarantine && frees == (mode == 8 ? 2 : 1) &&
               !module_refs && !dev.references);
    }
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'owner.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    for mode in range(10):
        subprocess.run([exe, str(mode)], check=True)
print('Ring owner: confirmed unmaps free; ambiguous map/STOP/unmap retains one allocation and forbids reuse.')
