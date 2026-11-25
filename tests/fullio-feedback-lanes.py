#!/usr/bin/env python3
"""Test PA-off feedback-analysis classifications without starting an audio graph."""

from copy import deepcopy
import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile

spec = importlib.util.spec_from_file_location("feedback_samples", Path(__file__).with_name("fullio-feedback-samples.py"))
feedback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feedback)


def window(rate, seed, shape):
    pcm = bytearray()
    for i in range(rate // 100):
        left = i * i + i * seed - 1000
        right = shape(left, i, seed)
        pcm.extend(struct.pack("<ii", left, right))
    return pcm


def check_case(kind, payload, error=None):
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            feedback.inspect(kind, payload)
        except ValueError as exc:
            if error is None or error not in str(exc):
                raise
        else:
            assert error is None, (kind, error)


def main():
    for kind in ('CPS',):
        rate, _ = feedback.TAPS[kind]
        samples = lambda f: b"".join(window(rate, s, f) for s in range(11))
        live = samples(lambda left, i, seed: i * i * (i + seed) + 100)
        check_case(kind, live)
        check_case(kind, live[:-1], "complete 10 ms")
        check_case(kind, bytes(len(live)), "silent, constant, or repeated")
        check_case(kind, samples(lambda left, i, seed: -32768), "silent, constant, or repeated")
        check_case(kind, samples(lambda left, i, seed: left + 123), "copies or inversions")
        check_case(kind, samples(lambda left, i, seed: -left + 123), "copies or inversions")
        check_case(kind, window(rate, 3, lambda left, i, seed: i ** 3) * 11, "silent, constant, or repeated")
    def vi_frames(mutate=lambda components: components):
        return b''.join(struct.pack('<hhhh', *mutate((
            (i * i + seed * i) - 1000,
            (i * i * 3 + seed * i) - 2000,
            (i * i * 5 - seed * i) - 3000,
            (i * i * 4 + seed * i * 3) - 4000,
        ))) for seed in range(11) for i in range(80))

    vi = vi_frames()
    check_case('VI', vi)
    check_case('VI', vi[:-1], 'complete 10 ms')
    for idx in range(4):
        check_case('VI', vi_frames(lambda parts: parts[:idx] + (-32768,) + parts[idx+1:]),
                   'silent, constant, or repeated')
    check_case('VI', vi_frames(lambda p: (p[0], p[1], p[0] + 9, p[3])), 'copies or inversions')
    check_case('VI', vi_frames(lambda p: (p[0], p[1], p[2], -p[1] + 9)), 'copies or inversions')
    check_case('VI', vi[:640] * 11, 'silent, constant, or repeated')
    with tempfile.TemporaryDirectory() as d:
        archive = Path(d) / 'synthetic.bin'

        def packets(tap, base):
            rate = 8000 if tap == 2 else 24000
            for i in range(11):
                size = rate // 100 * 8
                pkt = bytearray(104 + size)
                pkt[0] = 0x10
                struct.pack_into('<HHH', pkt, 2, len(pkt) - 4, len(pkt) - 4, 0x1586)
                struct.pack_into('<II', pkt, 24, i, size)
                struct.pack_into('<I', pkt, 52, tap)
                struct.pack_into('<IHH', pkt, 64, rate, 2, 32)
                yield base + i / 100, pkt

        def check_window(cps_start, window, error=None, *, allow_empty=False):
            records = sorted((*packets(2, .10), *packets(3, cps_start)), key=lambda x: x[0])
            archive.write_bytes(b''.join(struct.pack('<dI', t, len(p)) + p for t, p in records))
            try:
                samples, _ = feedback.decode_archive(archive, window, allow_empty=allow_empty)
            except ValueError as exc:
                if error is None or error not in str(exc):
                    raise
            else:
                assert error is None
                assert all(samples.values()) or (allow_empty and not any(samples.values()))

        check_window(.11, (100, 100.05, 100.25))
        check_window(.25, (100, 100.05, 100.40), 'overlap less than')
        check_window(.25, (100, 100.05, 100.21), 'did not contain both taps')
        check_window(.11, (100, 100.25, 100.05), 'invalid monotonic')
        check_window(.11, (100, 100.01, 100.05), 'did not contain both taps')
        check_window(.11, (100, 100.01, 100.05), allow_empty=True)
        check_window(.25, (100, 100.05, 100.21), 'did not contain both taps', allow_empty=True)
        check_window(.25, (100, 100.05, 100.40), 'overlap less than', allow_empty=True)
        check_window(.11, (100, 100.05, 100.25))
        observed = []
        feedback.decode_archive(archive, (100, 100.05, 100.25), observed)
        binding = {'VI': dict(tap=2, source=0x4026, session=75),
                   'CPS': dict(tap=3, source=0x402b, session=83)}
        records = [dict(graph=1, tap=binding[k]['tap'], session=binding[k]['session'], sha256=h)
                   for k, h in observed]
        evidence = dict(version=1, graph=1, binding=binding, records=records)
        feedback.check_external_decode(observed, evidence)
        for edit in (
            lambda e: e['records'][0].update(session=82),
            lambda e: e['records'][0].update(graph=2),
            lambda e: e['records'][0].update(sha256=e['records'][1]['sha256']),
            lambda e: e['records'].pop(),
            lambda e: e['binding']['CPS'].update(source=0x4026),
        ):
            wrong = deepcopy(evidence)
            edit(wrong)
            try:
                feedback.check_external_decode(observed, wrong)
            except ValueError:
                pass
            else:
                raise AssertionError('accepted an unbound external record')
        def rx_packet(seq, *, energy=False, bits=16, rate=48000, tag=1):
            pkt = bytearray(104 + 192)
            pkt[0] = 0x10
            struct.pack_into('<HHH', pkt, 2, len(pkt) - 4, len(pkt) - 4, 0x1586)
            struct.pack_into('<II', pkt, 24, seq, 192)
            struct.pack_into('<I', pkt, 52, tag)
            struct.pack_into('<IHH', pkt, 64, rate, 2, bits)
            pkt[104] = int(energy)
            return pkt

        for rows, expected in (
            ([(.01, rx_packet(0, energy=True)), (.26, rx_packet(1))], (0, 0, 1, 1)),
            ([(.10, rx_packet(0))], (1, 0, 0, 0)),
            ([(.10, rx_packet(0xffffffff)), (.11, rx_packet(0, energy=True))], (2, 1, 0, 0)),
            ([(.10, rx_packet(0, bits=32))], 'format or payload length'),
            ([(.10, rx_packet(1)), (.11, rx_packet(1))], 'duplicate or backwards'),
        ):
            archive.write_bytes(b''.join(struct.pack('<dI', t, len(p)) + p for t, p in rows))
            rx0 = dict(packets=0, nonzero_packets=0, before=0, after=0, sequence=None)
            try:
                samples, other = feedback.decode_archive(archive, (100, 100.05, 100.25),
                                                         allow_empty=True, rx0=rx0)
            except ValueError as exc:
                assert isinstance(expected, str) and expected in str(exc), exc
            else:
                assert not any(samples.values()) and other == 0
                assert tuple(rx0[key] for key in ('packets', 'nonzero_packets', 'before', 'after')) == expected
        rows = [(.10, rx_packet(0)), (.11, rx_packet(0, bits=32, rate=24000, tag=4, energy=True))]
        archive.write_bytes(b''.join(struct.pack('<dI', t, len(p)) + p for t, p in rows))
        marked = dict(tag=4, packets=0, nonzero_packets=0, before=0, after=0, sequence=None, formats={})
        legacy = dict(marked, tag=1, formats={})
        samples, other = feedback.decode_archive(archive, (100, 100.05, 100.25), allow_empty=True,
                                                 rx0=marked, legacy=legacy)
        assert not any(samples.values()) and other == 0
        assert legacy['packets'] == 1 and legacy['formats'] == {(48000, 2, 16, 192): 1}
        assert marked['packets'] == 1 and marked['nonzero_packets'] == 0
        assert marked['formats'] == {(24000, 2, 32, 192): 1}
        for tag, seq_rates, failure in (
            (1, [(0, 24000)] * 2, 'duplicate or backwards'),
            (4, enumerate(range(24000, 24017)), 'too many observed packet formats'),
        ):
            rows = [(.10 + i * .001, rx_packet(seq, tag=tag, rate=rate))
                    for i, (seq, rate) in enumerate(seq_rates)]
            archive.write_bytes(b''.join(struct.pack('<dI', t, len(p)) + p for t, p in rows))
            marker = dict(tag=4, packets=0, nonzero_packets=0, before=0, after=0, sequence=None, formats={})
            try:
                feedback.decode_archive(archive, (100, 100.05, 100.25), allow_empty=True,
                                        rx0=marker, legacy=dict(marker, tag=1, formats={}))
            except ValueError as exc:
                assert failure in str(exc), exc
            else:
                raise AssertionError(f'tap {tag}: accepted {failure}')
    print('Feedback checks: packed VI/CPS liveness, scoped receipt, external session consistency and RX0/tag 4 separation.')


if __name__ == "__main__":
    main()
