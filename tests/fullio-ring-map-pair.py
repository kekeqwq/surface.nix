#!/usr/bin/env python3
"""Exercise the fixed PCM map sequence and FullIO push/pull guard offline."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])


def extract(path, name):
    return re.search(rf'^(?:static )?int {name}\([^{{]*\{{.*?^\}}',
                     path.read_text(), re.M | re.S).group()


source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <errno.h>
#define BUFFER_BYTES_MAX 8192
#define POS_BUFFER_BYTES 4096
#define READ_ONCE(x) (x)
#define dev_err(...) ((void)0)
#define dev_err_probe(d, r, ...) (r)
typedef uint64_t phys_addr_t;
typedef uint32_t u32;
struct device { int unused; };
struct q6apm_dai_data { int64_t sid; bool has_reserved_mem; size_t reserved_buf_size; };
struct snd_soc_component { struct device *dev; struct q6apm_dai_data *pdata; };
struct snd_pcm_substream { struct { phys_addr_t addr; } dma_buffer; };
struct audioreach_graph_info { u32 mem_map_handle, pos_buf_mem_map_handle; bool fullio; };
struct q6apm_graph { struct audioreach_graph_info *info; };
static int err_data, err_pos, data_calls, pos_calls, config_calls;
static phys_addr_t data_addr, pos_addr;
static struct q6apm_dai_data *snd_soc_component_get_drvdata(struct snd_soc_component *c)
{ return c->pdata; }
static int q6apm_map_memory_fixed_region(struct device *d, int id, phys_addr_t addr, size_t size)
{ assert(d && id == 0 && size == BUFFER_BYTES_MAX); data_calls++; data_addr = addr; return err_data; }
static int q6apm_map_pos_buffer(struct device *d, int id, phys_addr_t addr, size_t size)
{ assert(d && id == 0 && size == POS_BUFFER_BYTES); pos_calls++; pos_addr = addr; return err_pos; }
static bool audioreach_fullio_graph(struct audioreach_graph_info *i) { return i->fullio; }
static int audioreach_setup_push_pull(struct q6apm_graph *g, phys_addr_t a, phys_addr_t b,
                                     u32 d, u32 p, u32 n)
{ assert(a == data_addr && b == pos_addr && g->info->mem_map_handle == d &&
         g->info->pos_buf_mem_map_handle == p && n == 1024); config_calls++; return 0; }
''' + '\n' + extract(root / 'q6apm-dai.c', 'q6apm_dai_memory_map') + '\n' + extract(
    root / 'q6apm.c', 'q6apm_push_pull_config') + r'''
int main(void)
{
    struct device dev = {0};
    struct q6apm_dai_data pdata = { .sid = 1 };
    struct snd_soc_component comp = { &dev, &pdata };
    struct snd_pcm_substream sub = { {0x20000} };
    err_data = -ETIMEDOUT;
    assert(q6apm_dai_memory_map(&comp, &sub, 0, true) == -ETIMEDOUT && data_calls == 1 && !pos_calls);
    err_data = 0; err_pos = -EIO;
    assert(q6apm_dai_memory_map(&comp, &sub, 0, true) == -EIO && data_calls == 2 && pos_calls == 1);
    assert(data_addr == 0x100020000 && pos_addr == 0x100022000);
    assert(!q6apm_dai_memory_map(&comp, &sub, 0, false) && data_calls == 3 && pos_calls == 1);
    err_pos = 0;
    assert(!q6apm_dai_memory_map(&comp, &sub, 0, true) && data_calls == 4 && pos_calls == 2);
    struct audioreach_graph_info info = { .fullio = true };
    struct q6apm_graph g = { &info };
    for (unsigned state = 0; state < 4; state++) {
        info.mem_map_handle = state & 1 ? 23 : 0;
        info.pos_buf_mem_map_handle = state & 2 ? 45 : 0;
        assert(q6apm_push_pull_config(&g, data_addr, pos_addr, 1024) == (state == 3 ? 0 : -ENODATA));
        assert(config_calls == (state == 3));
    }
    info.fullio = false; info.mem_map_handle = 0;
    assert(!q6apm_push_pull_config(&g, data_addr, pos_addr, 1024) && config_calls == 2);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp) / 'maps.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('PCM map pair: first error survives, no position request after ring failure, FullIO requires both handles.')
