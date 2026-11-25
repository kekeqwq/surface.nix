#!/usr/bin/env python3
"""Check the private record inventory of the pinned FullIO v19c artifact.

This is an offline ABI check, not validation of protection or amplifier gain.
No payloads are sent to a DSP.
"""
import argparse
import hashlib
import re
import struct
from pathlib import Path

WORD = struct.Struct("<I")
HEADER = struct.Struct("<4I")
WIDGET_SIZE = 132
CONTROL_LINKS = 0x08001061
FIRST_STAGE = 0x53503101
LAST_STAGE = 0x5350310A
CONTAINERS = {
    "sp11.sh_mem_pull_mode.4660": 0xE000004C,
    "sp11.speaker_protection.4027": 0xE0000001,
    "sp11.speaker_protection_vi.4024": 0xE0000007,
    "sp11.vol_ctrl.4a63": 0xE0000114,
}
BACKENDS = {
    "sp11.codec_dma_sink.4157": 0x69,
    "sp11.codec_dma_source.4026": 0x6A,
    "sp11.codec_dma_source.402b": 0x6C,
}
# Golden hardware endpoint rows: stage, q6 DMA interface and channel mask.
# iid: (DIAG log code, tap point, mode) in the original bootstrap.
LOGGER_CONFIG = {
    0x4003: (0x1586, 1, 1),
    0x4025: (0x1586, 2, 0),
    0x402A: (0x1586, 3, 0),
    0x465C: (0x152E, 1, 0),
    0x467A: (0x19B0, 1, 0),
    0x47E9: (0x1531, 1, 0),
}
ENDPOINTS = {
    0x4157: (2, 48000, 16, 1),  # WSA speaker RX0
    0x4026: (5, 8000, 32, 1),   # WSA VI TX0
    0x402B: (1, 24000, 32, 3), # WSA CPS TX1
}
EP_MEDIA = 0x08001017
EP_INTF = 0x08001063
VOL_GAIN = 0x08001038
VOL_MUTE = 0x08001039
Q28_UNITY = 0x10000000
# Packed APM control-link rows: peer IIDs, control ports, single intent.
GOLDEN_LINKS = (
    (0x4024, 0x80000000, 0x4027, 0x80000000, 0x08001204),  # VI to SP
    (0x4028, 0x80000000, 0x4027, 0x80000001, 0x08001537),  # CPS consumer to SP
    (0x4157, 0x80000007, 0x40DF, 0xC0000001, 0x080010C2),  # External timer peer
    (0x4664, 0x80000000, 0x4663, 0x80000000, 0x08001118),  # EQ/volume peer
)
# The frontend uses these single frames in order. Keep them distinct from
# the out-of-band stages, which are multi-frame blobs, not one SET_CFG each.
INBAND = {
    6: (
        (0x4027, 0x080011E9, 8),
        (0x4024, 0x080011F5, 24),
        (0x4024, 0x080011F4, 24),
        (0x4024, 0x080011FF, 8),
    ),
    7: ((0x4A63, VOL_GAIN, 104),),
    9: ((0x4A63, VOL_MUTE, 104),),
}
STAGE_BYTES = {
    1: 10464, 2: 64, 3: 1888, 4: 1328, 5: 64,
    6: 128, 7: 120, 8: 216, 9: 120, 10: 40,
}
EXPECTED = {
    "sp11.sh_mem_pull_mode.4660": {1: 107, 2: 2},
    "sp11.speaker_protection.4027": {3: 7, 6: 4, CONTROL_LINKS: 4},
    "sp11.speaker_protection_vi.4024": {4: 5, 5: 2},
    "sp11.vol_ctrl.4a63": {7: 1, 8: 4, 9: 1, 10: 1},
}


def u32(data, offset):
    return WORD.unpack_from(data, offset)[0]


def find_all(data, marker):
    offset = data.find(marker)
    while offset >= 0:
        yield offset
        offset = data.find(marker, offset + 1)


def widget_payload(data, name):
    # The exact artifact is separately hash-checked. Resolve a named, packed
    # snd_soc_tplg_dapm_widget rather than mistaking graph strings for widgets.
    markers = [
        WORD.pack(WIDGET_SIZE) + WORD.pack(widget_type) + name.encode() + b"\0"
        for widget_type in range(32)
    ]
    matches = [offset for marker in markers for offset in find_all(data, marker)]
    if len(matches) != 1:
        raise ValueError(f"{name}: expected exactly one widget, got {len(matches)}")
    start = matches[0]
    size = u32(data, start + WIDGET_SIZE - WORD.size)
    start += WIDGET_SIZE
    if size > len(data) - start:
        raise ValueError(f"{name}: truncated private data")
    return data[start : start + size]


