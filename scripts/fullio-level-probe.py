#!/usr/bin/env python3
"""Session-only Denali level logger. Audio stays in pipes; only metrics reach disk."""
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess as sp
import time

SINK = 'alsa_output.platform-sound.HiFi__Speaker__sink'
MIC = 'alsa_input.platform-sound.HiFi__Mic__source'
PCM = Path('/proc/asound/card0/pcm0p/sub0/status')
CAPTURE_PCM = Path('/proc/asound/card0/pcm2c/sub0/status')
RATE = 48000
TONE_STRIDE = 4
TONE_RATE = RATE // TONE_STRIDE
TONE_BLOCK = TONE_RATE // 4
TRANSIENT_FRAMES = RATE // 100  # 10 ms per stereo peak pair


class TransientPeaks:
    """Fixed frame-aligned blocks, independent of pipe and reporting splits."""

    def __init__(self):
        self.frames = 0
        self.peak = [0, 0]
        self.blocks = []

    def add(self, samples, received):
        pos = 0
        count = len(samples) // 2
        while pos < count:
            step = min(count - pos, TRANSIENT_FRAMES - self.frames % TRANSIENT_FRAMES)
            for ch in range(2):
                lane = samples[2 * pos + ch:2 * (pos + step):2]
                self.peak[ch] = max(self.peak[ch], max(lane), -min(lane))
            pos += step
            self.frames += step
            if self.frames % TRANSIENT_FRAMES == 0:
                # This is an upper bound from the PCM pipe, not an ADC
                # timestamp. Multiple blocks can share a receipt time.
                self.blocks.append([self.frames, received, *self.peak])
                self.peak = [0, 0]

    def take(self):
        blocks, self.blocks = self.blocks, []
        return blocks


def tone_basis(freqs):
    return {f: ([math.cos(math.tau * f * i / TONE_RATE) for i in range(TONE_RATE)],
                [math.sin(math.tau * f * i / TONE_RATE) for i in range(TONE_RATE)])
            for f in freqs}


