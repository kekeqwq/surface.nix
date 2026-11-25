#!/usr/bin/env python3
"""Verify the routed PA-off shutdown timeline from monotonic trace and journal lines."""

import argparse
from decimal import Decimal
from pathlib import Path
import re


def check(text: str, taps: bool = False, missing_proof: bool = False) -> str:
    def clocks(pattern: str, description: str, count: int) -> list[Decimal]:
        found = re.findall(pattern, text, re.M)
        if len(found) != count:
            raise ValueError(f"expected {count} {description}, found {len(found)}")
        return [Decimal(stamp) for stamp in found]

    def journal(message: str, count: int = 1):
        times = clocks(r"^\[\s*(\d+\.\d+)\][^\n]*" + message + r"[^\n]*$", message, count)
        return times[0] if count == 1 else times

    def dapm(event: str, widget: str, val: int) -> Decimal:
        return clocks(
            rf"^\s*[^\n]*?\s(\d+\.\d+): snd_soc_dapm_widget_{event}: widget={widget} val={val}$",
            f"{widget} {event}={val}", 1,
        )[0]

    entries = re.findall(r"^# entries-in-buffer/entries-written: (\d+)/(\d+)", text, re.M)
    if len(entries) != 1 or entries[0][0] != entries[0][1] or int(entries[0][0]) == 0:
        raise ValueError("missing, empty or overwritten DAPM trace")
    if taps:
        configured = journal("FullIO immediate VI/CPS taps configured")
        stop = journal("FullIO silent START/STOP audit passed; no PA enable or PCM writes")
    elif missing_proof:
        first_missing, second_missing = journal("FullIO injected missing PA-off proof after both hardware checks", 2)
        stop = journal("FullIO start audit failed; GRAPH_STOP acknowledged")
        unverified = journal("FullIO paired PA shutdown unverified: PA=-61, graph audit=-61; render locked")
        if "FullIO synthetic fault notice: paired PA-off worker verified" in text:
            raise ValueError("missing proof was incorrectly accepted")
    else:
        worker = journal("FullIO synthetic fault notice: paired PA-off worker verified before DSP STOP")
        stop = journal("FullIO start audit failed; GRAPH_STOP acknowledged")
    for side, amp in (("Left", 0), ("Right", 1)):
        widget = f"Spkr{side} SPKR"
        on = dapm("power", widget, 1)
        post_pmu = dapm("event_done", widget, 2)
        off = dapm("power", widget, 0)
        pre_pmd = dapm("event_done", widget, 4)
        verified = journal(rf"sdw:1:0:0217:0204:00:{amp}: FullIO PA-off teardown verified;", 2 if missing_proof else 1)
        if missing_proof:
            first, second = verified
            good = (on <= post_pmu < first <= first_missing < stop < second <= second_missing <= unverified
                    and first_missing < off <= pre_pmd)
        elif taps:
            # This fixture takes the verified pair-STOP readbacks after DSP STOP.
            good = on <= post_pmu < configured < stop <= verified and configured < off <= pre_pmd
        else:
            # The worker must finish before both teardown paths. DAPM can react
            # to the STOP itself, or run later during ALSA cleanup.
            good = on <= post_pmu < verified <= worker < stop and worker < off <= pre_pmd
        if not good:
            raise ValueError(f"{side}: inconsistent DAPM / PA-off / STOP order")
    if taps:
        return "Both speaker routes active during the PA-off immediate-tap observation, with final PA-off readbacks."
    if missing_proof:
        return "Both hardware checks repeated; discarded proof remained unverified across DSP STOP."
    return "Both routed speakers verified PA-off before DAPM power-down and DSP STOP."


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    fixture = p.add_mutually_exclusive_group()
    fixture.add_argument("--taps", action="store_true", help="verify the immediate-feedback-tap fixture")
    fixture.add_argument("--missing-proof", action="store_true", help="verify the PA-off proof-loss fixture")
    p.add_argument("logs", type=Path, nargs="+")
    args = p.parse_args()
    try:
        print(check("\n".join(path.read_text() for path in args.logs), taps=args.taps, missing_proof=args.missing_proof))
    except ValueError as exc:
        p.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