def records(data):
    offset = 0
    while offset < len(data):
        if len(data) - offset < 12:
            raise ValueError("truncated AudioReach record")
        length, kind = struct.unpack_from("<2I", data, offset)
        if kind == CONTROL_LINKS or FIRST_STAGE <= kind <= LAST_STAGE:
            if (len(data) - offset < HEADER.size or not length or length % 4
                or u32(data, offset + 8) or u32(data, offset + 12)):
                raise ValueError("invalid FullIO record header")
            end = offset + HEADER.size + length
            if end > len(data):
                raise ValueError("truncated FullIO record payload")
            yield kind, data[offset + HEADER.size : end]
            offset = end
        else:
            if length < 12 or length > len(data) - offset:
                raise ValueError("invalid AudioReach tuple length")
            offset += length


def frame_records(data):
    offset = 0
    while offset < len(data):
        target, param, size, status = HEADER.unpack_from(data, offset)
        if not target or not param or not size or status:
            raise ValueError("invalid calibration frame")
        next_offset = offset + ((HEADER.size + size + 7) & ~7)
        if next_offset > len(data):
            raise ValueError("invalid calibration frame bounds")
        yield target, param, size, data[offset + HEADER.size : offset + HEADER.size + size]
        offset = next_offset


def frames(data):
    for target, param, size, _ in frame_records(data):
        yield target, param, size


def verify_control_links(data):
    # v19c uses exactly two properties per row: one intent and heap=1.
    expected = WORD.pack(len(GOLDEN_LINKS)) + b"".join(
        struct.pack("<12I", a, a_port, b, b_port, 2,
                    0x08001062, 8, 1, intent, 0x0800136F, 4, 1)
        for a, a_port, b, b_port, intent in GOLDEN_LINKS
    )
    if data != expected:
        raise ValueError("Golden control-link peer, port, intent or heap mismatch")
    return len(GOLDEN_LINKS)


def word_tuple(data, offset):
    size, kind, count = struct.unpack_from("<3I", data, offset)
    if kind != 4 or size != 12 + 8 * count or size > len(data) - offset:
        raise ValueError("invalid AudioReach word tuple")
    values = dict(struct.iter_unpack("<2I", data[offset + 12 : offset + size]))
    if len(values) != count:
        raise ValueError("duplicate AudioReach word token")
    return values, offset + size


def verify_render_mute_path(edges):
    # Prove only that host PCM on the pinned static graph traverses VOL_CTRL.
    # This says nothing about DSP-generated data downstream, dynamic edges,
    # analogue silence, gain or feedback liveness.
    pull, mute, sink = 0x4660, 0x4A63, 0x4157
    adjacency = {}
    for source, _, dest, _ in edges:
        adjacency.setdefault(source, set()).add(dest)

    def reaches(start, end, omit=None):
        seen = {omit}
        pending = [start]
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            if node == end:
                return True
            seen.add(node)
            pending.extend(adjacency.get(node, ()))
        return False

    if not (reaches(pull, mute) and reaches(mute, sink)):
        raise ValueError("no host render route through the final VOL_CTRL")
    if reaches(pull, sink, omit=mute):
        raise ValueError("host render route bypasses the final VOL_CTRL")


def verify_feedback_paths(modules, edges):
    # Include the logger's output. A matching tap and endpoint alone could
    # show activity even with its protection consumer not connected.
    paths = (
        ((0x4026, 0x07001024), (0x4025, 0x0700101A), (0x4024, 0x070010E3)),
        ((0x402B, 0x07001024), (0x402A, 0x0700101A), (0x4029, 0x07001098),
         (0x4028, 0x070010E4)),
    )
    feedback = {iid for path in paths for iid, _ in path}
    wanted = {
        (src, 1, dst, 2) for path in paths for (src, _), (dst, _) in zip(path, path[1:])
    }
    actual = {edge for edge in edges if edge[0] in feedback or edge[2] in feedback}
    if actual != wanted or any(modules.get(iid) != mid for path in paths for iid, mid in path):
        raise ValueError("Golden VI/CPS data path to protection consumers mismatch")
    if modules.get(0x4027) != 0x070010E2:
        raise ValueError("Golden VI/CPS control links do not terminate at SP")


