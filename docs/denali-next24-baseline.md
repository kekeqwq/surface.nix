# Denali Gen21 candidate: `next-20261124`

## Upstream and patch audit (2026-11-25)

Official kernel.org tag refs checked before building:

| Candidate | Tag object | Decision |
| --- | --- | --- |
| `v7.3` | `091b06388b117fefdcb63336ac09956a4914b961` | Not a replacement for the tested Next hardware base. |
| `v7.4-rc4` | `a4d7daea71be591034445c17d4d81132a1785a12` | Compared with the Next candidate; the Denali OLED DTS and GENI SPI source differ. |
| `next-20261120` | `2c0da72bad5631bda9c70dcfbe3497a0ebd9f936` | Previous test base. |
| `next-20261123` | `1422acaa190f2daef38ee0b8c50c6ca0fb7f3771` | Intermediate integration tag, not the selected candidate. |
| `next-20261124` | `ecfab21e114b19a8425356b5b7547c471bd6ebb2` | Candidate: same checked display path, new SoundWire allocation bounds/unwind, and retains the Denali/touch/FullIO source after patch reconciliation. |

- GPU/display: compared `a6xx_catalog.c`, `a7xx_catalog.c`, `dpu_hw_sspp.c` and `dp_display.c` across the old Next, new Next and RC4 snapshots; each of those files is identical across the three. The OLED DTS is identical across the two Next snapshots. Keep the local post-training eDP stream-depth patch: its change is absent in all three. Keep the native GPU path, without a compression debug override. The snapshots do not substitute for a hardware modeset test.
- SoundWire: `6c067677192f0` (disable IRQ before gating the clock) was already present. The new `soundwire/next` tip `d9ea256ee889f` introduces a separate output-array bound and rollback of ports allocated by the failed attempt. Retain those upstream semantics as well as the local rule that the last explicitly mapped port is legal (the auto allocator's sentinel is not a port). Reconcile register access with the new peer-aware SoundWire helpers, preserving the checked Offset2 readback. Preserve dependent-controller PM handling and the local Denali admission/quarantine on uncertain clock-stop and resume.
- Touch: the raw HID registration files and GENI SPI source differ. Replayed the ordered SPI-HID/QSPI stack with no fuzz. The added driver, GENI QSPI operations and Denali board wiring are not superseded by these changes. No patch was removed solely because of a matching subject or a line offset.
- ASoC and Denali: the touched raw AudioReach, codec, LPASS, ASoC core and Denali include sources are unchanged between the Next snapshots. Keep the matched v19c topology, paired WSA and VI/CPS lifecycle, and MicArray. Replayed the consolidated source and reran the offline UCM, UKI, PCM ownership/position, clock, PA, GainStep and port-bound checks.

## Git source pin

`pkgs/surface-next.nix` fetches the official `next-20261124` tag with
`fetchgit`, not a snapshot archive. The annotated tag object
`ecfab21e114b19a8425356b5b7547c471bd6ebb2` must peel to commit
`3dd8c790a7b7027abdd568e36db5e82ffaea7c77`; the fetch hook checks both
before Git metadata is discarded. The clean checkout is independently
locked by the recursive SHA-256 hash
`sha256-1NXXoLsXnVT2yu9PvWe9zec5hZeJUo/rtrB9UQW63Qs=`. The Linux tree contains
case-only filename pairs, so a macOS checkout cannot represent all paths and
must not be used to hash it. The hash was measured on the native AArch64
checkout after its tag object and peeled commit matched. Only the source
transport changed; the tag, patch stack, config and module release stayed pinned.

## Deployment boundary

The hardware flake only exposes the normal Denali module and the protected
FullIO module. The Surface host selects FullIO explicitly. No experimental
acoustic monitor, alternate boot fixture, test executable or audio tool is
installed in the system profile. The two desktop services reference only
their exact dependencies. The graph holder uses a runtime FIFO and targets
the internal Speaker sink; the keeper retains the reviewed −3 dB transaction.
Persistent WirePlumber state is separate from Gen20's state.

Gen21 is still a **test** baseline: the existing host-local credential-free
SSH and `sudo -n` remain by request. They must be removed before formal use.
No storage migration, credentials, firmware distribution or change to other
hosts is included.

## Gen21 PCM recovery

The idle test closed the playback PCM and reached SoundWire runtime suspend
with both amplifiers still attached. A fresh PCM reopened and the endpoint
keeper armed it. During the later playback/MicArray run, a subsequent ALSA
PREPARE checked the already-unmuted DSP endpoint against the initial mute
condition. The readback failed, PREPARE detached the runtime DMA buffer, and
a PipeWire write then hit the ALSA missing-DMA warning. This identifies the
failed recovery, not the reason PipeWire requested recovery in the first place.

The repair retires a previously started graph before reusing that PCM file.
It checks both PAs and feedback clocks are off, drains the watermark work,
and requires scoped STOP, last-reference CLOSE and UNMAP before a fresh
muted graph can start. It does not retry an unverified transition; the first
error is latched on that PCM file. The native playback copy and silence
operations reject a missing or out-of-bounds sample buffer without involving
capture or the stock PCM. `tests/fullio-pcm-recycle.py` exercises the actual
replacement and transfer helpers with mocked transport and DMA. The official
refs were rechecked before the native rebuild; `v7.4-rc4` and `next-20261124`
remained the latest mainline RC and listed Next tag, so the kernel pin stayed
unchanged.

The private one-shot (`3v4hgqi9…`) passed three idle-close/reopen rounds with
both amps remaining attached. Each fresh graph armed before a duplex test
captured 192,000 MicArray frames while playing through the Speaker sink. A
separate silent `RW_INTERLEAVED` test filled both periods, used ALSA DROP and
PREPARE on the same fd, and armed both graph epochs. STOP/CLOSE/UNMAP and
clock-off logs were clean. An initial direct-test attempt primed just 480
frames and reported an underrun at START (`hw_ptr=624`, `appl_ptr=480`); the corrected
full-ring test does not explain the first trigger of the original PipeWire
recovery. Neither test establishes actual detach/reattach or long-term
listening stability. The one-shot also verified SSH, greetd/Niri, FL/FR
routing and the hardware Adreno renderer (1024 GLES pixel readbacks).

The same closure passed a 20-cycle desktop playback test and a five-minute
soak (2,880,144–2,880,672 frames per minute on one graph), then became the
regular Gen22 default through `nixos-rebuild switch`. After a real reboot,
three further idle/reopen and 192,000-frame duplex rounds passed. A temporally
matched onboard MicArray spot check found the 997/1499/1997 Hz probe tones
38.0/34.6/37.7 dB above nonmatching windows and sidebands. This corroborates
acoustic output at the test level; it is not calibrated SPL, independent L/R
verification, or listening acceptance. Active volume settings are unchanged.
