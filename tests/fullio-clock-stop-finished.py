#!/usr/bin/env python3
"""Keep STOP command, raw pending bit, and threaded IRQ evidence distinct."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
from runpy import run_path
import sys

text = Path(sys.argv[1]).read_text()
case = text.split('case SWRM_INTERRUPT_STATUS_CLK_STOP_FINISHED_V2:', 1)[1].split('case ', 1)[0]
assert re.fullmatch(
    r'\s*if \(ctrl->version >= SWRM_VERSION_2_0_0 && qcom_swrm_fullio_pm_audit\(ctrl\)\)'
    r'\s*dev_info_ratelimited\(ctrl->dev,\s*"FullIO PM transition '
    r'clock-stop-finished-irq: raw_irq=0x%08x\\n",\s*intr_sts\);\s*break;\s*', case
)
snapshot = text.split('static void swrm_fullio_pm_snapshot(', 1)[1].split('\n}', 1)[0]
assert snapshot.count('ctrl->reg_read(') == 3 and 'reg_write' not in snapshot
assert 'slave_status, irq_status);' in snapshot

parse = run_path(str(Path(__file__).with_name('fullio-pm-replay-trace.py')))['summarize_transition']


def line(t, msg, dev='6b10000.soundwire'):
    return f'[{t}] surface kernel: qcom-soundwire {dev}: FullIO PM transition {msg}'


def report(*lines):
    with redirect_stdout(buf := StringIO()):
        parse('', '\n'.join(lines))
    return buf.getvalue()


old = line('2.000002', 'after-enter-clock-stop: clash=0 frame=1 result=0 slaves=0x00000014')
pending = line('3.000002', 'after-enter-clock-stop: clash=0 frame=1 result=0 slaves=0x00000014 raw_irq=0x00004400')
threaded = line('3.000010', 'clock-stop-finished-irq: raw_irq=0x00004000')
wrong = line('3.000009', 'clock-stop-finished-irq: raw_irq=0x00004000', '6b20000.soundwire')
wrong_bit = line('3.000008', 'clock-stop-finished-irq: raw_irq=0x00000400')
assert 'not completion' in report(old)
assert 'raw_irq=0x00004400' in report(pending)
assert 'threaded handler observed' not in report(pending, wrong, wrong_bit)
result = report(threaded, pending, threaded)
assert result.count('threaded handler observed') == 1
assert result.index('3.000002:') < result.index('3.000010:')
print('ClockStopNow, raw pending IRQ bits, and actual handler dispatch remain separate observations.')