def verify_render_edges(topology):
    # ABI v5 widget records in the hash-pinned artifact. Mixer widgets and
    # ordinary capture graphs do not contribute module edges to render graph 0.
    names = re.findall(
        rb"\x84\x00\x00\x00[\x00-\x1f]\x00\x00\x00([A-Za-z0-9._ -]{2,43})\x00",
        topology,
    )
    modules, edges = {}, set()
    edge_tokens = [(206, 207, 209)] + [(i, i + 1, i + 2) for i in range(210, 231, 3)]
    for name in names:
        data = widget_payload(topology, name.decode())
        if not data or u32(data, 4) != 4:
            continue
        graph, offset = word_tuple(data, 0)
        if graph.get(1) != 0 or offset == len(data):
            continue
        _, offset = word_tuple(data, offset)
        if offset == len(data):
            continue
        module, _ = word_tuple(data, offset)
        instance = module.get(201)
        if instance is None:
            continue
        if instance in modules:
            raise ValueError(f"repeated render module {instance:#x}")
        modules[instance] = module.get(200)
        for source, destination, instance_id in edge_tokens:
            if all(k in module for k in (source, destination, instance_id)):
                edge = (instance, module[source], module[instance_id], module[destination])
                if edge in edges:
                    raise ValueError(f"repeated render module edge {edge}")
                edges.add(edge)
    if len(modules) != 29 or len(edges) != 26:
        raise ValueError(f"unexpected render graph: {len(modules)} modules, {len(edges)} edges")
    if any(src not in modules or dst not in modules for src, _, dst, _ in edges):
        raise ValueError("render edge extends outside graph 0")
    if modules.get(0x466B) != 0x07001019:
        raise ValueError("graph 0 lacks Golden SOFT_PAUSE at instance 0x466b")
    required_edges = {
        (0x4660, 1, 0x465C, 2),
        (0x466A, 1, 0x466B, 2), (0x466B, 1, 0x412B, 2),
    }
    if not required_edges <= edges:
        raise ValueError("render graph lacks a required pull or SOFT_PAUSE edge")
    verify_feedback_paths(modules, edges)
    if {iid for iid, mid in modules.items() if mid == 0x0700101A} != LOGGER_CONFIG.keys():
        raise ValueError('unexpected data-logging module inventory in graph 0')
    rx_logger = 0x4003
    rx_edges = {(0x4002, 1, rx_logger, 2), (rx_logger, 1, 0x4157, 2)}
    if (modules.get(rx_logger) != 0x0700101A or
            {edge for edge in edges if rx_logger in (edge[0], edge[2])} != rx_edges or
            (0x4027, 1, 0x4002, 2) not in edges):
        raise ValueError("Golden RX0 tap is not between SP and the speaker DMA sink")
    verify_render_mute_path(edges)


