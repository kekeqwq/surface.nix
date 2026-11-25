#!/usr/bin/env python3
"""Summarize WSA-only regmap replay and device PM states from an isolated trace."""

import argparse
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import re


AMPS = ("sdw:1:0:0217:0204:00:0", "sdw:1:0:0217:0204:00:1")
EVENT = re.compile(r"[ \t](\d+\.\d+): (regcache_sync|regmap_hw_write_start|rpm_status): (\S+) (.*)$", re.M)


def summarize(text):
    limits = re.findall(r"^# entries-in-buffer/entries-written: (\d+)/(\d+)", text, re.M)
    if len(limits) != 1 or limits[0][0] != limits[0][1] or int(limits[0][0]) == 0:
        raise ValueError("missing, empty, or overwritten trace")
    active = {}
    regions = defaultdict(list)
    other_writes = defaultdict(int)
    states = []
    for stamp, event, device, rest in (m.groups() for m in EVENT.finditer(text)):
        now = Decimal(stamp)
        if event == "rpm_status":
            if device not in (*AMPS, "6b00000.codec", "6b10000.soundwire"):
                raise ValueError("unexpected PM device in allowlisted trace")
            states.append((stamp, device, rest))
            continue
        if device not in AMPS:
            raise ValueError("unexpected codec in allowlisted trace")
        if event == "regmap_hw_write_start":
            m = re.fullmatch(r"reg=[0-9a-f]+ count=(\d+)", rest)
            if not m or int(m[1]) == 0:
                raise ValueError("malformed hardware write trace")
            if device in active:
                active[device][1] += int(m[1])
            else:
                other_writes[device] += int(m[1])
        elif rest.endswith(" status=start"):
            if device in active:
                raise ValueError(f"overlapping cache syncs on {device}")
            active[device] = [now, 0]
        elif rest.endswith(" status=stop"):
            if device not in active:
                raise ValueError(f"unmatched cache sync stop on {device}")
            start, writes = active.pop(device)
            if now < start:
                raise ValueError(f"backwards trace time on {device}")
            regions[device].append(((now - start) * 1000, writes))
    if active or not states:
        raise ValueError("unfinished sync or no PM transitions")
    for stamp, device, rest in states:
        print(f"{stamp} {device} {rest}")
    for amp in AMPS:
        desc = ", ".join(f"{ms:.3f} ms/{n} writes" for ms, n in regions[amp]) or "no complete sync"
        print(f"{amp}: {desc}; outside sync={other_writes[amp]} writes")


def summarize_slots(journal):
    """Classify raw slots, not PA readiness or retained codec context."""
    pattern = re.compile(
        r'^\[\s*(\d+\.\d+)\].*6b10000\.soundwire: FullIO PM transition enum: '
        r'slaves=(0x[0-9a-f]{8})->(0x[0-9a-f]{8})$', re.M)
    # Denali paired WSA devices in this boot use slots 1 and 2, not
    # the unassigned slot 0. Require full ATTACHED after any observed loss.
    def pair(bits):
        return tuple((bits >> (2 * slot)) & 3 for slot in (1, 2))

    # A runner may append a full same-boot journal after its scoped log.
    # Sort and deduplicate those repeated records; inputs must be one boot.
    events = sorted(set(pattern.findall(journal)), key=lambda entry: Decimal(entry[0]))
    result, missing_since = [], None
    for stamp, old, new in events:
        before, after = pair(int(old, 16)), pair(int(new, 16))
        if missing_since is None and all(v in (1, 2) for v in before) and 0 in after:
            missing_since = Decimal(stamp)
            result.append(f'{stamp}: paired WSA slot loss ({old}→{new}).')
        elif missing_since is not None and after == (1, 1):
            interval = (Decimal(stamp) - missing_since) * 1000
            result.append(f'{stamp}: both raw WSA slots ATTACHED again ({interval:.3f} ms after loss); retention unproven.')
            missing_since = None
    if missing_since is not None:
        result.append('No paired raw-slot reattachment observed after loss; slot 0 alone is not the pair.')
    return result


def summarize_transition(trace, journal):
    for line in summarize_slots(journal):
        print(line)
    samples = re.findall(
        r"^\[\s*(\d+\.\d+)\].*6b10000\.soundwire: FullIO PM transition (\S+): "
        r"clash=([01]) frame=([01]) result=(-?\d+)(?: slaves=(0x[0-9a-f]{8}))?"
        r"(?: raw_irq=(0x[0-9a-f]{8}))?$",
        journal, re.M,
    )
    preclear = [sample for sample in samples if sample[1] == "clock-start-before-clash-clear"]
    if not preclear:
        print("No controller pre-clear snapshot in this observation.")
    boundaries = {
        "before-cgcr-reset": "before CGCR reset (hclk and main IRQ already enabled)",
        "after-cgcr-reset-before-clock-start": "after CGCR reset, before clock-start write",
        "clock-start-before-clash-clear": "after clock-start write, before stock clash clear",
        "after-clash-clear-before-irq-restore": "after stock clash clear, before IRQ-mask restore",
        "after-irq-restore-before-frame-wait": "after IRQ-mask restore, before frame wait",
        "before-exit-clock-stop": "before core clock-stop exit",
    }
    boundaries['after-enter-clock-stop'] = 'after ClockStopNow command (not completion of controller stop)'
    lines = set()
    for stamp, stage, clash, frame, result, slaves, raw_irq in samples:
        if stage not in boundaries:
            continue
        state = f" slaves={slaves}" if slaves else ""
        irq_bits = f" raw_irq={raw_irq}" if raw_irq else ""
        lines.add((stamp, f"{boundaries[stage]}: clash={clash} frame={frame}{state}{irq_bits} result={result}."))
    finished = re.findall(
        r'^\[\s*(\d+\.\d+)\].*6b10000\.soundwire: FullIO PM transition '
        r'clock-stop-finished-irq: raw_irq=(0x[0-9a-f]{8})$', journal, re.M)
    for stamp, raw_irq in finished:
        if int(raw_irq, 16) & (1 << 14):
            lines.add((stamp, f'threaded handler observed CLK_STOP_FINISHED (raw_irq={raw_irq}).'))
    for stamp, line in sorted(lines, key=lambda x: (Decimal(x[0]), x[1])):
        print(f'{stamp}: {line}')
    for _, stage, _, _, result, _, _ in samples:
        if stage == "after-exit-clock-stop" and int(result) != 0:
            print(f"Clock-stop exit returned {result}; RPM_ACTIVE alone cannot show recovery.")
    irq = re.search(r"^\[\s*(\d+\.\d+)\].*SWR bus clsh detected", journal, re.M)
    sync = [Decimal(stamp) for stamp, event, _dev, tail in (m.groups() for m in EVENT.finditer(trace))
            if event == "regcache_sync" and tail.endswith(" status=start")]
    if irq and sync and Decimal(irq[1]) < min(sync):
        print("First reported clash preceded the first observed codec cache sync; do not blame that replay for the first clash.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("trace", type=Path)
    p.add_argument("--journal", type=Path, help="monotonic controller diagnostic log from the same observation")
    args = p.parse_args()
    try:
        trace = args.trace.read_text()
        if args.journal:
            summarize_transition(trace, args.journal.read_text())
        summarize(trace)
    except ValueError as exc:
        p.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
