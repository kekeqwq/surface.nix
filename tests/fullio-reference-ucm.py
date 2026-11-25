#!/usr/bin/env python3
"""Guard the reference-render UCM against silent routing regressions.

The critical failure mode found on hardware: a shared Include placed
inside an EnableSequence list is silently skipped, leaving the WSA RX
MUX/INP at ZERO and producing physical silence with every other layer
healthy. This checks the final UCM text for the complete proven routing.
"""
from pathlib import Path
import re
import sys

ucm = Path(sys.argv[1] if len(sys.argv) > 1 else
           Path(__file__).resolve().parent.parent / 'modules/denali/fullio-reference-ucm.conf')
text = ucm.read_text()

# No shared Include inside a sequence list; sequence items must be csets.
for block in re.findall(r'(EnableSequence|DisableSequence)\s*\[(.*?)\]', text, re.S):
    kind, body = block
    assert 'Include.' not in body, f'{kind} contains an Include (silently skipped on hardware)'
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            assert stripped.startswith('cset '), f'{kind} has non-cset item: {stripped}'

verb = re.search(r'SectionVerb\s*\{(.*?)\n\}', text, re.S).group(1)
enable = re.search(r'EnableSequence\s*\[(.*?)\]', verb, re.S).group(1)

# Proven Wsa1SpeakerEnableSeq routing: AIF1_PB feeds both RX MUXes and
# each RX INP0 receives its own DAC lane.
required = [
    ("name='WSA WSA RX0 MUX' AIF1_PB", 'RX0 MUX routing'),
    ("name='WSA WSA RX1 MUX' AIF1_PB", 'RX1 MUX routing'),
    ("name='WSA WSA_RX0 INP0' RX0", 'RX0 input routing'),
    ("name='WSA WSA_RX1 INP0' RX1", 'RX1 input routing'),
    ("name='WSA WSA_RX0 Digital Mute' 0", 'RX0 unmute'),
    ("name='WSA WSA_RX1 Digital Mute' 0", 'RX1 unmute'),
    ("name='WSA WSA_RX0 Digital Volume' 81", 'RX0 ceiling'),
    ("name='WSA WSA_RX1 Digital Volume' 81", 'RX1 ceiling'),
    ("name='WSA WSA_Softclip0 Enable' 0", 'softclip off'),
    ("name='WSA_CODEC_DMA_RX_0 Audio Mixer MultiMedia1' 1", 'render FE link'),
]
for needle, label in required:
    assert needle in enable, f'missing {label}: {needle}'

speaker = re.search(r'SectionDevice\."Speaker"\s*\{(.*?)\n\}', text, re.S).group(1)
for needle, label in (
    ('PlaybackPCM "hw:${CardId},0"', 'FullIO render PCM'),
    ("name='SpkrLeft PA Volume' 24", 'left validated PA gain'),
    ("name='SpkrRight PA Volume' 24", 'right validated PA gain'),
    ("name='WSA WSA_AIF_VI Mixer WSA_SPKR_VI_1' 1", 'left VI source'),
    ("name='WSA WSA_AIF_VI Mixer WSA_SPKR_VI_2' 1", 'right VI source'),
):
    assert needle in speaker, f'Speaker device missing {label}: {needle}'
assert 'DisableSequence' in speaker and 'WSA_SPKR_VI_1' in speaker

mic = re.search(r'SectionDevice\."Mic"\s*\{(.*?)\n\}', text, re.S).group(1)
assert 'CapturePCM "hw:${CardId},2"' in mic
assert "name='TX DMIC MUX0' 'DMIC1'" in mic and "name='TX DMIC MUX1' 'DMIC0'" in mic  # mic enum quoting kept

print('Reference UCM: RX routing, unmute, gain ceilings, Speaker/Mic devices verified.')