class Levels:
    def __init__(self, basis=None, *, transient=False):
        self.pending = b''
        self.transient = TransientPeaks() if transient else None
        self.basis = basis or {}
        self.cursor = 0
        self.block_frames = 0
        self.block_iq = {f: [[0., 0.], [0., 0.]] for f in self.basis}
        self.clear()

    def clear(self):
        self.frames = 0
        self.energy = [0, 0]
        self.peak = [0, 0]
        self.tone_frames = 0
        self.iq = {f: [[0., 0.], [0., 0.]] for f in self.basis}
        self.block_power = {f: [0., 0.] for f in self.basis}
        self.blocks = 0

    def add_tones(self, samples):
        # Accumulate coherent amplitudes at fixed stimulus frequencies, not
        # spectra or PCM. Preserve phase across chunk and JSONL boundaries.
        start = (-self.cursor) % TONE_STRIDE
        phase = ((self.cursor + start) // TONE_STRIDE) % TONE_RATE
        lanes = [samples[2 * start + ch::2 * TONE_STRIDE].tolist() for ch in range(2)]
        count = len(lanes[0])
        offset = 0
        while offset < count:
            step = min(count - offset, TONE_RATE - phase, TONE_BLOCK - self.block_frames)
            for ch, lane in enumerate(lanes):
                values = lane[offset:offset + step]
                for f, (cs, sn) in self.basis.items():
                    for axis, basis in enumerate((cs, sn)):
                        value = sum(a*b for a, b in zip(values, basis[phase:phase + step]))
                        self.iq[f][ch][axis] += value
                        self.block_iq[f][ch][axis] += value
            offset += step
            phase = (phase + step) % TONE_RATE
            self.block_frames += step
            if self.block_frames == TONE_BLOCK:
                for f, channels in self.block_iq.items():
                    for ch, pair in enumerate(channels):
                        self.block_power[f][ch] += pair[0]**2 + pair[1]**2
                        pair[:] = [0., 0.]
                self.blocks += 1
                self.block_frames = 0
        self.tone_frames += count
        self.cursor += len(samples) // 2

    def add(self, data, *, received=None):
        data = self.pending + data
        length = len(data) // 4 * 4
        self.pending = data[length:]
        samples = memoryview(data)[:length].cast('h')
        self.frames += len(samples) // 2
        if self.transient:
            self.transient.add(samples, received)
        if self.basis:
            self.add_tones(samples)
        for ch in range(2):
            values = samples[ch::2]
            self.energy[ch] += sum(x*x for x in values)
            if values:
                self.peak[ch] = max(self.peak[ch], max(values), -min(values))

    def take(self):
        result = {
            'frames': self.frames,
            'rms_dbfs': [round(10 * math.log10(e / self.frames / 32768**2), 2)
                         if self.frames and e else None for e in self.energy],
            'peak': self.peak,
        }
        if self.transient:
            result['peak_blocks'] = self.transient.take()
        if self.tone_frames:
            result['tone_amplitudes'] = {f: [round(2 * math.hypot(*iq) / self.tone_frames, 2) for iq in channels]
                                         for f, channels in self.iq.items()}
        if self.blocks:
            result['short_tone_amplitudes'] = {f: [round(2 * math.sqrt(p / self.blocks) / TONE_BLOCK, 2)
                                                   for p in channels] for f, channels in self.block_power.items()}
        self.clear()
        return result


def pcm_state(path):
    fields = ('state', 'trigger_time', 'hw_ptr', 'appl_ptr', 'delay', 'avail_max')
    lines = path.read_text().splitlines()
    if lines == ['closed']:
        return {'state': 'closed'}
    return {key.strip(): val.strip() for line in lines
            for key, _, val in [line.partition(':')] if key.strip() in fields}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('closure', type=Path)
    parser.add_argument('log', type=Path, help='new private JSONL file (refuses overwrite)')
    parser.add_argument('--stimulus-tones', action='store_true',
                        help='also save scalar amplitudes at six fixed periodic probe frequencies')
    parser.add_argument('--transient-blocks', action='store_true',
                        help='save 10 ms peak pairs with stream frame indices and pipe receipt times (not ADC timestamps)')
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument('--monitor-only', action='store_true',
                         help='only link the playback monitor; do not open the Surface MicArray')
    sources.add_argument('--mic-only', action='store_true',
                         help='only link the Surface MicArray; do not open the playback monitor')
    parser.add_argument('--direct-mic-80ms', action='store_true',
                        help='diagnostic only: use direct ALSA MicArray (3840/15360-frame geometry)')
    parser.add_argument('--stage-duplex', action='store_true',
                        help='verify three seconds of stable monitor attachment before linking MicArray')
    args = parser.parse_args()
    if args.direct_mic_80ms and args.monitor_only:
        parser.error('--direct-mic-80ms requires MicArray')
    if args.stage_duplex and (args.monitor_only or args.mic_only):
        parser.error('--stage-duplex requires both sources')
    if Path('/run/booted-system').resolve(strict=True) != args.closure:
        parser.error('unexpected boot closure')
    if args.direct_mic_80ms and Path('/run/current-system').resolve(strict=True) != args.closure:
        parser.error('direct probe requires the booted closure to remain current')
    os.umask(0o077)
    running = True

    def stop(*_):
        nonlocal running
        running = False

    for sig in signal.SIGTERM, signal.SIGINT:
        signal.signal(sig, stop)

    capture = {}
    if not args.mic_only:
        capture['monitor'] = (SINK, 'monitor')
    if not args.monitor_only:
        capture['mic'] = (MIC, 'capture')
    pw_capture = {name: route for name, route in capture.items()
                  if name != 'mic' or not args.direct_mic_80ms}
    procs = {}
    basis = tone_basis((203, 206, 449, 454, 1009, 1017)) if args.stimulus_tones else {}
    db = {name: Levels(basis, transient=args.transient_blocks) for name in capture}
    node = f'denali-level-probe-{os.getpid()}'
    volume = None
    next_volume = 0.0
    with args.log.open('x', buffering=1) as out, selectors.DefaultSelector() as sel:
        def write(**fields):
            out.write(json.dumps({'time': dt.datetime.now().astimezone().isoformat(timespec='milliseconds'),
                                  'mono': round(time.monotonic(), 3), **fields}, separators=(',', ':')) + '\n')

        metadata = {'peak_block_frames': TRANSIENT_FRAMES, 'peak_block_clock': 'pipe_receipt_mono'} if args.transient_blocks else {}
        if args.direct_mic_80ms:
            metadata.update(mic_transport='alsa-hw', mic_period_frames=3840, mic_buffer_frames=15360)
        write(event='start', closure=str(args.closure), rate=RATE, sources=list(capture), **metadata)
        try:
            for name in pw_capture:
                procs[name] = sp.Popen(['pw-record', '--target', '0', '-P', f'node.name={node}-{name}',
                                        '--rate', str(RATE), '--channels', '2', '--format', 's16',
                                        '--raw', '-'], stdout=sp.PIPE, bufsize=0)
            # Only connect explicit source ports; never use the default target.
            ports = {f'{node}-{name}:input_{ch}' for name in pw_capture for ch in ('FL', 'FR')}
            for _ in range(25):
                if not ports:
                    break
                listed = sp.check_output(['pw-link', '-i'], text=True, timeout=2).splitlines()
                if ports <= set(listed):
                    break
                if not running or any(proc.poll() is not None for proc in procs.values()):
                    return
                time.sleep(0.2)
            else:
                raise RuntimeError('capture ports not ready')
            held_trigger = None
            if args.stage_duplex:
                state = pcm_state(PCM)
                held_trigger = state.get('trigger_time')
                if not held_trigger or state.get('state') != 'RUNNING':
                    raise RuntimeError('staged attach requires playback already RUNNING')
            for name, (source, kind) in pw_capture.items():
                for ch in ('FL', 'FR'):
                    sp.run(['pw-link', f'{source}:{kind}_{ch}', f'{node}-{name}:input_{ch}'],
                           check=True, timeout=2)
                sel.register(procs[name].stdout, selectors.EVENT_READ, name)
                if args.stage_duplex and name == 'monitor':
                    write(event='monitor-linked', playback_trigger=held_trigger)
                    until = time.monotonic() + 3
                    seen_monitor = False
                    while running and time.monotonic() < until:
                        state = pcm_state(PCM)
                        if (state.get('state') != 'RUNNING' or state.get('trigger_time') != held_trigger or
                                CAPTURE_PCM.read_text().splitlines()[0] != 'closed'):
                            raise RuntimeError('PCM epoch changed or capture opened at monitor attach')
                        for key, _ in sel.select(timeout=.1):
                            data = os.read(key.fd, 65536)
                            if not data:
                                raise RuntimeError('monitor closed during staged attach')
                            seen_monitor = True
                    if not running:
                        return
                    if not seen_monitor or pcm_state(PCM).get('trigger_time') != held_trigger:
                        raise RuntimeError('monitor did not settle on the held playback epoch')
                    write(event='mic-link-request', playback_trigger=held_trigger)
            if args.direct_mic_80ms:
                if pcm_state(CAPTURE_PCM).get('state') != 'closed':
                    raise RuntimeError('MicArray already open before the direct probe')
                procs['mic'] = sp.Popen(['arecord', '-q', '-D', 'hw:0,2', '-t', 'raw', '-f', 'S16_LE',
                                         '-r', str(RATE), '-c', '2', '--period-size=3840',
                                         '--buffer-size=15360', '--fatal-errors', '-'],
                                        stdout=sp.PIPE, bufsize=0)
                expected = {'access: RW_INTERLEAVED', 'format: S16_LE', 'channels: 2',
                            'period_size: 3840', 'buffer_size: 15360'}
                hw_path = CAPTURE_PCM.with_name('hw_params')
                for _ in range(30):
                    if not running:
                        return
                    if procs['mic'].poll() is not None:
                        raise RuntimeError('arecord failed before MicArray was armed')
                    hw = hw_path.read_text().splitlines()
                    if expected <= set(hw) and any(line.startswith('rate: 48000 ') for line in hw):
                        break
                    time.sleep(.05)
                else:
                    raise RuntimeError('unexpected direct MicArray geometry')
                sel.register(procs['mic'].stdout, selectors.EVENT_READ, 'mic')
            write(event='linked')
            last = time.monotonic()
            while running:
                for key, _ in sel.select(timeout=0.2):
                    data = os.read(key.fd, 65536)
                    if not data:
                        if not running:
                            return
                        raise RuntimeError(f'{key.data} capture closed')
                    db[key.data].add(data, received=time.monotonic() if args.transient_blocks else None)
                now = time.monotonic()
                if now - last < 1:
                    continue
                if now >= next_volume:
                    result = sp.run(['wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@'], capture_output=True,
                                    text=True, timeout=2)
                    volume = result.stdout.strip() if result.returncode == 0 else None
                    next_volume = now + 5
                write(elapsed=round(now - last, 3), pcm=pcm_state(PCM),
                      capture_pcm=pcm_state(CAPTURE_PCM), volume=volume,
                      **{name: levels.take() for name, levels in db.items()})
                last = now
        except (OSError, RuntimeError, sp.SubprocessError) as exc:
            write(event='error', error=str(exc))
            raise
        finally:
            for proc in procs.values():
                if proc.poll() is None:
                    proc.terminate()
            for proc in procs.values():
                try:
                    proc.wait(timeout=2)
                except sp.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            write(event='stop')


if __name__ == '__main__':
    main()
