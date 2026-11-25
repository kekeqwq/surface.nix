#!/usr/bin/env python3
"""Validate the pinned codec cold transaction and fail-closed attachment."""
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
table = re.search(r'^static const struct reg_sequence wsa884x_fullio_cold_init\[\] = \{.*?^\};', text, re.M | re.S)[0]
rows = re.findall(r'\{\s*(WSA884X_\w+),\s*(0x[0-9a-f]+)\s*\}', table)
assert len(rows) == 63
assert hashlib.sha256('\n'.join(' '.join(row) for row in rows).encode()).hexdigest() == (
    '298c3639a79dea2ff8445c3a1fe634f2a52986431763d6f300ce871cddc8ca4b'
)
assert all(reg != 'WSA884X_PA_FSM_EN' for reg, _ in rows)
regs = sorted({reg for reg, _ in rows}) + ['WSA884X_VPHX_SYS_EN_STATUS', 'WSA884X_PA_FSM_EN']
assert all(re.search(rf'^#define {reg}\b', text, re.M) for reg in regs)
# The DT CPS sidechain is board wiring: preset at probe and immune to
# userspace/alsa-restore disable (reference set_swr_port semantics).
probe_at = text.index('wsa884x->feedback_enabled = true;')
assert 'wsa884x->port_enable[WSA884X_PORT_CPS] = true;' in text[probe_at:probe_at + 900]
setter = re.search(r'^static int wsa884x_set_swr_port\(.*?^}', text, re.M | re.S)[0]
assert (setter.index('WSA884X_PORT_CPS && wsa884x->feedback_enabled')
        < setter.index('if (ucontrol->value.integer.value[0])'))
assert setter.count('wsa884x->port_enable[portidx] = true;') == 2


def function(name):
    return re.search(rf'^static int {name}\(.*?^\}}', text, re.M | re.S)[0]


status = function('wsa884x_update_status')
# Re-attach re-runs the reference cold table; only a failed regcache/cold
# table latches unrecoverable.
assert (status.index('regcache_sync')
        < status.index('wsa884x->fullio_cold_failed = true')
        < status.index('wsa884x_fullio_cold_start') < status.index('wsa884x_init(wsa884x)'))
assert function('wsa884x_hw_params').index('!READ_ONCE(wsa884x->hw_init)') < function('wsa884x_hw_params').index('sdw_stream_add_slave')
assert '!mute && wsa884x->feedback_enabled' in function('wsa884x_mute_stream')
source = r'''
#include <stdbool.h>
#include <errno.h>
#include <assert.h>
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define WRITE_ONCE(a, b) ((a) = (b))
#define WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK 1
struct reg_sequence { unsigned int reg, def; };
struct wsa884x_priv { void *regmap; int dev; bool fullio_cold_failed, hw_init; };
#define dev_warn(d, ...) assert(d)
''' + 'enum { ' + ', '.join(regs) + ' };\n' + table + r'''
static unsigned int reads, writes, supply, pre_pa, post_pa, failed_write;
static int read_error_at;
static int regmap_read_bypassed(void *map, unsigned int reg, unsigned int *val)
{
    assert(map && reads <= 2);
    ++reads;
    assert(reg == (reads == 1 ? WSA884X_VPHX_SYS_EN_STATUS : WSA884X_PA_FSM_EN));
    if ((int)reads == read_error_at)
        return -ETIMEDOUT;
    *val = reads == 1 ? supply : reads == 2 ? pre_pa : post_pa;
    return 0;
}
static int regmap_write(void *map, unsigned int reg, unsigned int value)
{
    assert(map && reads == 2 && writes < ARRAY_SIZE(wsa884x_fullio_cold_init));
    assert(reg != WSA884X_PA_FSM_EN && reg == wsa884x_fullio_cold_init[writes].reg);
    assert(value == wsa884x_fullio_cold_init[writes].def);
    return ++writes == failed_write ? -EIO : 0;
}
''' + function('wsa884x_fullio_cold_start') + r'''
static void run(int result, unsigned int read_count, unsigned int write_count, bool reattach_ok)
{
    struct wsa884x_priv amp = { .regmap = &amp, .dev = 1 };
    reads = writes = 0;
    assert(wsa884x_fullio_cold_start(&amp) == result);
    assert(amp.hw_init == !result);
    assert(reads == read_count && writes == write_count);
    amp.hw_init = false; /* SoundWire detach */
    reads = writes = 0;
    if (reattach_ok) {
        /* Reference lifecycle: re-run the cold table on a clean re-attach. */
        assert(wsa884x_fullio_cold_start(&amp) == result);
        assert(amp.hw_init == !result && reads == read_count && writes == write_count);
    } else {
        /* A failed table is never retried. */
        assert(wsa884x_fullio_cold_start(&amp) == -ENOTRECOVERABLE);
        assert(!amp.hw_init && !reads && !writes);
    }
}
int main(void)
{
    /* A VPHX mismatch is diagnostic only; the reference still applies the
       2S table (observed at SoundWire re-attach when the status reads late). */
    supply = 1;
    run(0, 3, 63, true);
    supply = 2; pre_pa = 1;
    run(-EBUSY, 2, 0, true);           /* PA already on: refuse before writes */
    pre_pa = 0;
    for (failed_write = 1; failed_write <= 63; ++failed_write)
        run(-EIO, 2, failed_write, false);   /* partial table: never retry */
    failed_write = 0;
    read_error_at = 1;
    run(0, 3, 63, true);               /* VPHX read failure: warn and apply */
    read_error_at = 2;
    run(-ETIMEDOUT, 2, 0, true);       /* PA state unreadable: no writes */
    read_error_at = 3;
    run(-ETIMEDOUT, 3, 63, false);     /* post-write readback failed: latch */
    read_error_at = 0; post_pa = 1;
    run(-EIO, 3, 63, false);
    post_pa = 0;
    run(0, 3, 63, true);               /* success re-inits on every attach */
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src = Path(tmp) / 'cold.c'
    src.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', src, '-o', src.with_suffix('')], check=True)
    subprocess.run([src.with_suffix('')], check=True)
print('Golden 63-write cold sequence matches; VPHX diagnostic-only per reference, PA pre-write gate, failed tables never retried.')
