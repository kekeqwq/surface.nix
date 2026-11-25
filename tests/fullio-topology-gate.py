#!/usr/bin/env python3
"""Check the native reference-render gates in the composed kernel sources."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

topology = Path(sys.argv[1]).read_text()
machine = Path(sys.argv[2]).read_text()

# The topology loader accepts FullIO records only on explicitly selected
# Denali fixtures (silent audit or native protected render).
validate = re.search(r'^static int audioreach_validate_private\(.*?^\}', topology, re.M | re.S)[0]
assert validate.rstrip().endswith('return fullio && !muted_fixture ? -EOPNOTSUPP : 0;\n}')
assert 'audioreach_validate_fullio_links' in topology

ready = re.search(r'^static int audioreach_widget_ready\(.*?^\}', topology, re.M | re.S)[0]
gate = ready[:ready.index('int ret = audioreach_validate_private')]
assert gate.index('of_machine_is_compatible("microsoft,denali")') < gate.index('microsoft,denali-fullio-muted-test') \
    < gate.index('microsoft,denali-fullio-reference-render')
assert 'muted-test' in gate and 'reference-render' in gate
assert 'audioreach_validate_private(&tplg_w->priv, muted_fixture)' in ready

# The machine keeps the upstream PA damage cap unless the protected route
# is explicitly selected; the RX digital ceiling stays unconditional.
init = re.search(r'^static int x1e80100_snd_init\(.*?^\}', machine, re.M | re.S)[0]
assert init.index('WSA2 WSA_RX1 Digital Volume", 81') < init.index('reference-render')
assert re.search(r'if \(!of_machine_is_compatible\("microsoft,denali"\) \|\|\s*'
                 r'!of_property_read_bool\(card->dev->of_node,\s*'
                 r'"microsoft,denali-fullio-reference-render"\)\) \{', init)
branch = init[init.index('if (!of_machine_is_compatible("microsoft,denali")'):]
branch = branch[:branch.index('\n\t\t}')]
assert branch.count('snd_soc_limit_volume(card, "Spkr') == 2
assert 'SpkrLeft PA Volume", 6' in branch and 'SpkrRight PA Volume", 6' in branch
assert 'Digital Volume' not in branch

source = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <string.h>
static bool denali, muted, native;
static bool of_machine_is_compatible(const char *name)
{ assert(!strcmp(name, "microsoft,denali")); return denali; }
static bool of_property_read_bool(const void *node, const char *name)
{
    assert(node);
    if (!strcmp(name, "microsoft,denali-fullio-muted-test")) return muted;
    assert(!strcmp(name, "microsoft,denali-fullio-reference-render"));
    return native;
}
static int accept(bool fullio, bool fixture) { return fullio && !fixture ? -EOPNOTSUPP : 0; }
static bool fixture_gate(void)
{
    return of_machine_is_compatible("microsoft,denali") &&
        (of_property_read_bool((void *)1, "microsoft,denali-fullio-muted-test") ||
         of_property_read_bool((void *)1, "microsoft,denali-fullio-reference-render"));
}
static bool pa_cap(void)
{
    return !of_machine_is_compatible("microsoft,denali") ||
        !of_property_read_bool((void *)1, "microsoft,denali-fullio-reference-render");
}
int main(void)
{
    for (int d = 0; d <= 1; ++d)
        for (int m = 0; m <= 1; ++m)
            for (int n = 0; n <= 1; ++n) {
                denali = d; muted = m; native = n;
                bool fixture = fixture_gate();
                assert(accept(false, fixture) == 0);
                assert(accept(true, fixture) == ((denali && (muted || native)) ? 0 : -EOPNOTSUPP));
                assert(pa_cap() == !(denali && native));
            }
}
'''
with tempfile.TemporaryDirectory() as td:
    path = Path(td) / 'gates.c'
    binary = path.with_suffix('')
    path.write_text(source)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', path, '-o', binary], check=True)
    subprocess.run([binary], check=True)
print('FullIO topology and PA-range gates accept both explicit Denali fixtures and reject everything else.')
