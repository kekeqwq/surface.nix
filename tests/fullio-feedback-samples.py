#!/usr/bin/env python3
"""Check exported VI/CPS sample windows offline; never starts an audio graph.

Inputs are raw interleaved stereo S32_LE from the DSP source outputs, not
SoundWire counters, packet headers, or the post-protection render stream.
VI packs two S16 components per speaker word. Check both without inferring
physical channel order from sample variation.
"""

import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

TAPS = {"VI": (8000, "0x4026"), "CPS": (24000, "0x402b")}
MIN_WINDOWS = 10
MAX_SECONDS = 5


def summarize(data, rate, *, packed_vi=False):
    window_bytes = rate // 100 * 8  # 10 ms, two little-endian S32 samples per frame
    count, remainder = divmod(len(data), window_bytes)
    if remainder or not MIN_WINDOWS <= count <= MAX_SECONDS * 100:
        raise ValueError("expected 0.1–5 seconds of complete 10 ms windows")

    varied = [set() for _ in range(4 if packed_vi else 2)]
    distinct = 0

    def no_copy(a, b):
        # Use wide integer arithmetic for genuine S32 and packed S16.
        delta, total = a[0] - b[0], a[0] + b[0]
        return (any(x - y != delta for x, y in zip(a, b)) and
                any(x + y != total for x, y in zip(a, b)))
    def s16(word):
        word &= 0xffff
        return (word ^ 0x8000) - 0x8000

    for pos in range(0, len(data), window_bytes):
        pcm = array("i", data[pos:pos + window_bytes])
        if sys.byteorder != "little":
            pcm.byteswap()
        left, right = pcm[::2], pcm[1::2]
        if packed_vi:
            # The halfwords retain the wire order. Name them Lo/Hi here,
            # because variance alone does not prove which is voltage.
            channels = tuple(array('h', (s16(x >> shift) for x in lane))
                             for lane in (left, right) for shift in (0, 16))
            pairs = ((channels[0], channels[2]), (channels[1], channels[3]))
        else:
            channels = (left, right)
            pairs = ((left, right),)
        live = []
        for lane, channel in enumerate(channels):
            nonconstant = min(channel) != max(channel)
            live.append(nonconstant)
            if nonconstant:
                varied[lane].add(hashlib.sha256(channel.tobytes()).digest())
        if all(live) and all(no_copy(a, b) for a, b in pairs):
            distinct += 1
    return count, tuple(len(hashes) for hashes in varied), distinct


def inspect(kind, samples):
    rate, instance = TAPS[kind]
    count, channels, distinct = summarize(samples, rate, packed_vi=kind == 'VI')
    order = 'L-Lo/L-Hi/R-Lo/R-Hi' if kind == 'VI' else 'L/R'
    print(f"{kind} {instance} ({rate} Hz): {count} windows, unique varying {order}={channels}, distinct stereo={distinct}")
    if min(channels) < MIN_WINDOWS:
        raise ValueError(f"{kind}: silent, constant, or repeated windows on at least one lane")
    if distinct < MIN_WINDOWS:
        raise ValueError(f"{kind}: too few windows with both lanes varying independently of exact copies or inversions")