def verify(topology):
    verify_render_edges(topology)
    for name, backend in BACKENDS.items():
        data = widget_payload(topology, name)
        graph, offset = word_tuple(data, 0)
        _, offset = word_tuple(data, offset)
        module, _ = word_tuple(data, offset)
        if graph.get(1) != 0 or module.get(263) != backend:
            raise ValueError(f"{name}: expected backend {backend:#x} to belong to graph 0")

    endpoints = []
    loggers = []
    volume = []
    for name, expected in EXPECTED.items():
        data = widget_payload(topology, name)
        _, offset = word_tuple(data, 0)
        props, _ = word_tuple(data, offset)
        if (props.get(100), props.get(105), props.get(106)) != (
            CONTAINERS[name], 0xFFFFFFFF, 1
        ):
            raise ValueError(f"{name}: unexpected container ID, parent or heap")
        actual = {}
        for kind, payload in records(data):
            key = kind if kind == CONTROL_LINKS else kind - FIRST_STAGE + 1
            if key in actual:
                raise ValueError(f"{name}: duplicate private record {kind:#x}")
            if key == CONTROL_LINKS:
                actual[key] = verify_control_links(payload)
            else:
                if len(payload) != STAGE_BYTES[key]:
                    raise ValueError(f"{name}: unexpected stage {key} length")
                decoded = tuple(frame_records(payload))
                sequence = tuple((iid, pid, length) for iid, pid, length, _ in decoded)
                endpoints.extend((iid, key, pid, body) for iid, pid, _, body in decoded
                                 if iid in ENDPOINTS and pid in (EP_MEDIA, EP_INTF))
                loggers.extend((key, iid, body) for iid, pid, _, body in decoded if pid == 0x08001031)
                volume.extend((key, iid, pid, body) for iid, pid, _, body in decoded
                              if pid in (VOL_GAIN, VOL_MUTE))
                if key == 1:
                    query = HEADER.pack(0x412B, 0x0800113D, 28, 0) + bytes(32)
                    if payload[8352:8400] != query or payload.count(query) != 1:
                        raise ValueError("unexpected SPR_SESSION_TIME query record")
                    writes = payload[:8352] + payload[8400:]
                    if len(tuple(frames(writes))) != 106 or hashlib.sha256(writes).hexdigest() != (
                        "6b111c9c26fe190a94e1709f650666f25a3afb5c54e7ae1cad6662af5dcf9971"
                    ):
                        raise ValueError("unexpected write-only bootstrap")
                if key in INBAND and sequence != INBAND[key]:
                    raise ValueError(f"{name}: unexpected in-band stage {key} order")
                actual[key] = len(sequence)
        if actual != expected:
            raise ValueError(f"{name}: expected {expected}, got {actual}")
    expected_loggers = [(1, iid, struct.pack('<3I', *cfg)) for iid, cfg in LOGGER_CONFIG.items()]
    if sorted(loggers) != sorted(expected_loggers):
        raise ValueError('unexpected stage or logger configuration in Golden inventory')
    # Bootstrap uses a single all-channel selector, whereas the optional
    # reference final-volume stages explicitly enumerate left and right.
    # Mute word zero here describes the reference artifact, NOT what the
    # native PA-off driver's hard-mute command sends to the DSP.
    expected_volume = []
    for pid, value, stage in ((VOL_GAIN, Q28_UNITY, 7), (VOL_MUTE, 0, 9)):
        expected_volume.extend((
            (1, 0x4669, pid, struct.pack('<4I', 1, 0xFFFFFFFE, 0xFFFFFFFF, value)),
            (stage, 0x4A63, pid, struct.pack('<7I', 8, 2, 0, value, 4, 0, value) + bytes(76)),
        ))
    if sorted(volume) != sorted(expected_volume):
        raise ValueError('unexpected volume stage, target, channel selector or body')
    expected_endpoints = []
    for iid, (stage, rate, bits, index) in ENDPOINTS.items():
        expected_endpoints.extend((
            (iid, stage, EP_MEDIA, struct.pack('<IHHI', rate, bits, 2, 1)),
            (iid, stage, EP_INTF, struct.pack('<III', 2, index, 3)),
        ))
    if sorted(endpoints) != sorted(expected_endpoints):
        raise ValueError('unexpected Golden RX0/VI/CPS endpoint format, interface, mask, or stage')
    print("FullIO v19c: graph 0 matches Golden VI/CPS data paths, 4 control-link declarations, exact logger and volume inventories, and RX0/VI/CPS endpoint formats; 29 modules, 26 edges, 10 stages, 134 frames")


