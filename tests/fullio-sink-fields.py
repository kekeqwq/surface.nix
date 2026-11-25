#!/usr/bin/env python3
"""Test actual Denali SIMPLE sink declarations offline."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

text = Path(sys.argv[1]).read_text()
helper = re.search(r'^static int wsa884x_fullio_init_sink_fields\([^;{]*\{.*?^\}', text, re.M | re.S).group()
code = r'''
#include <assert.h>
#include <string.h>
#include <stdbool.h>
#include <errno.h>
#define GFP_KERNEL 1
#define WSA884X_PORT_DAC 0
#define WSA884X_PORT_COMP 1
#define WSA884X_PORT_BOOST 2
#define SDW_DPN_SIMPLE_TRANSPORT_BLOCKCTRL3 1
#define SDW_DPN_SIMPLE_TRANSPORT_OFFSETCTRL2 8
struct sdw_dpn_prop { unsigned simple_transport_registers; };
struct sdw_slave { struct { struct sdw_dpn_prop *sink_dpn_prop; } prop; };
struct device { struct sdw_dpn_prop copy[4]; bool fail; };
struct wsa884x_priv { struct sdw_slave *slave; struct device *dev; bool feedback_enabled; };
static struct sdw_dpn_prop wsa884x_sink_dpn_prop[4];
static bool denali;
static bool of_machine_is_compatible(const char *name) { assert(!strcmp(name, "microsoft,denali")); return denali; }
static void *devm_kmemdup(struct device *dev, const void *src, unsigned len, int flags)
{
    assert(len == sizeof(dev->copy) && flags == GFP_KERNEL);
    return dev->fail ? 0 : memcpy(dev->copy, src, len);
}
''' + helper + r'''
int main(void)
{
    struct device left = {0}, right = {0};
    struct sdw_slave a = {0}, b = {0};
    struct wsa884x_priv amp = { &a, &left, true };
    assert(!wsa884x_fullio_init_sink_fields(&amp) && a.prop.sink_dpn_prop == wsa884x_sink_dpn_prop);
    denali = true; amp.feedback_enabled = false;
    assert(!wsa884x_fullio_init_sink_fields(&amp) && a.prop.sink_dpn_prop == wsa884x_sink_dpn_prop);
    amp.feedback_enabled = true; left.fail = true;
    assert(wsa884x_fullio_init_sink_fields(&amp) == -ENOMEM && a.prop.sink_dpn_prop == wsa884x_sink_dpn_prop);
    left.fail = false;
    assert(!wsa884x_fullio_init_sink_fields(&amp) && a.prop.sink_dpn_prop == left.copy);
    assert(left.copy[0].simple_transport_registers == 1 && left.copy[1].simple_transport_registers == 8);
    assert(left.copy[2].simple_transport_registers == 8 && !left.copy[3].simple_transport_registers);
    amp.slave = &b; amp.dev = &right;
    assert(!wsa884x_fullio_init_sink_fields(&amp) && b.prop.sink_dpn_prop == right.copy);
    assert(!memcmp(left.copy, right.copy, sizeof(left.copy)));
    for (unsigned i = 0; i < 4; i++) assert(!wsa884x_sink_dpn_prop[i].simple_transport_registers);
}
'''
with tempfile.TemporaryDirectory() as d:
    src = Path(d) / 'sink.c'
    exe = src.with_suffix('')
    src.write_text(code)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', src, '-o', exe], check=True)
    subprocess.run([exe], check=True)
print('Denali sink fields match Golden: per-codec DP1 BlockCtrl3, DP2/3 OffsetCtrl2; generic table untouched.')
