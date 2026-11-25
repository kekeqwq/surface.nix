#!/usr/bin/env python3
"""Keep the capture-only CPS PCM open past its usual blocking-read deadline."""
import ctypes as c
import errno
from pathlib import Path
import re
import sys
import time


def main():
    lib, device, filename = sys.argv[1:]
    sound = Path('/sys/firmware/devicetree/base/sound')
    if (sound.joinpath('model').read_bytes().rstrip(b'\0') != b'Denali-FullIO-CPS-Probe'
        or not re.fullmatch(r'hw:\d+,\d+', device)):
        raise SystemExit('Expected the isolated CPS probe and a raw hardware PCM.')
    alsa = c.CDLL(lib)
    alsa.snd_strerror.restype = c.c_char_p
    alsa.snd_pcm_readi.argtypes = (c.c_void_p, c.c_void_p, c.c_ulong)
    alsa.snd_pcm_readi.restype = c.c_long
    alsa.snd_pcm_format_value.argtypes = (c.c_char_p,)
    handle = c.c_void_p()

    def check(step, rc):
        if rc < 0:
            raise RuntimeError(f'{step}: {alsa.snd_strerror(rc).decode()} ({rc})')

    # ALSA: capture=1, non-blocking=1, RW_INTERLEAVED=3.
    check('open', alsa.snd_pcm_open(c.byref(handle), device.encode(), 1, 1))
    try:
        check('prepare', alsa.snd_pcm_set_params(handle, alsa.snd_pcm_format_value(b'S32_LE'),
                                                3, 2, 24000, 0, 160000))
        check('start', alsa.snd_pcm_start(handle))
        start = time.monotonic()
        chunk = c.create_string_buffer(960 * 8)
        frames = 0
        with Path(filename).open('xb') as out:
            while time.monotonic() - start < 3 and frames < 48000:
                rc = alsa.snd_pcm_readi(handle, chunk, min(960, 48000 - frames))
                if rc == -errno.EAGAIN or rc == 0:
                    time.sleep(.005)
                    continue
                check('read', rc)
                if not frames:
                    print(f'First CPS frames after {time.monotonic() - start:.3f}s', flush=True)
                frames += rc
                out.write(chunk.raw[:rc * 8])
        print(f'CPS: {frames} frames received in {time.monotonic() - start:.3f}s before closing')
        return 0 if frames == 48000 else 1
    finally:
        alsa.snd_pcm_close(handle)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError) as error:
        sys.exit(str(error))