def decode_archive(path, receive_window=None, observed=None, *, allow_empty=False, rx0=None, legacy=None):
    """Decode the reference <receive time, datagram length, bytes> export."""
    frame = struct.Struct("<dI")
    taps = {2: "VI", 3: "CPS"}
    samples = {kind: bytearray() for kind in TAPS}
    counters = {kind: None for kind in TAPS}
    packet_sizes = {}
    other = 0
    times = {kind: [] for kind in TAPS}
    if receive_window is not None:
        origin, begin, end = receive_window
        if not all(map(math.isfinite, receive_window)) or not 0 <= origin <= begin < end:
            raise ValueError('invalid monotonic origin/start/end')
    last_time = -math.inf
    with path.open("rb") as stream:
        for _ in range(8192):
            prefix = stream.read(frame.size)
            if not prefix:
                if receive_window is not None:
                    if allow_empty and not any(times.values()):
                        return samples, other
                    if not all(times.values()):
                        raise ValueError('receive window did not contain both taps')
                    overlap = min(v[-1] for v in times.values()) - max(v[0] for v in times.values())
                    if overlap < .05:
                        raise ValueError('VI/CPS receive intervals overlap less than 50 ms')
                return samples, other
            if len(prefix) != frame.size:
                raise ValueError("truncated archive prefix")
            timestamp, length = frame.unpack(prefix)
            if not math.isfinite(timestamp) or timestamp < last_time or not 0 < length <= 65536:
                raise ValueError("invalid archive timestamp or packet length")
            last_time = timestamp
            pkt = stream.read(length)
            if len(pkt) != length:
                raise ValueError("truncated archive packet")
            if pkt[0] != 0x10 or pkt[6:8] != b"\x86\x15":
                continue
            if length < 104:
                raise ValueError("truncated 0x1586 audio header")
            outer, inner = struct.unpack_from("<HH", pkt, 2)
            sequence, payload_size = struct.unpack_from("<II", pkt, 24)
            tap = struct.unpack_from("<I", pkt, 52)[0]
            rate, channels, bits = struct.unpack_from("<IHH", pkt, 64)
            if outer != length - 4 or inner != outer or payload_size != length - 104:
                raise ValueError("inconsistent 0x1586 lengths")
            diag = None
            if tap == 1 and legacy is not None:
                diag = legacy
            elif rx0 is not None and tap == rx0.get('tag', 1):
                diag = rx0
            if diag is not None:
                # Golden tap 1 (0x4003), measured 1 ms stereo S16_LE
                # before RX0. No decoder claim about firmware session ID.
                shape = (rate, channels, bits, payload_size)
                if 'formats' in diag:
                    formats = diag['formats']
                    if shape not in formats and len(formats) == 16:
                        raise ValueError(f'tap {tap}: too many observed packet formats')
                    formats[shape] = formats.get(shape, 0) + 1
                elif shape != (48000, 2, 16, 192):
                    raise ValueError(f'RX0: unexpected tap format or payload length: '
                                     f'rate={rate} channels={channels} bits={bits} payload={payload_size}')
                if diag['sequence'] is not None:
                    advance = (sequence - diag['sequence']) & 0xFFFFFFFF
                    if not 0 < advance < 0x80000000:
                        raise ValueError('RX0: duplicate or backwards DSP packet sequence')
                diag['sequence'] = sequence
                if receive_window is not None:
                    if origin + timestamp < begin:
                        diag['before'] += 1
                        continue
                    if origin + timestamp >= end:
                        diag['after'] += 1
                        continue
                diag['packets'] += 1
                if 'formats' not in diag:
                    diag['nonzero_packets'] += bool(any(pkt[104:]))
                continue
            if tap not in taps:
                other += 1
                continue
            kind = taps[tap]
            if receive_window is not None:
                if not begin <= origin + timestamp < end:
                    continue
                times[kind].append(timestamp)
            expected_rate, _ = TAPS[kind]
            # The native-Windows capture uses 10 ms packets, the forced
            # Linux logger uses 1 ms. Normalize both to 10 ms analysis windows.
            valid_sizes = (expected_rate // 1000 * 8, expected_rate // 100 * 8)
            if (rate, channels, bits) != (expected_rate, 2, 32) or payload_size not in valid_sizes:
                raise ValueError(f"{kind}: unexpected audio format or payload length")
            if packet_sizes.setdefault(kind, payload_size) != payload_size:
                raise ValueError(f"{kind}: changed packet size during a capture")
            if counters[kind] is not None:
                advance = (sequence - counters[kind]) & 0xFFFFFFFF
                if not 0 < advance < 0x80000000:
                    raise ValueError(f"{kind}: duplicate or backwards DSP packet sequence")
            counters[kind] = sequence
            if observed is not None:
                observed.append((kind, hashlib.sha256(pkt).hexdigest()))
            samples[kind].extend(pkt[104:])
            if len(samples[kind]) > expected_rate * 8 * MAX_SECONDS:
                raise ValueError(f"{kind}: capture exceeds the 5-second sample limit")
        raise ValueError("diagnostic archive exceeds the packet limit")


def check_external_decode(observed, annotation):
    """Compare raw packet hashes to an independently decoded, session-bound list.

    This does NOT decode legacy firmware session fields or authenticate the
    annotator. Establish and record the graph binding outside this checker.
    """
    binding = annotation.get('binding')
    records = annotation.get('records')
    graph = annotation.get('graph')
    if (annotation.get('version') != 1 or type(graph) is not int or graph < 0 or
            not isinstance(binding, dict) or set(binding) != set(TAPS) or
            not isinstance(records, list) or len(records) != len(observed)):
        raise ValueError('invalid or incomplete external decode')
    if {kind for kind, _ in observed} != set(TAPS):
        raise ValueError('external decode must cover both taps')
    for kind, tap, source in (('VI', 2, 0x4026), ('CPS', 3, 0x402b)):
        row = binding[kind]
        if (not isinstance(row, dict) or row.get('tap') != tap or row.get('source') != source or
                type(row.get('session')) is not int or not 0 <= row['session'] <= 0xffffffff):
            raise ValueError(f'{kind}: invalid external graph binding')
    seen = set()
    for (kind, packet), record in zip(observed, records):
        row = binding[kind]
        if (not isinstance(record, dict) or record.get('sha256') != packet or
                record.get('graph') != graph or record.get('tap') != row['tap'] or
                record.get('session') != row['session'] or packet in seen):
            raise ValueError(f'{kind}: replayed, mixed-session, or unbound packet')
        seen.add(packet)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="reference-style 0x1586 datagram archive")
    parser.add_argument('--report-rx0', action='store_true',
                        help='report in-window tap 1 zero/nonzero packet counts, not physical silence')
    parser.add_argument('--rx0-tag-audit', action='store_true',
                        help='inventory tap 4 packet formats without interpreting samples')
    parser.add_argument('--expected-legacy-records', type=int,
                        help='cross-check legacy tap 1 count in the tag-4 audit')
    parser.add_argument('--expected-rx0-records', type=int,
                        help='cross-check aggregate tap 1 count reported by the collector')
    parser.add_argument('--external-decode', type=Path,
                        help='session annotations from an independent firmware-matched decoder')
    parser.add_argument('--receive-window', nargs=3, type=float, metavar=('ORIGIN', 'START', 'END'),
                        help='only compare records received inside this host monotonic window; not a DSP generation proof')
    parser.add_argument("--allow-empty-archive", action="store_true", help="report zero VI/CPS tap records as a PA-off observation, not a sample pass")
    parser.add_argument("vi", nargs="?", type=Path, help="tap 2 / VI 8 kHz stereo S32_LE payload only")
    parser.add_argument("cps", nargs="?", type=Path, help="tap 3 / CPS 24 kHz stereo S32_LE payload only")
    args = parser.parse_args()
    if (args.archive and (args.vi or args.cps)) or (not args.archive and not (args.vi and args.cps)):
        parser.error("supply --archive or both raw sample paths")
    if args.allow_empty_archive and not args.archive:
        parser.error("--allow-empty-archive requires --archive")
    if args.receive_window and not args.archive:
        parser.error('--receive-window requires an archive')
    if args.report_rx0 and not args.receive_window:
        parser.error('--report-rx0 requires --archive and --receive-window')
    if args.rx0_tag_audit and not args.report_rx0:
        parser.error('--rx0-tag-audit requires --report-rx0')
    if args.expected_rx0_records is not None and (not args.report_rx0 or args.expected_rx0_records < 0):
        parser.error('--expected-rx0-records requires --report-rx0 and a nonnegative count')
    if args.expected_legacy_records is not None and (not args.rx0_tag_audit or args.expected_legacy_records < 0):
        parser.error('--expected-legacy-records requires --rx0-tag-audit and a nonnegative count')
    if args.external_decode and args.allow_empty_archive:
        parser.error('--external-decode is not an observation-only check')
    if args.external_decode and not args.receive_window:
        parser.error('--external-decode requires --receive-window')
    try:
        if args.archive:
            observed = [] if args.external_decode else None
            rx0 = dict(packets=0, nonzero_packets=0, before=0, after=0, sequence=None) if args.report_rx0 else None
            legacy = None
            if args.rx0_tag_audit:
                legacy = dict(rx0, tag=1, formats={})
                rx0.update(tag=4, formats={})
            samples, other = decode_archive(args.archive, args.receive_window, observed,
                                            allow_empty=args.allow_empty_archive, rx0=rx0, legacy=legacy)
            for row, expected in ((rx0, args.expected_rx0_records), (legacy, args.expected_legacy_records)):
                if row is None:
                    continue
                tag = row.get('tag', 1)
                total = row['before'] + row['packets'] + row['after']
                if expected is not None and total != expected:
                    raise ValueError(f'tap {tag}: collector reported {expected} but archived {total}')
                timing = f"inside={row['packets']} before={row['before']} after={row['after']}"
                if 'formats' in row:
                    print(f"0x1586 tap {tag}: {timing}; packet formats (rate, channels, bits, bytes)={row['formats']}; "
                          "no sample interpretation.")
                else:
                    print(f"0x1586 tap {tag}: {timing}; nonzero={row['nonzero_packets']}; "
                          "receipt only, no acoustic or graph provenance proof.")
            if args.external_decode:
                with args.external_decode.open('rb') as stream:
                    raw = stream.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError('external decode exceeds 2 MB')
                annotation = json.loads(raw)
                if not isinstance(annotation, dict):
                    raise ValueError('external decode must be a JSON object')
                check_external_decode(observed, annotation)
                print('Packet hashes and sessions match supplied external decode; decoder and graph binding not authenticated here.')
            print(f"0x1586: VI={len(samples['VI'])} bytes, CPS={len(samples['CPS'])} bytes, other taps={other}")
            if args.allow_empty_archive and not any(samples.values()):
                print("Observation only: neither feedback tap provided samples.")
                return
        else:
            samples = {}
            for kind, path in (("VI", args.vi), ("CPS", args.cps)):
                with path.open("rb") as stream:
                    samples[kind] = stream.read(TAPS[kind][0] * 8 * MAX_SECONDS + 1)
        for kind in TAPS:
            if not samples[kind]:
                raise ValueError(f"no {kind} sample payload in this input")
            inspect(kind, samples[kind])
    except (OSError, ValueError) as error:
        parser.exit(1, f"FullIO feedback: {error}\n")
    print("Both payloads contain varying samples. Verify live provenance, timing, and fault behavior separately.")


if __name__ == "__main__":
    main()