def self_test(topology):
    # Mutate the compiled artifact rather than the decoded output. All
    # replacements preserve record sizes, edge counts and link counts.
    def reject_mutation(name, old, new, expected_error):
        payload = widget_payload(topology, name)
        assert len(old) == len(new) and payload.count(old) == 1 and topology.count(payload) == 1
        mutant = topology.replace(payload, payload.replace(old, new), 1)
        try:
            verify(mutant)
        except ValueError as exc:
            if str(exc) != expected_error:
                raise
        else:
            raise AssertionError(f"accepted corrupted {name}")

    path_error = "Golden VI/CPS data path to protection consumers mismatch"
    reject_mutation("sp11.data_logging.4025", struct.pack("<2I", 209, 0x4024),
                    struct.pack("<2I", 209, 0x4028), path_error)
    reject_mutation("sp11.mux_demux.4029", struct.pack("<2I", 207, 2),
                    struct.pack("<2I", 207, 4), path_error)
    reject_mutation("sp11.unknown_0xe4.4028", struct.pack("<2I", 200, 0x070010E4),
                    struct.pack("<2I", 200, 0x070010E3), path_error)
    reject_mutation('sp11.data_logging.465c', struct.pack('<2I', 200, 0x0700101A),
                    struct.pack('<2I', 200, 0x07001019),
                    'unexpected data-logging module inventory in graph 0')
    reject_mutation("sp11.data_logging.4003", struct.pack("<2I", 209, 0x4157),
                    struct.pack("<2I", 209, 0x4027),
                    "Golden RX0 tap is not between SP and the speaker DMA sink")
    link_error = "Golden control-link peer, port, intent or heap mismatch"
    name = "sp11.speaker_protection.4027"
    for row in GOLDEN_LINKS[:2]:
        a, a_port, b, b_port, intent = row
        old = struct.pack("<9I", a, a_port, b, b_port, 2, 0x08001062, 8, 1, intent)
        reject_mutation(name, old, old[:-4] + WORD.pack(intent ^ 1), link_error)
        reject_mutation(name, old, old[:12] + WORD.pack(b_port ^ 1) + old[16:], link_error)
    for pid, value, changed in ((VOL_GAIN, Q28_UNITY, Q28_UNITY + 1), (VOL_MUTE, 0, 1)):
        prefix = HEADER.pack(0x4A63, pid, 104, 0) + struct.pack('<6I', 8, 2, 0, value, 4, 0)
        reject_mutation('sp11.vol_ctrl.4a63', prefix + WORD.pack(value), prefix + WORD.pack(changed),
                        'unexpected volume stage, target, channel selector or body')
    print('FullIO topology self-test: rejected changed feedback paths, logger MID/RX0 edge, IMCL wiring and final volume')


def retag_rx0(topology, *, log_off=False, feedback_off=False, keep_cps=False):
    if keep_cps and not feedback_off:
        raise ValueError('CPS-only contrast requires feedback logger control')
    rows = {0x4003: (0 if log_off else 0x1586, 4, 1)}
    if feedback_off:
        if not log_off:
            raise ValueError('feedback logger control requires RX0 log off')
        rows[0x4025] = (0, 2, 0)
        if not keep_cps:
            rows[0x402A] = (0, 3, 0)
    result = topology
    allowed = set()
    for iid, config in rows.items():
        header = HEADER.pack(iid, 0x08001031, 12, 0)
        old = header + struct.pack('<3I', *LOGGER_CONFIG[iid])
        new = header + struct.pack('<3I', *config)
        if topology.count(old) != 1 or new in topology:
            raise ValueError(f'logger {iid:#x}: expected one Golden configuration and no diagnostic tuple')
        start = topology.index(old) + len(header)
        if iid == 0x4003:
            allowed.add(start + 4)
        if not config[0]:
            allowed.update((start, start + 1))
        result = result.replace(old, new, 1)
    changed = {i for i, (a, b) in enumerate(zip(topology, result)) if a != b}
    if changed != allowed:
        raise ValueError('audit changed bytes beyond the expected logger code/tag edits')
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topology", type=Path)
    parser.add_argument("--self-test", action="store_true", help="also reject known corrupt variants")
    parser.add_argument('--retag-rx0-out', type=Path, help='write a separate fixture with RX0 tap ID 4')
    parser.add_argument('--rx0-log-off', action='store_true', help='also set only the RX0 logger code to zero')
    parser.add_argument('--feedback-log-off', action='store_true', help='also zero the VI/CPS logger codes')
    parser.add_argument('--keep-cps-log', action='store_true', help='retain the CPS code during feedback logger control')
    args = parser.parse_args()
    if args.keep_cps_log and not args.feedback_log_off:
        parser.error('--keep-cps-log requires --feedback-log-off')
    if args.feedback_log_off and not args.rx0_log_off:
        parser.error('--feedback-log-off requires --rx0-log-off')
    if args.rx0_log_off and not args.retag_rx0_out:
        parser.error('--rx0-log-off requires --retag-rx0-out')
    topology = args.topology.read_bytes()
    verify(topology)
    if args.self_test:
        self_test(topology)
    if args.retag_rx0_out:
        with args.retag_rx0_out.open('xb') as out:
            out.write(retag_rx0(topology, log_off=args.rx0_log_off,
                                feedback_off=args.feedback_log_off, keep_cps=args.keep_cps_log))
