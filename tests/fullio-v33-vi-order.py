#!/usr/bin/env python3
"""Compile the actual Golden-v33 VI order helper against a mock regmap."""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

text = Path(sys.argv[1]).read_text()
helper = re.search(r'^static int wsa_macro_fullio_v33_vi_order\([^\{]+\{.*?^\}', text, re.M | re.S)
assert helper
lifecycle = text[text.index('static int wsa_macro_fullio_tx_clocks('):text.index('EXPORT_SYMBOL_GPL(wsa_macro_fullio_protclk)')]
pair = text[text.index('static int wsa_macro_fullio_start_pair('):text.index('/* Only a future card-local coordinator')]
assert 'end = first + 2' in pair
assert pair.index('CDC_WSA_TX_SPKR_PROT_NO_RESET') < pair.index('return ret ?: wsa_macro_fullio_v33_vi_order(wsa);')
first = lifecycle.index('ret = wsa_macro_fullio_start_pair(wsa, 0);')
recheck = lifecycle.index('ret = verify_ready(ctx);', first)
second = lifecycle.index('ret = wsa_macro_fullio_start_pair(wsa, 2);', recheck)
verify = lifecycle.index('ret = verify_ready(ctx);', second)
rollback = lifecycle.index('cleanup = wsa_macro_fullio_tx_update(wsa, 0, ARRAY_SIZE(fullio_tx_regs),', verify)
assert 'if (!ret)\n\t\t\treturn 0;' in lifecycle[verify:rollback]
assert 'CDC_WSA_TX_SPKR_PROT_RESET, true' in lifecycle[rollback:]

source = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#define CDC_WSA_TOP_TOP_CFG1 0x84
#define CDC_WSA_TX_SPKR_PROT_RESET_MASK 1
#define CDC_WSA_TX_SPKR_PROT_PCM_RATE_MASK 2
#define CDC_WSA_TX_SPKR_PROT_CLK_EN_MASK 4
#define CDC_WSA_TX_SPKR_PROT_RESET 1
#define CDC_WSA_TX_SPKR_PROT_NO_RESET 0
#define CDC_WSA_TX_SPKR_PROT_PCM_RATE_8K 0
#define CDC_WSA_TX_SPKR_PROT_CLK_ENABLE 4
struct wsa_macro { void *regmap; };
static int writes, reads, write_error, read_error, ignore_write;
static unsigned physical;
static int regmap_write(void *map, unsigned reg, unsigned value)
{
    assert(map && reg == CDC_WSA_TOP_TOP_CFG1 && value == 3);
    writes++;
    if (write_error) return write_error;
    if (!ignore_write) physical = value;
    return 0;
}
static int regmap_read_bypassed(void *map, unsigned reg, unsigned *value)
{
    assert(map && reg == CDC_WSA_TOP_TOP_CFG1);
    reads++;
    *value = physical;
    return read_error;
}
static unsigned step, expected_first, fail_step;
static int wsa_macro_fullio_tx_update(struct wsa_macro *wsa, unsigned first,
                                    unsigned end, unsigned mask, unsigned value, bool exhaustive)
{
    static const unsigned masks[] = {1, 2, 4, 1};
    static const unsigned values[] = {1, 0, 4, 0};
    assert(wsa && !exhaustive && first == expected_first && end == first + 2);
    assert(step < 4 && mask == masks[step] && value == values[step]);
    return ++step == fail_step ? -EIO : 0;
}
''' + helper.group() + '\n' + pair + r'''
int main(void)
{
    struct wsa_macro wsa = { &wsa };
    assert(!wsa_macro_fullio_v33_vi_order(&wsa) && physical == 3);
    assert(!wsa_macro_fullio_v33_vi_order(&wsa) && writes == 2 && reads == 2);
    write_error = -ENODEV;
    assert(wsa_macro_fullio_v33_vi_order(&wsa) == -ENODEV && reads == 2);
    write_error = 0;
    read_error = -ETIMEDOUT;
    assert(wsa_macro_fullio_v33_vi_order(&wsa) == -ETIMEDOUT);
    read_error = 0;
    ignore_write = 1;
    physical = 0;
    assert(wsa_macro_fullio_v33_vi_order(&wsa) == -EIO);
    int old_writes = writes;
    ignore_write = 0;
    assert(!wsa_macro_fullio_start_pair(&wsa, 0) && step == 4 && writes == old_writes + 1);
    expected_first = 2; step = 0;
    assert(!wsa_macro_fullio_start_pair(&wsa, 2) && step == 4 && writes == old_writes + 2);
    step = 0; fail_step = 2;
    assert(wsa_macro_fullio_start_pair(&wsa, 2) == -EIO && step == 2 && writes == old_writes + 2);
}
'''
with tempfile.TemporaryDirectory() as d:
    c = Path(d) / 'vi.c'
    exe = c.with_suffix('')
    c.write_text(source)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', c, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Golden-v33 VI producer: repeated writes and uncached readback required; failure enters clock rollback.')
