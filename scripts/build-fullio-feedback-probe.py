#!/usr/bin/env python3
"""Generate an offline-only, capture-only VI or CPS topology from pinned v19c."""

import argparse
from pathlib import Path
import re

PCM = "MultiMedia3 Capture"
TX = "TX_CODEC_DMA_TX_3"
MIXER = "MultiMedia3 Mixer"
FE = tuple(f"stream2.{name}1" for name in ("logger", "mfc", "pcm_converter", "pcm_encoder", "rdsh_ep"))
BE = ("device120.codec_dma_tx1", "device120.logger1")
PROBES = {"vi": ("WSA_CODEC_DMA_TX_0", 106, 8000, 1), "cps": ("WSA_CODEC_DMA_TX_1", 108, 24000, 3)}


def single(pattern, text):
    matches = re.findall(pattern, text, re.M | re.S)
    if len(matches) != 1:
        raise ValueError(f"expected one match for {pattern}, got {len(matches)}")
    return matches[0]


def section(text, name):
    return single(rf"^{re.escape(name)} \{{\n(.*?)^\}}", text)


def block(text, name):
    return single(rf"^\t'{re.escape(name)}' \{{\n.*?^\t\}}", text)


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"expected one {old!r}")
    return text.replace(old, new)


def generate(source, probe):
    backend, graph_id, rate, interface_index = PROBES[probe]
    parts = []
    for title, names in (
        ("SectionControlMixer", (TX,)),
        ("SectionWidget", FE + BE + (MIXER,)),
        ("SectionPCM", (PCM,)),
        ("SectionPCMCapabilities", (PCM,)),
        ("SectionVendorTokens", FE + BE + (MIXER, TX)),
        ("SectionVendorTuples", tuple(name + ":tuple0" for name in FE + BE + (MIXER, TX))),
    ):
        content = section(source, title)
        selected = []
        for name in names:
            entry = block(content, name)
            if title == "SectionPCMCapabilities":
                for old, new in (("S16_LE", "S32_LE"), ("rate_min 48000", f"rate_min {rate}"),
                                 ("rate_max 48000", f"rate_max {rate}"), ("channels_min 1", "channels_min 2")):
                    entry = replace_once(entry, old, new)
            if title == "SectionVendorTuples" and name in tuple(n + ":tuple0" for n in BE + (TX,)):
                entry = replace_once(entry, "token1 120\n", f"token1 {graph_id}\n")
            if title == "SectionVendorTuples" and name == BE[0] + ":tuple0":
                # CODEC_DMA_INTF_CFG from v19c: WSA LPAIF=2, VI=1, CPS=3.
                entry = replace_once(entry, "token250 4\n", "token250 2\n")
                entry = replace_once(entry, "token251 1\n", f"token251 {interface_index}\n")
            selected.append(entry)
        parts.append(title + " {\n" + "\n".join(selected) + "\n}\n")

    data_names = FE + BE + (MIXER, TX)
    parts.append("SectionData {\n" + "".join(f"\t'{n}:tuple0'.tuples '{n}:tuple0'\n" for n in data_names) + "}\n")
    lines = [f"{FE[0]}, , {MIXER}"]
    lines += [f"{right}, , {left}" for left, right in zip(FE, FE[1:])]
    lines += [f"{BE[0]}, , {TX} Capture", f"{BE[1]}, , {BE[0]}"]
    parts.append("SectionGraph {\n\tprobe_routes {\n\t\tindex 1\n\t\tlines [\n" +
                 "".join(f"\t\t\t'{line}'\n" for line in lines) + "\t\t]\n\t}\n" +
                 f"\tprobe_mix {{\n\t\tindex 2\n\t\tlines [ '{MIXER}, {TX}, {BE[1]}' ]\n\t}}\n}}\n")
    return "\n".join(parts).replace(TX, backend)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("probe", choices=PROBES)
    cli.add_argument("reference", type=Path)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    args.output.write_text(generate(args.reference.read_text(), args.probe))


if __name__ == "__main__":
    main()
