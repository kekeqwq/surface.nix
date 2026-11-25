#!/usr/bin/env python3
"""Check that FullIO uses the upstream VI descriptor and keeps CPS private."""
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text()

def table(name):
    return re.search(rf'\b{name}\[.*?\]\s*= \{{(.*?)^\}};', text, re.M | re.S)[1]


def vi(name):
    return re.search(r'\[WSA884X_PORT_VISENSE\] = \{([^}]+)\}', table(name))[1]


desc = vi('wsa884x_sink_dpn_prop')
request = vi('wsa884x_pconfig')
channels = int(re.search(r'\.ch_mask\s*=\s*(0x[0-9a-f]+|\d+)', request)[1], 0).bit_count()
assert channels == 2
assert int(re.search(r'\.min_ch\s*=\s*(\d+)', desc)[1]) <= channels
assert int(re.search(r'\.max_ch\s*=\s*(\d+)', desc)[1]) >= channels
assert re.search(r'feedback_ports\[0\]\s*=\s*wsa884x_sink_dpn_prop\[WSA884X_PORT_VISENSE\];', text)
assert re.search(r'feedback_ports\[1\]\s*=\s*wsa884x_fullio_cps_port;', text)
assert re.search(r'\.src_dpn_prop\s*=\s*wsa884x->feedback_ports;', text)
assert re.search(r'feedback_ports\[1\]\.offset1\s*=\s*offset;', text)
print('FullIO VI inherits the upstream two-channel DP5 capability; CPS retains private DP6/offset setup.')
