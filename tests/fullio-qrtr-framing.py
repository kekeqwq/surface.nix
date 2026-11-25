#!/usr/bin/env python3
"""Exercise the LPASS data framing helper without QRTR or audio hardware."""

from pathlib import Path
import subprocess
import tempfile


CHECKS = r"""
int main(void)
{
    unsigned char packet[] = {0x7e, 1, 2, 0, 0x7e, 0x22, 0x7e,
                              0x7e, 1, 1, 0, 0x10, 0x7e};
    size_t pos = 0, length, count = 0;

    while ((length = non_hdlc_frame(packet + pos, sizeof(packet) - pos))) {
        pos += length;
        count++;
    }
    assert(pos == sizeof(packet) && count == 2);
    for (size_t n = 0; n < 7; n++)
        assert(!non_hdlc_frame(packet, n));
    assert(non_hdlc_frame(packet, 7) == 7);

    /* Do not recover by scanning for the next delimiter or frame. */
    packet[3] = 0xff;
    assert(!non_hdlc_frame(packet, sizeof(packet)));
    packet[3] = 0;
    packet[6] = 0;
    assert(!non_hdlc_frame(packet, sizeof(packet)));
    packet[6] = 0x7e;
    packet[1] = 2;
    assert(!non_hdlc_frame(packet, sizeof(packet)));
}
"""


def main():
    source = Path(__file__).with_name("fullio-qrtr-lpass-discovery.c").read_text()
    start = source.index("static size_t non_hdlc_frame(")
    end = source.index("\nstatic int capture_taps(", start)
    with tempfile.TemporaryDirectory(prefix="fullio-qrtr-frame-") as tmp:
        src, exe = Path(tmp) / "frame.c", Path(tmp) / "frame"
        src.write_text("#include <assert.h>\n#include <stddef.h>\n" + source[start:end] + CHECKS)
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", src, "-o", exe], check=True)
        subprocess.run([exe], check=True)
    print("LPASS QRTR: batched, truncated and malformed non-HDLC framing tests passed")


if __name__ == "__main__":
    main()
