#!/usr/bin/env python3
"""Check static Denali FullIO speaker/feedback routing in the built DTB.

Names and port numbers are not evidence of physical speaker direction or
active gain. This tool only reads the provided file through fdtget.
"""
from collections import Counter
from pathlib import Path
import argparse
import subprocess


def verify(dtb, fdtget):
    def read_ints(node, prop, kind='x'):
        output = subprocess.check_output(
            [fdtget, '-t', kind, dtb, node, prop], text=True,
        )
        return tuple(int(word, 16) for word in output.split())

    def strings(node, prop):
        data = bytes(read_ints(node, prop, 'bx'))
        if not data.endswith(b'\0'):
            raise ValueError(f'{node}: malformed {prop}')
        return data[:-1].decode('ascii').split('\0')

    def expect(label, actual, expected):
        if actual != expected:
            raise ValueError(f'{label}: expected {expected!r}, got {actual!r}')

    properties = subprocess.check_output([fdtget, '-p', dtb, '/sound'], text=True).splitlines()
    if 'microsoft,denali-fullio-pa-on-smoke' in properties:
        raise ValueError('/sound: withdrawn PA-on marker is not allowed in FullIO fixtures')

    controller = '/soc@0/soundwire@6b10000'
    macro = '/soc@0/codec@6b00000'
    bedais = '/soc@0/remoteproc@6800000/glink-edge/gpr/service@1/bedais'
    wiring = []
    for address, prefix, ports in (
        (0, 'SpkrLeft', (1, 2, 3, 7, 10, 13)),
        (1, 'SpkrRight', (4, 5, 6, 7, 11, 13)),
    ):
        node = f'{controller}/speaker@0,{address}'
        expect(f'{prefix} address', read_ints(node, 'reg'), (0, address))
        expect(f'{prefix} control prefix', strings(node, 'sound-name-prefix'), [prefix])
        expect(f'{prefix} port order', read_ints(node, 'qcom,port-mapping'), ports)
        wiring.append(node)
    wiring.extend((controller, macro))

    def phandle(node):
        value, = read_ints(node, 'phandle')
        count, = read_ints(node, '#sound-dai-cells')
        expect(f'{node} DAI cell width', count, 1)
        if value in (0, 0xffffffff):
            raise ValueError(f'{node}: invalid phandle')
        return value

    handles = [phandle(node) for node in wiring]
    cpu = phandle(bedais)
    expect('distinct WSA path phandles', len(set([cpu, *handles])), 5)
    for link, dai, codec_ids in (
        ('wsa-dai-link', 0x69, (0, 0, 0, 0)),
        ('wsa-vi-dai-link', 0x6a, (1, 1, 9, 2)),
        ('wsa-cps-dai-link', 0x6c, (2, 2, 10, 4)),
    ):
        path = f'/sound/{link}'
        expect(f'{link} CPU backend', read_ints(f'{path}/cpu', 'sound-dai'), (cpu, dai))
        expected = tuple(v for entry in zip(handles, codec_ids) for v in entry)
        expect(f'{link} codec DAI wiring', read_ints(f'{path}/codec', 'sound-dai'), expected)

    routes = strings('/sound', 'audio-routing')
    if len(routes) % 2:
        raise ValueError('odd audio-routing length')
    speaker_routes = Counter(
        (sink, source) for sink, source in zip(routes[::2], routes[1::2])
        if sink in ('SpkrLeft IN', 'SpkrRight IN') or source in ('WSA WSA_SPK1 OUT', 'WSA WSA_SPK2 OUT')
    )
    expect('speaker DAPM routes', speaker_routes, Counter({
        ('SpkrLeft IN', 'WSA WSA_SPK1 OUT'): 1,
        ('SpkrRight IN', 'WSA WSA_SPK2 OUT'): 1,
    }))


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('dtb', type=Path)
    cli.add_argument('--fdtget', default='fdtget')
    args = cli.parse_args()
    verify(args.dtb, args.fdtget)
    print('Denali DTB: ordered left/right speaker routing and RX0, VI, CPS endpoints match Golden.')
