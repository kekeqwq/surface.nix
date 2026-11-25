#!/usr/bin/env python3
"""Acoustic loopback self-test for the protected Denali render path.

Plays exact-frequency probe tones through the default PipeWire sink and
records the internal MicArray concurrently. If the internal speakers
emit physically, the microphone capture contains narrow peaks at the
probe frequencies, measured with Goertzel filters against neighbouring
bin floors. This verifies real acoustic output without a human listener;
it never replaces the user's listening acceptance.
"""

import argparse
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

RATE = 48000
SEGMENTS = ((997, 1.0, 0.0), (1499, 0.0, 1.0), (1997, 0.7, 0.7))
PRE_ROLL_S = 1.0


def find_tool(pattern):
    import glob
    hits = sorted(glob.glob(pattern))
    if not hits:
        raise SystemExit(f'tool not found: {pattern}')
    return hits[-1]


def build_probe(path: Path, amplitude: float) -> None:
    frames = bytearray()
    for freq, gl, gr in SEGMENTS:
        n = 2 * RATE
        for i in range(n):
            env = 1.0
            if i < 2400:
                env = i / 2400
            if i > n - 2400:
                env = (n - i) / 2400
            v = amplitude * env * math.sin(2 * math.pi * freq * i / RATE)
            frames += struct.pack('<hh', round(v * gl * 32767), round(v * gr * 32767))
    with wave.open(str(path), 'wb') as out:
        out.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
        out.writeframes(bytes(frames))


def goertzel(samples, freq):
    coeff = 2.0 * math.cos(2 * math.pi * freq / RATE)
    s1 = s2 = 0.0
    for value in samples:
        s0 = value + coeff * s1 - s2
        s2, s1 = s1, s0
    power = max(s1 * s1 + s2 * s2 - coeff * s1 * s2, 0.0)
    return math.sqrt(power) / (len(samples) / 2.0)


def analyze(capture: Path):
    raw = capture.read_bytes()
    count = len(raw) // 4
    mono = []
    for i in range(count):
        left, right = struct.unpack_from('<hh', raw, i * 4)
        mono.append((left + right) / 2.0)
    results = []
    for index, (freq, _gl, _gr) in enumerate(SEGMENTS, 1):
        start = int((index * 2 - 2 + PRE_ROLL_S + 0.4) * RATE)
        window = mono[start:start + RATE]
        tone = goertzel(window, freq)
        floor = (goertzel(window, freq - 61) + goertzel(window, freq + 61)) / 2
        snr = 20 * math.log10((tone + 1e-9) / (floor + 1e-9))
        results.append((freq, tone, floor, snr))
    return results


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--work', type=Path, help='directory for probe/capture files')
    cli.add_argument('--amplitude', type=float, default=0.25)
    cli.add_argument('--min-snr', type=float, default=12.0)
    cli.add_argument('--min-tone', type=float, default=5.0)
    args = cli.parse_args()

    pw_play = find_tool('/nix/store/*-pipewire-*/bin/pw-play')
    pw_record = find_tool('/nix/store/*-pipewire-*/bin/pw-record')
    work = args.work or Path(tempfile.mkdtemp(prefix='fullio-acoustic-'))
    work.mkdir(parents=True, exist_ok=True)
    probe = work / 'probe.wav'
    capture = work / 'probe-mic.raw'
    build_probe(probe, args.amplitude)

    record = subprocess.Popen(
        [pw_record, '--rate', str(RATE), '--channels', '2', '--format', 's16', '--raw',
         '-n', str(int((6 + 2 * PRE_ROLL_S) * RATE)), str(capture)])
    try:
        import time
        time.sleep(PRE_ROLL_S)
        played = subprocess.run([pw_play, str(probe)], capture_output=True, text=True)
        if played.returncode:
            raise SystemExit(f'pw-play failed: {played.stdout}{played.stderr}')
    finally:
        record.wait()
    if not capture.exists():
        raise SystemExit('capture missing')

    ok = True
    for freq, tone, floor, snr in analyze(capture):
        passed = snr >= args.min_snr and tone >= args.min_tone
        ok &= passed
        print(f'{freq}Hz: tone={tone:.1f} floor={floor:.1f} SNR={snr:.1f}dB '
              f'{"EMITTED" if passed else "NOT DETECTED"}')
    print('ACOUSTIC LOOPBACK: SPEAKERS EMITTING' if ok else 'ACOUSTIC LOOPBACK: NO OUTPUT DETECTED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
