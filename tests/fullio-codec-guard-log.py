#!/usr/bin/env python3
"""Check read-only PA-off WSA watchdog observations against routed DAPM."""

import argparse
from decimal import Decimal
from pathlib import Path
import re


def check(text: str) -> None:
    if "FullIO PA-off codec guard unverified" in text:
        raise ValueError("a codec guard snapshot was unverified")
    for amp, side in enumerate(("Left", "Right")):
        pattern = (
            rf"^\[\s*(\d+\.\d+)\][^\n]* sdw:1:0:0217:0204:00:{amp}: "
            r"FullIO PA-off codec guard: route=(on|off) PDM_WD_CTL=0x([0-9a-f]{2}) CURRENT_LIMIT=0x([0-9a-f]{2})$"
        )
        samples = re.findall(pattern, text, re.M)
        if [s[1] for s in samples] != ["on", "off"]:
            raise ValueError(f"{side}: expected exactly one active and one inactive snapshot")
        on, off = samples
        if Decimal(on[0]) >= Decimal(off[0]) or not (int(on[2], 16) & 1) or int(off[2], 16) & 1:
            raise ValueError(f"{side}: watchdog enable did not track the PA-off widget lifecycle")
        if on[3] != off[3]:
            raise ValueError(f"{side}: current-limit register changed during shutdown")
        print(f"{side}: stock PDM watchdog bit toggled; limit register 0x{on[3]} (not calibrated current).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("log", type=Path)
    args = ap.parse_args()
    try:
        check(args.log.read_text())
    except ValueError as exc:
        ap.exit(1, f"{exc}\n")
    print("PA-off configuration only: no watchdog trip or under-load protection verified.")


if __name__ == "__main__":
    main()
