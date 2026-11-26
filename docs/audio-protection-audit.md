# Denali speaker loudness/protection audit

**DIAG interpretation correction.** Historical local observations using
byte 52 as the 0x1586 tap ID cannot establish a tap's presence or absence.
The reference and an unfiltered live census identify byte 60 instead;
see `fullio-audio-acceptance.md`. Where the old collector discarded
records before archiving, an offline decoder cannot recover them.

## Priority

Deferred until the other hardware bring-up tasks are complete, by user request.
Retain present gain caps and the independently bootable desktop; do not run
higher-gain/protection experiments while bringing up touch. External speakers
are the interim option, subject to separate connection-specific testing.

## Scope and current result

Read-only source/document audit. No amplifier limits, kernel sources, firmware
registers, or active protection settings were changed for this audit. All test
playback loops were stopped. The accepted desktop is unaffected.

Our current audio candidate enumerates the internal card and produces audible
output through PipeWire with software mixing and RW_INTERLEAVED access, but the
user reports inadequate loudness even at 100%. This is not usable built-in
speaker acceptance. External audio is an alternative, not yet a tested claim.

### Recovering the previously audible baseline

The 2026-11-19 test was actual user-confirmed speaker output, not a PCM
transport inference: direct ALSA was audible at 11:32 UTC, PipeWire with
`RW_INTERLEAVED` at 11:39 UTC was audible but too quiet, and at 11:43 UTC the
user could hear the material clearly but still judged the level unusable.
The remembered PipeWire candidate is still rooted by
`~/surface-next-build/audio-result` on the Surface, resolving to
`/nix/store/q4pagqn2kjn40adgccnkc8gs3fziz1v0-nixos-system-surface-nixos-26.11.20261119.25f9ec8`
(next-20261118). The active PCM was `hw:X1E80100Microso,0`, stereo 48 kHz
S16_LE, `RW_INTERLEAVED`, period 480 and buffer 3840 frames. The software
mixer and non-mmap rule are retained in `modules/denali/firmware.nix`.
This was the upstream capped topology, **not** FullIO and not evidence that
current FullIO has ever been audible here.

The 2026-11-24 read-only Gen20 check instead showed `Dummy Output` and
both WSA884x probes deferred with `Failed to get reset`, despite a running
ADSP. The normal kernel seed lost `GPIO_SHARED_PROXY` in pruning; FullIO
had separately restored it. Restored the proxy in the stock config (which
already has `RESET_GPIO=m`), removed the duplicate FullIO override and
added both symbols to the kernel regression check. Native stock candidate
build state: `/home/keke/.local/state/surface-stock-audio-apUtlA`.
The verified private one-shot UKI (SHA256
`157fe5395d98ba7ad5a85b6f3541f58d47d2bdd03e97fdf0d88b77a978eb050c`)
booted exact closure
`/nix/store/w4b7b6w5224x2dpvdxk77w7x75wfvyx2-nixos-system-surface-26.11.20261121.56f282a`
on `.137`. Both codecs bound `wsa884x-codec`, PipeWire exposed the speaker
and mic, and SSH/sudo/greetd remained active. Gen20 is still the normal
profile and default; its archived image matched before deployment and the
one-shot variable was consumed.

The initial PCM used `MMAP_INTERLEAVED` despite the Nix rule. An old
profile-only user fragment at `~/.config/wireplumber/wireplumber.conf.d/51-surface-speaker.conf`
shadowed the same-named Nix fragment. Moved just that hash-checked fragment
into the candidate state as `shadowing-user-51-surface-speaker.conf` and
restarted WirePlumber, restoring `api.alsa.disable-mmap` and soft-mixer.
Both PA controls were capped at `6/6` and WSA RX at `81/81`. An 8 s bounded
PipeWire run to `alsa_output.platform-sound.HiFi__Speaker__sink` used
`RW_INTERLEAVED`, 48 kHz stereo S16_LE, period 480 and buffer 3840;
`hw_ptr` advanced 2400→26880, playback returned 0, idle closed the PCM,
and the kernel emitted no entries in the run window. Test WAV SHA256
`b52d4ac63d8e4d33ba832628310bc43a7f62ba5e3e4eec8427d66ce21f2025b9`;
no listener confirmation for this boot. This stock result does not justify
lifting caps or treating it as FullIO acceptance.

OE v12 source `36870b6257fddedc22bee26da89626a5f38f7190` comparison:
`q6apm-dai.c`, `q6apm.c` and `audioreach.c` match the pinned Golden-v32
source overlay byte for byte. The differences in the sampled hardware
files are paired PA-to-macro clock reporting/withdrawal, physical VI
`TOP_CFG1`, and the gated SoundWire Offset2 and CPS wake sequence. OE v12
is an independent bootable packaging target, not an independent PCM
implementation or evidence that current Surface-next render is qualified.

## 1. Primary reference does not claim unrestricted loudness

Reference:

- `dwhinham/archiso-aarch64-sp11`, commit
  `9a50ce3c81e4e17b30adcfc0dd517c19795e89f3`,
  [README](https://github.com/dwhinham/archiso-aarch64-sp11/blob/9a50ce3c81e4e17b30adcfc0dd517c19795e89f3/README.md).
- Kernel reference `dwhinham/linux-sp11`, commit
  `46bb6beace94874a3ec602bfb83e6f87995bc5d0`.

The README explicitly says speakers work but are intentionally volume-limited
because speaker protection is not implemented. Its kernel retains the same
machine-driver speaker caps we have upstream. The premise that this reference
already supplies normal, safely protected loudness is therefore unsupported.

Our existing upstream topology at
`linux-msm/audioreach-topology@993a17dcb672357998a463a73f120064d6c74f4f`
is a basic playback/capture/DisplayPort graph, not the research project's
SP/SPVI/VI/CPS protected graph. Runtime controls in our candidate report both
VISENSE switches and both WSA_AIF_VI feedback switches off. Do not turn these
on arbitrarily: complete transports, DSP graph and calibration must agree.

## 2. Upstream cap is intentional, not a Surface-specific safe-power rating

[Upstream commit 0a5ee0e520eff98ee2b4568194562870877b050f](https://github.com/torvalds/linux/commit/0a5ee0e520eff98ee2b4568194562870877b050f)
limits WSA digital gain to -3 dB and PA gain to 0 dB until active speaker
protection exists or higher safe levels are established. This is a conservative
machine-driver policy across X1E machines, not a calibrated Denali maximum-SPL
specification.

At 100% PipeWire volume we observed stream and sink gain 1.0, unmuted, PA
controls 6/6 (0 dB), WSA digital controls 81/81 (-3 dB). This excludes leftover
attenuation in those inspected software controls. It does not by itself prove
the cap is the sole cause of insufficient loudness, nor certify these settings
as safe under all signals and durations.

Speaker protection must address coil heating and mechanical excursion. An amp
fault/overcurrent mechanism, soft clipping, temperature observation, or the mere
existence of a DSP protection module is not equivalent to a calibrated working
closed-loop speaker-protection system.

## 3. Separate research implementation: relevant but unverified here

Audited repository:
`geocausa/SP11X1e-audio@3232e1dacdeb580a10a9cb8d4756a4518a7bd83e`.
This is an independent research reference, not our primary downstream kernel
reference and not evidence of upstream review or manufacturer certification.

Relevant pinned paths:

- `docs/findings/2026-08-01-SOLVED-loudness-ceiling-upstream-cap.md`
- `docs/audit/2026-08-26-SP11-NATIVE-AUDIO-FULLIO-V19C-AUDIT.md`
- `deploy/native-audio-v19c/README.md`
- `docs/checkpoints/2026-08-24-GOLDEN-V33-PROMOTED.md`
- `repro/native-audio-v19c/build-kernel-initrd-and-verify.sh`
- `repro/golden-v33/build-and-verify.sh`
- `repro/golden-v32/source-overlay/sound/soc/qcom/qdsp6/audioreach.c`
- `patches/0025-sp11-finalize-clean-protected-playback.patch`
- `patches/0038-qcom-cps-readiness-and-protection-gate.patch`

### How it claims to obtain loudness

The August 1 checkpoint removes PA caps and selects PA 24 (reported as +27 dB
by that control scale), retaining digital 81 and enabling soft clipping. This
is an operating point claimed for that author's calibrated/protected setup,
not a value to apply to our present unprotected graph. Later production
checkpoints use a different complete gain/volume lifecycle; the old PA setting
is not a sufficient description of the latest implementation.

The newer v19c stack combines a custom protected AudioReach graph, SP/SPVI
modules, VI and CPS feedback, calibration/config transactions, codec and
SoundWire changes, endpoint-volume lifecycle and the UbiG userspace engine.
It is not a single ALSA profile or a two-patch port: its advertised two-patch
microphone delta is **on top of** the substantial Golden v33/v32 baseline.
Build scripts explicitly reconstruct that baseline first. Their base is Linux
7.1.5; applicability to our next-20261118 snapshot has not been established.

### Evidence provided by that project

The repository reports source/artifact hash gates, Windows/Linux acoustic A/B,
protection-module acceptance, VI feedback/calibration, and a 20-cycle cold
playback soak without PA faults or XRUNs. These are useful investigation
leads, but they are the project's reported tests. We have not reproduced their
build, acoustic measurements, feedback data or stress tests on this machine.
Absence of recorded faults does not establish long-term speaker safety.

### Concrete safety-review concern found in source

In the Golden v32 `audioreach.c` overlay used by the v33 reproduction chain,
`audioreach_configure_protection()` checks VI/CPS readiness. If either is absent,
it disables protection, warns, and jumps to `volume_config` instead of
refusing playback. Patch 0038 describes the same keep-playback-available policy.
The v33 script copies the v32 q6apm module; the v19c script layers microphone
changes on that baseline. Thus this is not merely a random rejected historical
patch when following that pinned reproduction chain.

This demonstrates a protection-bypass branch, not that it executes in the
project's successful playback tests. It also does not prove the effective amp
gain in every failure path. However, importing a raised PA ceiling without
establishing a conservative fallback or fail-closed high-gain policy would be
unacceptable. The whole lifecycle must be checked, not only startup PASS logs.

## 4. Investigation gates before any higher-gain experiment

1. Reduce reference changes to a dependency map against next-20261118; mark
   upstreamed/redundant changes and distinguish diagnostics from runtime code.
2. Audit provenance/licensing of topology, calibration and source overlays.
   Per-unit R0/T0 calibration from another machine is not our calibration.
3. Build a separate low-gain candidate that adds only required feedback and
   protection plumbing, keeping current caps and the known-good desktop UKI.
4. Validate physical VI/CPS sample order and liveness, DSP protection state,
   calibration matching, mute/idle transitions and runtime-PM teardown.
5. Validate missing/stale feedback, failed calibration and failed DSP commands
   cause safe behavior: no unprotected high-gain playback. Require a physical
   test/recovery plan before introducing such failure tests on real hardware.
6. Establish device-specific operating limits using reliable electrical,
   thermal and acoustic evidence before considering a bounded gain change.
   Do not use subjective loudness or another repository's PA number as a limit.

No higher-gain candidate has been implemented or tested. Suspend/resume,
long-duration behavior, safe maximum SPL and protected loudness remain open.

## Surface-next FullIO port

`packages.aarch64-linux.fullio-capture-kernel` is a compile-only target based
on our pinned `next-20261120`, not a replacement kernel for the installed
system. `pkgs/patches/sp11-fullio-next-capture.patch` adapts the reference's
production capture patches 0072 (VA DMIC divider) and 0078 (VA/TX clock broker).
It changes no speaker gains and is not in the normal Denali patch queue. The
first capture-code-only kernel compiled on Surface. This target now also
restores `GPIO_SHARED_PROXY` in its own config and includes
`pkgs/patches/sp11-fullio-capture-dt.patch`. That patch's test DTB
compiled with `dtc` and resolved `TX_CODEC_DMA_TX_3`, enabled the TX macro and
set the VA clock request to 4.8 MHz. The existing VA link remains present to
register the clock provider. The combined kernel also built on Surface; its
OLED DTB contains `TX DMIC Capture` and its modules include the shared GPIO
proxy and its auxiliary bus alias. It is not a complete runtime configuration.

`packages.aarch64-linux.fullio-reference-topology` compiles the pinned v19c
source and requires byte identity with the reference; that Nix build passed
on Surface. The artifact is not installed in the firmware search path. A
runtime candidate must match the MicArray UCM routing and protected render
links, not just the capture code and clock setup. The
reference protection patch 0038 does not apply to Surface-next; it depends on
Golden baseline Q6APM/AudioReach, SoundWire and machine-driver changes. Port
these and validate a conservative fallback before exposing the speaker path.
Do not substitute the reference DTB or initrd for our working Denali UKI.

The next feedback layer is staged as `sp11-fullio-q6-feedback.patch` and
`sp11-fullio-machine-feedback.patch`. The corresponding ARM64 objects compiled
against the Surface-next capture-test headers. TX0 VI and TX1 CPS declare the
reference stream formats (8 kHz and 24 kHz respectively, two-channel S32),
and the Denali machine driver no longer negotiates those two backend IDs as
ordinary 48 kHz streams. Neither patch is in an active kernel queue yet.
They do not establish feedback liveness, change amplifier caps, or issue
protection calibration transactions. The WSA884x/LPASS codec DAIs and physical
SoundWire feedback transport are still required before wiring these paths.
`sp11-fullio-wsa-macro-feedback.patch` ports the LPASS-side endpoints and
`sp11-fullio-sdw-simple-feedback.patch` allows a codec to opt in to the extra
SIMPLE-port registers and a per-slave OffsetCtrl1. Both ARM64 objects compile;
no existing port uses the new SoundWire properties. The compile-only
`fullio-feedback-kernel` also includes `sp11-fullio-wsa884x-feedback.patch`:
per-DAI SoundWire runtime tracking and opt-in DP5/DP6 source ports. The codec
object compiled on Surface against the adapted SoundWire header. No board node
opts in yet. `sp11-fullio-qcom-feedback.patch` compiles
on Surface and schedules these companion playback DAIs as physical SoundWire
inputs. It checks both source ports, coalesces the two CPS sources into one
DP13 master port, and does not reserve ports on a failed setup. The board
fragment `sp11-fullio-feedback-dt.patch` compiles on top of the capture DT
and resolves the VI and CPS link references to the expected IDs.

Do not enable that board fragment yet. The reference also has controller
packetization and wake changes and a custom DSP topology parser (integrated
backend, control-link and calibration records), which are not part of the
scheduler patch. Declaring a pair of endpoints is not proof that calibration
and live feedback are working.

`sp11-fullio-dsp-parser.patch` adds bounded parsing for both ALSA vendor tuples
and the shipped FullIO raw records. The actual v19c binary carries a 16-byte
FullIO record header, including two reserved words. Treating it as an 8-byte
header misaligns the next record. Existing AudioReach module config records
also use a 16-byte header; only FullIO requires those reserved words to be zero. An offline test of the C parser
accepted all 36 baseline widgets, framed all 38 FullIO widgets, and rejected
truncation in each of the four FullIO widgets containing private payloads.
The ARM64 topology object also compiled. `sp11-fullio-dsp-ctrl-links.patch` stages the bounded `GRAPH_OPEN` control-link
list serializer; both AudioReach and topology objects compiled on ARM64.
`sp11-fullio-dsp-containers.patch` adds parent/heap serialization while
retaining the existing wire layout for ordinary containers. The kernel
objects compiled on ARM64. `tests/fullio-topology.py` checks the shipped
artifact's parent/heap values, 10 calibration stages (134 frames), and four
control links; the reference topology package runs this check after verifying
byte identity. The same check verifies that FullIO frontend graph 0 owns the
speaker RX0, VI and CPS backend DAIs. `sp11-fullio-dsp-ownership.patch` parses
that token and rejects ambiguous ownership and premature backend graph setup.
The related ARM64 objects compiled on Surface.

Surface-next already supplies generic PCM pull-mode ring mapping, position
tracking and watermark registration. Reuse that infrastructure instead of
replacing it with the 7.1.5 reference driver. FullIO widgets remain blocked
with `-EOPNOTSUPP`: the frontend must still own FullIO-specific event setup,
ordered calibration and the fail-closed protection transaction. The
`sp11-fullio-dsp-graph-lifecycle.patch` makes `GRAPH_OPEN` wait for a successful
DSP acknowledgement before another owner can acquire the graph, and rolls back
the software reservation on failure. Its ARM64 object compiled. The offline
artifact test also distinguishes in-band calibration frames from OOB blobs
and rejects out-of-order SPVI frames. Neither check is DSP acknowledgement or
measured VI/CPS feedback on hardware.

`sp11-fullio-feedback-lifetime.patch` publishes VI/CPS transport enablement
per APM device only after a real SoundWire runtime is enabled, not when the
helper merely succeeds with no runtime. Both paths are cleared before hardware
free or shutdown. The machine and Q6APM ARM64 objects compiled. This state is
necessary for calibration, but it does not prove sample liveness or authorize
a gain increase.

`sp11-fullio-dsp-oob-map.patch` adds a separate token-matched map/unmap path
for caller-owned calibration DMA memory. It requires the actual nonzero DSP
map handle and marks a region unusable on an uncertain map or unmap result;
a caller must not free or reuse such a region until the DSP is reset. The
ARM64 object compiled. An offline test of the callback rejected stale or
duplicate responses, a truncated map reply and a failed unmap; a generic
successful response was insufficient to complete a map.

`sp11-fullio-dsp-fe-dma.patch` adds the PCM frontend owner. Only the identified
Denali pull-mode graph with both transports enabled can claim its 16 KiB
calibration buffer; unsupported SCM DMA configurations fail without mapping.
The ARM64 PCM object compiled. Offline fault injection verified that an
acknowledged unmap frees memory, while a timeout or an already-poisoned map
retains the buffer and device reference with one slot occupied. There is no
reset-assisted reclaim yet. No calibration is sent: even after a successful
map the test path unmaps and refuses playback, and the FullIO topology gate is
still enabled.

`sp11-fullio-dsp-cal-transport.patch` adds bounded in-band and OOB `SET_CFG`
packing with token-matched confirmation. It refuses missing transports,
invalid frame lengths or a poisoned buffer; a failed OOB command quarantines
that region. The ARM64 object compiled. Tests accepted the real 10,464-byte
v19c bootstrap blob only as an aggregate and rejected a wrong mode, nonzero
frame status, truncation and oversized data. No active code calls either
submission helper. The reference sends bootstrap before feedback setup;
verifying which ordering the DSP accepts with a muted, capped output is a
separate hardware gate, not a reason to bypass feedback on failure.

`sp11-fullio-dsp-stage-index.patch` collects all ten stages by owner and length.
`sp11-fullio-dsp-fe-preflight.patch` requires a complete profile and common
RX0/VI/CPS graph ownership before allocating a DMA buffer. ARM64 objects
compiled; a mock graph accepted the complete profile and rejected a missing
stage, a duplicate, a wrong owner and a wrong length without publishing a
partial profile. `sp11-fullio-dsp-companion-backends.patch` lets the three
matching Denali playback backends remain transport-only: the machine and codecs
handle SoundWire while none of those DAIs opens, configures, starts or closes
the frontend DSP graph. The LPASS object compiled; the topology gate is still
closed. No playback or calibration command was issued.

`sp11-fullio-dsp-readback.patch` adds the two pinned SP/SPVI `GET_CFG` queries.
It requires a token-matched readback with exact module, parameter, length and
success statuses, not just a basic acknowledgement. The ARM64 object compiled.
An offline test of the C reply parser accepted both captured reference replies
(92 and 68 bytes including headers) and rejected wrong targets, bad status and
truncation without copying unvalidated data. Configuration readback is not
proof of live feedback, and no hardware path calls these helpers yet.
`sp11-fullio-dsp-verify-tag.patch` additionally compares the readback body to
the first calibration frame in the corresponding tag stage. The pinned
reference captures match these 68-byte and 44-byte values exactly; a success
status with different contents would fail. The ARM64 AudioReach object
compiled. No real DSP requests were issued for this check.

`sp11-fullio-dsp-cal-sequence.patch` sequences the 11 bootstrap, dynamic, tag
and endpoint operations (including both readbacks). It excludes protection
enable, gain, unmute and graph start. A mock using the reference dynamic frames
verified the sequence and forced failure and transport loss at each step;
there was no fallback. A separate hard FullIO graph-start gate remains.
`sp11-fullio-wsa884x-pa-readback.patch` adds a cache-bypassing PA-off check;
it and the DSP sequence compile on ARM64. The earlier calibration-transport
integrated build exited 0.

`sp11-fullio-dsp-muted-preflight.patch` hooks the sequence into the experimental
FE path while the topology gate remains closed. The two WSA Playback codecs
must both read PA-off before allocation, before each operation and after the
last one. The FullIO feedback codec rejects normal unmute; successful diagnostic
calibration still refuses render, and FullIO GRAPH_START remains denied.
The changed ARM64 objects compiled; this has not executed on hardware. The
integrated build is queued in `~/.local/state/fullio-muted-RvmrVl`.

The separate `nixosModules.fullio-muted` fixture selects the muted kernel,
adds VI/CPS links and an explicit topology-parser opt-in to the existing
Denali OLED device tree, and installs the hash-verified FullIO reference
binary under its own firmware name. WirePlumber defaults this card to off;
use controlled ALSA tests before assessing desktop enumeration. The default
module and Gen18 are untouched. A full `flakes#surface` toplevel evaluated
with the fixture added via `extendModules`. The kernel/topology and system
builds are queued in `~/.local/state/fullio-fixture-DNyMnp`; no ESP write or
boot was attempted. The existing UCM is not yet validated for this topology.

The sequence-only kernel built successfully. For the muted fixture,
`scripts/prepare-fullio-uki.py` stages and verifies a UKI off the ESP after the
closure build, using the known-good Denali command line with only `init=`
replaced. The running closure and FAT destinations are rejected; no loader
entry or EFI variable is written. The active Gen18 command line passed the
prerequisite checks. Private staging is queued behind the fixture build.

After a successful one-shot boot, check `/proc/asound/cards` and
`/proc/asound/pcm` first. Locate the `MultiMedia3 Capture` hardware PCM rather
than assuming card 0; record a short two-channel clip only on request, inspect
both channels independently, and keep the recording private. After the user
is ready to record, use the exact native format from v19c:

```sh
device=$(python3 tests/fullio-micarray.py) || exit 1
work=$(mktemp -d "${XDG_RUNTIME_DIR:?}/fullio-micarray.XXXXXX") || exit 1
arecord -D "$device" -f S16_LE -r 48000 -c 2 -d 5 -t wav "$work/mic.wav" &&
  python3 tests/fullio-micarray.py "$work/mic.wav"
```

The validator checks channel activity, exact duplication (including inversion),
and reports clipping. Synthetic distinct/silent/duplicated/inverted input
cases passed their expected checks; this is not timing, physical routing,
or clarity validation. An ALSA card with the WirePlumber profile off does not
imply a Waybar source or sink.

The rebuilt fixture topology passed the byte hash and structure checks on
Denali. Source review also confirms that Surface-next DPCM prepares backends
before the frontend; the FE can check the transport bits at `prepare`, but
it still needs evidence that both VI and CPS routes actually prepare. One
remaining reference parity difference is explicit: the reference configures
PCM_CNV `0x465f` and MFC `0x466a` (48 kHz/16-bit/stereo) before protection
`SET_CFG`. The current muted FE diagnostic enters calibration before those
commands. Keep it silent, check the DSP acknowledgements, and port that exact
media-format prelude before any render decision. Do not indiscriminately send
playback media parameters to all the integrated feedback modules.

First one-shot boot: fixture kernel and Denali FullIO sound-node model verified
on hardware. GPIO shared proxies are bound. ALSA enumerates an `x1e80100` card,
`MultiMedia1 Playback` and `MultiMedia3 Capture` (`hw:0,2`); WirePlumber sees
`alsa_card.platform-sound` without a managed speaker or mic node because the
profile is off. Early probing logged missing graph 0; ALSA enumeration does
not prove either graph opens after probe or that samples flow. With the
profile off, the first raw capture open returned `EINVAL` because no backend
was routed. Temporarily enabling only the TX MicArray route (DEC0 ← DMIC1,
DEC1 ← DMIC0, TX_AIF1, MultiMedia3 → TX_CODEC_DMA_TX_3) yielded 240,000
stereo frames at 48 kHz/S16_LE. Channels were active and distinct, with
AC RMS 52.16/50.74 and zero clipped frames. Mixer values were restored and
the clip stayed under the local runtime directory. Capture clarity and
physical channel assignment are not yet confirmed. No calibration was run;
startup logs show playback `GRAPH_OPEN` rejected by the DSP (status `0x18`).

`modules/denali/fullio-mic-ucm.conf` now defines only the verified TX MicArray
route. The experimental module overrides the Surface 11 UCM include without
loading the standard speaker and WSA initialization. On the booted fixture,
`alsaucm` loaded a private copy, listed only `Mic`, enabled and disabled it,
and resolved capture to hardware PCM 2; the FE mixer returned to `off,off`.
WirePlumber's active service was not changed and the fixture profile remains
off by default; this does not yet verify a Waybar capture node.

The pinned playback topology supplies 29 modules and 26 unique module edges,
including `0x4660:1 → 0x465c:2`. The v19c source avoids adding a second
mixer edge for an internal link. `sp11-fullio-graph-dedup.patch` differs from
the reference's blanket same-graph skip: it suppresses the mixer edge only
when all four endpoints match a serialized module edge, using the same
predicate for packet size and serialization. ARM64 compilation passed. The
offline topology test now verifies the inventory and rejects cross-graph
endpoints. This does not show which bytes the current DSP rejected, or prove
deduplication fixes `0x18`. The next muted kernel, capture-only UCM and private
UKI built under `~/.local/state/fullio-dedup-jfVvDd` and booted one-shot. ALSA
still enumerates both PCMs; WirePlumber exposes a two-channel
`alsa_input.platform-sound.HiFi__Mic__source`. No speaker node was exposed.

With only the physical playback FE mixer routed, the open-only v2 probe
succeeded (no data written, no prepare or trigger), so the previous DSP
`GRAPH_OPEN` rejection did not recur. The first params/prepare probe failed
at `SPKR_VI` with `-ENODEV` when VISENSE/CPS controls were off. Temporarily
enabling only those feedback controls on both codecs got through backend
hw_params into FE prepare, where the DSP rejected the ordinary media-format
`SET_CFG` (status `1`) before calibration. Restore all altered controls after
the probe. Next, use the v19c PCM_CNV/MFC prelude instead of applying the
ordinary PCM media-format walk to the integrated FullIO playback graph. No
samples went to the speakers and no calibration success was observed in v2.

V4 reached calibration and quarantined its DMA slot after `EIO`. V5
(`fullio-trace-QS3wkB`) confirmed PCM_CNV/MFC and map acceptance, then a DSP
`0x3` rejection of the original bootstrap `SET_CFG`. The pinned reference
isolates frame 63 (offset 8352, IID `0x412b`, PID `0x0800113d`) as GET-only
SPR_SESSION_TIME. The v19c source aggregate and the variant without that exact
48-byte record match both recorded SHA-256 values; all 106 writes are retained.

V6 (`fullio-write-only-USvCwS`) booted one-shot and accepted both media
commands, the write-only bootstrap, all later calibration operations, and the
SP/SPVI byte-for-byte readbacks on Denali. The driver checked both physical
PAs off throughout and explicitly returned `-EOPNOTSUPP` after logging muted
calibration success. No trigger or audio data was sent. The restored playback
mixer was off, and the WirePlumber stereo MicArray source remained enumerated.
This does not establish live VI/CPS samples or authorize speaker release.

The sample probe must observe the DSP source outputs, not just the SoundWire
master: the reference identified tap 2 after `CODEC_DMA_SOURCE 0x4026` (VI,
8 kHz), and tap 3 after `0x402b` (CPS, 24 kHz). Earlier Golden Linux runs had
transport enabled but no samples at those taps even under audible render.
`tests/fullio-feedback-samples.py` checks stripped stereo S32 payloads for
varying data on both lanes. Offline distinct, all-zero, dead-lane, replay and
truncation tests passed. A live collector must additionally validate tap
identity, timing and association with the current stream; the offline test
cannot establish those. A PA-off zero baseline does not by itself disprove
feedback under a real load. Do not enable the reference forced-tap boot
services or call a muted/empty probe a speaker acceptance result.

The offline checker also accepts bounded reference-style `0x1586` datagram
archives and checks tap ID, exact length, PCM metadata, timestamps and DSP
sequence order before admitting samples. The published Linux archive yielded
391 non-feedback audio packets and zero VI/CPS packets, while the two older
CPS diagnostic archives yielded none. Synthetic VI/CPS inputs passed and
truncated, wrong-rate and replayed packets were rejected. The Denali boot
has the ADSP `IPCRTR` transport; that is not confirmation of an available DIAG
endpoint or proof that the current topology produces tap 2/3. No live DSP
logging has been enabled and no firmware mask or render gate was changed.

`tests/fullio-qrtr-discovery.c` queried the v6 local QRTR name server without
opening a DIAG session. Node 5 advertised services, but not the reference
collector's ports 45/46. This does not rule out unadvertised raw ports. Do not
send control or mask commands to guessed endpoints. The topology test now
confirms both source-to-logger edges (`0x4026 → 0x4025`, `0x402b → 0x402a`)
and their exact `0x1586` tap IDs in the acknowledged bootstrap. The unresolved
pieces are log delivery or an isolated host capture path, followed by sample
validation; replacing the production logger settings is not justified yet.

`scripts/build-fullio-feedback-probe.py` generates two isolated capture-only
ALSA topologies from pinned v19c. Each retains the known host read-shared-memory
capture path, substitutes only one WSA source (`TX_0`, VI at 8 kHz, or `TX_1`,
CPS at 24 kHz, both stereo S32_LE), and has no render PCM or protection graph.
Both compiled and decoded on Denali with the expected caps; `alsatplg` warned
about the external CPU DAI widget names. These offline outputs are not wired
into any firmware path. Runtime requires a separate explicit fixture:
WSA884x feedback DAIs currently advertise only ASoC playback-companion mode,
and the CPU capture caps omit 24 kHz. Do not switch the shared/default
directions or relax the physical PA gate to exercise this capture path.

`fullio-feedback-probes` now builds both hash-checked artifacts natively with
Nix, with no firmware path. The experimental kernel queue contains
`sp11-fullio-feedback-capture-fe.patch`: only an explicit muted Denali sound
node with the `vi` or `cps` probe marker can open capture graph 2 at its
respective exact rate, S32_LE, stereo. That marker refuses playback opens
before DSP graph creation. The ARM64 FE object compiled; no current DT sets
the marker. `sp11-fullio-feedback-capture-backends.patch` stages matching CPU,
codec, LPASS and SoundWire capture support. The SoundWire master reuses the
existing two-speaker slave-to-master allocator only when the controller flag,
muted sound-node marker, capture direction and selected VI/CPS DAI all match.
Without those device-tree markers, the companion playback path is unchanged.
All four changed ARM64 objects compiled. `nixosModules.fullio-feedback-vi`
and `.fullio-feedback-cps` now select distinct OLED DTBs and matching
capture-only firmware names. Each DTB contains only its selected feedback
link, no WSA Playback link, and opts into the guarded capture allocator;
WirePlumber does not auto-open the card. FE prepare verifies hardware PA-off
on both codecs through that link. Both complete system configurations
successfully evaluated; builds and private UKI verification are staged in
`~/.local/state/fullio-probe-system-5qhvw8`. The first VI probe boot reached
SSH and Niri at native eDP 2880 × 1920/120 Hz, but the user reported a black
screen with only a thin top line. The ALSA card did not register; ASoC refused
inherited DAPM routes that still referenced the removed TX/VA microphone
widgets. There was also one APM GET_SPF_STATE timeout; do not assume route
cleanup will resolve it or the visible screen symptom. The probe module now
builds a separate DTB source that drops inherited `audio-routing` and verifies
the single selected feedback child and model. Both corrected closures and
private UKIs built in `~/.local/state/fullio-probe-dapm-EWkmF8`, reusing the
same kernel. The corrected VI fixture registered ALSA with only capture PCM 2.
At native 8 kHz/S32 stereo, after enabling only the VI capture route, APM
rejected backend 106 `GRAPH_START` with status 1 before any host samples.
The temporary mixer controls were restored. The ordinary CODEC_DMA media
walk declares aligned body sizes, whereas the v19c endpoint records use
actual 4/12-byte parameter sizes with padding outside them. The new
`sp11-fullio-probe-native-endpoint.patch` ports the five pinned endpoint
records for the exact probe graph and codec module only, retaining DSP
acknowledgement and logging it. Both changed ARM64 objects compiled; the
next fixtures are building in `~/.local/state/fullio-probe-native-tIQE8b`.
The native-endpoint VI fixture booted one-shot and logged acceptance of the
five endpoint records. With both PAs locked off, `arecord` completed 16,000
stereo S32_LE frames at 8 kHz, but every sample on both lanes was `0x80008000`.
This proves the isolated host transport advances, not live VI; the constant
signal was correctly rejected by the checker. Playback did not exist on the
fixture and mixer values were restored. CPS remains untested.

Live trace on the native-endpoint VI fixture disconfirmed the missing-prepare
hypothesis. `tests/fullio-trace-soundwire.sh` observed the machine helper,
`sdw_prepare_stream` and `sdw_enable_stream` (both returned 0), WSA884x port
callbacks, and the LPASS VI DAPM callback. Disable and deprepare also returned
0. The repeated 16,000-frame capture remained constant `0x80008000` on both
lanes. The sysfs `words`/`channels` entries describe advertised capability
arrays, not the live bank state or sample delivery. Do not deploy the retired
extra controller `.prepare` build: it duplicates the machine's job. These
results demonstrate a working stream lifecycle with the PAs off, not valid
feedback under real speaker load.

The native-endpoint CPS fixture booted one-shot and registered only capture
PCM 2. The DSP acknowledged the CPS endpoint settings, but two native
24 kHz/S32_LE stereo reads returned `EIO` before producing any bytes.
This is distinct from VI's completed constant capture. The next bounded trace
includes SoundWire lifecycle, graph start, and the DSP read submissions to
locate the failure; the speaker gate remains closed.

The CPS trace showed SoundWire prepare/enable and both graph starts return
0; four FE read commands were submitted before the BE start. 40, 80, and
120 ms periods failed alike. The `fullio-cps-first-WGj22Y` one-shot then
confirmed the CPS source starts before FE reads, but still returned `EIO`
and zero bytes. Starting the source first is insufficient. The next trace
records GPR response opcodes/tokens (no payloads), to distinguish absent read
completions from rejected or mismatched replies. Unprivileged `strace`
confirmed native ALSA `PREPARE` succeeds and the kernel's `READI_FRAMES`
returns `EIO`; this is not an `arecord` format or output-file error. The
kernel PCM wait path uses `EIO` for no available period before the timeout.
The GPR trace saw all four `READ_DONE` tokens (0–3), but only after
SoundWire disable/deprepare began; no completions were seen during capture.
A nonblocking run (`tests/fullio-cps-nonblock.py`) kept ALSA running for a
full three seconds and still received zero frames. A longer ALSA deadline
cannot explain the result. These late packets are consistent with teardown
completions; their status/byte count was not captured. Investigate the CPS
source wake/packetization path without changing gain or enabling either PA.

`nixosModules.fullio-feedback-cps-wake` is a separate A/B fixture for the
reference's two WSA controller wake/DP13 packetization settings. It requires
an additional device-tree marker, saves the two original settings, verifies
readback of both diagnostic values, and attempts restoration on teardown,
logging any restore failure. Ordinary CPS, VI, and render fixtures do not
opt in. The ARM64 object compiled; the closure and private UKI are building
under `~/.local/state/fullio-cps-wake-UuYgaI`. A prior reference run observed
more CPS packets with these settings but not real samples; do not treat
wake, packet counts, or accepted readback as sample liveness. On Denali the
wake variant did restore period delivery: first samples at 47 ms and 48,000
stereo frames in 2.003 s at 24 kHz, but both lanes were entirely zero with
both PAs off. The kernel verified both programmed registers. This resolves
the no-period symptom, not feedback liveness.

The reference's nonzero CPS test also required active Offset2 and protection
clocks sequenced after both PAs report up. `fullio-feedback-cps-offset2`
builds a separate A/B variant that adds only the active DP13 Offset2 change
with readback; neither PA can be enabled by this capture fixture. It is
built under `~/.local/state/fullio-cps-offset-WAEJbn` and booted one-shot.
The driver verified wake plus active DP13 Offset2=0; 48,000 frames arrived,
first at 41 ms, but all samples were zero on both channels. This measures the
PA-off baseline, not the reference's full post-PA condition.

The reference's post-PA test is a separate condition, not an instruction to
copy the WSA start tables or raise gain. Its patch 0069 counts two PA-up events
with global state and assumes ordering at a mixer callback. The local port
must instead track distinct codecs on the same card, verify actual PA state,
and clear clock permission at the first teardown or fault. Keep the DSP
output hard-muted during any such diagnostic; valid VI and CPS are separate
from clock or command success. Do not enable the clock earlier to manufacture
a positive sample result. The feedback archive checker now supports the
reference's 1 ms forced Linux frames and 10 ms Windows frames; synthetic
cases for both passed, while a cadence change in the same tap was rejected.

`sp11-fullio-wsa884x-diagnostic-pa-state.patch` adds a cache-bypassing
PA snapshot of `PA_FSM_EN`, `STA0` and `STA1`. The enable register is read
before and after the status registers; errors, detach and a changing enable
value abort the snapshot without publishing it. The existing PA-off guard
uses this read-only helper. The ARM64 codec object compiled; no current
candidate uses these values to enable clocks, release mute, or declare PA-up.

`sp11-fullio-checked-protection-clocks.patch` stages the WSA macro TX0–TX3
protection-clock transaction for a future explicit post-PA fixture. It
requires a readiness callback before and after enabling, validates masked
hardware readback, and attempts shutdown on all four lanes if any step
fails. The normal DAPM path is unchanged unless the new marker is set.
The ARM64 object compiled and extracted C tests covered masked readback,
early enable failure, and exhaustive teardown. The new API has no caller,
DT opt-in, or runtime proof; retain PA and DSP render lockout.

`sp11-fullio-dsp-hard-mute.patch` adds one fixed final `VOL_CTRL` command
for both FL and FR after the accepted calibration stages, with hardware
PA-off snapshots before and after and a token-matched DSP acknowledgement.
The pinned topology's original mute-stage packet has both mute values zero;
we construct an explicit `1` for each lane instead, with no unmute or gain
command. Keep the capture/feedback and render gates separate. An ACK is not
an acoustic measurement or DSP readback. The muted-only system and private
UKI built in `~/.local/state/fullio-hard-mute-SMqm07`, booted one-shot, and
logged DSP stereo-mute acknowledgement plus full muted calibration success.

The strict `VOL_CTRL GET_CFG` test (`fullio-mute-readback-z3osDu`) booted and
again got the SET acknowledgement, but the readback returned `-EPROTO`.
That is not proof of an unmuted or muted state, or proof the query is entirely
unsupported: the response may use a different envelope. The next trace uses
`tests/fullio-mute-smoke.sh` and `tests/fullio-trace-soundwire.sh` to inspect
reply header opcode, token and byte count only, never DSP payload contents.
The first traced run stopped early with `-ENODEV`, so its lone basic
response is not evidence about GET_CFG. The verified mixer sequence uses
`1,1` to write the topology mixer and expects `on,off` on readback (the
second slot does not reflect the route). The corrected prepare-only script
reproduced the DSP SET acknowledgement followed by `-EPROTO` at
`192.168.2.123`. The rerun captured three `APM_CMD_RSP_GET_CFG` replies:
SP (92 bytes), SPVI (68 bytes), then the mute query (124 bytes, token
`0x80000032`). The last reply has the expected opcode and outer length
(`4 + ALIGN(16 + 104, 8)`), so the failure is in the parameter header,
not a missing or short reply. `sp11-fullio-dsp-mute-response-header.patch`
logs only that header on `-EPROTO`; validation is unchanged and no parameter
body is logged. The UKI in `~/.local/state/fullio-mute-header-94cq99`
booted one-shot at `192.168.2.173`. Hardware returned matching instance
`0x4a63` and parameter `0x08001039`, with both statuses zero, but declared
16 bytes of parameter data in the unchanged 124-byte reply.

`sp11-fullio-dsp-mute-compact-readback.patch` allows that exact envelope
only for the final VOL_CTRL mute query. The decoder accepts the 16-byte
form only if it describes one entry selecting both FL and FR, no high mask
bits, and `mute=1`; hardware has not yet corroborated those body values.
SP/SPVI checks are unchanged. ARM64 objects and an extracted C test passed
(valid compact form, single-field mutations, short replies, and strict
SPVI sizing). The regression test is available as
`python3 tests/fullio-mute-readback.py <patched-kernel-tree>`; it compiles
and exercises the actual helper bodies without booting the fixture.
The follow-up UKI in `~/.local/state/fullio-mute-compact-7ci50Z` booted
one-shot at `192.168.2.150`. All four prepare-only runs verified the DSP
stereo mute readback and completed calibration; all four returned the
intended `-EOPNOTSUPP` with render disabled. PipeWire independently
enumerated `alsa_input.platform-sound.HiFi__Mic__source` as 2 channels
`[ FL, FR ]`; this does not establish physical microphone lane mapping.
No PCM start, data write, PA enable, or clock sequence was attempted.

`sp11-fullio-card-amp-pair.patch` resolves one matching runtime and
requires the two amplifier roles to belong to distinct devices on the
same card before the existing hardware PA-off checks. The fixture's
feedback-specific link selection remains gated by its DT marker. The
ARM64 DAI object and system/UKI built in
`~/.local/state/fullio-amp-pair-6S7CGk`. The one-shot at `192.168.2.131`
passed both PA-off checks through hardware reads, verified the DSP mute,
and kept render disabled. The extracted-code regression also passed
absent/duplicate runtime and codec roles, foreign card, missing device,
and aliased-device cases. This still cannot turn on either amplifier.
`sp11-fullio-graph-mute-evidence.patch` records mute evidence only on the
open graph that completed calibration, stereo readback, PA-off checks and
DMA unmap. Re-prepare, stop, flush and close invalidate the graph epoch;
VI or CPS transport teardown invalidates the transport epoch even if it
is immediately enabled again. No clock code consumes the evidence yet.
ARM64 objects and extracted-code tests (wrong graph, stale attempt,
transport loss/re-enable and saturation) passed. The verified UKI in
`~/.local/state/fullio-mute-evidence-vcguy8` booted one-shot at
`192.168.2.225`: calibration logged graph-local mute verification and
returned the intended `-EOPNOTSUPP`, with no trigger or PCM samples.

`sp11-fullio-wsa884x-pa-epoch.patch` additionally rejects a codec snapshot
if it overlaps the existing mute/PA teardown writes or crosses a delivered
non-attached SoundWire notification, even if PA enable before and after
looks identical. The ARM64 codec object compiled; this patch is not in the
booted image. It does not monitor latent hardware faults, call clock
shutdown, or change permission to start the render graph.

`sp11-fullio-wsa884x-pa-ready.patch` adds a separate, unused readiness
query. It samples both fault-condition registers and requires global PA
enable, `STA0=0x2f`, and zero `STA1`/fault conditions. `0x2f` is a pinned
reference observation, not a documented FSM enumeration: `0x2a` also
occurred with enable set and no fault bits, but that channel was silent.
The PA-off path still uses its original register set. ARM64 compilation
and extracted tests covering OFF, enabled-but-silent and fault samples
passed. The integrated PA-off regression UKI in
`~/.local/state/fullio-pa-ready-1Gij2K` booted one-shot at `192.168.2.210`
and passed graph-local mute verification with render still blocked.
No post-PA caller is enabled;
SoundWire notifications must not perform clock or PCM transactions
inline while bus locks may be held.

`sp11-fullio-post-pa-pair-guard.patch` stages a read-only predicate for a
future synchronous post-PA transaction. It needs the opt-in marker and
verified mute on the current playback graph, resolves the two codecs on
that card, and samples left/right/left/right. It compares observations
from before and after the clock transaction using the codec epochs. An
unready codec, hardware error, changed epoch or revoked mute evidence
fails the check. ARM64 compilation and the extracted-code fault tests
passed. Neither the DT opt-in nor a caller is installed; this does not
arm a PA, start a graph, or detect a fault after the diagnostic window.

`sp11-fullio-clock-off-before-pa-teardown.patch` adds a shutdown-only hook
for the future marker. A playback-mute event first invalidates that PA's
snapshot epoch, then resolves the WSA macro on its own card's playback
link and requests verified clock shutdown before writing PA-off. On error
it still attempts PA-off and reports the clock failure. It does not do
clock work in the SoundWire status callback. Both ARM64 objects and
`tests/fullio-clock-off.py` passed, including ordering, lookup rejection
and continuing PA-off writes after modeled clock failure. The integration
build in `~/.local/state/fullio-clock-off-Osk9vg` booted at
`192.168.2.227` and verified graph-local mute with playback still blocked.
The post-PA marker was absent, so it did not exercise the clock hook live.

`sp11-fullio-clock-off-feedback-free.patch` adds a second shutdown-only
hook to the existing VI/CPS transport lifetime. After revoking transport
proof, the machine driver requests checked clock-off on the same card
before normal SoundWire teardown; failure never skips stream release.
ARM64 objects and the extracted VI/CPS ordering tests passed. The follow-up
build in `~/.local/state/fullio-feedback-free-JnJAMj` passed UKI validation;
it is superseded for the next one-shot by the clock-off audit below. No
clock has been started or stopped under load; asynchronous amplifier faults
are separate.

`nixosModules.fullio-clock-off-audit` keeps the muted topology and adds
only the `microsoft,denali-fullio-clock-off-audit` marker to the native
OLED DTB. It deliberately omits the post-PA marker, skips the early VI
DAPM clock write and rejects active clock transactions. On VI/CPS
teardown the card-local route checks TX0–TX3 with cache-bypassing reads
of the clock-enable bits, without writing the protection-clock registers.
ARM64 compilation and routing tests passed. The private one-shot build
in `~/.local/state/fullio-clock-audit-FOHcma` booted one-shot at
`192.168.2.170` and passed both graph-local mute verification and four
`TX0-TX3 hardware readback off` observations during teardown. The
post-PA marker was absent, so this is evidence of the quiet baseline,
not of turning running clocks off under load.

The topology check also now removes `VOL_CTRL` (`0x4a63`) from the pinned
static render graph and verifies that the host pull module (`0x4660`) can
no longer reach the RX0 sink (`0x4157`). The original route and rejection
of missing legs and direct/indirect bypasses passed offline. This is not
proof of analogue silence: protection and other DSP modules after the
mute can have their own state or generate output independently.

`nixosModules.fullio-dsp-prepare-audit` adds a second marker to the
PA-off clock audit. After calibration, stereo mute readback and DMA
unmap, it requests only DSP `GRAPH_PREPARE`, then reads mute back without
rewriting it and resamples both PAs before publishing graph-local evidence.
It still rejects ALSA playback and never sends `GRAPH_START`, unmute, gain
or PCM samples. ARM64 objects and the existing readback regressions passed;
the private UKI was rebuilt against the Surface access configuration in
Gen20 (`~/.local/state/fullio-prepare-gen20-8D9rNu`). The one-shot at
`192.168.2.215` verified both DSP mute readbacks, including after PREPARE;
all four clocks read back off at teardown. ALSA prepare intentionally
returned `-EOPNOTSUPP`; no graph start, unmute or PCM samples were sent.

The next opt-in `nixosModules.fullio-dsp-start-audit` tests only one
DSP START/STOP transaction per APM lifetime, with token-matched replies.
It requires the PA-off and clock-off markers, no post-PA marker, successful
prepare and graph-local mute proof. Hardware PA/clock state and DSP mute
are checked around START, and STOP is attempted even if START returns an
error or times out. The normal PCM start and codec unmute guards remain
unchanged. ARM64 object compilation and `tests/fullio-start-audit.py`
passed; private one-shot build is in `~/.local/state/fullio-start-audit-ubTxj4`.
On its first boot (`192.168.2.179`), the WSA SoundWire link reported parity,
port-test and bus-clash errors. The PA-off guard returned `-ENODEV` before
calibration or START. Keeping the WSA macro and controller runtime-active
briefly did not reattach both codecs; their PM policies were restored.
On a second boot of the identical UKI (`192.168.2.202`), both codecs were
attached. Token-matched DSP START and STOP passed with stereo mute, both
PAs off, all four protection clocks off, and no PCM sample writes. This
establishes that the earlier failure was before the DSP START transaction,
not that the intermittent SoundWire fault is fixed. No load feedback or
acoustic result is claimed.

`sp11-fullio-dsp-start-audit-zero-ring.patch` removes ALSA PCM data mmap
from this opt-in fixture, bounds and clears the mapped host audio ring
before START (not the DSP position area), and checks it remains zero
before STOP. Normal FullIO user-triggered start remains rejected. The
ARM64 DAI object compiled; the one-shot in
`~/.local/state/fullio-zero-ring-071xAq` passed on `192.168.2.230`.
It completed muted START/STOP with all four clocks off and the ring
still zero. The smoke script now treats only the intentional
`-EOPNOTSUPP` as the expected result; e.g. `-ENODEV` no longer looks
like a passing mute test. A separate PipeWire MicArray capture on the
preceding boot yielded 231,424 stereo S16_LE/48 kHz frames, no clipping,
and nonidentical channels; the private clip was removed after analysis.

`nixosModules.fullio-sidechain-audit` adds only a marker for the native WSA
controller to the zero-ring fixture. It extends the pinned CPS wake test
and sets active-bank Offset2 to zero on VI DP10/DP11 and CPS DP13 without
changing passive bank setup or PA/clock permissions. CPS originals must
read back after teardown. The ARM64 SoundWire object and extracted register
checks passed (wrong controller, isolated-vs-integrated markers, exact port
mask, repeated apply, and restore failure). The one-shot in
`~/.local/state/fullio-integrated-sidechain-CDX6Bo` booted at `192.168.2.139`.
DP10, DP11 and DP13 all reported `Offset2=0` in both banks when enabled;
CPS wake and restoration both read back, and the muted zero-ring START/STOP
passed with all protection clocks off. This is a transport register check,
not a source of VI/CPS sample or speaker evidence.

An ordinary QRTR registry scan alone misses LPASS DIAG. The pinned public
`linux-msm/diag@23c12c167e93215853af4e59c021551767f6fec8` registers LPASS
service 4097 versions 64/66/68. Our bounded helper reproduced dynamic
node-5 version 65 discovery (ports varied), received the reference
`FEATURE=0x0bbef7`, sent the negotiated `0x08a053` reply, and returned only
the four allowlisted DIAG IDs from the same control sender. All publications
were absent after close. A second registration on the same DSP boot did not
replay the DIAG IDs, so capture needs a fresh boot until session re-entry
is understood. There is no listening Unix/IP socket or DIAG command-channel
write.

The first fresh PA-off capture sent only the 0x1586 log-mask bit, then sent
a zero mask and verified removal of the temporary QRTR registrations. It
received no data datagrams. ALSA had already failed with `-ENODEV` before
DSP START, with both SoundWire slaves unattached, so this says nothing
about tap delivery during a running graph. The next closure in
`~/.local/state/fullio-diag-capture-MaGTPd` suppresses internal-card
WirePlumber startup probes, but keeps the identical kernel and PA lockout.
That closure booted at `192.168.2.171` and both codecs attached. The muted
zero-ring START/STOP and CPS restoration passed. The bounded DIAG session
saw one data datagram but no VI/CPS tap records. This does not on its own
prove why the tap records were absent, or that changing WirePlumber fixed
all SoundWire attach races.

`nixosModules.fullio-immediate-taps-audit` is the controlled follow-up.
It uses the API fields from AudioReach Engine `d416046c2acc858400adcc605b86954c63c34cae`
(`data_logging_api.h`): mode 1 for immediate logging, and `0x08001313=1`
to allow island exit. It targets only the known VI/CPS loggers `0x4025`
and `0x402a`. Both PAs, gain, and all protection clock enables remain
unchanged/off while the zero-ring DSP graph runs for a 150 ms observation.
The ARM64 build and private UKI (`~/.local/state/fullio-immediate-taps-wvCvOx`)
passed. The first boot showed both codecs attached before the test, but
ALSA returned `-ENODEV` during prepare and both were unattached afterward.
On two subsequent boots, with a temporary runtime-PM hold of the WSA macro,
SoundWire controller and both slaves after attachment, the DSP accepted the
logger configuration and both silent audits completed. Runtime-PM policies
were reverted. This is a workaround for these observations, not proof of a
fix for attach or clock-stop handling.

LPASS can batch multiple non-HDLC frames in one QRTR datagram. The original
single-frame filter missed them. The corrected parser found **45** complete
`0x1586` records in five datagrams during the second runtime-held audit,
but none were VI tap 2 or CPS tap 3. Thus the DIAG handshake, mask and data
framing work on this fixture. There is still no VI/CPS sample or load
proof; the absence is consistent with the intentionally disabled PAs/TX
protection clocks. Do not enable clocks early to try to make packets appear.

`nixosModules.fullio-dsp-stop-fault-audit` injects only `-ECANCELED` after
an otherwise verified silent START. It reuses the token-matched STOP and
per-APM no-retry latch. `tests/fullio-start-audit.py` covers this path and
checks that injected failure still sends STOP and rejects a second START.
The one-shot fixture in `~/.local/state/fullio-stop-fault-kEH69E` passed
on hardware at `192.168.2.207` with both SoundWire slaves active under the
temporary runtime hold. The injection returned `-ECANCELED` after STOP ACK;
a second prepare returned `-EALREADY` with no second START. Both runs
verified TX0–TX3 off and CPS wake restoration; runtime policies were restored.
This is not an amp fault test or proof of fault-stop under load.

Read-only mixer inventory on the immediate-taps fixture confirmed both
`Spkr{Left,Right} PA Volume` report 6/6 (0 dB on the ALSA scale) and
`WSA WSA_RX{0,1} Digital Volume` report 81/81 (-3 dB). The separate MIX
controls reported 84/124 (0 dB, writable higher): verify route use and
bound these if they enter any future render path. ALSA caps and cached
control values do not prove the active CSR gain, compander gain, or total
hardware gain. Any PA-on fixture must establish those independently and
retain the earlier board caps.

To separate MicArray/DSP coexistence from independent capture, the
`fullio-muted-mic-coexistence.sh` smoke checks the same native 48 kHz
stereo ALSA capture's hardware pointer and trigger timestamp before/after
the silent START/STOP. The private WAV is deleted, not transferred. On
`192.168.2.158`, both WSA slaves were `Attached/suspended` before the
runtime hold, then both became `UNATTACHED/active` with `SWR bus clsh
detected`. The hold was reverted; the capture never started. This narrows
one class of failures to runtime resume even without a PCM open. To test
that hypothesis with no new kernel behavior, `fullio-sidechain-pm-audit`
sets `power/control=on` for only the WSA macro and SoundWire controller
on udev add/bind. This is an opt-in temporary diagnostic, not a proposed
power-management fix. An isolated idle clock-stop test can then release
just one runtime vote and report suspend/resume, both slave states, and
bus errors without a PCM or PA enable.

The early-PM one-shot (`~/.local/state/fullio-early-pm-inaIs0`) booted twice
with both platform devices active and 0 ms runtime-suspended. First raw
MicArray open lacked the UCM routes; the corrected test applies the known
route and aborts before DSP START unless the recorder is actually running.
On `192.168.2.115`, the same native PCM/trigger stayed running and advanced
from 6,240 to 12,480 frames across the silent START/STOP. The 288,000-frame
S16_LE/48 kHz capture had independent varying channels (AC RMS 62.20/53.50,
no clipping), no reported XRUN, and was deleted locally. This proves native
capture coexists with the silent graph, not playback/capture duplex or
microphone clarity.

After that audit, one controller-only runtime stop and five paired idle
stops passed, with both codecs still attached. Macro-only release did not
suspend the macro while its consumer was held, so that leg is inconclusive.
The filtered `rpm_status` trace shows the controller suspended before the
macro, and the macro resumed before the controller. This does not reproduce
or resolve the earlier attach loss. A separate boot of the same early-hold UKI (`192.168.2.196`) also passed
its first idle paired clock-stop/resume before any PCM; both suspended-time
counters were zero beforehand. After the resumed slaves stayed attached,
the MicArray test passed again (hardware pointer 6,240 → 18,720 over the
PA-off audit; no clipping in either 288,000-frame channel). These controlled
transitions cannot explain the intermittent clash on a normal boot.

The next opt-in `fullio-pa-off-gain-audit` records DRE_CTL_0/1 in the
existing cache-bypassing PA-off snapshot while keeping clocks and PA
unmute blocked. The current Surface-next `snd_soc_limit_volume` also calls
`snd_soc_clip_to_platform_max`, unlike some historical audit assumptions.
Readback is still necessary to distinguish current control state from
active hardware gain. `wsa884x.o` and the extracted gain snapshot tests
passed (marker, teardown epoch and read failure). The one-shot hardware
run (`~/.local/state/fullio-pa-off-gain-mQLV43`, `192.168.2.231`) repeatedly
read `DRE0=0x70`, `DRE1=0x33`, `CSR_GAIN=25`, `CSR_GAIN_EN=1` on both chips
with the PA bit verified off. The inverted ALSA control maps 25 to `31-25=6`
(0 dB on its scale), consistent with the cap for this snapshot. It does not
establish effective analogue gain with the PA enabled. Silent START/STOP,
CPS restoration and return of the runtime policies also passed.

The first `fullio-pa-off-teardown-audit` fixture, `fullio-pa-stop-kiiINi`
at `192.168.2.232`, passed the zero-ring DSP audit but emitted neither PA
teardown marker. A failed ALSA prepare did not reach the new codec mute
branch, so this is not a verified stop test. V2 calls the same verified
DRE/PA-disable path for both distinct amps after the muted DSP transaction,
while playback still owns the transports. It attempts both sides even on
error. The same-card clock check is read-only, no PA can be enabled, and
normal rendering/unmute stays blocked. The ARM64 codec/macro/DAI objects and
extracted error-path tests pass, including failure of the first PA and
subsequent verification of the second attempt. The native build is in
`~/.local/state/fullio-pa-stop-v2-Sjxviz`. On `192.168.2.219` both amps emitted
verified stop markers while the link was still owned, after silent START/STOP
and before shared CPS wake restoration. PA bits and TX clock reads were off.
This is synchronous, already-off verification—not a loaded fault result.

`fullio-pa-off-fault-worker` adds the next bounded test. A pre-armed
SoundWire notifier merely enqueues scoped work under a spinlock. Once the
zero-ring graph is started and independently verified muted, a synthetic
notice uses that same enqueue helper; no hardware status is forged. The
worker attempts both verified PA-off stops without a PCM/DSP transaction.
The caller revokes both notifier pointers and flushes the work before the
existing DSP STOP. The test requires both hardware stop markers and the
worker marker in order before DSP STOP ACK. ARM64 objects and modeled tests
pass (duplicate notice, partial registration, missing event, stop error).
Native build: `~/.local/state/fullio-fault-worker-8AMmRH`. On `192.168.2.178`
PA-off verification appeared on each codec before the deferred-worker
marker at monotonic 33.758348 s and token-matched STOP ACK at 33.765970 s.
ALSA returned `-ECANCELED`, CPS wake was restored, and runtime votes were
released. This does not establish bounded fault latency or validate shutdown
under load. The filtered DAPM trace was empty: the test intentionally did
not select the normal WSA RX muxes or DAC transport. The same-UKI
comparison on `192.168.2.192` applied only four upstream stereo RX mux
controls and two DAC transport switches, then restored and verified all
six. Both `Spkr{Left,Right} SPKR` widgets powered up and ran POST_PMU
around 38.617 s, with both PA bits and protection clocks read back off.
Both PA-off teardown verifications preceded the worker marker (38.754897 s),
then DAPM widget shutdown (~38.763 s) and DSP STOP ACK (38.765100 s).
Routed `DRE0=0xf0` instead of `0x70`; `DRE1=0x33`, `CSR_GAIN=25`, and
`CSR_GAIN_EN=1` were unchanged. This verifies widget routing and cleanup,
not physical stereo output or active analogue gain.

**Serious fault: stop live FullIO experiments.** After the successful
routed test, a separate shared-reset diagnostic checked both PCMs closed,
both PA-off verifications and attached codecs, matching active-low
`reset-gpios` specifiers, and an initially high LPASS GPIO12. Unbinding
only the first WSA884x driver triggered a kernel NULL-pointer Oops in
`regcache_cache_only()` from `wsa884x_runtime_suspend()`. The stack runs
through `pm_runtime_disable_action` and `devres_release_all` during
unbind, consistent with a device-managed resource lookup failing during
teardown. The second codec was not unbound. Neither assertion of shared
SD_N nor safe in-place reset on transport loss was demonstrated. Private
journal: `/tmp/surface-fullio-wsa-unbind-oops.D6EqY6`. The one-shot was
cleared and a reboot to the unchanged Gen20 default was requested. The
user reported a stuck boot splash and pinned SSH discovery did not find
Surface after the reboot request; the running generation is unconfirmed.
Do not repeat driver unbind or enable PA/feedback clocks to work around this.
Gen20 recovered after a physical power cycle, and pinned SSH and greetd
were verified at `192.168.2.213`. No live unbind, module unload, or reset
is used on subsequent boots.

`sp11-wsa884x-runtime-pm-lifetime.patch` uses the codec-owned regmap in
runtime callbacks and disables PM before clearing autosuspend, before
devres frees the map. The base source confirms `devres_release_all()`
moves lookup entries before invoking release actions. The actual callback
model and ARM64 object passed; the FullIO-only native build and verified
private UKI are in `~/.local/state/fullio-wsa-pm-nFHnY9`. The one-shot
booted at `192.168.2.147`: SSH/greetd active, both WSA attached, no Oops
or bus clash. No live codec unbind was attempted to prove the fix.

With routed stereo speaker widgets active and both PA bits off, native
MicArray progressed from 6,240 to 18,720 frames through the synthetic
fault worker. Both PA readbacks preceded the worker (45.462889 s), then
DSP STOP ACK (45.467173 s) and DAPM power-down (45.467274 s); the latter
two can reverse relative order and both must follow verified PA-off.
TX0–TX3 remained off; CPS and runtime policy restoration passed.
The private WAV was deleted after analysis: 288,000 stereo 48 kHz
frames, varying and distinct lanes, AC RMS 71.77/69.68, no clipping or
recorded XRUN. The overall script correctly failed at MicArray mixer
rollback: DEC0 was still enabled after DEC1 was disabled. A healthy
ordinary reboot recovered Gen20 with SSH/greetd at `192.168.2.140`.

`sp11-lpass-tx-stereo-decimators.patch` fixes the underlying TX macro
bookkeeping: use per-DAI DEC membership, derive count from the same map,
and apply DAI mute to all active capture lanes. ARM64 TX object and the
extracted tests for duplicate enables/disables, reverse stereo teardown,
DAI isolation and mute-write failure passed. The rebuilt one-shot
(`~/.local/state/fullio-tx-stereo-1e6dZu`, `192.168.2.222`) passed the
routed PA-off worker/MicArray run and a second capture-only cycle in
one boot. Both recordings had 288,000 varied, distinct 48 kHz stereo
frames, no observed XRUN or clipping, and all mixer values read back
at their original values after each run. Both worker PA readbacks
preceded DSP STOP; idle postflight still had SSH/greetd and both WSA.
No recordings were retained. Rebooted normally to Gen20 at
`192.168.2.105`, confirming the exact Gen20 closure and default.
No clear stereo playback, live protection feedback, or audible duplex
has been established.

`fullio-routed-taps-audit` uses the same kernel as the passing TX fixture
and adds only the opted-in immediate-logger DT path, removing the fault
worker to preserve the full bounded observation. It selects only the
verified direct stereo RX route, checks alternate routes disabled and
main/PA controls no higher than 81/6, and requires both PA-off teardown
readbacks. The comparison isolates whether absence of the normal RX
route affected tap delivery with PA and protection clocks off. The
feedback checker now rejects exact duplicated or inverted lanes even
with a DC offset, not just constant/repeated samples. No raw DIAG or
mic data leaves the test laptop.

At `192.168.2.236` (`fullio-routed-taps-Rv3IVN`), the runtime-held PA-off
comparison verified both direct speaker widgets, expected `-EOPNOTSUPP`,
paired PA-off readbacks, CPS restoration and healthy idle postflight.
Eight QRTR datagrams contained 94 valid `0x1586` records, **none of them
VI tap 2 or CPS tap 3**. This rules out the absence of the standard RX
route as the sole cause of missing PA-off feedback. It does not test
load, protect against a live fault, or justify enabling clocks early.
Under the test-only night helper, the already running Niri session
accepted `power-off-monitors`; the eDP sysfs `enabled` attribute changed
from `enabled` to `disabled` while SSH/greetd stayed online. On Gen20,
the exact-closure guard refused the request before sending any IPC.

The stock WSA widget enables `PDM_WD_EN` on POST_PMU and clears it at
PRE_PMD, independently of the real PA bit. Its writes are not checked by
the widget, and the slave ops currently register only `update_status`,
not a codec protection IRQ callback. Existing software fault tests do
not demonstrate watchdog trip time, an independent amp kill on bus
loss, or any loaded current bound. The new guard observer will check the
stock watchdog/limit fields and stable PA-off state without writes; it
must not be used as proof of hardware protection under load. In particular,
the reference's `2026-08-17-WSA-PDM-WATCHDOG-LATCH-V14-REJECTION.md`
rejects simply leaving the watchdog enabled across a Linux transport stop.
Its later three-state codec sequence is evidence, not permission to copy
startup tables or change the watchdog policy in this port.

The native `fullio-pa-off-codec-guard-audit` one-shot at `192.168.2.125`
(`fullio-codec-guard-VHGmoy`) passed both screens-off and audio preflight.
Both WSA chips independently read `PDM_WD_CTL=0x01` at speaker widget
activation and `0x00` at power-down. `CURRENT_LIMIT=0xd4` throughout
(override bit set, selector `0x15`; not a measured current). The pair
was verified PA-off before synthetic worker/DSP STOP and remained so
at widget power-down. ARM64 compile and model rejected PA-on, suspended,
detached, mismatched-watchdog and read-error states. This confirms only
which watchdog/limit fields the stock PA-off route actually programs.

The private desktop MicArray test exposed a stereo UCM source, but its
WirePlumber/ACP startup also attempted playback `hw_params` and the
speaker VI backend rejected them; no actual render or PA enable took
place. Masking the playback character node prevented probes but also
prevented the private card monitor from creating the source. Do not use
either result as a successful desktop capture test. `fullio-mic-desktop`
therefore keeps the normal node present for discovery, but its dedicated
DT flag rejects PCM playback and compressed opens in `q6apm-dai` before
allocation or graph open. The Mic-only UCM is selected in the ordinary
session with WirePlumber's state isolated to the test runtime directory.
The extracted-model test passed. The native one-shot at `192.168.2.106`
(`fullio-mic-desktop-Le2JpC`) verified the private runtime state directory,
expected render-open `-EOPNOTSUPP`, the ordinary PipeWire FL/FR Mic source
and no hardware sink. Two five-second requests yielded 228,352 and
239,616 stereo 48 kHz frames, with different varying lanes and no clipped
frames or reported XRUN. Afterward both PCMs were closed, no render
`hw_params` or SPKR_VI errors were logged, SSH/greetd were active and all
private WAVs were gone. The fixture remains dark; Gen20 is still the
unchanged default and does not import this test.

### Narrowed idle SoundWire resume failure

`fullio-pm-replay-audit.sh` observed one normal runtime-PM wake on the
capture-only fixture after both PCM nodes were closed. All four WSA PM
policies began `auto/suspended`, both codecs `Attached`. A bounded ftrace
instance tracked only relevant runtime-PM states, codec cache syncs and
write counts (no values or PCM). Waking only the macro finished at
284.732824 s without a report; waking the controller reached `RPM_ACTIVE`
at 284.745428 s. Controller IRQ logged **bus clash at 284.746142 s** with
no explicit slave wake. In that same IRQ thread the first traced codec
regcache sync began at 284.747390 s. Thus the first observed clash
predates that replay; suppressing replay is not an evidence-based fix for
this occurrence. No further devices were woken. All four policies were
subsequently verified `auto/suspended`, both codecs attached, both PCMs
closed, eDP off, SSH/greetd active, and no kernel Oops. Do not repeat this
wake on the same boot merely to reproduce the failure. Investigate clock
start/exit ordering and controller state around IRQ reporting; an
`RPM_ACTIVE` value is **not** proof that the bus has recovered.

The next capture-only one-shot (`fullio-pm-transition-4fxMBu`,
`192.168.2.208`) adds read-only controller snapshots around the existing
clock-start, interrupt-clear and clock-stop-exit operations. It does not
change their order, reset, mask or error handling. At 50.139077 s the
short-idle wake showed `clash=0 frame=0` before the stock clear; the frame
bit became 1 by core exit and exit returned 0. Both codecs stayed
attached; each did one 51-write cache sync (~1.7 ms) when explicitly
woken. All policies were restored; natural autosuspend at 60.482973 s
was outside the original five-second test deadline (now 15 s).

On the same one-shot after another 300.225 seconds of controller suspend,
the wake showed `clash=0 frame=1` before clear and successful exit. The
attachment health check aborted before slave votes, with neither a
bus-clash message nor a codec cache sync in that observation. The test
had not logged the precise intermediate status, so this must not be
reported as a proven detach or as a resumed-ready bus. Subsequent
readback showed both codecs attached and all four devices suspended in
auto again; eDP remained off and SSH/greetd active. The next diagnostic
adds the physical device-number mapping, controller slave status word,
and rate-limited existing enum/alert reports to distinguish an ALERT
from an actual loss of attachment without guessing.

The expanded capture-only one-shot (`fullio-pm-slaves-7F8h7s`,
`192.168.2.144`) mapped left codec to device number 2 and right to 1.
After an additional 300.219 s of controller suspend, the supplier-first
wake preserved slave hardware status `0x00000014` (two Attached entries)
through frame-generator start and core clock-stop exit. Both codecs did
51 writes each and all four returned to sleep. A separate single-slave
vote on that same healthy boot woke the macro and controller through
normal PM dependencies, preserved `0x14`, replayed 51 writes only on the
left codec, and returned all devices to auto/suspended after ~11 s.
Neither trial saw a clash, ALERT or detach. This validates the trace, not
a fix for the intermittent failure; leave mask/reset/PM policy unchanged.

### Independent shutdown: what is and is not known

`fullio-pa-off-missing-stop-proof` (`fullio-stop-proof-J04Y0O`,
`192.168.2.107`) exercised the normal deferred worker, actual PA-off
readbacks on both codecs, and the fallback paired stop. After each pair
of successful reads the fixture withheld only the software proof. DSP
STOP ACK came at 49.440057 s between those two attempts. Final verdict
remained `PA=-ENODATA, graph audit=-ENODATA`, ALSA returned
`-ENOTRECOVERABLE` (`-131`), and no trigger/samples/PA enable occurred.
CPS and PM votes were restored and the test system stayed reachable and
dark. This validates the error distinction; no actual loss was injected.

Read-only `tests/fullio-reset-wiring.sh` verified that both distinct
WSA nodes refer to `pinctrl@6e80000` GPIO12, active-low SD_N. The known
capture-only one-shot at `192.168.2.161` also reported GPIO12 output-high
while **the macro, controller and both codecs** all stayed naturally
runtime-suspended. The data path was not woken; neither the GPIO nor
shared reset votes were operated. High here is the normal deasserted
idle level, not shutdown. Read-only pin visibility with the bus asleep
is not proof a write will succeed during a fault or physically stop PAs.

`tests/fullio-shared-sd-n.py` compiles the actual pinned reset-core and
GPIO-provider helpers against a fake active-low line. A successful
shared assert can leave the line high when another consumer holds it.
More importantly, a provider write failure consumes the last deassert
vote on this kernel; blindly retrying returns `-EINVAL` and risks
conflicting with devres cleanup. Do not implement an emergency cutoff
as two ordinary shared assertions. A candidate needs a single line
owner with an independent, sticky cutoff, no automatic deassert on
reattach, and uncached physical readback. This requires separate
qualification, not a reset or real bus-fault injection on the SSH
validation system. The DSP token transaction can wait up to `5 * HZ`
and the SoundWire FIFO has retries; neither is a physical cutoff time
bound.

`sp11-fullio-swrm-link-gate.patch` adds a distinct, controller-local
**new-stream** latch. Only the explicitly opted-in Denali FullIO WSA
controller uses it. A real master clash or a failed frame/clock-stop
resume records the first error for the controller lifetime; an attached
status or a later successful resume cannot clear it. New WSA startup
checks the latch before and after getting runtime PM, and port allocation
also checks it. Normal PM teardown and IRQ handling remain unchanged.
The extracted-code test verifies first-fault stickiness, per-controller
scope and balanced PM references on failures before and during startup.
The one-shot DT seeds the software policy only (no guessed/faked codec
status or deliberately failed bus operation) for hardware smoke testing.
On `fullio-link-gate-lPdCkr` (`192.168.2.175`) two fresh WSA requests were
rejected at `SDW Pin0` DAI startup (`-ENOTRECOVERABLE`); no PCM samples
or DSP START. ASoC obtains its own component PM votes *before* DAI
startup, so these denied opens did briefly wake the macro/controller.
Both codecs stayed attached and the macro/controller/slaves returned to
`auto/suspended` after normal autosuspend. This is not a no-wake gate.
A subsequent raw 48 kHz MicArray-only request advanced from 6,240 to
12,480 frames during the sample window and completed 288,000 varied,
non-copied frames per lane without clipping; all temporary controls were
restored and the recording deleted. Neither trial attempted a real bus
fault. The preflight confirmed the one-shot closure, Gen20 profile/default
and SSH/greetd, with no PCM open afterward.

`sp11-fullio-pre-pm-open-gate.patch` moves the first, side-effect-free
check to ASoC before pinctrl selection and component PM. The later DAI
checks stay in place for faults racing admission. On the native
`fullio-prepm-2f83eF` one-shot (`192.168.2.233`) two opens again returned
`-ENOTRECOVERABLE`, now at `__soc_pcm_open()` before DAI startup. An
allowlisted `rpm_status` instance recorded zero transitions for the
macro/controller/both codecs; no DSP START or leaked PCM. Capture still
returned two varying 48 kHz lanes (288,000 frames, no clipped samples),
restored all mixer settings and deleted the capture. This is evidence
for pre-PM admission, not cutoff of an already-open stream.

A new-stream gate is not an interlock for a prepared/running stream.
Hours after that successful smoke, the same boot reported a real WSA
master clash at 20656.166057 s. Read-only inspection found both codecs
`UNATTACHED` with sysfs device numbers `N/A`, all WSA PM policies `auto/suspended`,
and both PCM substreams closed. No contemporaneous PM/slot trace was
active; the log cannot identify a wake initiator or the order of slot
changes versus the clash. The seeded policy latch was already set from
boot, so its first-fault message is not the real incident. SSH/greetd
stayed active, and only the verified Niri display-off IPC was sent.
No PM vote, PCM, reset, automatic recovery or reboot was attempted.

The reference 7.1.5 controller path does not explicitly disable/re-enable
the main IRQ around runtime suspend/resume. Surface-next enables it after
preparing the interface clock, before the clock-start/clash-clear writes.
This is a candidate timing difference, not yet an explanation or a
reason to mask the IRQ. `sp11-fullio-clash-snapshot.patch` adds one
opt-in, rate-limited raw slot read before dispatch of an unmasked clash,
recording the IRQ word, slot word/read return, cached slots and PM state
without changing acknowledgment, masks or recovery. This can distinguish
a coincident reported detach from software's later status update on a
future valid test; it cannot reconstruct the previous incident.

Follow-up: the live Denali WSA node has one GIC interrupt specifier;
`of_irq_get(..., 1)` therefore does not arm the driver's separate wake IRQ.
There was no recorded system suspend/resume around this incident. That
rules out those two explanations for a wake, not runtime PM by a consumer.
Upstream `671ca2ef12fe` also documents stale clash status after hard reset;
this rules out treating a clash bit by itself as proof of a physical
collision. Both slaves reached Linux `UNATTACHED` state. `device_number`
shows `N/A` by definition for that state, so this is not independent
proof the hardware forgot its address; the raw slot snapshot is key.

Two checkable PM weaknesses were found independently: resume ignored
`clk_prepare_enable(iface)`, and suspend ignored failure to drain the write
FIFO even though upstream `9ac4a4441a39` requires it empty before suspend.
`sp11-fullio-pm-preconditions.patch` fails closed on these paths only for
the opt-in FullIO link gate: clock failure leaves IRQ state unchanged and
returns before MMIO; FIFO timeout returns before clock-stop preparation,
IRQ masking or clock gating. The offline prefixes test checks both cases;
neither was intentionally injected on the Surface. Neither is established
as the cause of the observed detach.

A useful next capture on a fresh verified PA-off fixture is a bounded
filtered `rpm_resume` trace with a stack trigger for WSA controller/macro
resume, alongside `rpm_status` for both slaves and the clash snapshot.
The running kernel exposes those trace events. This should identify the
runtime-PM caller even if there is no PCM, and discriminate stale IRQ
status, an already missing slot, and a later status change. Do not run it
as a wake/recovery operation on the already detached boot.
`fullio-passive-link-audit` is the prepared capture-only fixture: render
open is prohibited, the real link gate and PM/slot observer are enabled,
and the synthetic-fault flag is absent. Native closure and off-ESP UKI
were built and verified, then the candidate booted once at
`192.168.2.179` after verifying the previous faulted boot had closed
PCMs, no kernel Oops and healthy SSH. No live recovery on that old boot;
Gen20 remained the permanent default. The new boot passed closure,
attachment, journal and session preflight and Niri turned eDP off.
`tests/fullio-passive-resume-trace.sh` requires the exact healthy closure,
starts with the four devices suspended, filters the trace to those
four, and stops at a logged fault or loss of attachment. The script
refuses to draw a conclusion from an overflowed/truncated trace. The
previously booted detached fixture was rejected before trace setup.
On the healthy passive fixture a 300 s idle window and a separate 25 s
window covering two ordinary desktop MicArray requests yielded no
WSA runtime-PM entries or loss of attachment. The two captures returned
231,424 and 238,592 varying stereo frames without clipping, with clips
deleted. This rules out WSA wake in those capture trials, not every
possible audio consumer.

A single ordinary left-slave runtime PM vote validated the observer's
positive case. `rpm_resume` backtraces attributed the controller wake
at 445.223514 s to `control_store` → `pm_runtime_forbid`, and the WSA
macro wake to `rpm_get_suppliers`. The macro was active first, then the
controller, then the left codec; hardware slots stayed `0x14`. Only the
left codec synchronized (51 writes, ~1.706 ms). All four devices returned
to `auto/suspended`, both were still attached, and no clash occurred.
This validates trigger visibility and one normal runtime-PM cycle, not
the cause or recovery of the earlier spontaneous failure.

`sp11-fullio-feedback-pair.patch` tightens the paired VI/CPS SoundWire
port admission: the two slave runtimes must be attached WSA884x devices
on this same bus and must have distinct assigned slot numbers. This
matters for CPS, where both slave runtimes legitimately share master
DP13, so counting two runtime records does not establish two sources.
The offline extracted helper rejects duplicates, wrong bus or part,
unattached/unassigned devices and out-of-range slots before any master
port registration. This instantaneous admission check is not a guarantee
that attachment persists and is not proof of two live feedback channels.
`sp11-fullio-detach-latch.patch` also handles actual status loss without a
master-clash event. After a successful controller slot-status read, the
opted-in gate remembers which slots were ever attached and latches
`-ENODEV` if any become `UNATTACHED`; initially empty slots and `ALERT`
do not latch. The real admission predicate then returns `-ENOTRECOVERABLE`
even after reattachment. The extracted-code test covers those cases and
checks that the policy is per-controller and disabled on unmarked
controllers. This is an admission gate after observed loss, not a
mechanism to stop an already-powered amplifier. The native
`fullio-detach-latch-ZZ5e7Z` capture-only one-shot at `192.168.2.115`
booted without a false latch during enumeration, and a subsequent 300 s
passive window had no WSA events. No real detach was induced; its error
branch is covered offline, not proven in a faulted live session.
Native compilation and positive live integration passed on the
`fullio-pair-integrated-bcLB52` one-shot (`192.168.2.180`). The exact
sidechain DT routed the real two-codec pair through the tightened
admission check: all DP10/11/13 paths reached hardware Offset2=0
readback on both banks, DSP mute survived PREPARE, zero-ring START/STOP
completed, and both PA-off/clock-off teardown reads and the CPS restore
passed. Expected ALSA result was `-EOPNOTSUPP`; no user-triggered PCM or
samples, PA enable, or protection-clock enable. Both codecs stayed
attached and per-slave PM votes were restored; the fixture's intentional
early supplier PM hold remains separate from that rollback. No raw
feedback was collected for this admission test.

Cross-platform evidence: `justririll/x1e-speakers@83c4f1f` documents
another WSA8845 laptop losing VI or both SoundWire slaves while rendering.
Its stated recovery uses a card profile transition and autosuspend, not a
verified hard cutoff; neither that recovery nor its 48 kHz VI/Asus ACDB
choices belong on Denali. Its packed V/I description agrees with the
Denali v33 evidence that TAP2 contains four ordered S16 components carried
as two S32 words. The checker now independently requires variation in all
four halfwords, and rejects copied/inverted same-position components
across speakers even if the other component varies. It deliberately does
not infer V/I order or physical L/R from variation. Synthetic tests cover
a stuck halfword in every position, repeats, truncation and copying. The
checked-in reference packet archives examined during this pass contain no
paired VI/CPS payload, so they cannot serve as a positive sample fixture.

Host timing for a later sample run: the collector now timestamps after
`recvfrom()` (previously at poll entry, up to one 40 ms wait too early)
and prints its monotonic origin. The opt-in taps audit records `ktime_get_ns()`
at accepted START and immediately before sending STOP; it reports both
verification and STOP status. `fullio-feedback-samples.py --receive-window
ORIGIN START END` uses the same host monotonic domain (seconds; convert
kernel nanoseconds to seconds), excludes records outside that interval,
and requires at least 50 ms of actual receive-interval overlap. Synthetic
archives cover simultaneous/nonoverlapping/stale records and invalid bounds.
This is only a host receipt association: an old buffered DSP packet can
still arrive in a new host window. It is neither DSP graph/session
provenance nor permission to unmute. No external raw samples are required
by the test.

`sp11-fullio-prepare-recheck-tags.patch` checks both pinned SP/SPVI
readback payloads after GRAPH_PREPARE on the same graph, before verifying
mute and publishing the graph-local mute ticket. Earlier equality checks
ran during initial calibration only. The extracted-code test verifies
failure at either GET aborts before ticket commit. On
`fullio-prepare-tags-4swDmD` (`192.168.2.138`) both post-PREPARE payloads
matched byte-for-byte; mute remained set, both WSA supply reads were
`0x02`, and the prepare-only fixture returned `-EOPNOTSUPP` with no START,
trigger or samples. The screen was off and both codecs stayed attached.
This is retained static protection configuration, not live feedback.

`sp11-fullio-scope-mute-ticket.patch` keeps the mute ticket scoped to
START/STOP diagnostics. The PREPARE-only path still checks both tags,
mute and both PAs, but publishes no ticket. The caller revokes any valid
ticket left by an early START-audit rejection before running the stop
proof; after an actual START attempt the original revoke-before-STOP
ordering is unchanged. The extracted-code PREPARE and START models pass
(including START timeout, STOP failure and one-attempt policy). Native
AArch64 fixture `fullio-mute-ticket-soxMqo` built successfully as
`j4ibp0xfjvn2b7rjpdbszfanhzk69dwx-nixos-system-surface-26.11.20261121.56f282a`.
No one-shot was prepared or selected for this lifetime fix alone.

`sp11-fullio-latch-shutdown-proof.patch` makes the missing-proof verdict
sticky for the q6apm DAI component lifetime on the opt-in audit. It denies
new PCM and compressed render before graph allocation and rejects a new
prepare on an existing playback handle; it does not control pinctrl or
stand in for the SoundWire pre-PM gate. It does not block capture or
turn off an already powered PA. ARM64 build and the extracted-code
stop-proof model passed. On `fullio-stop-latch-cdFjyx` (`192.168.2.174`,
closure `v0ghn5g3yp3lkw9qm94jw4gizjqkhmv4-nixos-system-surface-26.11.20261121.56f282a`),
the PA-off fixture deliberately withheld the paired readback proof; the
single zero-ring START audit received a STOP ACK. The next `snd_pcm_open`
failed with `-ENOTRECOVERABLE` at `snd_soc_component_open`, with no new
calibration or START. Native MicArray still captured 288,000 frames
(two different unclipped channels) with the latch set; the temporary
controls and recording were restored/deleted. Both codecs stayed attached
and returned to auto/suspended; the two supplier devices retained the
fixture's intentional discovery holds. Gen20 and SSH remained intact.

`sp11-fullio-latch-dsp-stop.patch` reports the actual STOP transaction
error separately from the aggregate START/verifier result. Without a
STOP ACK the caller now latches render even when the worker verified
both PAs or the PA audit was not selected. A START timeout followed by
an acknowledged STOP is distinguishable and does not by itself latch
this policy. The model exercises identical `-ETIMEDOUT` on START and
STOP, early refusal without a STOP, required PA checks after a failed
STOP, and capture unaffected by the latch. Native fixture
`fullio-dsp-stop-latch-K1plTb` built closure
`qmzrbdm0j6mfwm416f9hs4l96sygsxmf-nixos-system-surface-26.11.20261121.56f282a`;
not deployed, no live DSP/transport fault injected. This is an admission
policy, not proof that the DSP stopped accessing memory. The generic
final `q6apm_put_audioreach_graph()` still discards GRAPH_CLOSE status;
qualify ring/mapping ownership on uncertain STOP/CLOSE before a loaded
path. The separate calibration OOB quarantine is not that proof.

`sp11-fullio-ring-map-pair.patch` propagates data-ring map errors before
issuing the position-map request, and rejects missing handles before
FullIO push/pull setup. The compiled offline test covers ring timeout,
position error, ordinary non-push/pull capture, and all four combinations
of missing/present handles. Native fixture `fullio-ring-map-pair-lmSfq5`
built `6cxz2nwcv98965bq0d3mmk6h577pz44s-nixos-system-surface-26.11.20261121.56f282a`;
not deployed. Rechecked kernel.org: `next-20261120` and `v7.4-rc4`
remain the latest visible next/mainline tags. No pin change.

The remaining ownership hazard is concrete: construction uses an ALSA
fixed preallocation, map/position handles are stored in graph info and
indexed by graph ID/type rather than a unique transaction, and an
unknown map can leave a zero local handle. Generic unmap returns success
without sending a command for a zero handle. ASoC's `.pcm_free` ignores
both unmap results; ALSA's `snd_pcm_free()` then frees the preallocation
after `private_free`. Merely checking two nonzero handles, holding an
open or setting a render latch cannot make those paths safe. Before
exercising actual failure, FullIO needs lifetime-managed ring backing
that can outlive the PCM, transaction-matched map/unmap for **both**
regions, and a bounded quarantine policy when an accepted request times
out. In particular, an acknowledged rollback of one region does not
release backing when the other region's ownership is unknown. Validate
failure at every boundary offline; do not force teardown, remoteproc
reset, or a real mapping timeout on the SSH test device.

`sp11-fullio-ring-owner.patch` adds a dormant coherent backing owner and
one retained quarantine slot; it does not replace PCM preallocation.
The extracted-code model covers successful paired unmap, timeout at
both map and both unmap boundaries, unknown DSP quiescence, duplicate
handles, and invalid SID-address overlap. The verified system
`gykw5qd3g4zflblbljls54bsgp49g8y2` uses kernel derivation
`6id57j9c2aqlpjv9k5dwn7czp51b9qym`, whose references match the four
latch/map/owner patches recorded as applied in the original build log.
The closure's decompressed `q6apm-dai.ko.zst` contains the PA and DSP
STOP lockout and ring mapping error messages; searching the compressed
UKI or built-in Image was not a valid check for this loadable module.
The dormant owner can be optimized out and is not exercised by booting
this image. `tests/fullio-ring-replies.py` separately compiles the real
OOB reply handler and verifies that BASIC MAP success without a handle,
a zero or truncated handle, a delayed MAP duplicate, and a wrong echoed
opcode cannot supply the proof required for reuse. `sp11-fullio-global-oob-token.patch`
uses a module-wide saturating counter so APM reprobe cannot reuse a token
while the module stays loaded. Offline checks cover 4096 allocations
across four threads, exhaustion without wrap, and a late MAP reply to a
replacement APM. Native fixture `fullio-global-token-5YLCsd` built as
`5izzps187qfnb3vcgrfs8vs4b82h0fzh-nixos-system-surface-26.11.20261121.56f282a`;
its kernel derivation and build log both record the patch. Not deployed.
Token uniqueness is not proof of old DMA revocation or quiescence, and
it does not persist through module reload. PCM integration must still
bind reclamation to the owning APM instance and graph quiescence.
The earlier private OLED UKI hash is
`21819f3ea7722516c8cd15cc49969690b57a0d1990590470da703cc2082a00aa`.
That earlier image was not installed or selected.

`sp11-fullio-ring-map-audit.patch` uses the owner in an explicitly
selected, PA-off map-only fixture; it does not change normal PCM backing.
The DAI checks both PAs before and after and returns `-EOPNOTSUPP` prior
to configuring the graph. The audit helper excludes START and post-PA
fixtures, runs at most once for the loaded module, and never publishes
these addresses to a graph. On `fullio-ring-map-audit-YqIQCS`
(`192.168.2.123`, `rc593psfnq4m3vp92hf7a2dci5iaf9g7`), the actual DSP
acknowledged MAP and UNMAP for both isolated regions at 45.182053 s.
Both WSA PA-off checks passed around the transaction, TX clocks read off,
and there was no START, graph use of the backing, or PCM trigger. The
private UKI was selected once after byte-comparing the Gen20 ESP UKI
with the off-ESP archive. Exact closure, default Gen20, healthy greetd/SSH,
attached WSA pair, closed PCM and eDP off were checked. This establishes
DSP support for the mapping protocol without audio; it does not qualify
teardown after the DSP has used the backing.

`sp11-fullio-graph-close-proof.patch` requires a token-matched
`GRAPH_CLOSE` on the last reference to a FullIO graph. If the result is
unverified, further FullIO graph opens on that APM are blocked before
reusing or reserving an ID. Other graphs retain their existing path;
`tests/fullio-graph-close.py` verifies the timeout latch and isolation
from MicArray. In the PA-off one-shot `fullio-graph-close-8I8VFw`
(`192.168.2.207`, `3wjcslcxqkxykb4pfb90yp6vykbd0yq7`), the DSP
acknowledged the isolated maps/unmaps at 47.900009 s and acknowledged
the never-started FullIO graph's final CLOSE at 47.939412 s. No address
was supplied to the graph and no START, trigger or PA enable occurred.
The Gen20 default, archive-matching Gen20 UKI, SSH, greetd and paired
attachments were verified; the screen was turned off through Niri.
This verifies CLOSE protocol support, not the DMA revocation ordering
when a graph has already used the backing. Failure was modeled only.

`sp11-fullio-ring-attach-audit.patch` adds a separate opt-in fixture that
supplies the two mapped addresses and handles to the push/pull module
using token-matched SET_CFG. The last graph reference owns the backing
before SET_CFG is sent; even an ambiguous SET_CFG error goes through
CLOSE. Unconfirmed CLOSE skips UNMAP and quarantines the allocation;
UNMAP failure also quarantines it. The native `fullio-ring-attach-x35yrk`
one-shot (`192.168.2.160`, `17gm6kpna64dfx5b7v1vkm7m5xbd8djb`) recorded
SET_CFG at 42.599069 s, CLOSE at 42.618024 s, and both UNMAPs confirmed
and backing released at 42.618451 s. Both PAs were off around SET_CFG,
TX0–TX3 read off on cleanup, and ALSA prepare deliberately returned
`-EOPNOTSUPP` without START, trigger, or samples. Preflight passed on
both sides, Gen20 remained the default, and Niri turned eDP off. This
establishes teardown for a configured but never-started graph; it does
not establish teardown after active DMA or change the normal ALSA PCM
allocation path.

`sp11-fullio-ring-dma-audit.patch` uses the same independent backing in
an opt-in silent START audit. An attempted START is remembered before
the transaction, so CLOSE alone does not release backing even if START
times out: both STOP and final CLOSE must be acknowledged before both
UNMAPs. The position observer requires two stable advancing DSP counters
with an in-range index, not just a START ACK. Models cover missing STOP,
late replies, bad position indices, stale/torn counters, and quarantine.
In `fullio-ring-dma-IkAAn3` (`192.168.2.216`, `bkck8blkdln77yjf93vpp76gqss7qp1f`),
SP/SPVI and mute were verified, but the position observer returned
`-ENODATA`. DSP acknowledged STOP at 42.551066 s, CLOSE at 42.567172 s,
and both UNMAPs by 42.574624 s. The run is **not** evidence of active DMA.
No PA was enabled and no user PCM samples were sent. The next variant
explicitly configures the SHMEM pull source media format before
calibration and PREPARE; PCM_CNV/MFC configuration alone does not send
that parameter to the pull source.

The SHMEM variant `fullio-ring-dma-media-ACKR9P` (`192.168.2.181`,
`x9kjb7bz7qw1kr8xm6jq9fgfg8wzx6aj`) passed exact one-shot preflight,
but at 46.376123 s the controller reported a real SoundWire clash.
Prepare returned `-ENODEV` before the independent-ring SET_CFG marker,
so the new SHMEM media step and START were not reached. Clock-off cleanup
was read back and final CLOSE acknowledged. Both WSA devices then read
`UNATTACHED`, all four relevant runtime-PM devices were `auto/suspended`,
and all PCMs were closed. SSH/greetd and Gen20 default/profile were still
healthy. No retry, unbind, reset or reboot was issued. The clash precedes
the change under test and does not establish the cause of the earlier
missing position progress. Stop live playback diagnostics until the
SoundWire failure can be investigated without compromising recovery.

A read-only review of the full boot journal found repeated SPKR_VI
`hw_params -ENODEV` and four FullIO graph CLOSEs at 10.225–10.240 s,
near WirePlumber startup, well before the 46.376 s clash. This supports
removing uncontrolled desktop probes as a variable, not assigning the
clash to WirePlumber. The boot had neither the real link gate nor the PM
transition snapshot marker. Do not infer raw slot contents or causal
clock-stop ordering from the later `UNATTACHED` state.

The next DMA fixture now enables the real link gate, pre-dispatch clash
snapshots and clock-stop transition snapshots, and disables only the
Surface audio card in WirePlumber. Its preflight requires both DT markers
and rejects the synthetic seed. `fullio-ring-dma-observe-bqOyi8`
(`r1j58cijvsy05vksvxyxh1hcisd3bhzm`) built natively with the same kernel
as the failed fixture; `fdtget` verified the delivered boot DTB and the
closure contains the scoped `device.disabled` rule. No deployment, PCM
open or PM policy change was performed. The new gate protects admission;
it neither recovers the existing bus nor qualifies loaded PA shutdown.

`tests/fullio-passive-resume-trace.sh` now records hard-IRQ delivery for
both the `soundwire` and optional `swr_wake_irq` action alongside RPM
stacks/status on the monotonic trace clock. It preserves the relevant
monotonic kernel journal (including pre-dispatch raw slot snapshots and
PM transition lines) on both clean and fault exits. An IRQ entry is not
proof the threaded controller handler ran, and an action name alone
cannot distinguish controllers; keep numerical IRQs and raw snapshots.
The running test kernel exposed the expected event fields and clock;
an isolated trace instance accepted the filter and recorded a test
marker without opening PCM, touching PM, or reading bus registers. The
current boot had only a `soundwire` row (IRQ 248, GIC 202); the absence
of a matching wake row is not evidence of zero delivered wake IRQs.
The passive run itself remains gated on a healthy attached pair; it
was not run on the detached boot.

`sp11-fullio-clock-stop-entry-latch.patch` closes an admission gap found
by source inspection. After the driver masks clash notification, either
clock-stop prepare or entry can fail and return without a sticky fault.
Both now latch a negative result on opted-in controllers (except the
existing empty-bus `-ENODATA` case), without adding any IRQ/clock
operation, reset, or recovery. The extracted-function models verify
both errors independently, first-error retention and unchanged
unmarked behavior. `fullio-clock-stop-entry-RAwpl2`
(`y5w5if6bzbh3kzblg4xm0zsj1vqvb960`) built natively; the derivation and
patch application log, SoundWire module, DTB markers and private UKI
were verified. No switch, deployment or PCM open occurred; Gen20 is
still the default. This guard does not identify the cause of the clash.

For external cutoff analysis, `tests/fullio-cutoff-trace.py` now rejects
an SD_N edge and output-off edge in the same sampled interval as
ambiguous ordering. Use `--vbat-min-v` with simultaneous measured
`vbat_l_v`, `vbat_r_v` and independently verified `software_mute`
columns to reject supply dips and concurrent or unverified software
mute. Set the supply minimum from the qualified load and amplifier
specification; the synthetic test values are not hardware limits. A
passing CSV does not authenticate these channels or identify the
watchdog mechanism; the unextended CSV is timing only. The checker
self-test passes both supported modes and rejects 20 invalid captures.
Two publicly indexed datasheets checked for this step were for WCD9335
(LM80-P2751-29) and WSA8810/8815 (LM80-P2751-28), not WSA8845; neither
qualifies Denali cutoff timing.

Reference correction: `geocausa/SP11X1e-audio@3232e1dacdeb580a10a9cb8d4756a4518a7bd83e`
records successful protected playback on this machine family. The pull
startup source explicitly requires a 3840-byte ring and 1920-byte period
at 48 kHz stereo S16_LE, and registers pull watermarks at 1920 and 3840
before setting SHMEM media. The previous zero-ring experiment skipped
watermarks and used the ALSA buffer size. The opt-in diagnostic now
uses that ring geometry in its independent backing, registers the two
watermarks through the native API, and suppresses ALSA period callbacks
for that backing only. It still requires position progression, STOP,
CLOSE and both UNMAPs; SET_CFG and event ACKs cannot substitute for those.
Soft-pause event registration and direct module addressing are separate
reference differences, not claimed as implemented by this change.
The follow-up `sp11-fullio-pull-config-parity.patch` now matches direct
module addressing for the DMA audit: send SET_CFG from the graph port
to the pull instance, with the 44-byte parameter envelope rounded to
48 bytes and the parameter body size left at 28. Token/opcode checks
remain in effect on the graph-port reply path. Map-only, attach-only
and ordinary PCM retain their original APM route. The compiled payload
model checked both routes, identifiers, unchanged body and zero pad;
soft-pause subscriptions remain a separate difference. The corrected
native build `fullio-direct-pull-Ra8onb` (`kmri5ln7hr46wxmalcq6yh2wwl8n5n87`)
applied the patch and produced a verified private UKI off ESP. It was
subsequently selected once after the archive comparison confirmed the
Gen20 UKI. On `192.168.2.162` the fresh exact closure re-enumerated both
WSA slots (`0x14`). PA-off preflight passed before and after a single
ring-DMA audit, with eDP off and Gen20 preserved. The LPASS clock-stop
exit snapshots at 59.026 s showed stable slots and no clash. The DSP
acknowledged direct SET_CFG at 59.050050 s, pull watermarks at 59.054084 s
and SHMEM media at 59.059066 s. After SP/SPVI and mute verification the
position counter demonstrably advanced (59.220993 s). STOP, final CLOSE
and the two UNMAP acknowledgements followed at 59.231164, 59.245049 and
59.245892 s respectively; only then was the backing freed. PAs and TX
feedback clocks remained off, and no PCM trigger or user samples were
sent. The combined parity changes address the earlier missing progress;
this run does not isolate which change was necessary, establish the
cause of the earlier clash, or qualify live VI/CPS or audible playback.
On the same boot a 300 s passive window (90.677–390.964 s) recorded
only begin/end markers (2/2 entries, no truncation); primary IRQ 248
stayed at 17 and the four relevant active counters remained unchanged.
Both WSA devices remained attached; the fixture did not touch PCM or
PM policy during the window. This is not proof that a clash cannot recur.

The opt-in `fullio-ring-dma-sidechain-audit` combines the exact working
ring kernel with the existing integrated SoundWire route flags. Native
`fullio-dma-sidechain-v5Ekcj` (`xd0aza21dgvnwqj5jvl0pj1jz7ffjdym`,
`192.168.2.142`) used a verified private one-shot UKI and unchanged
Gen20. The smoke test requires DP10/11/13 Offset2 readbacks before DMA
progress and CPS restore after STOP. All passed on the same graph:
DP13 at 43.745506 s, position progress at 43.833998 s, STOP at 43.844029 s,
CPS restore at 43.867546 s, CLOSE at 43.870060 s and both UNMAPs by
43.870470 s. Clock-stop exit showed `0x14` with no clash; the post-test
preflight confirmed both WSA attached, PCM closed and SSH/greetd active.
PAs and TX feedback clocks stayed off. These readbacks establish route
coexistence with actual DSP ring progress, not validity of VI/CPS data.

`fullio-ring-dma-taps-audit` combines that ring with the existing
PA-off tap observer. Native `fullio-dma-taps-qQVDDI`
(`4q2vscbsgmwcywcx7vbhdx67j30x67dp`, `192.168.2.219`) passed boot
preflight and armed the bounded collector at 44.424084669 s. This run
failed earlier than the tap experiment: at 44.680481 s clock-stop exit
reported success, frame generator asserted, slots `0x14`, and no clash;
96 µs later the enumeration IRQ path read slots change `0x14→0x00`.
The preexisting real latch recorded `-ENODEV` and SDW Pin0 startup
refused the PCM open with `-ENOTRECOVERABLE`. No ring SET_CFG, START, or
new tap configuration was reached. The collector sent its zero mask
and counted zero datagrams, which is not a negative feedback result.
Both codecs remained detached, PCM closed, SSH/greetd healthy and Gen20
unchanged. No retry/reset. Unlike the earlier clash this loss was
observed without a master clash report. The successful DMA+sidechain
run recorded frame=0 immediately before clock-start settled, whereas
this boot already reported frame=1 on entering clock-stop and before
clash clear. Treat that as a comparison point, not a causal finding.
Subsequent unseeded preflight rejects a sticky latch even if the slots
later appear attached.

Discovery-held comparison `fullio-dma-taps-held-nzToCM`
(`kw2n19amrrl3m7v9p0d4d6x9as1h8hzc`, `192.168.2.227`) used the
identical kernel and only opted into the two supplier discovery holds.
Preflight verified both `on/active` and no observed clock-stop entry or
exit since boot, before and after the test. Both WSA stayed attached,
with position progress, route readback, CPS restore, STOP/CLOSE and two
UNMAP acknowledgements. Collector armed at 43.061626283 s and the
verified PA-off DMA window ran 43.431308575–43.601631179 s. There were
55 parsed records, all other taps, no parsed VI/CPS. Four 4096-byte
datagrams had trailing unmatched bytes; that capture cannot prove that
no feedback frames were sent. The runner also rejected its empty
window due to a parser-policy bug, not a verified feedback failure.
The observation-only decoder now allows a completely empty scoped
window without loosening positive validation; the collector accepts up
to 64 KiB and the runner rejects unmatched or oversized envelopes.
Native collector compilation with warnings-as-errors and offline
feedback tests passed; no repeat on this boot. This single held control
avoided the prior detach, but does not prove the hardware root cause or
qualify permanent PM holds, active protection, or audible playback.

Clean collector control on the identical held closure (`192.168.2.208`,
fresh private one-shot) armed at 47.224943678 s and covered the
47.682943678–47.853955292 s DSP window. DSP position progressed,
STOP/CLOSE/UNMAP and CPS restoration passed, and the two WSA remained
attached with PA and feedback clocks off. Five complete datagrams held
179 valid `0x1586` records, all other taps, with zero invalid, unmatched
or oversized envelopes; the scoped archive contained no VI/CPS.
The observation-only checker passed, including zero-mask send; its
regression test now demonstrates that the empty-window option cannot
accept one-sided or non-overlapping feedback. This rules out the old
collector's 4 KiB envelope handling as the reason for the recovered
control's zero VI/CPS. It does not prove firmware never generates those
taps, and repeating the identical PA-off clock-off capture would not
resolve the remaining gap. Reference `0069` starts feedback clocks
only after both PAs report ready; the positive `POSTPA-OFFSET2` captures
are thus a different hardware state, not a positive control for this
clock-off diagnostic.

Dormant lifecycle review against reference `0069`: the complete local
Golden pair-order patch already verifies readiness after acquiring PM
and between TX pairs. `sp11-fullio-clock-proof.patch` closes two narrower
boundaries: a stale post-resume readiness result drops the transient PM
vote without TX writes, and a stop with no tracked PM vote must still
read all four TX clock bits uncached before reporting success. Partial
activation still uses exhaustive rollback and retains its vote on
unverified cleanup. `tests/fullio-clock-proof.py` exercises real
extracted helpers, including unexpected enabled hardware, failed
register reads/PM get, and stale readiness before and after the first
pair. Golden VI order regression checks also passed. Native
`fullio-clock-proof-ul4S1F` (`rljnmdxawi3s3010js9cqnp2wfdfidz2`)
built and the patch and module were verified. It was not deployed;
this does not arm PA-on or establish physical cutoff.

Clock-stop chronology review: reference v19c and Surface-next both
perform the existing CGCR reset then write CLK_START on the clock-stop
resume path; Surface-next also has the main IRQ/hclk sequencing fix.
The former `clock-start-before-clash-clear` snapshot was after the
CLK_START write, so the observed frame=1 did not establish whether
frame generation was already on before resume operations.
`sp11-fullio-resume-boundaries.patch` adds scoped read-only snapshots
before and after the existing CGCR reset, then passes the first
nonzero EE/CLK_START result to the existing post-write snapshot. The
first sample is after hclk/main IRQ enable, not while suspended. No
reset, register write, retry or automatic recovery is added. The
extracted-function model exercised all clock-start register layouts
and combinations of operation result; journal parsing labels old and
new boundaries without inferring missing states. Native capture-only
`fullio-resume-boundaries-kIdqzK` (`4wn85hirkg0f65skg51ilhrnrwcqsqmd`)
passed build and module/DTB verification. It subsequently booted
once at `192.168.2.131` with archive-verified Gen20 and no persistent
switch. Boot enumerated both WSA slots (`0x14`), then entered
clock-stop at 20.991179 s (`clash=0 frame=0 result=0`). A 300 s idle
window followed by a 30 s window covering two desktop MicArray captures
showed only trace markers, unchanged IRQ 248 (3→3) and no increase in
active time for either WSA, the codec macro or controller. PipeWire
published FL/FR with no ALSA sink; both captures varied independently
(232448 and 238592 frames, zero clipping, no retained clips). The
extracted PCM/compressed gate test passed; no live playback open,
PM vote or forced transition was attempted. Both WSA remained attached,
PCMs closed, SSH/greetd healthy and eDP off. The new resume snapshots
had no occasion to run, so this is a negative control, not a fix or
an observation of successful resume.

`sp11-fullio-no-legacy-map-audit.patch` leaves only host ALSA allocation
for the marked Denali MultiMedia1 (graph 0) PCM; it skips legacy DSP
MAP/UNMAP and rejects compressed open for that graph in that fixture.
Other graphs and unmarked systems keep their normal allocation path.
The independent owner remains responsible for exactly the two regions
submitted to the DSP. Model tests cover the selector, capture/open
scope, ownership, position and final CLOSE proof. Native
`fullio-no-legacy-map-tRaAl5` (`jpr8fhdq0lfl4v8dm2sdhb8qpvbpiswn`,
`192.168.2.217`) verified the private one-shot and booted with Gen20
preserved. Kernel logged the skipped legacy map at 9.730006 s; independent
position progressed at 43.310039 s, STOP was confirmed at 43.321068 s,
CLOSE at 43.336074 s and both UNMAPs before release at 43.336497 s.
The added SoundWire snapshots caught a healthy resume: frame status
was 1 before and after CGCR reset, 0 immediately after CLK_START, then
1 at clock-stop exit. Slots stayed `0x14`, with no clash or nonzero
return. Thus a frame=1 readback alone does not predict detach. Both WSA
remained attached, PAs and feedback clocks were off, and PCM was closed
on completion; no user samples or audible playback were tested.

Reference `0064` is a different case from the observed long-lived
loss: the same-board v27 experiment documented a codec UNATTACHED →
ATTACHED pair and retained initialized state, with exactly two boot
initializations and no new cold register replay on a 20 s idle wake.
Its patch retains `hw_init` across a resident detach/attach; it does
not restore a missing hardware slot or prove full context retention
across arbitrary loss. The same-boot slot parser in
`tests/fullio-pm-replay-trace.py` now distinguishes the Denali pair
(slots 1 and 2) from the unassigned slot 0 and a codec ALERT. The
44.680577 s incident reached `0x00` from `0x14`; the later `0x01`
reported only slot 0, with no paired raw reattachment in the log and
both codecs still detached in sysfs. The healthy independent-ring log
has no witnessed paired loss. The parser was checked against both
logs and synthetic initial enumeration/ALERT/partial/full return and
repeated same-boot logs. No change to codec retention, link admission,
PM, or live playback was made based on this distinction.

### Soft-pause scope in the render port

The actual v19c topology package (SHA-256 `e7bb06a0…`) already includes
Golden SOFT_PAUSE (`0x07001019`, instance `0x466b`) on graph 0 in the
`MFC 0x466a → SOFT_PAUSE 0x466b → SPR 0x412b` path. The build-time
`tests/fullio-topology.py` now checks both edges and the module identity;
the real binary passed, and changing either the module ID or the
outgoing edge was rejected. Do not add a duplicate module to the graph.
The independent DMA fixture subscribes to the two pull watermarks but
not to the two SOFT_PAUSE events (Golden `0x0800103f`, `0x08001043`).
Registration is not a mute or STOP proof: Golden separately issues
PAUSE/RESUME and waits for completion. Its render-parity regression
also found that a pull callback can block completion under the ALSA
stream lock. A normal PCM port must handle this ordering and not wait
for events while holding that lock. The current diagnostic still
refuses ALSA render START/RESUME. The former DMA fixture lacked those
registrations; `sp11-fullio-pull-events.patch` adds only the three
Golden subscriptions (40, 24, 24 byte bodies) to the PA-off independent
ring branch. It checks the configured ring/period and module identities,
requires separate token/opcode-matched acknowledgements, and propagates
any error to the existing final-CLOSE cleanup. It does not send PAUSE
or RESUME, forward their events to ALSA, or change ordinary PCM.

`tests/fullio-pull-events.py` checked the extracted kernel encoder,
order, reserved zero words and 8-byte alignment, invalid dimensions and
identity, and immediate failure at each of the three command positions.
Official tags were rechecked (`next-20261120` `2c0da72b`, `v7.4-rc4`
`a4d7daea`); the current pin was kept. Native fixture
`fullio-pull-events-tskl4z` (`49wvymf5m8ajdfch210bgbpb6hv4qpis`)
built, passed DTB/module checks and booted once with private UKI SHA-256
`4c2bc95a0d62511132c2883163c1bd0d905e19bc66b17161ca6f4cc0707efc52`.
Gen20's installed image was compared to the off-ESP archive before
selection; profile and default were unchanged. Strict SSH confirmed the
new closure on `.209` and preflight verified both WSA initially
attached. One PA-off open was attempted with PCM originally closed.

**The new subscription commands were not reached.** On the first PCM
wake, raw slots were `0x14` at 42.017425 s after CLK_START/before clash
clear, and `0x00` at 42.017514 s before `sdw_bus_exit_clk_stop()`.
Both samples showed `clash=0 frame=1`; the 89 µs interval includes the
stock interrupt clear/re-enable, delay and frame check. It excludes
`sdw_bus_exit_clk_stop()` itself and any new registration command as
the first cause. A per-boot latch stored `-ENODEV`, startup returned
`-ENOTRECOVERABLE`, and no retry was performed. Slot 0 later reentered
enumeration, but both WSA stayed UNATTACHED on the read-only follow-up;
SSH/greetd stayed active, exact closure matched, and both PCMs were
closed. The previously observed `.219` loss was *after* exit; these
are not identical timings. The matched Golden source uses the same
clock-start/interrupt-clear/delay/exit ordering but differs in runtime
IRQ/hclk and EE handling; the observed bracket does not identify one
write as causal. The exact live DT uses `qcom,soundwire-v2.0.0`,
GIC SPI 170, `iface`, and `swr_audio_cgcr`, matching Golden. The
pinned match table sets `ee = SWRM_EE_CPU` for that compatible, making
the apparent EE difference inert on this controller. Main IRQ/hclk
ordering remains a real difference. Logs: `/tmp/surface-pull-events-live.log`
and the tmux build/boot log. No PA-on, load, live feedback or listening claim.

The follow-up `sp11-fullio-resume-irq-mask-audit.patch` samples after the
existing clash clear and after IRQ mask restore (before the frame wait).
Only scoped reads were added. The return fields preserve the clear
result and first nonzero result from the existing mask/enable writes;
no new writes, retry, mask policy, or error propagation. Those reads
can perturb the timing and only bound an observation, not establish
which write caused a loss. The extracted-source test covers 192
version/error combinations and enforces the original write sequence.
The replay parser recognizes both boundaries and the pre-exit sample.
Native `fullio-resume-irq-mask-G7IQQp`, closure `31cibanwp259nv84pq4frkrl0cwd7vmf`,
verified both new strings in the compressed module, the scoped PA-off
DT flags, and private UKI SHA-256
`b2c74f5dd2fccf9600290c499fb3dbc8442e5a4e1aab5c76f081b328761c12f0`.
It was not copied to ESP or selected; the `.209` faulted boot was not
reopened or restarted. Gen20 and the active SSH/greetd path were retained.

Before that build (2026-11-24 local), official `next-20261123`
`1422acaa190f2daef38ee0b8c50c6ca0fb7f3771` was compared against the
Nov 20 pin; mainline remained `a4d7daea` (`v7.4-rc4`) and `linux-7.3.y`
`1a038884`. The new next has byte-identical SoundWire qcom source and no
Denali, QDSP6 or WSA codec/macro changes in the official path diff.
GPIO shared-proxy `31678e68` propagates `-ENOTSUPP` from `.set_config`,
not from GPIO reset assertion; the Qualcomm pinctrl change concerns
pull-up decode and the MSM display change concerns initial DRM state.
None addresses the observed resume-loss bracket. Sound `for-next`
`11ef0d515100259c7979f5b4c61b6ea97c6cdc27` had identical WSA884x and
Q6APM sources to next; comparison across the previous sound tip returned
404, so the relevant files were inspected separately. A genuine
nonintegrated change, LPASS WSA macro `cd054a6e`, converts runtime PM to
`of_pm_clk_add_clks()`. That walks Denali DT order (`mclk, macro,
dcodec, fsgen`) rather than the pinned explicit enable order; core
`pm_clk_resume()` logs individual gate enable errors without returning
them. This is a candidate for separate clock-order/error review, not
a demonstrated SoundWire fix or a drop-in equivalent. Keep `next-20261120`
for this diagnostic comparison.

The pinned SoundWire core and both WSA884x drivers (pin and Golden)
agree on the simple clock-stop capability. Core skips explicit prepare
and deprepare register writes for those slaves, but still sends the
`ClockStopNow` broadcast. The Qualcomm broadcast waiter is completed
by `SPECIAL_CMD_ID_FINISHED` (bit 10); `CLK_STOP_FINISHED_V2` (bit 14)
is separate and was only cleared by the common IRQ loop. Upstream
`6c067677192f` protects hclk against concurrent handler access by
masking the main IRQ around gating, but does not wait for bit 14.
Do not interpret the existing `after-enter-clock-stop` `result=0`
as proof that bit 14 was observed or processed before hclk was gated.

`sp11-fullio-clock-stop-finished-audit.patch` prints the raw value
from the *existing* PM status read and marks a rate-limited dispatch of
bit 14 in the existing version-2+ IRQ branch. The parser and
`tests/fullio-clock-stop-finished.py` distinguish successful command,
pending bit, and threaded IRQ observation (and accept old logs without
raw bits). Silence is not negative proof, notably with rate limiting
and non-atomic snapshots. No new register reads, IRQ handler writes,
wait, or recovery were added; logging can still change timing.
Official tags were unchanged from the prior comparison. Native
`fullio-clock-stop-finished-7Lmbso` (`qbxxf40fv9zd4xhphrkqhimgv1ikvadd`)
passed module/DT and private UKI verification, SHA-256
`86f0af47eca1cc7e27c813f5bf4bc1f6c0ecea98c5b76b87f1055d630386fc0a`.
Not selected at build time; the old `.209` closure and Gen20 profile
were unchanged, SSH/greetd active, and no ALSA open was retried.

The verified UKI was later selected **once for passive boot only**.
Initial staging hit ESP `ENOSPC` (35 MiB free); no entry was selected.
Two known inactive one-shots (isolated ring-map and ring-attach) were
copied byte-for-byte off ESP to root-only
`/var/lib/surface-recovery/fullio-retired-oneshots-4lS2PN`, their four files
hash-checked, then only those ESP copies were removed (114 MiB free).
The active and Gen20 entries were not removed. The retry was of UKI
installation, not of the earlier SoundWire failure. Strict SSH found
`.237` booted in the exact `qbxxf40fv9zd4xhphrkqhimgv1ikvadd` closure,
with greetd healthy, the one-shot consumed, installed test UKI equal
to the off-ESP copy and Gen20 UKI equal to the off-ESP rescue archive.

Passive entry on `.237`: slots `0x14`, frame `0`, return `0`, raw IRQ
`0x00000000` at 20.260134 s. No `clock-stop-finished-irq` dispatch or
resume was logged by the read-only recheck. This is an observation gap,
not proof that the controller never asserted bit 14. Both WSA stayed
attached and all four runtime-PM devices were suspended; both PCMs
were closed, no `SET_CFG` was reached and no PCM open was attempted.
Niri accepted screen-off on the fixture only. Evidence:
`/tmp/surface-clock-stop-finished-live.log`; tmux logs use the pinned
`.237` SSH host. This passive run does not reproduce or explain detach,
and does not verify protection feedback, physical cutoff, or audio.

The next experiment isolated command acceptance rather than repeating
that wake. `fullio-pull-events-held-QB0ev2` booted once on `.151` in
`/nix/store/z8c0dv4dsgs1g4zsmvx666r80g45kxlv-nixos-system-surface-26.11.20261121.56f282a`
with private UKI SHA-256
`b9d7b1c8a4d857669aaf2d918425753ce6354b2463d5b2c392ac1009b6235571`.
Kernel and `q6apm-dai`, `snd-q6apm`, `soundwire-qcom` modules were
byte-identical to the passive `.237` boot; the held fixture adds its
scoped DT sidechain/tap flags and the two discovery-time PM votes.
Official tags had not changed. Gen20 and exact UKI/ESP byte comparisons,
SSH/greetd, both WSA attached and no PCM open passed pre/post; no
clock-stop transition was observed and both suppliers were `on/active`.

The single PA-off run now **reached and passed** the three token-matched
subscriptions at 44.732073 s, after `SET_CFG` and before SHMEM format.
SP/SPVI tags and endpoint mute survived PREPARE; the independent DSP
position advanced at 44.969171 s. STOP 44.979028 s, CPS register restore
44.992014 s, final CLOSE 44.996562 s, both UNMAPs and release
44.996748 s. Both WSA remained attached. The headset/desktop path was
not used. The audit sent neither PAUSE nor RESUME, started no ordinary
ALSA PCM, and collected no DIAG feedback; tap setup and TX0–3 off are
not live VI/CPS protection evidence. Preserve the discovery hold as a
control, not as a production clock or recovery policy. Log:
`/tmp/surface-pull-events-held-live.log`.

The capture-only closure no longer allocates or pre-maps playback
backing for MultiMedia1. `sp11-fullio-capture-only-no-render-backing.patch`
shares the same playback-only graph-0 predicate at `pcm_new` and
`pcm_free`, separate from the independent diagnostic ring selector.
Both render open gates remain before graph allocation. The extracted
code checks all combinations of board, DT marker, graph 0/1/2, and
playback/capture substreams; the independent ring scope test still
passes. This changes no legacy mapping on other configurations.

Native `fullio-capture-no-render-backing-QHUjaD` booted once on `.229`,
exact closure `/nix/store/xrkhbpcj3bdvy0hhzv5kcflqkygywip8-nixos-system-surface-26.11.20261121.56f282a`,
private UKI SHA-256
`408cb1fff145ae31a5ac301fd6b86053a602d7db88cd374a1f8ea8462fd24335`.
Official next/mainline tags were unchanged. The module, PA-off/capture-only
DT flags and Gen20 ESP rescue were verified before selection. Two old
unused diagnostic pairs (no-legacy-map and resume-boundaries) were
byte-checked off ESP in `/var/lib/surface-recovery/fullio-retired-oneshots-pdaGj6`
before removing just their ESP copies. Boot logged the skipped backing
at 9.733172 s. Normal PipeWire exposed `[FL, FR]` MicArray and no hardware
sink; two temporary stereo recordings (232448 and 238592 frames) both
varied and had no clips, and were deleted. No test attempted render open.
Immediate post-capture preflight returned 1 without a fault message;
read-only follow-up (no capture or render retry) passed, with both PCMs
closed, both WSA attached, SSH/greetd active, no witnessed WSA resume or
ring activity and Gen20 default. This is capture regression evidence,
not physical channel-map or speaker acceptance. Log:
`/tmp/surface-capture-no-render-backing-live.log`.

`sp11-fullio-mix-unity-cap.patch` additionally caps the two Denali
FullIO WSA MIX digital controls at code 84 (signed register unity,
TLV −84 dB + 84 one-dB steps). Both existed on `.229`, with current
code 84 but an exposed maximum of 124 (+40 dB). The scoped card init
fails if either cap cannot be installed; generic and Gen20 card
behavior is unchanged. The pinned `snd_soc_limit_volume()` clips the
current control if required; the extracted `soc_mixer_valid_ctl()`
test verifies 0/84 accepted and 85/124 rejected for both channels,
plus scope and failure propagation. No over-limit mixer writes were
attempted on hardware.

Native `fullio-mix-unity-cap-tGAsXI` booted on `.218` in exact closure
`/nix/store/4iw2l6865wixgl4s8q4icyafw2281aq7-nixos-system-surface-26.11.20261121.56f282a`
with verified private UKI SHA-256
`b00e6bccd5add9acb06a70a5d60621b32c0986d17baf3fe243096b02bc192a07`.
Official tags unchanged, machine module and capture-only DT verified,
Gen20 recovery bytes checked before selecting the one-shot. Read-only
`amixer cget` showed MIX 84/84 on each channel (current level did not
increase or change), main digital 81/81 (−3 dB) and PA 6/6 (0 dB).
Both WSA attached, PCMs closed, SSH/greetd healthy, Gen20 default, and
no observed resume or ring activity; no PA enable. Log:
`/tmp/surface-mix-unity-cap-live.log`. This closes one ALSA gain-control
gap, not composite hardware gain, verified active routing, VI/CPS or
physical protection under load.

The static render/feedback routing audit now checks both **built** artifacts.
`tests/fullio-topology.py` requires exactly one Golden media/interface pair
per endpoint in its intended stage: speaker RX0 `0x4157` (48 kHz, 16-bit,
WSA interface 1), VI `0x4026` (8 kHz, 32-bit, WSA interface 1), and CPS
`0x402b` (24 kHz, 32-bit, WSA interface 3); all are fixed-point, two
channels, active-channel mask `0x03`. The VI row describes the endpoint
container, not four independently observed V/I components. These are
staged FE parameters; the physical backend must not configure a second
DSP copy of the graph. `tests/fullio-render-dtb.py` checks left/right
codec addresses, distinct phandles, port maps, the three CPU/codec DAI
link tuples and exact DAPM speaker output edges independently of phandle
number allocation. It is run in the clock-off fixture DTB derivation.

Both verifiers passed on untouched artifacts, including the live `.218`
closure's built DTB. Mutations of the actual compiled topology (mono RX0,
wrong interface, or lost channel mask) and private copies of the DTB
(swapped speaker routes or wrong left port group) were rejected. Native
`fullio-render-wire-audit-9cFZqV` built both validated derivations and
`/nix/store/75a42b1iszszsbvs938a0y3d6zsz1614-nixos-system-surface-26.11.20261121.56f282a`
without a kernel rebase, profile switch or reboot. The checked properties
are necessary wiring and format declarations; they cannot establish
DSP runtime direction, actual analogue left/right, or protection liveness.

### Same-graph RX0 readback (PA-off, 2026-11-24 local)

`fullio-sink-readback-audit` is a separate discovery-held fixture, not a
playback prerequisite or an ordinary boot change. It uses the independent
attached ring and the existing bounded GET_CFG RPC on graph 0. After
PREPARE/SP/SPVI verification it asks for the 12-byte RX0 media row first,
then the 12-byte interface row only if the first matches exactly. A
missing/negative reply is reported as unverified; `-EILSEQ` means a
successfully parsed but mismatching value. This fixture never STARTs or
publishes a mute ticket. `tests/fullio-sink-readback.py` exercised both
rows with exact, mismatched, timed-out, and unexpected-positive replies.

Official `next-20261123` (`1422acaa190f…`) and `v7.4-rc4`
(`a4d7daea71be…`) were unchanged from the preceding comparison; retained
Nov 20. Native `fullio-sink-readback-Pf5ZDe` exited 0 with closure
`/nix/store/b385d64yn4gl3ja91bssx74q4zc621i7-nixos-system-surface-26.11.20261121.56f282a`.
Module strings, DT flags, and off-ESP private UKI
`9bc5e8c3408774e03af022ca8a653f82de45ad86fc0f4bd7dd6bcb28eba36dc9`
were checked. Two inactive test images were byte-verified and archived
in `/var/lib/surface-recovery/fullio-retired-oneshots-Ebh9lM`; Gen20
profile/default and image bytes against the private archive were verified
before staging. After DHCP changed to `.107`, the pinned key matched and
booted/current closures and preflight passed, with both suppliers `on`
and `active` and both WSA attached.

One PA-off prepare at 109 s: independent ring SET_CFG 109.236056,
watermarks/events 109.240189, SHMEM media 109.241008, and stereo mute
readback 109.335041. RX0 `0x4157/0x08001017` GET_CFG returned `-EIO`
at 109.352154, before the interface request; no positive runtime RX0
readback or value mismatch was observed. TX0–TX3 were verified off, final
CLOSE ACK at 109.373603 and both UNMAPs/release at 109.373774; final
preflight passed. No START, retry, tap capture or audible playback. The
local full kernel and test excerpts are `/tmp/surface-sink-readback-{kernel,live}.log`.
The public generic AudioReach ALSA endpoint implementation handles this
media parameter in SET but not in its CAPI GET switch; this supports
checking read capability separately, not inferring the proprietary DSP's
exact reason from Linux `-EIO`. Windows `GetDmaCfgInfo` hits use the
interface selector but describe endpoint HW lookup, not proof of a
same-graph GET reply from `0x4157`. Do not reuse either as live lane or
protection evidence.

### Independent ring callback boundary and future ALSA STOP contract

`sp11-fullio-ring-no-pcm-callback.patch` replaces the late PREPARE-time
watermark flag: an independent diagnostic graph has no PCM callback or
PCM callback context from GPR port creation, and its ALSA facade does
not advertise PAUSE/RESUME. Basic control ACKs and token-matched
GET_CFG replies are handled before the unsolicited module-event path.
Ordinary graphs still deliver watermarks, with the module-event header
length checked before access. `tests/fullio-ring-no-pcm-callback.py`
exercises absent, truncated, valid and unknown module-event envelopes
against the actual extracted dispatch branch.

Review of the pinned ALSA/GPR source constrains the normal playback
implementation separately. `snd_pcm_action_lock_irq()` takes the PCM
stream lock for pause/resume; the pinned APR driver dispatches through a
single RX worker, and `gpr_free_port()` removes the port then flushes that
worker. A waiter in trigger or close must not depend on RX doing an
inline `snd_pcm_period_elapsed()` under the same stream lock (including
linked streams). Also, `snd_pcm_do_stop()` discards the STOP trigger's
return code and advances ALSA state; `snd_pcm_sync_stop()` discards the
component sync return. `soc_pcm_hw_clean()` similarly does not propagate
DAI digital-mute failure. Error returns alone therefore cannot enforce
shutdown. Future normal FullIO playback needs a separate sticky render
admission gate and ownership proof, with PCM notification deferred off RX
and drained before any callback context is freed. The diagnostic change
neither implements nor advertises normal FullIO START or SOFT_PAUSE.

`tests/fullio-pcm-order.py` checks the pinned ALSA/APR and composed q6apm
source before exercising this contract. There is a second lock cycle
that muting only the render watermark cannot remove: ordinary q6apm
capture calls `snd_pcm_period_elapsed()` for `DATA_READ_DONE` on the same
single APR RX worker. ALSA can link streams with matching states and
`nonatomic` settings; `snd_pcm_action_group(..., true)` takes the
peer's mutex **or** spinlock before running trigger. A queued capture
callback can then wait for that peer lock ahead of the render ACK,
while render trigger waits for the ACK. The reference's local render
watermark suppression does not cover this schedule; making a PCM
nonatomic only changes the lock type.

For a future ordinary FullIO path, trigger must not wait for APR RX
or flush a notifier/worker while holding the stream/group locks. A
publish-only trigger is a candidate, not proof of correct PCM START:
async start failure, XRUN, link-group rollback and first-frame timing
still need a concrete driver contract. Retire the notification epoch
under serialization, remove the port and drain its RX callbacks, then
synchronously drain notifications outside the stream/group locks before
freeing context. A notifier that can call back into STOP must not hold
private state locks across ALSA notification. The offline model detects
the linked-capture and locked-drain cycles, enumerates STOP/callback/drain
interleavings, and rejects mutants that permit revoked notification or
free before port drain. Cold render reopen is independent of ALSA SETUP:
a missing DSP STOP, clock-off, paired PA-off, CLOSE or both UNMAP proofs
must deny reuse. This does not change diagnostic callbacks, normal capture,
PA state or the currently booted closure.

Native AArch64 `fullio-ring-no-pcm-callback-bfQus9` built the existing
held taps fixture (status 0) while retaining `next-20261120`; official
`next-20261123`/`v7.4-rc4` tags were unchanged. Exact closure:
`/nix/store/mvp19bfsqacxw3wq2136pk0skfvcq7zv-nixos-system-surface-26.11.20261121.56f282a`.
Build log confirms patch application; built DTB, selected modules and
private UKI SHA-256 `7f3254be8ccc875c4c46dddd512532759e7281c96dd59ca9758dde7ad2a95f1e`
were checked. Gen20 profile/default and archived image bytes were checked
before selecting this exact UKI once. Pinned SSH rediscovery at `.205`
verified the exact boot and both WSA attached; suppliers were on/active
before and after the test with no observed clock-stop/resume or clash.

One PA-off open produced SET_CFG ACK at 48.953067 s, subscription ACKs
48.956045, mute and SP/SPVI tag proof after PREPARE 49.047063/49.047120,
DSP position progress 49.233169, STOP ACK 49.245999, CPS restoration
49.257971, CLOSE 49.262020 and both UNMAPs/release 49.270142. Final
preflight passed and all PCMs were closed. Logs are
`/tmp/surface-ring-no-pcm-callback-live.log` and
`/tmp/surface-open-test-switch.log`. The fixture did not write PCM samples,
exercise ALSA PAUSE/RESUME, collect active VI/CPS, or enable either PA.

### Decline ClockStop exit when the FullIO link has already failed

On `.209`, the frame generator was already running but raw slots fell
from `0x14` at 42.017425 s to `0x00` at 42.017514 s, before
`sdw_bus_exit_clk_stop()`; the later slot check did not prevent that
transaction. The `.219` sample lost slots only after the exit boundary,
so a pre-exit check alone does not replace the post-exit observer.
`sp11-fullio-resume-admission.patch` checks both sides of exit on the
opt-in link-gated controller. It stops progression on an unsuccessful
CGCR reset, EE/CLK_START setup, clash clear, interrupt restoration or
frame wait, and skips exit for unreadable/missing previously attached
slots or a latched error. It preserves the first negative error; positive
controller command failures are normalized to `-EIO` rather than
published as success. An exit failure is latched before doing any more
slot reads. Ordinary controllers retain the previous operation order.

After the resume callback has acquired iface/IRQ, an incomplete link
keeps that ownership and returns to PM as powered, not operational for
FullIO. The separate sticky admission gate denies new render work, and
runtime suspend of the incomplete controller refuses another clock-stop
attempt before FIFO access or state changes. This is a quarantine for
an opt-in fixture, not a claim of no I/O from every other SoundWire
client, not recovery from detach, and not an autonomous amplifier cutoff.
Offline tests on composed source exercise the `.209` and `.219` slot
sequences, failed reads and setup operations, first-error retention,
rejected re-suspend, and the unchanged legacy resume-write ordering.

Official next/mainline/stable refs were unchanged (`next-20261123`,
`v7.4-rc4`, `linux-7.3.y` at `1a0388846138…`); kept `next-20261120`.
Native `fullio-resume-admission-tSBHEB` built successfully (status 0):
`/nix/store/l8jk8dvfmvbhjicx2mvhr9qr1c0vzmsm-nixos-system-surface-26.11.20261121.56f282a`.
Verified patch application, SoundWire module SHA-256
`e995813179ec5eaa343e6831ff7f716d2792f1153ee73371b934772d4c59a835`,
passive DTB flags (`capture-only`, link gate, PM audit; no START or
post-PA flag), and off-ESP UKI SHA-256
`e52441384829aac8141c23a13791d2dcf36077bd0831d4b73a3411c92f9cfa70`.
Candidate is not installed or selected. No new live resume sample,
induced detach, playback attempt, or change to Gen20.

### Passive frame-generator stop handoff

Same-board reference `2026-08-17-SOUNDWIRE-POST-STOP-FRAMEGEN-WAIT-V16-REJECTION.md`
and patch `0057` separate the broadcast ClockStopNow ACK from the
physical controller frame-stop state (`SWRM_COMP_STATUS[0]`). Windows
checks the latter before gating lower resources. Reference v16 observed
frame-stop-before-gate and an acoustic improvement versus its bad repeat
cycle, but failed its acoustic parity gate. Reference v17 (skip CGCR
reset) and v19 (matched 500 ms stop timing) were also rejected; neither
change is adopted here.

`fullio-frame-stop-audit` is an independent capture-only/passive DT
fixture. After a successful ClockStopNow and only on link-gated Denali
with the new opt-in DT flag, `sp11-fullio-frame-stop.patch` checks actual
frame state before IRQ/hclk release: up to 30 reads separated by 1–1.1 ms
sleeps. A failed read or timeout fails suspend, latches the first link
error and keeps iface/IRQ ownership. `-ENODATA` is not a positive command
ACK and does not trigger a wait. The generic and prior fixture paths
are unchanged. Existing CGCR reset and runtime-PM timers are unchanged.
The composed-source PM test checks immediate and last-read completion,
unsuccessful reads and timeout without IRQ/hclk release, and no polling
on empty-bus and unmarked paths. Bit-14 pending/dispatch and the polled
frame status remain separate observations.

Native `fullio-frame-stop-xbcqnI` status 0 retained `next-20261120`
(official refs still `next-20261123` and `v7.4-rc4`). Candidate
`/nix/store/88l72pm1vwaxn615qdyarxvmvyfl1rlr-nixos-system-surface-26.11.20261121.56f282a`
carried the checked capture-only/PM/link/frame-stop DT flags, SoundWire
module SHA-256 `57a81dae58f91e77b72a6d98c6fb5256824b0cfe8a40cfc7a999b3e53e738b2b`,
and private UKI SHA-256 `8a009b46f96afa8131560215f57951924041f827ccadc54800d64097231a0419`.
Verified archived Gen20 image against ESP and kept it default. Two
inactive images were archived byte-for-byte in
`/var/lib/surface-recovery/fullio-retired-oneshots-fBHWKE` before staging.
The one-shot returned via pinned SSH at `.152` and matched its booted
and current closures. `tests/fullio-frame-stop-smoke.sh` opened no PCM:
ClockStopNow returned 0 at 20.490034 s with slots `0x14`, frame=0,
raw IRQ=0; at 20.490410 s, the very first checked read reported
`COMP_STATUS=0x800008` (bit 0 clear) before iface gate. Both suppliers
and WSA slaves reached runtime suspend; both WSA remained attached;
final SSH/greetd/PCM/Gen20 preflight passed. See
`/tmp/surface-frame-stop-live.log` and `/tmp/surface-open-test-switch.log`.
No retry, wake-triggered check, detach, or PA-on action. This sample
validates the gate and shows the first passive entry needed no poll
sleep; it does not explain slot loss on a later resume.

**Controller-only resume control, same closure.** Sysfs identifies
`6b00000.codec` as `6b10000.soundwire`'s runtime-PM supplier (`runtime_pm=1`,
not `sync_state_only`). Reused the exact frame-stop image (private and
archived bytes matched, same SHA-256); archived only the inactive
pre-START SOFT_PAUSE image in
`/var/lib/surface-recovery/fullio-retired-oneshots-9t94j9`. Gen20 bytes,
default and profile passed verification. On the one-shot at `.135`, the
*first* ClockStopNow ACK at 20.437023 s instead reported `frame=1`, slots
`0x14`, raw IRQ=0. The second checked read at 20.438009 s proved
`COMP_STATUS=0x800008` before gating. Thus the ACK and frame stop are
observably distinct on this very device; the preceding first-read result
was not universal.

`tests/fullio-frame-stop-resume.sh` then issued one ordinary runtime-PM
vote to the controller only, no codec or PCM open, under a filtered
10/10-entry RPM trace. The macro became active at 53.627908 s before the
controller's pre-CGCR snapshot at 53.628082 s; neither WSA codec had a
PM event. Slots stayed `0x14` through CGCR reset/CLK_START and exit. Bit
14 dispatched at 53.628845 s, **during resume** after IRQ restore and
before exit, not as an observed first-idle completion. That timestamp
locates dispatch, not when the bit first asserted. Normal `auto` policy
was restored only after the clean postflight. Next idle passed at
57.465394 s (first read); both suppliers and codecs were again suspended,
both codecs attached, PCMs closed, SSH/greetd healthy. See
`/tmp/surface-frame-stop-resume-live.log`. The saved trace passes the
supplier-order check; overflow and wrong-device mutations are rejected.
This is one successful supplier-only wake and does not establish
that the guard fixes intermittent detach or that codec replay is its cause.

**Paired left-codec control, same boot/closure.** After all four devices
were again `auto/suspended`, the same script issued one ordinary vote
only to the left codec. The scoped trace captured 30/30 entries: WSA
macro `RPM_ACTIVE` at 223.423111 s, master `RPM_ACTIVE` at 223.423831 s,
then left `regcache_sync` 223.423837–223.425535 s with 15 enclosed regmap
write events. The right codec had no PM or regmap event. Within the
kernel journal, raw slots stayed `0x14` through CGCR/CLK_START and both
sides of ClockStop exit, with bit 14 dispatched during resume again.
Use ordering within each trace, not direct sub-millisecond subtraction
between journal and tracefs clocks. Restore to `auto` passed; at
233.680079 s ClockStopNow again acknowledged while frame=1, and the second
checked read at 233.680386 s proved frame stop before the gate. Final
preflight found all four devices suspended, both WSA attached, SSH and
greetd healthy, all PCMs closed and Gen20 unchanged. Saved
`/tmp/surface-frame-stop-left-resume-live.log` (register values omitted).
Trace checks reject overflow, right-codec activity and a missing replay
boundary. This proves a real one-sided replay can finish without detach;
it does not isolate the intermittent failure or qualify simultaneous
render startup, active protection, or speaker output.

**Natural-idle PA-off ALSA control.** `fullio-frame-stop-render-audit`
adds `qcom,denali-fullio-wait-frame-stop` to the existing non-held
ring/taps fixture, with real link admission and no seeded fault or
post-PA path. No kernel change/rebuild: native system build reused the
verified after-START modules byte-for-byte. State
`/home/keke/.local/state/fullio-frame-stop-render-qNXVpE`, status 0,
`/nix/store/hx9lrfq1bls8k2wm482qlqyi4gd6aybx-nixos-system-surface-26.11.20261121.56f282a`;
private UKI SHA-256
`0c0f51eac743af557f7d5c08793414e823a5f6ee30be76988e84880f80639a9d`.
Archived only the inactive after-START SOFT_PAUSE entry/image to
`/var/lib/surface-recovery/fullio-retired-oneshots-2wRkNX` after byte/hash
checks. Pinned SSH rediscovered `.104` on the exact closure.

`tests/fullio-frame-stop-render-smoke.sh` required all four PM devices
`auto/suspended`, first frame-off proof at 19.618405 s, and no prior
resume; no PM hold or preliminary vote. Its one prepare resumed with
slots `0x14` through CGCR, CLK_START and ClockStop exit (49.527045 s).
SET_CFG followed at 49.547052 s; subscriptions, SHMEM, stereo mute,
SP/SPVI and TX0–TX3 off readback passed. Cursor at 49.826988 s advanced
sequence 173→177, bytes 2496→3264. STOP 49.835377, CPS restoration
49.847469, CLOSE 49.850997, both UNMAPs/release 49.859251. The ALSA
`-EOPNOTSUPP` is the fixture's intentional prepare-only denial after
its internal audit, not desktop playback success. No trigger, PCM write
or PA enable. At 60.660070 s the subsequent stop ACK still had frame=1;
second read proved frame-off at 60.660428. Final preflight confirmed
all four again suspended, both WSA attached, all PCMs closed, SSH/greetd
healthy, and Gen20 unchanged. Logs `/tmp/surface-frame-stop-render-live.log`
and `/tmp/surface-open-test-switch.log`. One successful real wake/silent
transport cycle without hold does not establish the intermittent detach
rate or validate live protection.

**Close the post-failure codec-transfer gap (offline negative tests).**
The left-only vote established that the SoundWire parent becomes active
before WSA regcache replay. In a failed FullIO resume the controller
intentionally returns success to runtime PM to retain its iface and
IRQ ownership, so the codec may enter `regcache_sync()` despite the PCM
admission latch. The revised `sp11-fullio-resume-admission.patch`
publishes the sticky `fullio_resume_incomplete` flag before returning to
PM; Qualcomm `xfer_msg` checks it before address-page handling and any
slave-message FIFO access. `SDW_CMD_FAIL_OTHER` maps to `-EIO` in the
SoundWire core; any core retries hit the same software gate and do not
submit hardware commands. This only covers new slave messages after
publication. It neither cancels an in-flight transfer nor blocks direct
controller IRQ/status access, and does not turn a general transport
fault into proof of PA shutdown.

`tests/fullio-resume-admission.py` compiles the actual composed resume
and transfer branches. Healthy paged read/write reaches the mocked
FIFO and updates the page cache; each of 11 failed resume cases denies
both operations without changing the cache or read buffer. Removing the
transfer guard fails the model at the first quarantined read. Composed
resume-boundary, PM precondition, bit-14 and detach tests also passed
with the entry-latch and frame-stop patches in queue order. On Nov 24,
mainline `v7.4-rc4` and `next-20261123` had the same tag hashes as the
preceding comparison; retained `next-20261120`. Native build-only state
`/home/keke/.local/state/fullio-resume-xfer-uBA3hG` finished with status 0:
`/nix/store/2819q1q6lfnsk8crlqaxy0aqmh5vd3zz-nixos-system-surface-26.11.20261121.56f282a`.
The built DTB passed the routing check. `soundwire-qcom.ko.zst` SHA-256
`721697ca68b59270bd9684e4708ba251f0b06fa41c316cf5e606d4e0f9701cf0`;
AArch64 disassembly checks the new flag before reading the message page
selector. Verified off-ESP private UKI SHA-256
`f12fa6e0a00a4bd45f60df1a478269d6bdda2d04f9fa1516206efc1c1fb53899`.
The candidate was not selected; read-only preflight on the running
`.104` closure passed again, Gen20 unchanged. No failed resume was
induced, and this evidence is not a live recovery or protection test.

**Distinguish an ignored ClockStop command from an empty bus.** The
Qualcomm broadcast helper latches `-ETIMEDOUT` on missing completion,
but its write path returns `SDW_CMD_IGNORED`, which the SoundWire core
maps to `-ENODATA`. The old runtime suspend code could ignore that
return, skip the frame wait and release IRQ/iface despite a fault. It
could also make a second ClockStop attempt after a failed frame wait.
`sp11-fullio-clock-stop-quarantine.patch` makes the first latched error
win, treats ignored prepare/broadcast after a previously attached slot
as `-ENODEV` without an empty-bus exemption, and extends the same sticky
PM quarantine to uncertain entry and frame-stop failures. It retains
IRQ/iface, blocks subsequent suspend before FIFO checks and denies new
slave messages via the same transfer gate. An ignored result on a
never-seen, non-faulted bus keeps its existing semantics. An unrelated
existing link latch refuses suspend but is not automatically repurposed
to deny cleanup transfers. Unmarked controllers are unchanged.

Composed-source models cover a core-visible `-ENODATA` with an internal
broadcast timeout latch, known-slot ignored prepare/broadcast, never-seen
bus, timed-out and unreadable frame state, no retry side effects and
healthy PM. All six related models passed. No physical failure, PA
cutoff or new protection behavior is inferred from these models. Official
Nov 24 `v7.4-rc4` and `next-20261123` refs unchanged; build retains
`next-20261120`. Build state
`/home/keke/.local/state/fullio-clock-stop-quarantine-8g0Lli`, status 0:
`/nix/store/7ry60lf2bgf1x1xabw98vf6v24j4nlrh-nixos-system-surface-26.11.20261121.56f282a`.
Removing the first-error read fails the model for the masked timeout.
Native build applied the patch and checked the Golden DTB routing;
`soundwire-qcom.ko.zst` SHA-256
`7cf98a6c974c91c20d4b936f3e8ab2d8e8684460f60b417d3a304c2d7f29717b`,
private UKI SHA-256
`413cdd0cdc2d7fd3ce013d5bd20b0e7c46a04faa035f7c88af5fef9c44568631`.
The inactive passive fixture's re-created BLS file did not match the
old archive even though the UKI did; no files were removed at that
check. Archived the exact current inactive pair in
`/var/lib/surface-recovery/fullio-retired-oneshots-f6ooHs`, verified
bytes and hashes, preserved the running fixture. Verified Gen20
bytes, profile and default before selecting the new one-shot. Pinned SSH
rediscovered `.163` on the exact closure. First stop ACK at 20.390109 s
had frame=1; second read at 20.391044 s proved stop. The single natural
idle PA-off prepare retained `0x14` through ClockStop exit at 65.153826 s;
verified mute, SP/SPVI and TX clocks off. Cursor at 65.435996 s advanced
sequence 170→174, bytes 1920→2688. STOP at 65.441062, CPS restore
65.458047, CLOSE 65.460048, both UNMAPs and release 65.460219. No
ALSA trigger, sample writes or PA enable. At 76.014517 s the next
idle frame-stop check passed; both WSA remained attached and all four
PM devices returned to `auto/suspended`. Final exact-system preflight
confirmed Gen20, SSH/greetd and all PCM closed. Evidence
`/tmp/surface-clock-stop-quarantine-live.log` and
`/tmp/surface-open-test-switch.log`. This is the healthy path on the new
closure. The masked-timeout path was tested offline only.

### Require actual byte-cursor progress in the PA-off transport audit

The position page's sequence publishes a coherent snapshot; it can change
without any byte-index movement. Public AudioReach `pull_push_mode.c`
clears the sequence, publishes the byte index/timestamp, then publishes
an incremented sequence. That layout explains the read protocol, not
Denali's proprietary DSP scheduling. `sp11-fullio-ring-byte-cursor.patch`
now requires two coherent samples with increasing sequence and different,
4-byte-aligned cursors inside the configured stereo S16_LE ring. A cursor
wrap to zero is valid; a stationary or aliased cursor is insufficient
proof within the bounded sample window. Position-page initialization,
mute, STOP/CLOSE/UNMAP requirements and ordinary PCM/capture are unchanged.
`tests/fullio-ring-position.py` covers zero, stalled index, wrap, torn
samples, out-of-range/unaligned cursor and inconsistent sequence/index.

Independent cutoff literature cross-check: the publicly indexed Qualcomm
[Device Specification PDF](https://assets.sourcengine.com/datasheets/a964520a-cee5-4ad1-82eb-ba190cbdf1c4.pdf)
was downloaded and its cover read; it is **WSA8810/WSA8815**, document
`LM80-P2751-28 Rev. A`, not WSA8845. Do not transfer its timing tables.
The WSA884x driver and binding substantiate the enabled watchdog, timeout
selector and active-low shutdown designation, not output cutoff latency
on this revision or the board's shared reset topology.

`fullio-byte-cursor-FBvmOy` built natively (status 0, no pin change):
`/nix/store/an5397826m0d1rhb9zyvjwaq66pg96wn-nixos-system-surface-26.11.20261121.56f282a`.
Built held/muted DT flags and routing checked; `snd-q6apm.ko.zst`
SHA-256 `d54f7022fb3a7b78854be7300ccdfd445f218154b745f9e6e113bfb25c6608f5`,
private one-shot UKI SHA-256 `f3aea01854f82a184959b5dc993466533ca5d0e9eaa11f2e8c991474f92e2028`.
The pre-deploy check matched archived Gen20 bytes and preserved its
default/profile. The one-shot came back at `.243` with the pinned SSH
key; exact closure, PA-off preflight and discovery holds passed. The
single audit measured sequence **164→168** and byte cursor **768→1536**
at 54.816050 s (192 stereo frames of modulo movement, consistent with
four 1 ms publications). `GRAPH_STOP` at 54.825052, CPS restore
54.837568, final `GRAPH_CLOSE` 54.841085, and both UNMAPs/release
54.841495; postflight and smoke status 0. Both codecs were attached and
all PCMs closed. No samples were written, no desktop playback started,
and no live VI/CPS or loaded PA evidence was gathered. Full excerpt:
`/tmp/surface-byte-cursor-live.log` and `/tmp/surface-open-test-switch.log`.

### Isolated SOFT_PAUSE command and completion check

`fullio-soft-cycle-audit` uses the existing discovery-held, PA-off DMA
fixture, with one pause/release cycle between observed cursor progress and
final STOP. Golden render-parity v2 identifies zero-body SET_CFG
`0x0800102e`/`0x0800102f` for module `0x466b` and corresponding completion
IDs `0x0800103f`/`0x08001043`. The audit arms the expected event on the
one-shot graph port before each send. It separately demands a token-matched
SET_CFG ACK and an empty completion from that DSP module to that graph
port, allowing either arrival order. These module events are tokenless;
this diagnostic intentionally never rearms the same event or repeats a
cycle after ambiguity. It is not a general reusable desktop pause API.
The existing PCM callback remains absent. Timeout/rejection returns to the
existing verified STOP→CLOSE→UNMAP path rather than issuing release or
retrying a failed pause. Success also requires renewed byte-cursor
progress and mute, both PA-off and TX-clock-off checks after release.
`tests/fullio-soft-cycle.py` checks both orderings, event framing/source,
negative ACK and missing completion; it does not exercise ALSA trigger.

First build caught `gpr_hdr.dst_port` versus the actual `dest_port`;
the corrected native build produced
`/nix/store/z011p5ajy6kjl9gddcqr56va0qwfwm8j-nixos-system-surface-26.11.20261121.56f282a`
with private UKI SHA-256
`067ff8a1afa5d28b7393e2aff56443cfb5c15f083377f9f8e057aac107016a6c`.
On `.230` the first live attempt exposed a separate placement mistake:
the pre-START side of the tap verifier fell through to the new hook.
The ring's `start_attempted` guard returned `-EPERM` at 58.127168 s;
neither GRAPH_START nor either pause command was sent. CPS registers
restored at 58.154993, then CLOSE 58.163029 and both UNMAPs 58.171288.
Preflight passed again. `/tmp/surface-soft-cycle-live.log` preserves this
failed diagnostic. Added the explicit `started` guard and a composed-source
placement check; do not repeat the PCM open on the original closure.

The corrected `fullio-soft-cycle-after-start-WBBI4q` built natively
(status 0) on the unchanged pin, closure
`/nix/store/jcgkssbiwm3hpayd8336rxvksy0hhmxc-nixos-system-surface-26.11.20261121.56f282a`.
Checked the held/ring/muted/soft-cycle flags and absence of post-PA and
seeded faults, the Q6APM/DAI modules, and private UKI SHA-256
`3e7045d5743ae02be78f2e6dab6b8dbe1a9a4a028a97066e57a0cbfa32e6e39e`.
Archived the inactive frame-stop image in
`/var/lib/surface-recovery/fullio-retired-oneshots-jON4i1` before staging;
Gen20 profile/default and archived bytes passed verification.
The one-shot returned at `.121` via pinned SSH. Both suppliers were
active before the single test; no ClockStop transition or clash was
observed on the held boot. In order: first byte-cursor proof 48.186067 s
(`1920→2688`), pause ACK+event 48.238075, resume ACK+event 48.238285,
mute readback 48.238327, renewed cursor proof 48.245042 (`1344→2304`),
STOP 48.253074, CPS restore 48.265039, CLOSE 48.269074 and both
UNMAPs/release 48.269659. Smoke status 0, postflight: both WSA attached,
all PCMs closed, SSH and greetd healthy, Gen20 still default. Logs:
`/tmp/surface-soft-cycle-after-start-live.log` and
`/tmp/surface-open-test-switch.log`. This proves the single DSP control
cycle, not an ALSA PAUSE/RESUME trigger, cursor behavior while paused,
active VI/CPS feedback, or physical speaker cutoff. No PCM samples
were written and no PA was enabled.

### Readiness for audible acceptance

| Required evidence | Current result |
|---|---|
| Same-board Linux playback is viable | Reference geocausa v19c/Golden-v33 passed protected playback; upstream repo HEAD rechecked at the pinned `3232e1d`. |
| This port has verified render transport and recovery | Native `an539782...` proved aligned DSP byte-cursor movement and STOP, CLOSE and both UNMAPs. That experiment used discovery hold and did not test resume. Earlier healthy resume and separate detach evidence remain; the hold is not a permanent fix. |
| Gain caps and effective live feedback | PA-off cap reads, bounded encoder and static SP/SPVI verified; 179 complete records in the clock-off tap control yielded no VI/CPS. Reference positive feedback is post-PA/post-clock, not proof for this closure. |
| Credible loaded paired loss-to-off | No qualifying trace or vendor bound for this Denali path. Neither same-board playback nor Asus's working playback/recovery evidence (`83c4f1f`, HEAD rechecked) measures the requested loss-to-output-off behavior. Software clock/PA acknowledgements and the 20 synthetic cutoff cases do not substitute. |
| Normal desktop output and user listening | Not tested. `scripts/generate-fullio-listening-check.py` prepares an 8 s, 48 kHz stereo S16_LE clip (left only, right only, then distinct simultaneous sweeps), with no audio-device access. Two local generations matched and channel order, duration, peak ≤1024 and stereo variation were verified. Observed WAV SHA-256 `b52d4ac63d8e4d33ba832628310bc43a7f62ba5e3e4eec8427d66ce21f2025b9`. Digital peak is not a physical safety claim. Do not play it on the internal route until prerequisites pass. |
| Recovery preserved | Exact `.243` fixture pre/postflight: running/booted closure match, Gen20 profile/default, SSH/greetd active, both WSA attached, PCMs closed. Off-ESP Gen20 bytes checked before staging. |

Further identical PA-off reads cannot test a loaded cutoff or the
reference's post-PA feedback state. An independently instrumented
sacrificial setup or applicable vendor timing/fault evidence is needed
to qualify that transition without repeating a real fault on the SSH
Surface. This is not a request for more proof that Linux playback works.
`fullio-pull-parity-yO670R` (`qp585xhbrn6shdjmkzhmlg2c7blq5hsh`)
built natively. The build log records application of the changed patch;
the decompressed DAI module contains both watermark and SHMEM acceptance
markers. The delivered DTB has the DMA/link/PM flags and no post-PA
flag. A verified private UKI exists off ESP, not installed or selected.
The running fixture still reported both WSA devices `UNATTACHED`, with
all PCMs closed and SSH/greetd active. No new hardware outcome is claimed.

Cross-reference: `justririll/x1e-speakers` documents actual playback
and V/I protection on an Asus Vivobook S5507QA, but also reports a track
change with both amplifiers `UNATTACHED` and register reads failing. Its
userspace recovery turns off the card profile and lets the bus idle;
that is evidence the symptom can recur even on a playing port, not proof
of the Denali cause or permission to copy automatic recovery. The
same-board geocausa acceptance remains the primary playback reference.

The previous PREPARE-only fixture remained booted at `192.168.2.138`.
After the fixture released its PM holds, two passive 300 s observations
found both codecs attached with `auto/suspended` on both codecs, the
macro and the controller. PM active counters did not increase and both
traces had 0/0 events; in the IRQ-labelled second window the `soundwire`
action remained at 17 interrupts across all CPUs. No clash, detach or
kernel fault was seen. This localizes those windows to idle, not to a
successful new resume or a reproduced fault; the earlier incident was
more than five hours into its boot. No PCM, PM policy, or boot changes
were made. The watcher now emits before/after PM and IRQ snapshots.

Rebase hazard: the [Collabora Speaker Switch proposal](https://lore.kernel.org/linux-sound/20261014-wsa884x-mute-support-v1-1-74d98d79e635@collabora.com/)
uses mixer state and `pa_on` to call a writer that changes DRE and
`GLOBAL_PA_EN` directly; it is not a separate DAC mute or a shutdown
path outside SoundWire. That control is absent from pinned next and
from the current live FullIO card. `fullio-boot-preflight.sh` now refuses
PCM diagnostics if this unreviewed control is exposed (including codec
prefixes). If rebased onto a version with the control, explicitly audit
all user-mute, PCM-trigger, DAPM, and restore call paths before deploying;
do not treat a userspace UCM profile or mute LED as protection evidence.

Live `fullio-tap-window-mW2HDH` one-shot (`192.168.2.230`): the LPASS
collector armed at 43.962088782 s, START ACK was 44.304307324 s and STOP
was sent at 44.472421178 s (168.114 ms host window, verify=0/stop=0).
Eight datagrams carried 100 valid `0x1586` records, all other taps; VI and
CPS were both absent. Mask cleanup/publication removal, PA-off/clock-off
readbacks and CPS/PM restore passed. No archive was retained. This tests
the timing instrumentation and rules out late arming for this run; it
does not test positive-payload session correlation. Do not repeat this
PA-off route without a new discriminating variable.

Research cross-checks: upstream `6c067677192f` (main IRQ around hclk)
is already present in pinned Surface-next, verified against the patch
and local controller source; do not reapply or undo it. On 2026-11-23
kernel.org listed mainline `v7.4-rc4` and integration `next-20261120`.
A targeted source comparison found that rc4's `qcom.c` does not have
that core IRQ gating pair while the pinned next file does; rc4 also
lacks the proposed `intr_lock` serialization. This is not a complete
platform delta audit, but there is no reason to switch the FullIO
baseline to rc4 just because its date is later. Upstream
`6a33b082bf6e` addresses stale interrupt state on power-up, not proof
that runtime detach is benign. Review Lee Jones's v2 09/10 and 10/10
(Nov 3, 2026) for interrupt mask serialization and stale broadcast
completion only as independent code risks. They are not in the pinned
source, and no upstream merge or causal match to this incident was
verified. If a natural fault later includes a broadcast timeout or
late completion, correlate it with PM caller/slot evidence before
considering a one-variable candidate. Never inject a live bus fault.
The actual SoundWire maintainer `next` HEAD `afd88e7ad781` is the PDM bps
mismatch fix, already present in pinned `drivers/soundwire/stream.c`.
It is unrelated to late completion. `sp11-fullio-broadcast-timeout.patch`
adds a narrower, opt-in response: if the existing timed wait does
expire, log the register and observed FIFO drain and stickily deny new
streams; leave return codes and cleanup access unchanged. It neither
changes ack arbitration nor assumes a timeout caused the earlier fault.
The extracted-code test covers timeout followed by success, unicast cleanup
and an unmarked controller; no real timeout was injected.

Pinned `drivers/soundwire/bus.c` explicitly skips unnumbered or
unattached slaves in `sdw_bus_exit_clk_stop()` and returns success when
none qualify; it also logs several de-prepare failures without passing
them back. `sp11-fullio-resume-slots.patch` checks raw controller slots
at that boundary and passes them to the existing loss latch even when
the generic helper returned zero. A lost previously attached slot or a
slot read failure denies future streams; nothing changes a PM reference,
acknowledges an IRQ early, touches a codec register or starts recovery.
The offline stub covers healthy slots, lost slots, register read failure
and zero reads on an unmarked controller. This is controller status,
not proof of successful uncached reachability of both codecs. Native
`fullio-resume-slots-MCR8la` at `192.168.2.229` exercised one ordinary
left codec vote after initial suspend. Raw slots stayed `0x14` before and
after exit, no timeout/clash/latch occurred, and all four devices returned
to `auto/suspended`; both codecs remained attached. This is positive-path
coverage; the loss branch was not injected on hardware.

Qualcomm's 23 Oct 2026 AudioReach WSA884x RFC uses 8 kHz packed V/I over
1-bit PDM DP5 and establishes capture transport before ASoC digital
unmute. It is useful to compare transport ownership and DAPM order, but
not evidence for live VI before unmute, CPS on Denali, or an independent
fault cutoff (tested targets are ThinkPad/Glymur, not Denali). The pinned
reference's 10 Aug readback matrix explicitly reports DSP error 3 for
SP thermal/CPS statistics and SPVI speaker condition, despite successful
GET framing. Do not repeat those requests as a substitute for verified
feedback or infer liveness from static calibration state.

The [22 Nov v2 series](https://lore.kernel.org/linux-sound/20261122161437.5994-1-srinivas.kandagatla@oss.qualcomm.com/)
adds explicit per-direction stream ownership, paired `.hw_free`,
codec-only opposite-direction DAPM events and a write-only calibration
trigger; its 60 s software watchdog resets an armed calibration mode,
not the PA on link loss. The series was posted on `next-20261120`, not
shown merged. Save it for comparison/rebase of our transport adapter
when generic support lands; do not stack both owners of the same ports.

One `for-7.4` prerequisite, `54c121eaeed8` (managed WSA884x runtime PM),
is already in the pinned source. It is **not** equivalent to our PM
lifetime fix. On this base `devres_release_all()` removes resources from
the lookup list before callbacks, `dev_get_regmap()` uses that list,
and the generic PM action calls `pm_runtime_dont_use_autosuspend()`
before disabling PM. The original Surface Oops already ran through
that managed action. `tests/fullio-wsa-upstream-pm-parity.py` compares
those pinned sources with the local callbacks and models the observed
teardown without unbind. It confirms why the local private-regmap and
disable-before-idle changes must both remain until upstream is genuinely
equivalent. No hardware lifecycle test was repeated.

Public AudioReach `capi_data_logging.c` supplies a module-instance
logging ID, per-instance sequence and timestamp to its logging backend;
its public Pine/DLS layout does not authenticate the Denali legacy DIAG
wire offsets. For a positive trace, seek a firmware-matched QCAT/QXDM
decode paired with raw records (or a validated private archive) and
map tap/session to the two configured source instances independently
of host receipt time. The optional offline `--external-decode` check
requires the scoped `--receive-window` and validates JSON version 1:
`graph` (integer), `binding` (`VI` and `CPS`, each with `tap`, `source`,
`session`), and `records` in capture order (each with `sha256` of the raw
packet, `tap`, `graph`, `session`). VI and CPS may have different session
IDs; their source IIDs must be `0x4026`/`0x402b`. This rejects mismatched,
replayed, missing, and mixed-session annotations but cannot authenticate
an annotation or discover legacy offsets. The decoder and graph binding
must be independently established before using it; no positive Denali
archive is presently available. Neither searching public WSA8845 materials nor
Microsoft's service guide supplied net-level APSS wiring or a hardware
watchdog/cutoff timing guarantee.
The next independent cutoff qualification needs the codec's documented
SD_N and watchdog timing/conditions, or external measurement on a
separate setup: observe SD_N **at both codec pins** and both differential
outputs, record command-to-pin and pin-to-output timing separately, and
verify output remains off after transport restoration. A pinctrl sample
or cached register view alone does not meet either timing criterion.

The LPASS GPIO provider is outside the SoundWire register path, but it
is not outside all audio failure domains. Pinned `hamoa.dtsi` gives
`pinctrl@6e80000` its `core` and `audio` clocks via Q6PRM
(`LPASS_HW_MACRO_VOTE` and `LPASS_HW_DCODEC_VOTE`). The LPI GPIO driver
resumes the provider for a read or pin configuration. An allowlisted
`rpm_status` trace on `192.168.2.175` recorded GPIO-provider resume
from 2208.850855 s to 2208.852838 s and return to suspended at
2208.979395 s around a read-only audit. No WSA macro/controller/slave PM
transition appeared. That ~1.98 ms provider resume is a healthy sample,
not a worst-case shutdown latency. This explains how the
pin can be read while WSA SoundWire remains asleep, and why a successful
read in that state cannot establish independence from Q6PRM/DSP loss.
A future hold might remove a cold clock vote from the SoundWire-only
failure path, but cannot itself prove clock retention on DSP loss or
supply a physical pin-to-output bound. Treat loss of SoundWire while
Q6PRM remains healthy and shared-domain/DSP loss as distinct tests.
A read-only phandle audit on `192.168.2.233` ruled out an obvious
software power-cut substitute: `vreg_l15b_1p8` is shared by both WSA
codecs **and Wi-Fi** (`wcn7850-pmu/vddio-supply`), so cutting it would
threaten SSH recovery. `vreg_l12b_1p2` is the codecs' I/O rail; the DT
shows no controllable PA battery rail. Removing I/O power is not a
verified PA shutdown and was not attempted.

Public comparison: OnePlusOSS `android_kernel_modules_and_devicetree_oneplus_sm8650`
commit `38d50357db2728300a61b6f757f2d3a09651c155`,
`vendor/qcom/opensource/audio-kernel/asoc/codecs/wsa884x/wsa884x.c`,
reports separate PDM (`INTR_STATUS0` bit `0x20`) and clock (`0x40`)
watchdog interrupts. The PDM handler toggles watchdog enable over the
codec bus and the clock handler just logs. The register-mask header
names the timeout selector but gives no time values. This is useful for
fault classification, not evidence the amp hardware cuts output on
stall, nor a recovery strategy for a dead bus. No downstream handler or
register sequence was imported.

A second independent public implementation, ChromiumOS Depthcharge
[`779f94c4`](https://chromium.googlesource.com/chromiumos/platform/depthcharge/+/779f94c4aa8144bb270b80366bc7b3c8a8a49657),
uses the same SoundWire codec ID (`0217:0204`). Its
`src/drivers/sound/wsa8845_sndw.c:wsa8845_stop_beep()` queues writes of
`0x00` to `0x3430` for the primary and any attached second slave before
stopping DMA and resetting the master; the address and value are in
`src/drivers/bus/soundwire/qcom/qcom_swrm.h:CPUN_CMD_FIFO_WR_STOP_B0`.
That independently corroborates the Golden and local normal STOP
operation (`PA_FSM_EN.GLOBAL_PA_EN=0`) and its transport dependency. The
firmware also queues a read but this stop function does not check its
result. It gives neither a transport-loss fallback nor an output-off
latency. Do not copy the firmware reset sequence into Linux. In the
Golden source the separate `PA_FSM_BYP0.CLK_WD_EN` field is used in the
PA-off temperature-read override; it is not the playback predicate
`PDM_WD_CTL=0x01`. Neither this override nor the public upstream bit
names give an independently verified clock-loss trip time.

For independently calibrated captures, `tests/fullio-cutoff-trace.py`
checks externally supplied limits with no hardware access. Supply a
common timebase, an independent transport-fault marker and recovery
marker, voltages at both codec SD_N pins, and differential drive
**envelopes** that include class-D switching. Pre-fault load and drive
must be known, measured post-recovery drive must remain below the off
threshold, and the acquisition bandwidth and envelope method must make
short return-to-drive events detectable. Supply approved voltage and
timing limits separately; the checker deliberately has no defaults.
Use a qualified separate setup with suitable differential probes; software
values, synthesized traces and nominal scope samples cannot authorize
energizing the Surface speakers. The self-test verifies interpretation
of files, not physical behavior.

The checker also supports `--no-sdn-transition --fault-to-off-us N` in
place of the SD_N-specific limits. In this mode the marked event must
coincide with observed transport loss at the acquisition resolution;
both chips must have been driving before loss, both measured SD_N pins
must remain deasserted throughout, each differential drive envelope
must drop within the supplied bound, and both outputs must stay off
after verified transport restoration. It bounds the observed result
without identifying whether silicon stopped on an internal fault,
clock loss, or another hardware dependency. A bench owner must also
rule out concurrent software mute and removal of amp power, verify
fault/transport channels independently of the Linux journal, and
record the supply/clock conditions. Test SoundWire loss with DSP
healthy and shared power/clock-domain loss separately; one capture
cannot qualify both. The test machine is not the bench.

A candidate outside the LPASS/DSP clock domain is the APSS TLMM pair
GPIO204/205. The reference's `2026-08-02-sp11-dual-amp-enable-and-silent-state`
evidence identifies two `AUCD._CRS` resources, INF GPIOUID mapping, and
Windows KD traces of both being written high. There is no observed falling
edge, no established codec-pin mapping, and no output-off timing in those
records. The mapdiag candidate explicitly called the mapping provisional;
the pinned final v19c DT retains the shared LPASS reset and does not use
APSS 204/205 as a validated cutoff. Reference playback success cannot
establish this independent path.

`tests/fullio-apss-observe.sh` on the exact `.180` PA-off fixture found
both lines within range and outside `gpio-reserved-ranges`, output-high
GPIO function 0, no pull, 4 mA, and unclaimed, on `f100000.pinctrl`.
The APSS provider has no DT `clocks` or `power-domains` and reports
runtime PM unsupported, unlike the LPASS GPIO provider. This supports
APSS as a different software access path, not an electrical guarantee.
Do not claim or pulse the pins based on these observations. To advance
this path, obtain board-level continuity/polarity evidence and check
both individual and paired cutoff on an isolated, measured setup with
recovery independent of the boot/SSH validation Surface. Mapping only
one amp cannot satisfy the paired shutdown requirement.

`sp11-fullio-wsa-ready-watchdog.patch` strengthens the otherwise unarmed
post-PA readiness predicate. It includes an uncached `PDM_WD_CTL` read
inside the same enable/epoch bracket as the PA state and error reads.
The three reference-controlled bits must match Golden's `0x01` (enable
set; timeout selector and hold-off clear). An unreadable register or a
mismatch does not report this amp ready. The extracted-code test covers
all eight field combinations, the `0x2a` silent state and PA errors.
This does not enable the watchdog, establish its timeout in SI units,
or replace independent cutoff qualification.

The local FullIO stop helper used to clear `DRE_CTL_1.CSR_GAIN_EN`
before attempting PA shutdown, which could remove the configured cap
while a failed-off PA remained active. Golden's stop table starts with
`GLOBAL_PA_EN=0` and does not clear that gain field. The local
`sp11-fullio-stop-keep-gain-cap.patch` retains the cap throughout both
FullIO mute paths and requires the same PA epoch at uncached shutdown
readback. Verified stop still attempts the PA write and reads it back
when clock teardown fails; non-FullIO behavior is unchanged. The
extracted-core clock/PA test covers a lost epoch, read/write failures,
clock error, pair teardown, and the expected absence of a DRE write.
The follow-up `sp11-fullio-stop-cap-audit.patch` checks DRE1 hardware
readback immediately before and after the explicit PA-off stop under
one expected epoch increment. `fullio-stop-cap-audit-tvZS6l` (`.150`)
recorded `before=0x33 after=0x33` once for each chip, with both PA-off
readbacks, TX0–TX3 clock-off, intentional ALSA `-EOPNOTSUPP`, and CPS/PM
restore after the zero-ring transaction. No user PCM or PA activity.
None of this substitutes for an independent cutoff on transport loss.

The separately published Denali Linux 7.3 v15 source
(`ooaklee/linux_ms_dev_kit-sp11@54c026b31fa1`) also uses an explicit
analog supply guard: it re-reads `VPHX_SYS_EN_STATUS` on each init,
requires the measured 2S status for the Denali 4-ohm protected profile,
and falls back on read failure. This is useful precedent for a future
PA-off analog preflight; it does not prove independent cutoff. Do not
import its cold-init table merely because the controller identifies both
codecs, or assume that its separate transport configuration proves VPHX.

`fullio-vphx-X0gL1p` at `.187` measured `VPHX_SYS_EN_STATUS=0x02` on both
physical WSA nodes through uncached reads while the existing PA-off and
epoch checks held. Supply mode remained stable throughout PREPARE, DSP
mute survived, and ALSA returned the intentional `-EOPNOTSUPP`. This
fixture has no START-audit DT flag; no graph START, user sample, rail or
PA change was made by the supply audit. `0x02` matches the reference 2S
selector; it does not measure rail voltage, speaker impedance, PA gain,
current-limit behavior under load, or cutoff timing.

Independent downstream caution: [Omarchy #18383](https://github.com/omacom/omarchy/issues/18383)
reports an OLED Denali with recurrent right-PA faults and later
SoundWire failure, plus subsequent `0x00`/`0x21` VPHX values at reattach
after a known 2S boot. [PR #2577](https://github.com/omacom/omarchy-pkgs/pull/2577)
retains the first known configuration as a recovery policy. Do not use
cached supply metadata to authorize a FullIO session: the unarmed
readiness predicate now requires uncached `0x02` in its current PA epoch,
and fails on any other byte or read error. It never changes the supply
profile itself. [PR #2540](https://github.com/omacom/omarchy-pkgs/pull/2540)
limits software PA recovery attempts; its report is not a measured
independent shutdown bound. No automatic recycling of an amp after
fault is imported.

That source also confirms a concrete allocator distinction. An explicit
one-based map can use port `nports`, because `pconfig` has `nports + 1`
entries, but the automatic bitmap search returns `nports` as its
exhaustion sentinel. The pinned next generic allocator previously
rejected both. `sp11-swr-master-port-bound.patch` corrects that in the
FullIO kernel, with an extracted helper test for an explicit final
port, overflow, and true automatic exhaustion. This is not a diagnosis
of absent VI/CPS: our special feedback allocator does not use this helper.

A more direct Golden render-parity gap: reference patches 0065/0067
require codec DP1/DAC BlockCtrl3 and DP2/COMP + DP3/BOOST OffsetCtrl2.
The generic SIMPLE support was already ported for feedback, but the
existing Denali sink descriptors did not opt in. The running FullIO DT
at `.187` has the expected schedule: master ports 1/4 map to DAC with
pack mode `0x00`, 2/5 to COMP with Offset2 `0x07`, and 3/6 to BOOST
with Offset2 `0x1f`. This is DT evidence, not an active-bank readback.
`sp11-fullio-sink-fields.patch` enables the three fields using
per-codec copies, only for Denali with FullIO feedback selected. This
lets the existing SoundWire transport program the scheduler values;
no fixed register value, PA state, supply setup, gain or DSP config is
changed. Extracted-code tests cover per-codec ownership, allocation
failure and untouched generic properties. Golden 0065 specifically
links lack of COMP Offset2 to static in its CSR-off active configuration;
that does not explain silence in our deliberately PA-off fixture.

`fullio-sink-bank-AosaGH` (`192.168.2.191`) is the positive hardware
transport check. With only the six left/right DAC, COMP, BOOST software
port selection switches temporarily on, `GRAPH_PREPARE` (no START)
reached both actual WSA chips. Each reported active bank 0 with all
three channel enables and the exact fields `0x00`, `0x07`, `0x1f`.
The readback uses raw SoundWire reads, checks the bank did not change,
and only reports after the surrounding PA-off/epoch check. VPHX stayed
`0x02`, DSP mute survived PREPARE, and the probe returned deliberate
`-EOPNOTSUPP` without a trigger or samples. All six switches restored
and both PCMs closed. This validates the active sink fields for one
prepare epoch; no energized output, VI/CPS samples or cutoff measured.

The current base already reports `max_ch=2` for WSA884x DP5 after the
upstream VI channel-count fix. The old FullIO private DP5 descriptor
shadowed it with `max_ch=1` despite sending `ch_mask=0x3`. The older
7.3 Denali reference snapshot still shows the one-channel declaration;
that is not a reason to preserve it on next. The FullIO rebase now takes
the upstream DP5 descriptor directly and retains only a private DP6 CPS
descriptor with its per-device offset and SIMPLE extensions. The source
contract test checks the mask/capability match and independent CPS
assignment. No rate, word length, channel ordering or gain changed.
Pinned `stream.c` does not use `max_ch` to validate this path, so the
metadata mismatch is not evidence for the zero VI samples.

Until those cases have a defensible cutoff bound, do not promote a PA-on
fixture.

### Compiled VI/CPS routing through the protection consumers

Previously `tests/fullio-topology.py` validated the source-to-logger
edges but not where the logger outputs went, and only counted the
control links. It now checks exact MIDs, input/output ports and all
edges touching the VI/CPS data chains in graph 0:

- VI `0x4026 → 0x4025` (tap 2) `→ 0x4024` (SP_VI).
- CPS `0x402b → 0x402a` (tap 3) `→ 0x4029 → 0x4028` (CPS data router).
- SP `0x4027` has the Golden VI control port `0x80000000` with intent
  `0x08001204` and CPS port `0x80000001` with intent `0x08001537`.
  The checker also matches the remaining two packed link declarations
  (intent and heap properties included). One is the link from RX sink
  to the external timer `0x40df`; matching those bytes does not verify
  that the external peer is present or that any IMCL intent is active.

Native AArch64 output `/nix/store/38bpq33nha7zn32k0b5azdjb55qw4p8p-sp11-fullio-v19c-reference-topology-3232e1d`
retains the pinned binary SHA-256 `e7bb06a03e7bd9b869825a51775355a6743477d1579d78eb09fad5881cfb20f0`.
The build now runs seven size/count-preserving negative mutations:
wrong VI consumer, wrong CPS data port or MID, and wrong intent or
SP control port for either link. It rejects them for the intended
checks. `alsatplg` still reports four unresolved cross-component stream
names at compile time; a read-only lookup on the running `.104` closure
confirmed all four exact DAI widgets exist, with the three WSA DSP
endpoints and expected backend paths and the MicArray TX3 backend.
Evidence: `/tmp/surface-protection-topology-{build,dapm}.log`;
exact-system preflight passed, no PCM or PM vote. This rules out the
checked static miswires, not zero/stale sample delivery, live IMCL
activity or loaded cutoff. The candidate UKI remains unselected.

### RX0 diagnostic tap: packet receipt is distinct from cursor progress

The Golden `0x1586` tap 1 is DATA_LOGGING IID `0x4003`, between
`SP 0x4027 → SPLITTER 0x4002` and `CODEC_DMA_SINK 0x4157`. Other loggers
also use tap ID 1 but with different log codes. The topology check now
verifies the tap's exact data edges, MID and stage-1 configuration
`{0x1586, 1, 1}` and rejects a mutated sink edge. A reference capture
(`canonical-baseline-capture/packets.bin`, SHA-256
`da7056a46871a9bad6be12e390a84f34d9803a2753a11fa60d3127e0b4cb989b`)
contained 391 stereo S16_LE 48 kHz tap-1 packets with 192-byte payloads
(1 ms each), 390 nonzero and one zero. `--report-rx0` on the archive
checker now counts only matching tap-1 records in the audited host
receive window, independently of VI/CPS. Synthetic tests distinguish
no receipt, all-zero receipt and nonzero receipt, reject bad format and
duplicate sequence, and cover wrap. These counts do not establish a DSP
generation timestamp, physical PA silence, or the active graph's
protection state.

Native state `/home/keke/.local/state/fullio-rx0-tap-oKtkar`, status 0,
`/nix/store/rs364vmwprk15gjzirhyrgmcpcabgrgp-nixos-system-surface-26.11.20261121.56f282a`,
private UKI SHA-256
`21c9bedd773fc4c7b9f2044ce52ffbfdb61301c299d654e2e48a20af0bb256d6`.
The kernel modules and pinned topology payload are byte-identical to
the preceding candidate. Only the inactive `.104` entry/image was
archived in `/var/lib/surface-recovery/fullio-retired-oneshots-P1PvXV`,
verified before freeing ESP space. Gen20 bytes/default/profile checked
before arming the new one-shot. Native collector uses the existing
bounded LPASS log-mask scope; no audio input is supplied by this test.

The first `.220` run completed the safe ring/STOP/CLOSE/UNMAP cycle but
caught a measurement bug: all 176 `0x1586` records were tap 1, which
that collector counted as `other` and did not archive. The decoder's
zero was therefore **not** negative RX0 evidence. The corrected native
collector archives tap 1 alongside tap 2/3 without changing the log
mask, and the smoke test compares collector and decoded total tap-1
counts before reporting window buckets. Corrected collector SHA-256
`ef6c90f4ef43ff408fc5d9844858a50f28c594789ea3f48eacfefaee85fa93ed`.
The previous boot reached safe idle; replayed no PCM on it. Selected
the same byte-verified UKI once for the corrected collector, after
rechecking Gen20 bytes and default, without changing any boot profile.

On `.189`, the corrected collector archived 179 structurally framed tap-1
records in five datagrams (no truncation, VI=0, CPS=0). The strict RX0
checker did **not** accept the reference format. Do not infer payload
energy or exact RX0 PCM from that run. Slots remained `0x14` through
resume; sequence 167→173, bytes 1344→2496; STOP 73.805087 s,
CPS restore 73.816810, CLOSE 73.818795 and both UNMAPs 73.819334.
Collector sent the zero mask and removed the transient raw archive.
Final preflight found both WSA attached, all PCMs closed, all four PM
devices suspended, SSH/greetd and Gen20 intact. Evidence
`/tmp/surface-rx0-tap-corrected-live.log`. The decoder now prints the
actual rate/channel/bit/payload tuple for an unexpected format instead
of relaxing the requirement or interpreting unvalidated bytes.

A separate one-shot with that format diagnostic at `.231` archived 176
structurally valid tap-1 records, again no tap 2/3. The first format
rejection was **24000 Hz, 2 channels, 32 bits, 192 bytes**, not the
reference **48000 Hz, 2 channels, 16 bits, 192 bytes**. Length alone
cannot distinguish these geometries: both are 1 ms. The rate/width
matches the *declared CPS* geometry, but the packet tap is 1; neither
identity nor the actual RX0 sink media state follows from that match.
The local bootstrap still declares 48 kHz/16-bit on `0x4157`, 24 kHz/
32-bit on `0x402b`, and logger IDs 1/2/3 on `0x4003/0x4025/0x402a`.
The immediate-taps override writes only `0x4025/0x402a` and never
retargets `0x4003`. Keep the format failure visible; distinguish logger
provenance or format propagation before claiming a misconfigured DAC
or effective CPS. No sample classification was issued. Slots `0x14`,
cursor 1344→2112 at 94.840989 s, STOP 94.847998, CPS restore 94.882990,
CLOSE 94.886407 and both UNMAPs 94.886810. Final idle at 105.557535,
Gen20/SSH/greetd, both attached, PCMs closed, all four PM devices
`auto/suspended`. No PCM sample writes or PA enable. Evidence
`/tmp/surface-rx0-format-live.log`; no further open on that boot.

**Single-byte logger provenance comparison.** `fullio-rx0-tag-audit`
retags only `0x4003` from 1 to 4 under the same `0x1586` log code.
`cmp -l` reports only byte 9321 (1-based), `1 → 4`; restoring it
reproduces the verified Golden artifact. The regular topology payload
remains unchanged. The test-only DT flag selects a separately built
firmware payload in the existing PA-off and naturally idled diagnostic.
Media/route/PA policy and the three selected kernel modules are
unchanged. The collector archives both IDs and reports counts; the
parser counts tag 4 before/inside/after the host window and inventories
format tuples without interpreting samples or silently treating 24/32
as expected RX0. Synthetic tests reject conflation with tap 1 and confirm
that marking an energy-bearing payload does not classify it as audio.

Native closure
`/nix/store/vy9wdh98qb8h5dcn77pkxa5l5akms3ka-nixos-system-surface-26.11.20261121.56f282a`
(state `fullio-rx0-tag-xLftdt`, status 0). Runtime decompressed topology
SHA-256 `00d723fe124a163a3af034d05dea1c8133191ac9574ef53883e068f3461a36d6`;
collector SHA-256 `910f20822be7def880ca77c639ddcdc3381ac5856b848ecc176588ef6dd6bee1`;
private verified UKI SHA-256
`b31b8c1357ab06d42931df9a77b1ad201d33818e2d6463e65e28dc5bd5e7d58a`.
Retired only inactive `.163` entry/image to byte-verified
`/var/lib/surface-recovery/fullio-retired-oneshots-VFoH4G`; checked
Gen20 bytes/default/profile before selecting this one-shot.

Pinned SSH returned at `.221` on the exact closure. Also verified
`firmware_class.path=/run/surface/firmware` resolves the tagged compressed
payload to the same decompressed hash as the booted system; neither an
older live firmware path nor a stock blob was found there. The raw ALSA
prepare left slots at `0x14`, cursor advanced 1920→2688 at 61.095050 s,
STOP 61.106044, CPS restore 61.126082, CLOSE 61.130087 and both UNMAPs
61.137675. Collector captured **180 tap-1 records, zero tap 4, zero tap
2/3**, no invalid/oversize data. All 180 remained within the host receive
window; the tag-4 parser did not inspect their sample formats. The
zero-mask send and postflight passed; normal idle stopped at 71.615491 s,
all four PM devices suspended, both WSA attached, PCMs closed,
SSH/greetd and Gen20 healthy. `/tmp/surface-rx0-tag-live.log`.

The retag did **not** mark the observed stream; do not assign the legacy
records to `0x4003` based on their tap number. Firmware-path bytes do not
prove the DSP applied or retained that one SET_CFG. The public
AudioReach `capi_data_logging.c` GET handler for
`PARAM_ID_DATA_LOGGING_CONFIG` returns `{log_code, log_tap_point_id,
mode}` (12 B), unlike the public endpoint's media GET limitation.
This provides a concrete discriminator for the next same-graph PA-off
check: read the exact config after PREPARE and immediately before
START for `0x4003/0x4025/0x402a`; require token-matched replies and compare
against the scoped request. If the proprietary firmware returns the
requested config while legacy tap 1 persists, runtime packet producer
identity remains in question. If the GET fails, do not infer a match
or a format mismatch. No loaded protection or listening evidence.

**Same-graph logger GET_CFG audit.** `sp11-fullio-logger-readback.patch`
limits the additional GET allowlist to `0x08001031`, exactly 12 B each
for `0x4003/0x4025/0x402a`. It runs only under the tagged PA-off fixture,
after PREPARE and the existing immediate VI/CPS writes, before START.
Responses must match `{0x1586, 4/2/3, 1}` in that order. Existing
reply framing/token validation remains in force; an unverified reply
or mismatch stops before START and reports the exact failing IID.
The existing mute epoch and both PA/TX checks still gate START.
The composed test checks all three tuples, an error or individual
field mismatch at each logger, stop-on-first-error and START ordering.
Ring reply, SOFT_PAUSE, sink GET and callback models also passed, with
no change to the ordinary graph path. Official `v7.4-rc4` and
`next-20261123` tags unchanged; kept `next-20261120` for the build at
`/home/keke/.local/state/fullio-logger-readback-OQXMWO`, status 0,
`/nix/store/kv0y2vjd8gzpywiykmfjyxp7qcifdmvf-nixos-system-surface-26.11.20261121.56f282a`.
DTB route and tagged topology checks, selected module hashes and logger
verifier string checked. Private UKI SHA-256
`0a7ac87e7e0c55dbc94aba7774b5503240b43ee5eebe45c3e3453a1b44b59826`.
A test mutation with tag 1 in the expected RX0 row fails. Retired only
inactive legacy-tag entry/image to byte-verified archive
`/var/lib/surface-recovery/fullio-retired-oneshots-4Ti56L`, then checked
Gen20 bytes/default/profile before selecting this exact UKI once.

On `.239` the three token-matched pre-START reads succeeded at
2131.430245/276/305 s, with exactly `{0x1586, 4/2/3, 1}`. Yet the
collector received 177 valid legacy tap-1 records and zero tag 4,
VI or CPS. The tagged configuration is therefore verified *before*
START; treating the packet ID as the logger IID is still unwarranted.
Slot pair remained `0x14`, cursor 1536→2304 at 2131.607063 s,
STOP 2131.616073, CPS restore 2131.628049, CLOSE 2131.633741 and both
UNMAPs 2131.634205. Zero mask sent, normal idle proof 2142.688613,
four PM devices suspended, both attached, SSH/greetd, all PCMs closed,
Gen20 unchanged. `/tmp/surface-logger-readback-live.log`. No further
open on this boot.

The follow-up brackets START with the same three exact reads, placing
the second group after cursor advancement and before STOP. This tests
whether START changes the readable configuration. Both legacy and
marker packet inventories now preserve separate window counts and
bounded format histograms without interpreting samples. The public
AudioReach header layout is not used to infer a proprietary session
ID: the canonical reference's legacy offset 24 changes on every record
while offset 52 is 1 for all 391; copying the public C struct relative
to the DIAG envelope would put `log_tap_id` at offset 24 instead.
Composed pre/post, SOFT_PAUSE and mixed-archive tests passed; native
build state `/home/keke/.local/state/fullio-logger-poststart-JhMiQq`,
status 0, exact closure
`/nix/store/5b4hfrhw8k0mddhvw281cqbp4qg0ahj8-nixos-system-surface-26.11.20261121.56f282a`.
Verified DTB/routes, tagged runtime topology hash, selected modules
and pre/post strings. `q6apm-dai.ko.zst` SHA-256
`70b457a5f73efe26895a24d3a096b4b7196739e3e84cc65ffbea6a8be8c2df4c`,
private UKI SHA-256
`334ccb891a0e1e2f8b0e2146d93312a2ce48c95dbcc54ebb34e5a0eea418ac38`.
Archived only the inactive tag-without-GET ESP pair to
`/var/lib/surface-recovery/fullio-retired-oneshots-ff0lWS` after matching
bytes and hashes; checked Gen20 before selecting the one-shot.

Live `.155`: exact boot, naturally suspended, single PA-off prepare.
All three tuples verified before START (50.547115–50.547188 s) and
again after cursor progress (seq 163→167, bytes 576→1344 at 50.720994 s;
GETs 50.722494–50.723162 s). This excludes a persistent START-time
reset of the readable tuples as the explanation for the legacy-only
capture. 174 tap-1 records, all `(24000,2,32,192)`, 162 received inside
and 12 after the window; no tag 4/VI/CPS. Reference archive still
reports `(48000,2,16,192)` on all 391 tap-1 records. Neither format nor
receive time identifies a producer. STOP 50.728170, CPS restore
50.740078, CLOSE 50.745539, both UNMAPs 50.745953, zero-mask send and
frame-stop proof 61.236426. No clash, no detach; all four devices
`auto/suspended`, both WSA attached, SSH/greetd and Gen20 intact, all
PCMs closed. `/tmp/surface-logger-poststart-live.log`. No PA, ALSA
trigger, sample writes, or audible acceptance.

Follow-up inventory on the original compiled, pinned artifact: graph 0
contains **six** data-loggers, not three. The other three bootstrap
records target `0x465c/0x467a/0x47e9` with codes
`0x152e/0x19b0/0x1531`, each tap 1, mode 0. The topology verifier now
checks all six MIDs and all `0x08001031` records across stages, not just
selected IIDs in bootstrap. The three extra modules are not declared
`0x1586` producers. Native verifier and MID mutation passed
on `38bpq33nha7zn32k0b5azdjb55qw4p8p-sp11-fullio-v19c-reference-topology-3232e1d`.
This rules out an extra declared source using `0x1586` in the pinned
render stages, not a firmware remap or another DSP graph.

**RX0 log-code-zero control.** The opt-in `fullio-rx0-log-off-audit`
fixture retains the tagged PA-off graph and changes only logger
`0x4003`'s code from `0x1586` to zero. The public AudioReach implementation
checks nonzero `log_code` before enabling logger processing; this is a
source-backed test hypothesis, not a claim about proprietary behavior.
The native fixture payload differs from the tagged control only at
one-based bytes 9317–9318 (`86 15`→`00 00`), expected decompressed
SHA-256 `654cb655a1225e84c8faf8c629a1c2d64f73f6f1c7d5a2754ffb63b2e6023a38`.
Re-read all three loggers before and after START and check the existing
PA/TX-off, mute, byte cursor, shutdown and recovery conditions. A
legacy packet that survives is not accounted for by the read-back
`0x4003` code; disappearance would show dependency on this field,
not uniquely establish producer identity or actual endpoint samples.
No alternative source is enabled. The abstract logger guard tests
both fixture expectations and rejects a wrong code in either direction.
Latest `v7.4-rc4`/`next-20261123` unchanged; retained Nov 20 pin.
Build state `/home/keke/.local/state/fullio-rx0-log-off-uiPEGA`, status 0,
closure `/nix/store/nl30jsin0jdgg07hqkgqmj3hx9wrzxjc-nixos-system-surface-26.11.20261121.56f282a`.
DTB route test passed, decompressed firmware matched the checked payload;
`q6apm-dai.ko.zst` SHA-256
`c63e024f43d3a94f010040206024ff13d8f09b28df721f133005979865a29cab`.
Private UKI SHA-256
`8cb3b8bf3e142f104a190eed982442cabe05df966aa10ee27119d85fd6b54a42`.
Only the inactive pre-START-only ESP pair was retired to byte-verified
`/var/lib/surface-recovery/fullio-retired-oneshots-4RZ73i`; Gen20 profile,
default and recovery bytes were verified before selecting the one-shot.
On `.219`, `0x4003` verified zero at 38.002072 and 38.187071 s; the VI
and CPS logger tuples stayed `{0x1586,2/3,1}`. The collector still saw
194 legacy tap-1 records, all `(24000,2,32,192)`, 162 received inside
and 32 after the window; zero tag 4/VI/CPS. This traffic does not
require the readable `0x4003` log code to be `0x1586`. The zero code
alone does not prove that the proprietary logger stopped emitting.
Slots retained `0x14`, cursor 1344→2112, STOP 38.209066 s, CPS restore
38.233088, CLOSE 38.237075, both UNMAPs 38.237479, zero-mask send and
idle proof 48.485435. Both attached, all four devices `auto/suspended`,
Gen20, SSH/greetd and all PCM-closed checks passed. No PA enable,
ALSA trigger, sample writes or retry. `/tmp/surface-rx0-log-off-live.log`.

The independent `fullio-1586-log-off-audit` fixture extends that control
to VI/CPS loggers, both in bootstrap and in the pre-START writes. It
leaves all non-logger controls, logger mode/tags and the graph edges
unchanged relative to the RX0-only control. Both GET groups require
three zero codes. Payload diffs relative to that control are exactly
bytes 10861–10862 and 17037–17038, all going to zero. Expected
SHA-256 `9b7b4ae429b58e9f3f2e801e07371eccb9f06320d32e0d3d51df697190bf37fc`.
Negative tests reject conflating this fixture with RX0-only or tag-only.
Patch-stack models and pin check passed; native build state
`/home/keke/.local/state/fullio-1586-log-off-b0uQNX`, status 0,
closure `/nix/store/d4ksi5d1l5a42vj21kc89x20kvac31y9-nixos-system-surface-26.11.20261121.56f282a`.
DTB/routes, decompressed payload, collector and modules checked;
`q6apm-dai.ko.zst` SHA-256
`7172a52c5f155854b1e96f0b03420d5993b4b99efe7b30b9b3fe6bb4024a2c4c`.
Private UKI SHA-256
`37e0b249b70ef5edbcacf583b6dddd85422f93bb8678a4cd81f11a0196185d9e`.
Retired only inactive tag-only ESP pair to byte-verified
`/var/lib/surface-recovery/fullio-retired-oneshots-0WVLZg`; Gen20
profile/default and image bytes verified before selecting the one-shot.

Live `.234`, exact boot and one natural-idle PA-off prepare: all six
GET replies verified zero codes at 359.666482–359.666536 and
359.841252–359.841310 s. The byte cursor advanced 768→1344;
slot pair `0x14`, no clash. Host audit window
359.673581533–359.841180284 s was within the receiver interval starting
359.316293841. Collector counted **zero data datagrams and zero rejects**,
then sent zero mask (no firmware ACK exposed). In the RX0-only control
there were 194 legacy tap-1 records with the same LPASS selector and
collector hash. This makes a VI/CPS logger-config dependency the leading
explanation for the legacy traffic, not a producer identification:
this test changes both loggers and cannot exclude coupled firmware
behavior or a missed mask. It does not demonstrate electrical feedback.
The final shell result was 1 because the smoke wrapper still required
at least one `0x1586` record. The wrapper now permits zero only under
all three fixture markers while preserving the other log/coverage and
archive checks. The positive/zero gate was replayed against the actual
logs, and synthetic empty archive decoding accepted exact zero counts
and rejected a claimed nonzero count. No repeat live prepare was run.
STOP 359.848043, CPS restore 359.871855, CLOSE 359.875993, both UNMAPs
359.876393; idle frame-stop proof 370.069696. SSH/greetd, all PCM closed,
both WSA attached and all four PM devices auto/suspended, Gen20 intact.
`/tmp/surface-1586-log-off-live.log`; no PA or sample writes.

The reference forced single-tap negatives (Aug 18) also did not identify
live VI/CPS on their own, even with an independently verified speaker
signal. The later CPS result came with post-PA protection clocks and
packetization/wake parity; its 24 kHz/192 B format matches the legacy
geometry here but its tap and power conditions differ. An isolated
CPS-vs-VI logger contrast can distinguish the software dependency when
PA-off; neither outcome can substitute for VI/CPS measurement under
qualified protection or justify energizing the amps.

**CPS-only logger contrast.** Keep the same PA-off route/timing and
restore only `0x402a`'s code to `0x1586`, in both bootstrap and the
pre-START logging write. `0x4003/0x4025` remain zero. The same-graph
pre/post reads require exactly `{0,4,1}`, `{0,2,1}`, `{0x1586,3,1}`.
The payload differs from the all-zero fixture only at bytes 17037–17038,
`00 00`→`86 15`, SHA-256
`147254e051a0e3d3bd15b278bb172511a8323a746dfed62814d395881b15b9f3`.
A return of legacy tap 1 associates the old flow with the CPS logger
configuration under this PA-off contrast, not the physical ADC or a
verified DSP/PBR protection loop. Offline tests reject exchanging the
all-zero and CPS-only states or using the CPS override without the
required fixture markers. Upstream labels unchanged; retained the
November 20 pin. Native state
`/home/keke/.local/state/fullio-cps-only-log-0YMyMA`, status 0;
closure `/nix/store/0arnmvs6j3pbc5k7r52pklk4apw2ffcf-nixos-system-surface-26.11.20261121.56f282a`.
Verified DTB/routes, decompressed payload, collector and modules;
`q6apm-dai.ko.zst` SHA-256
`7abcfe5d57ee304a6be1930004ae6e293fed725b3532d1e864ab6bd0716b8009`,
private UKI SHA-256
`eef5495bd3569be65a1b65161d15c62fa59f8ae41c58e361cbb9deec913fcc3c`.
Retired only the inactive RX0-only log-off pair, byte-verified in
`/var/lib/surface-recovery/fullio-retired-oneshots-fwqc9A`, and verified
Gen20 before selecting the CPS-only one-shot.

Live `.215`: read both exact tuple groups at 344.587372–344.587428
and 344.765335–344.765395 s. Restoring just the CPS logger code brought
back 174 wire tap-1 records vs zero in the all-zero control. All were
24 kHz stereo 32-bit, 192 B; 162 received inside, 12 after, none before.
No wire tap 2/3/4, rejects, or oversized datagrams. This CPS configuration
alone is sufficient to restore the legacy flow under the tested
conditions. It does not prove a valid CPS payload, physical ADC output,
or which field the firmware uses for routing. In particular, the
readable CPS tag remains 3. Do not relabel wire tap 1 as calibrated CPS
or as RX0. The collector/smoke contract now uses `tap1`–`tap4` counter
names, with no producer names. Native `-Wall -Wextra -Werror` collector
build, framing and feedback parser tests passed; the renamed collector
was not used to re-open PCM on this boot.

SoundWire slots stayed `0x14`; cursor 768→1344, STOP 344.771999,
CPS restore 344.791356, CLOSE 344.794903, both UNMAPs 344.795309,
zero-mask send, natural frame-stop proof 355.170354. Postflight: both
WSA attached, all four `auto/suspended`, all PCM closed, SSH/greetd,
Gen20 default intact. `/tmp/surface-cps-only-log-live.log`.
No trigger, PCM samples written, PA enable or listening. Return to
independent transport/protection evidence rather than counting this
legacy stream as a feedback pass.

**DSP master-gain readback.** Bootstrap writes
`PARAM_ID_VOL_CTRL_MASTER_GAIN` (`0x4a63/0x08001035`) in Q13 format
with value `0x2000` (unity) and `PARAM_ID_VOL_CTRL_GAIN_RAMP_PARAMETERS`
(`0x08001037`) with `{10 ms, 1000 us, curve 3}`.  The optional
`PARAM_ID_VOL_CTRL_MULTICHANNEL_GAIN` stage (`0x08001038`, Q28 unity)
is present in the topology but is **not** sent by the calibration path.
`sp11-fullio-dsp-gain-readback.patch` adds a PA-off GET of
`0x4a63/0x08001035` gated by the existing
`microsoft,denali-fullio-pa-off-gain-audit` marker.  The readback
verifies `master_gain ≤ 0x2000` (Q13 unity) and `reserved == 0`,
failing closed on amplification or nonzero reserved.  It logs the
actual value so a lower user volume is visible in the audit trail.
Placement is after clock-off proof and before ring/taps, inside the
PA-off window.  Offline test compiles the extracted verifier with a
mock transport and checks unity pass, below-unity pass, above-unity
reject, nonzero-reserved reject, and transport error propagation.
Upstream tags `v7.4-rc4`/`next-20261123` unchanged; retained
`next-20261120`.  Build state
`/home/keke/.local/state/fullio-dsp-gain-readback-CMTw2b`, status 0,
closure `/nix/store/iw6dpn38jbgqxblik1blpm59ixjnnggf-nixos-system-surface-26.11.20261121.56f282a`.
Verified DTB/routes, original topology hash
`e7bb06a03e7bd9b869825a51775355a6743477d1579d78eb09fad5881cfb20f0`,
collector and modules. `q6apm-dai.ko.zst` SHA-256
`148a52722622baf78bd7b824cca9bdefae1c945ac68dfea3a9f337ad7f2f084a`.
Private UKI SHA-256
`ea04daa33ca66af9538568f731f5dfdb9b65b58b0b5cb60751e3d709387faa6c`.
Retired only the inactive CPS-only log pair to byte-verified
`/var/lib/surface-recovery/fullio-retired-oneshots-jLzDur`; Gen20
profile/default verified before selecting the one-shot.  Smoke test
greps for pre- and post-START master gain readback within the Q13
unity bound.

Live `.153`, exact boot and one PA-off prepare: **pre-START master gain
verified `0x2000` (Q13 unity) at 340.383257 s** and **post-START master
gain verified `0x2000` at 340.397246 s**.  Both WSA DRE/CSR snapshots
recorded `DRE0=0x70 DRE1=0x33 CSR_GAIN=25 CSR_GAIN_EN=1`.  Silent
START/STOP audit passed with no PA enable or PCM writes.  CPS wake
registers restored, GRAPH_CLOSE acknowledged.  All PA-off gain
evidence is consistent: DSP master gain at unity, hardware CSR gain
at 25, and ALSA mixer caps previously verified.  Smoke test output:
"Both WSA PA-off gain snapshots recorded; active analogue gain remains
unverified." and "DSP master gain readback within Q13 unity bound
before and after START."  Postflight: both WSA attached, slave PM
`auto/suspended`, codec/SoundWire `on/active` (sidechain fixture
keeps supplier active).  No PA enable, trigger, sample writes or
listening.  `/tmp/surface-dsp-gain-readback-live.log`.

### Golden-v33 port delta: physical VI producer ordering

The reference's Golden-v33 promotion and FullIO-v19c acceptance are
functional protected-render and duplex evidence on the reference 7.1.5
stack, not on Surface-next. Their reference scope explicitly excludes
system suspend/resume and does not claim a bounded independent kill
under transport loss. That distinction does not reduce the value of
using the reference as the production sequencing baseline. Repeated
PA-off tests cannot validate these missing parts of our port.

Golden-v33 WSA macro patch 0072 identifies a concrete missing producer
step: after enabling VI paths materially write `TOP_CFG1=0x03`.
Reference v32 measured physical I,V,I,V and v33 corrected it to V,I,V,I;
reordering again downstream was rejected due to right-amplifier faults.
`sp11-fullio-v33-vi-order.patch` ports this step in the checked, still
unarmed post-PA clock transaction. It forces a write and uncached
readback; an error or mismatch reaches the existing all-lanes shutdown
rollback. No new DT opt-in, PA enable, or DSP unmute. The extracted-code
test confirms repeated writes and rejection of write, read and hardware
mismatch errors. The follow-up `sp11-fullio-v33-pair-order.patch`
replaces the earlier four-lane phase batching with the reference order:
finish TX0/1, write/read `TOP_CFG1`, then TX2/3 and write/read it again.
Recheck the paired PA/mute epoch before, between and after the pairs,
and keep exhaustive four-lane rollback rather than copying the
reference's unchecked writes. The offline test exercises both pair
operations and verifies early failure skips materialization. This code
remains unarmed. Physical VI order on the Surface-next stack remains
unmeasured, as do the full reference-equivalent active PA lifecycle,
protected VI/CPS provenance, and exact CKV/GainStep volume transactions.

For the latter port, `tests/fullio-v19c-gainstep.py` verifies the hash-pinned
30-row reviewed inventory, the four ordered `0x489e` frame types and the
216/272/280-byte envelope classes. A private bundle can be checked against
its per-frame and aggregate SHA-256 hashes without being copied to this
repo or sent to DSP. Synthetic corruption tests covered IID, PID, length,
error word, payload and padding. `sp11-fullio-v19c-final-gain-frame.patch`
adds only the bounded 120-byte final gain frame encoder (`0x4a63`,
`0x08001038`, 104-byte body), with no sender, ALSA control or unmute.
A compiled test matches its asymmetric L/R output to the pinned reference
oracle byte-for-byte and verifies both channel caps and unity ceiling.
Reference transaction/order tests passed with an offline mixer stub;
this verifies tooling and formatting, not a runtime volume transition.

### Gate for a bounded PA-on experiment (not enabled)

- A watchdog enable bit, PDM widget event, DSP mute ACK, or software worker
  completion is not a bound on time at load. Verify the watchdog configuration
  separately from any evidence about when the PA physically shuts down. Keep
  stock guard writes and their order until the protection behavior is known.
- Distinguish an ordinary verified PA-off from a **failed or unreadable** PA
  shutdown. If the bus is detached, the same bus cannot prove or force that
  codec's PA off even when the healthy codec and DSP STOP both succeed. Do
  not clear a pending/failed fault on reconnect or let PCM resume automatically.
  The LPASS GPIO12 shared shutdown wiring is only a candidate independent
  path: software reference counts and a pin-state observation do not qualify
  it. Do not toggle it, unbind drivers, or inject a real transport fault on
  the boot/SSH validation system.
- Retain hard render lockout until there is an independently justified
  failure bound (documented hardware behavior or safely instrumented
  hardware) and same-graph feedback validation. For that validation, use the
  direct capped RX path and epoch-matched codec/clock observations; require
  both VI and CPS lanes with distinct nonconstant samples and known session
  provenance. A passing PA-off fixture cannot be promoted to unmuted audio.

`sp11-fullio-verify-pa-shutdown.patch` strengthens the dormant post-PA
mute path. It attempts both PA-off writes even if clock shutdown or the
DRE write fails, then reads the hardware PA enable bit without regcache
and rejects an enabled or detached amp. Ordinary and PA-off diagnostic
boots do not opt into this path. ARM64 compilation and injected clock,
DRE, PA write, readback and detach failures passed offline. No PA under
load has been stopped by this code yet.

### 2026-11-24: Withdrawn PA-on experiment and recovery

The withdrawn fixture directly requested amplifier enable without the required
protection and cutoff evidence. It is not a valid gain or safety diagnostic.
On `.190` the first PREPARE returned unexpected success and a second attempt on
the same boot returned `-EBUSY`. Neither result proves either PA state. On
`.162`, closure `s5s2h1fwsfaik9dspv5pc1i33sqiln5f` (UKI SHA-256
`cc21da139a3539d20dad2f6064b38b39b67ca456f2a6fcc88c0d01326c364d6e`)
logged the opt-in before START without a paired-enable marker. The `pa_on=1`
field was the DT option, not a hardware readback.

On `.244`, closure `n1l1q693k54cn9l16b6h7cv8qgg849aj` (UKI SHA-256
`51cb57fd47593bc8dd131ff10a4641a7c55b3e580314f7be0261926a67b6b99f`)
entered the left enable call at 314.683476 s (`both_pa_on ret=1`). The pinned
ASoC `snd_soc_component_write_field()` delegates to
`snd_soc_component_update_bits()`, whose positive return means success with
changed bits, not an errno. The early return skipped the right enable call and
aborted the diagnostic before DSP START. Treat this as a possible unilateral
PA enable: no direct hardware readback established physical output state or
paired cutoff. `q6apm_fullio_both_pa_off()` is a readback, not a disable write.
CPS restoration and GRAPH_CLOSE at 314.696185 s, closed PCM, and an ALSA
`Success (0)` result do not establish a safe PA state. The pinned
`snd_soc_pcm_component_prepare()` ignores positive callback results (`ret < 0`
only); this accounts for how the positive audit abort could read as success
without a completed diagnostic. No PCM samples were
written, no normal playback took place, and no listening was verified. The
subsequent `0f3qzyc7f8nxm89rr2iws83yb15s87pk` candidate was built but not
installed or booted.

Returned without reopening audio to Gen20 on `.225`; verified the exact
booted/current/profile closure `v9w3nd9lchbr4x3bic25in474dk2iv3s`, Gen20 current
and default, no pending `LoaderEntryOneShot` or `BootNext`, pinned SSH and
`sudo -n`, greetd, `NIXOS_ROOT` ext4 and `NIXOS_EFI` vfat. The Gen20 UKI, entry
and loader configuration matched `esp-before-open-test-prune-IH7MS7/esp.tar`
byte for byte before reboot and after withdrawing the experiment. The exact
inactive PA-on ESP entry and image were byte-verified into
`/var/lib/surface-recovery/fullio-rejected-pa-on.FeSf9M` before their removal;
the withdrawn fixture state was also quarantined there. Local evidence:
`/tmp/surface-pa-on-smoke-{live,debug-live,v2-live,v2-kernel}.log`,
`/tmp/surface-pa-on-recovery-preflight.log`, and `/tmp/surface-open-test-switch.log`.
The patch, flake export and DT insertion were removed. DTB validation and
PA-off smoke gates reject the historical marker; PREPARE success is again a
failure on the muted fixture. UKI staging also checks `/sound` in the input
DTB before building anything; use `--fdtget /path/to/dtc/bin/fdtget` if it is
not on PATH. Verified that the real withdrawn `n1l1q693…` DTB fails both
static validation and staging without producing a UKI.

Official kernel.org tags were rechecked before the corrected builds on
2026-11-24. `next-20261123` (`1422acaa190f…`) and `v7.4-rc4`
(`a4d7daea71be…`) remain the previously reviewed candidates; neither adds
qualified protection or fixes the paired slot-loss evidence, and the
Nov 20→Nov 23 Qualcomm SoundWire driver bytes are identical. Kept
`next-20261120` (`2c0da72bad56…`). ARM64 build `fullio-pa-off-recovery-ZJ68s7`
completed with status 0, closure `jr9jmnq0xs4h1pd6zixmjx02y8bmiyk4`, DTB
SHA-256 `7182725f8f3a2b856d69c09dacc50a50fbc8cd1350d6cb4c23f1b5cb22d31998`,
private UKI SHA-256 `b747c08c121af397860d1048c76915d3665cec7710a11239bce4f089c6889151`.
The four decompressed audio/SoundWire modules matched the previous PA-off
fixture byte for byte. Relevant shell/Nix/diff and patch grammar checks and
`flakes#checks.aarch64-linux.surface-boundaries` passed. The corrected
private UKI was not installed or selected; repeating the already recorded
PA-off gain transaction would add no loaded or protection evidence.

Follow-up hardening treats a positive diagnostic result that reaches
`q6apm_fullio_finish_audit()` as an invalid verdict and latches render off,
regardless of whether the fixture requests additional PA-off readbacks.
The test compiles the extracted helper and checks both settings, preserved
negative errno, balanced left/right checks, DSP STOP uncertainty and capture
admission. There is no PA enable in this path. The native ARM64 follow-up
`fullio-pa-off-verdict-Uin0Xi` completed with status 0, closure
`hqqdwp8dicb1qshyzzzh65hzb0vcwyk1`. Its DTB was byte-identical to the
prior PA-off recovery build; the compressed `q6apm-dai.ko.zst` SHA-256 was
`3501f0d8b1d7dd2237e06017499aff582f4586b7f668c9067a960b6cb79f3003`.
The decompressed module included the invalid-result latch and gain readback
and did not include the withdrawn PA-on strings. The privately staged UKI
SHA-256 was `88676be4aed942782fdbefb59ec4e44f0cce374641e2288ee13eda3110fe820b`;
not installed or selected. Native `nix flake check --no-build` passed.
Final read-only recovery verification found Gen20 active/current/default with
archive-identical recovery bytes, no pending one-shot, no withdrawn PA-on ESP pair,
no matching kernel faults, and healthy SSH/greetd. No PCM was opened.

For ordinary render, the pinned ALSA group code posts RUNNING only after all
triggers succeed and rolls back earlier successful START callbacks on a peer
failure. Waiting for the render stream lock outside trigger is necessary
before claiming START, but checking ALSA RUNNING alone isn't sufficient:
DPCM can return success with `trigger_pending`, and the later FE/BE trigger
can fail without moving DPCM to START. A future worker must prove both
commits for the same epoch. STOP supersedes the intent; a late START ACK or
unknown completion still needs owned teardown, not a retry or release. An
XRUN notification alone isn't a shutdown action (`snd_pcm_stop_xrun()`
checks that the stream is running before changing ALSA state). The extended
`tests/fullio-pcm-order.py` validates these source boundaries and rejects
mutations that omit either commit barrier or late-ACK teardown. It is an
offline model, not a new ordinary playback driver.

PA-off cursor progress, STOP/CLOSE/UNMAP, Offset2 and CPS wake readbacks remain
valid within the previously tested conditions. The CPS-only logger contrast
shows that its configuration suffices for the observed 24 kHz tap-1 traffic;
neither geometry nor ID authenticates the physical source or confirms active
protection. PA-off DSP and WSA gain settings do not bound loaded composite gain.
SoundWire link admission and clock-stop quarantine are containment, not proof
of paired output shutdown. Effective same-graph VI/CPS, bounded loaded gain,
and independent loaded paired cutoff evidence for SoundWire-only and shared
DSP/domain loss remain required before amplifier enable. Silence or lower test
stimulus does not waive any gate.

Two public same-board leads do not remove these dependencies. The
[ADR-0034 observation](https://github.com/ooaklee/linux-surface-pro-11-oe/blob/553fb2304abca435c678c07f47cfef565cd2396a/docs/adr/adr-0034-wsa2-regcache-right-speaker.md)
reports both WSA884x slaves attached while only the right DMA path stayed
off. It is not the paired slot-loss symptom. The downstream
[`3c1ce78b`](https://github.com/ooaklee/linux_ms_dev_kit-sp11/commit/3c1ce78b4ec4e430befb4e4058420ba403824a36)
fix for rejecting explicit master port 13 is semantically covered by local
`sp11-swr-master-port-bound.patch`; it fixes allocation before transport and
cannot account for attached slots later vanishing during controller resume.
The public [FCC C3K2076 index](https://fccid.io/C3K2076) lists schematic
exhibit `7240031` without available pages and records long-term
confidentiality. It supplies no pin mapping. No public WSA8845 source found
in this review specifies the physical drive-off behavior or worst-case
latency after SoundWire or shared DSP/domain loss.

The current SoundWire gate checks open, startup (including after the PM
vote), and `hw_params`; it is not a lease covering later START or in-flight
operations. A fault after the last admission check is still possible. An
ordinary render implementation must bind the START/STOP ownership decision
to the live link/graph generation and have a proven cutoff if the link
fails after admission; another admission check alone cannot provide that
cutoff. Do not run a new PA-on experiment on the only recovery Surface to
obtain this evidence. A qualified isolated load setup or authoritative
revision-matched board/codec timing documentation is needed for both loss
classes, with independent evidence of VI/CPS activity and loaded limits.

### Follow-up: retire test boot entries and follow the reference implementation

At the user's direction, archived and removed all 46 inactive FullIO and
Plymouth one-shot entry/image pairs and the orphaned `surface-next20-test.efi`.
`/var/lib/surface-recovery/esp-retired-tests.RmHx6b` contains the private archive
and SHA-256 manifest. Compared archive bytes and hashes before removal; before
and after, Gen20 was the sole NixOS generation and the current/default boot
with its original archive-identical entry, UKI and loader configuration. No
pending one-shot or direct firmware reference to the removed files. No reboot,
GC, or change to SSH/greetd; `/boot` went from 97% to 6% used, with 1.9 GiB free.
Details in `/tmp/surface-open-test-switch.log`.

For the direct reference port, `pkgs/fullio-reference-volume.nix` packages
the reference v19c volume transaction synchronizer, its two Python helpers,
the exact GainStep deltas, and the reference ALSA TLV writer from
`3232e1dacdeb580a10a9cb8d4756a4518a7bd83e`. The tool uses the pinned runtime
binaries and data from its own package rather than a manually populated home
folder. This is a package output only: not installed, configured as a service,
or run on the Surface. The v19c synchronizer requires the running protected
render graph, the reference volume/mute ALSA controls, and the UbiG endpoint;
this does not yet supply those prerequisites. No build or audio tests were
run for this change at the user's direction.

`sp11-fullio-native-endpoint-controls.patch` ports the v19c runtime
`SP11 Windows Volume Only` and `SP11 Windows Endpoint Mute` ALSA TLV
controls from Golden patches 0068 and 0066. The command bodies target only
final VOL_CTRL `0x4a63` (`0x08001038` / `0x08001039`), preserving the
reference FL/FR masks and Q28-unity maximum. The two callbacks share the
existing FullIO graph lock, operate only on the already running graph 0 with
both feedback transports present, and use token-matched APM SET_CFG. They do
not open a graph implicitly and are not published on the PA-off fixtures.
The same patch now also implements `SP11 Windows Volume Transaction`
(Golden 0048/0054): validate the reference stereo TLV and the ordered
216/272-byte four-frame GainStep delta for MSIIR `0x489e`, then send final
VOL_CTRL followed by the GainStep OOB write. Only the 30 exact reference
coefficient payloads are accepted (kernel SHA-256 against the pinned
runtime inventory); a correctly framed but modified coefficient body
is rejected without changing reference GainStep selection. Both commands
use the same live graph owner; a feedback epoch change cannot be reported
as success.
The OOB page has its own DMA mapping, is never borrowed from PCM samples
or the position page, and is retired with the ring after the necessary
DSP acknowledgements. Uncertain or aliased mappings cannot be reused.
On 2026-11-24 after the user reauthorized testing, the offline owner test
passed the third-map release and timeout/quarantine cases. The extracted C
validator accepted all 30 deltas from the pinned runtime inventory (SHA256
`2077bea085cea94f52853b8524205824ea36ac038522d7b2f93906c84756337e`) and
rejected malformed sizes, frame headers, and padding. The stereo Q28 frame
oracle, byte cursor audit, diff check, Nix parse and local no-build flake
check also passed. These tests did not submit a DSP write.

Official kernel.org tags rechecked before build: `v7.4-rc4`
`a4d7daea71be591034445c17d4d81132a1785a12` and `next-20261123`
`1422acaa190f2daef38ee0b8c50c6ca0fb7f3771` remain the most recent
relevant tags reported. Kept `next-20261120` as above. On Surface,
`/home/keke/.local/state/fullio-native-controls-fxidQA` completed its
native AArch64 **PA-off** build (`status=0`), closure
`/nix/store/vhqqz1nhdv9nv6qxwymgfb88021649cz-nixos-system-surface-26.11.20261121.56f282a`.
The decompressed `snd-q6apm.ko` contains all three controls (SHA256
`005fefc370d1f9e7194b2e843c7b72ae87e7d2f9e27239b495ca33575261ee19`);
DTB SHA256 `7182725f8f3a2b856d69c09dacc50a50fbc8cd1350d6cb4c23f1b5cb22d31998`
has the expected muted-test and PA-off audit flags. That closure cannot
perform audible playback. It was not staged or booted; booted/current
closure and system profile still point to Gen20, its ESP UKI matched the
private archive, and SSH/greetd were active. Additional stale entries in
`bootctl list` were `reported/absent` from `LoaderEntries`, not ESP files.

The source inspection also confirmed three deliberately closed paths:
FullIO PCM PREPARE does not return success, normal PCM START and APM
GRAPH_START return `-EOPNOTSUPP`, and WSA884x `.mute_stream` refuses to
unmute an amp with FullIO feedback. The live endpoint controls must only
be published against a protected normal-PCM owner that updates its render
state under `graph_lock`; the legacy start count alone is not a separate
render authorization. Do not stage the PA-off closure or remove these
checks as a shortcut to a listening result.

### Cross-project comparison for PCM and PA sequencing

- **geocausa/SP11X1e-audio `3232e1d`** remains the same-board source for
  topology, calibration, VI/CPS and paired PA/clock order. Its ALSA driver
  already suppresses watermarks during its own synchronous SOFT_PAUSE wait.
  That local suppression does not remove the shared APR receive-thread
  dependency for other linked streams on Surface-next. Do not transplant
  the inline `snd_pcm_period_elapsed()` path into a synchronous trigger.
- **ooaklee v15 `54c026b`**, Denali protected profile: the codec starts the
  PA, reads its fault status and reports readiness to the WSA macro; on
  shutdown it withdraws readiness before stopping the PA. This corroborates
  the order, but its recovery/retry branch and unchecked stop sequence are
  not substitutes for the native shutdown verification or admission latch.
- **justririll/x1e-speakers `83c4f1f`**, Vivobook S15: supports the need for a
  live SP VI → SP RX link and shows why `0x80008000` is not useful VI. Its
  48 kHz VI, separate MultiMedia5 capture and DRE calibration are for that
  board; do not replace Denali v19c's integrated VI/CPS or gain policy.
- **AudioReach Engine `d416046`**, `pull_push_mode.c`: the DSP publishes
  `frame_counter = 0`, writes the byte index/timestamp, then publishes the
  incremented counter. Split the one-shot non-sleeping read from the
  diagnostic polling loop in `sp11-fullio-ring-cursor-snapshot.patch`.
  Only a stable nonzero counter publishes an in-range, frame-aligned byte
  offset. Cursor zero and counter wrap are distinct valid cases. The
  extracted C tests passed zero/torn/out-of-range/unaligned, duplicate
  sequence, wrap, regression and forward-motion cases. This does not yet
  wire an ALSA `.pointer` caller for normal FullIO; no PCM or PA gate was
  changed and the patch was not built or deployed in this comparison pass.

The direct port shares the pull event and SHMEM media preparation order
in `sp11-fullio-pull-prepare.patch`. Existing isolated PREPARE now calls
that sequence after attachment and before calibration. Tests of the
actual C helper reject both registration and SHMEM failures without
falling through or resending. The reference's first PREPARE starts its
graph, ordinary START sends no second GRAPH_START, and repeated PREPARE
on the same open re-arms the producer without rewriting the pull ring.
The new helper is preparation only: the normal PCM owner and protected
output remain to be wired.

`sp11-fullio-pull-watermark.patch` distinguishes a reference pull watermark
from a cursor value. The FullIO callback checks ADSP domain, the pull module
and destination port, the one-word payload and the two registered levels;
other graphs retain their existing event handling. On close, the private
GPR port is removed and its callbacks drained before the graph reference
is released. CLOSE and UNMAP still use the APM service port. Extracted
registration and receive tests reject wrong source/destination, truncated
and malformed payloads, invalid levels and injected registration failures;
the PCM lock/lifetime test also checks drain-before-release. These checks
do not establish that Denali firmware sends the wakeups during normal PCM.

The 2026-11-24 AArch64 pinned-coefficient PA-off build completed as
`/nix/store/786s4zlkvnys9ggb65qmccg3ywafzcg6-nixos-system-surface-26.11.20261121.56f282a`;
`snd-q6apm.ko.zst` SHA-256
`1c00278207ad32a8f1ac6899fdbd34fe8d17bbba07e8b5324af017c8c6bb737f`.
No test UKI was staged; the running closure and profile were both Gen20.
Before building the pull-event changes, both official tag queries still
returned mainline `v7.4-rc4` (`a4d7daea71be…`) and `next-20261123`
(`1422acaa190f…`). Retained `next-20261120` (`2c0da72bad56…`): the previously
compared next SoundWire code was identical and neither candidate supplied
a demonstrated FullIO fix. The pull-event fixture build is recorded under
`/home/keke/.local/state/fullio-pull-events-VnQPyc`; it completed with
status 0 and closure
`/nix/store/ph60f16yxv2hy8mgmdlms8dapkvmi5kn-nixos-system-surface-26.11.20261121.56f282a`.
It was not deployed.

`sp11-fullio-pcm-watermark-work.patch` delivers PCM watermark wakeups on
workqueue context. GPR RX only queues a wakeup; the worker takes the PCM
group lock and checks whether the wakeup is still valid. STOP, pause and
suspend revoke pending work, and close drains it outside the group lock
before releasing the graph. The extracted callback test exercised delayed
STOP → START delivery, coalescing, and running-state checks; the actual
shared workqueue timing remains untested. The isolated fixture still
registers no ALSA period callback. Legacy capture DATA_READ_DONE is still
inline on GPR RX, so a linked FullIO trigger must not wait for GPR ACKs
while holding the PCM group lock.

`sp11-fullio-pcm-pointer.patch` samples the independently mapped DSP
cursor through the open graph reference rather than looking at the legacy
position header. Transient or not-yet-attached cursors hold the last stable
position; malformed data reports XRUN. Tests validate cursor publication,
initial zero and wrap, no-ring handling, and the independent callback
boundary. These changes do not admit normal FullIO START, publish the
actual sample DMA allocation to ALSA, or activate the paired PA route.
The six-patch endpoint/PCM delta composed byte-for-byte, and `nix flake
check --all-systems --no-build path:.` passed. The native build for both
PCM changes is in `/home/keke/.local/state/fullio-pcm-pointer-aoyra5`;
this is a compile-only fixture, with no system switch or UKI staged.

`sp11-fullio-pcm-dma.patch` removes the unused second PCM allocation for
independent FullIO. The graph owner publishes an ALSA sample-only DMA
view only after a confirmed pull-ring SET_CFG. The borrow requires exact
agreement with the configured sample bytes, never includes the position
page, and does not transfer the allocation or its DSP maps to ALSA.
Independent opens allow only RW-interleaved access (no data mmap). An
exact-size independent PREPARE can now attach the actual allocation to
ALSA, then detaches it when the muted audit ends; close also detaches
before releasing the graph. Larger diagnostic ALSA geometries can still
exercise the fixed DSP ring, but do not get a PCM sample view. The ordinary
PCM DMA path and capture retain their existing allocation. The owner and
cursor tests check unconfirmed/mismatched views, publication, and
quarantine; the DAI checks cover attaching and detaching in order. Flake
validation passed on all systems without builds. Native compile-only
state: `/home/keke/.local/state/fullio-pcm-dma-ucgFvd`. The borrow is not
proof of a successful `writei`: normal FullIO START and PA enable remain
disabled.

`sp11-fullio-pull-state.patch` replaces the independent ring's START/STOP
booleans with explicit DSP producer states. START marks running only on
ACK. SOFT_PAUSE and SOFT_RESUME require the expected prior state, and
commit only after the command ACK and the scoped event. A failed command
or missing event leaves the state uncertain; neither direction can retry
on that owner. The muted audit also rechecks the mute epoch after pause
before attempting resume. STOP remains the containment path and marks
stopped only on ACK. Last-reference CLOSE plus confirmed UNMAP can free a
never-started or confirmed-stopped ring; running, paused and uncertain
states retain quarantine. Extracted tests exercised both event orders,
wrong state, mute-epoch revocation, timeout, STOP cleanup, and CLOSE
quarantine; the eight-patch delta applied in flake order and
`nix flake check --all-systems --no-build path:.` passed. This exercises
the muted DSP lifecycle, not the paired PA transition or desktop playback.

`sp11-fullio-wsa-reference-cold.patch` ports the complete Golden codec
cold transaction (63 full-width writes from `3232e1d`, including the
ordered current-limit transitions). It replaces generic codec setup only
for an explicitly marked Denali feedback amplifier. The codec property
`qcom,denali-fullio-reference-codec` is not set by the existing DTs, and
requires `qcom,enable-cps`; a physical `VPHX=0x02` and PA-off readbacks
bracket the transaction. It contains no PA enable write. Any failure or
later detach leaves the opted-in codec unavailable for stream setup; no
cold-table replay or fallback to generic tuning follows. The normal
FullIO unmute guard is unchanged.

The register definitions and table matched the fixed reference; the
extracted C test exercised every write failure, all three read failures,
wrong supply, PA already enabled, and refusal to replay. Native ARM64
`wsa884x.o` compiled using the composed SoundWire header under
`/home/keke/.local/state/fullio-wsa-cold-object-aIt3Ti/module/`, SHA-256
`6beb74921c6efa2b515493e7afc94d3927c90dfd7fb17ab1cbd304dbd9005e56`.
`nix flake check --all-systems --no-build path:.` passed. Official tags
remained `v7.4-rc4` and `next-20261123`; retained `next-20261120` for the
same commit-level comparison above. The compile-only object is not an
installed module, and the new cold table was not run on hardware.

`sp11-fullio-wsa-reference-stop.patch` ports the exact six-write Golden
STOP table. For the opt-in codec, the callback resolves the protection
clock owner through the card's `WSA Playback` link, attempts clock-off
first, then attempts all STOP writes and confirms PA off against the
current attachment epoch. It returns the first failure and makes the
codec unavailable for another `hw_params` after a failure. Stock and
muted audit paths retain their prior STOP behavior. The future native
card marker `microsoft,denali-fullio-reference-render` suppresses early
DAPM protection-clock enable and admits clock-off at PA or feedback
teardown; it does not authorize enabling clocks or unmuting a PA. No
existing DT sets the marker.

The reference comparison matched all six writes. Extracted clock/codec
tests verified ordering, simultaneous failures, continued containment
writes, the stop latch, unchanged audit paths and Golden TX-pair order.
Native ARM64 objects in `/home/keke/.local/state/fullio-wsa-stop-objects-IG2dV1`
compiled: `wsa884x.o` SHA-256 `c466462d1c842abf161913365c2e77bd7a5e7ce152be00f8d3b96e39d17c9f10`;
`lpass-wsa-macro.o` SHA-256 `9cc8ee7ce034c787bb920f9c00b21afa6134cc24f7f7821b41262b014140617d`.
The all-systems flake evaluation passed. The separate PCM DMA fixture
built successfully as `/nix/store/wwv6l2dxf9xhhqi0b2bcsp9ng5pl5w1z-nixos-system-surface-26.11.20261121.56f282a`;
it was not booted. Both the actual booted closure and persistent profile
were still Gen20. No reference START, PA-on run or user listening was
performed.

`sp11-fullio-wsa-reference-start.patch` ports all ten reference START
writes and its 1–1.1 ms settle interval. The card-local callable requires
two distinct, explicitly marked Denali codecs and a caller-supplied
same-graph mute/feedback proof. Before enabling either PA it confirms both
amps are off, fault-free and 2S; verifies the card's clock owner and clocks
physically off; and checks that render, VI and CPS SoundWire streams are
enabled on both codecs. It then checks the graph and codec epochs between
PA transitions, reads both amps twice after both starts, and supplies those
checks to the checked Golden VI clock routine before/between/after the
TX pairs. On any partial failure, attempt STOP on both amps, return the
original failure, and separately report the first rollback error. No PA
recovery or automatic retry. Ordinary codec digital unmute still rejects
FullIO; no existing DT activates the path, and the normal q6apm PCM
coordinator does not yet call it.

The exact ten writes matched `3232e1d`; the extracted paired C test
verified both writes-before-clocks, every single write failure on both
amps, missing CPS/graph proof, stale epoch, and preserving the original
error separately from rollback. Clock-off, Golden VI producer and cold
regressions passed. Native ARM64 objects in
`/home/keke/.local/state/fullio-wsa-start-objects-UY90tp` compiled:
`wsa884x.o` SHA-256 `6eebc638379bf4f70874cae0997c5db18e391fde4d4dc3a3fccc259b5fb41645`;
`lpass-wsa-macro.o` SHA-256 `9cf69e73114b0edb1c887663f5026435bcaacaf93965019fd9861be058bae4df`.
All-systems flake evaluation passed. The compiled objects were not
installed and the paired START has not run on hardware.

## Native protected render wiring (2026-11-24/25)

`sp11-fullio-native-prepare.patch` connects the normal FullIO PREPARE to
the reference route only when the card carries
`microsoft,denali-fullio-reference-render` and no muted-fixture marker.
It pins the proven geometry (48 kHz stereo S16_LE, 1920/3840 bytes), and
on the first PREPARE performs the established sequence: both PAs verified
off, protection clocks off, one DMA/map/configure (pull ring, media,
event registration), then the v19c calibration and GRAPH_PREPARE with
SP/SPVI and physical mute readback. The mute proof is committed and the
DSP graph started exactly once; the sample buffer stays borrowed across
repeated prepare. Normal PCM START performs no DSP transaction. Trigger
START (`sp11-fullio-native-trigger.patch`) re-checks the mute epoch and
calls the paired reference START; STOP relies on ASoC's
`snd_pcm_release_substream` → `snd_pcm_drop` → trigger STOP → digital
mute path for PA containment, and close retires the DSP graph. The
trigger context is safe for sleeping codec work because the q6apm
topology loader sets `link->nonatomic = true` (`audioreach_link_load`).

The codec side now matches the reference lifecycle: per-amp digital
unmute defers PA-on to the card coordinator (no unilateral PA writes),
readiness accepts the Golden recorded states `0x2f` and silent `0x2a`,
and a bounded read-only settling poll (5 attempts, 2–3 ms) precedes the
protection clocks; no command is re-sent. All previous PA-off/muted
fixtures keep their exact behavior.

The topology gate (`sp11-fullio-reference-render-topology.patch`) accepts
the v19c graph only for the two explicit Denali fixtures, and
`sp11-fullio-reference-render-pa-range.patch` keeps the upstream PA
damage cap at 6 unless the protected route is selected (validated
reference operating point: PA Volume 24; RX digital ceiling 81 is
unchanged). `modules/denali/fullio-reference-render.nix` builds the one
fixture DT (reference-render on /sound, reference-codec on both WSA
nodes, muted-test and all audit markers rejected), the v19c topology,
the reference-derived UCM (`fullio-reference-ucm.conf`, speakers +
MicArray), and a WirePlumber rule for UCM HiFi with RW-interleaved
transport; WirePlumber state is kept private to the test session.

Verified in this pass: the extracted paired START test (26 cases
including settle polling), clock-off/proof/VI-order/cold regressions,
the new topology/PA-range gate test over the composed sources, PCM
ordering/lifetime tests, and `nix flake check --all-systems --no-build`.
The trigger+reference kernel closure built natively as
`/nix/store/y1121a8bfnz2wvqxbwcb7n62p6fs8ssq-nixos-system-surface-26.11.20261121.56f282a`
(status 0, not booted). The reference-render fixture build is running as
`/home/keke/.local/state/fullio-reference-render-iOaGwy`. Nothing has
been deployed; Gen20 remains the booted closure and profile.

Userspace arming pieces for the first protected listening attempt:
`scripts/fullio-reference-volume-once.py` applies one fixed reviewed
endpoint transaction (quarter-dB qcadcm quantization, nearest-CKV
GainStep selection, exact pinned delta, volume-before-mute ordering) via
the private `tlv_write` ABI helper; it has no UbiG/Stage-B dependency and
`tests/fullio-reference-volume-once.py` exercises q28/step selection,
payload layout, ordering and table-hash rejection with synthetic tables.
`scripts/prepare-fullio-uki.py --mode reference` stages the private
one-shot UKI only after verifying the exact reference-render DT markers
(reference-render on /sound, reference-codec on both WSA nodes, and
rejection of muted/audit/post-PA markers);
`tests/fullio-uki-dtb-gate.py` covers both gates. The default muted mode
is unchanged.

## First protected-route boot and triage (2026-11-25)

One-shot `fullio-reference-render` fixture booted from the verified
private UKI (`ec6b6298…`, closure
`/nix/store/fwbn7vym49n4hmnpqkdv7bcb06bhwzyd-nixos-system-surface-26.11.20261121.56f282a`);
Gen20 default entry and profile verified unchanged, pinned SSH restored.
On hardware: both WSA8845 attached/bound, **the 63-write Golden cold
transaction confirmed with PA off on both amplifiers**, and a normal
PipeWire desktop stream reached `state: RUNNING` with the independent
pull cursor advancing. The full PREPARE proof ran: watermarks/SOFT_PAUSE
registration, SHMEM media, PCM_CNV/MFC media, endpoint mute ACK +
readback, mute surviving GRAPH_PREPARE, byte-identical SP/SPVI tags, and
TX0–TX3 protection clocks read back off.

First-run failures, both diagnosed and fixed in source:

1. `SPKR_CPS` hw_params returned -ENODEV: the DT CPS sidechain port was
   never enabled (the UCM left `CPS Switch` unset). Root cause is
   reference semantics: a DT-enabled CPS path is board wiring.
   `sp11-fullio-reference-cps-port.patch` presets the CPS port when the
   DT enables feedback and ports the reference `set_swr_port` rule that
   refuses userspace/alsa-restore disable; the UCM also sets the switch
   explicitly. A manual runtime cset confirmed the diagnosis (the sink
   then appeared and playback ran).
2. The endpoint volume transaction returned -EAGAIN: the endpoint
   controls resolve a running render via `start_count`, which the native
   tokened PREPARE/START path did not maintain. The temporary gap
   between play-loop files also produced -EAGAIN (CLOSE owns teardown).
   `sp11-fullio-native-render-count.patch` publishes `start_count` only
   after the tokened DSP START and clears it only after the tokened STOP;
   the native-prepare model test now asserts both transitions and the
   ambiguous-START containment stop.

Standing operational rule recorded at the user's direction (corrected
after the first recording): **power off the test session's monitors
AFTER every reboot**, as soon as the session is up (`niri msg action
power-off-monitors`), not before it.

Not yet user-validated: no audible confirmation has been made. The
endpoint remains muted until the fixed transaction is applied during a
running render; the rebuilt fixture and listening run follow this entry.

## Protected route armed for user listening (2026-11-25 00:5x)

Second one-shot boot of the rebuilt fixture (closure
`/nix/store/40wh0x2aalq6kqaipilig6bdwfn3zdy2-nixos-system-surface-26.11.20261121.56f282a`,
private UKI `0ea87d3d…`; Gen20 default entry and profile unchanged;
screen powered off after boot per the corrected rule). Both amplifiers Attached, the
63-write cold transaction confirmed with PA off on each, no crash
markers or ASoC errors.

A continuous raw stereo stream (48 kHz S16_LE, the recorded L/R
identifiable material, SHA-256 `a5d7013c…` / original WAV
`b52d4ac6…`) plays through the PipeWire default sink
`Internal stereo speakers (protected FullIO render)` with the single
FullIO graph kept persistent (PW raw mode avoids per-file graph
churn). Evidence on hardware: PCM `state: RUNNING`, cursor advancing,
watermark/SOFT_PAUSE registration, SHMEM + PCM_CNV/MFC media, endpoint
mute ACK/readback, mute surviving GRAPH_PREPARE, byte-identical SP/SPVI
tags, and TX0–TX3 protection clocks off at PREPARE. ALSA START completed
through the paired reference START (a failure would abort the PCM), and
the fixed endpoint transaction then succeeded during the running render:
`SP11 Windows Volume Transaction` (q28 67427938 both channels, GainStep
14 pinned delta) and `SP11 Windows Endpoint Mute` = 0, both `rc=0`.

Waiting on the user's personal listening confirmation (complete, clear,
continuous, correctly mapped L/R stereo from the internal speakers) to
close the sole acceptance criterion.

### Listening-session evidence table (2026-11-25 01:0x)

| item | evidence |
| --- | --- |
| booted closure | `/nix/store/40wh0x2aalq6kqaipilig6bdwfn3zdy2-nixos-system-surface-26.11.20261121.56f282a` |
| private UKI | `0ea87d3d5ace3812fca18947b216418569c7833a8047efe674d229e510da778e`, one-shot |
| Gen20 fallback | default entry + `system-20-link` + profile unchanged (`v9w3nd9…`) |
| test material | L/R identifiable stereo, original WAV `b52d4ac63d8e…`, streamed raw `a5d7013c4698…` (2 s left 440 Hz, 2 s right 660 Hz, then stereo sweeps) |
| output node | `alsa_output.platform-sound.HiFi__Speaker__sink`, 2 ch `[FL, FR]`, links `output_FL→playback_FL`, `output_FR→playback_FR` active |
| endpoint arm | `SP11 Windows Volume Transaction` q28 67427938 (−12 dB, GainStep 14 pinned) `rc=0`; `SP11 Windows Endpoint Mute` = 0 `rc=0`, during running render |
| continuity | cursor +480288 frames / 10 s at 48 kHz, `state: RUNNING`, no XRUNs since the raw stream started |
| protection | paired reference START at ALSA trigger (PCM would abort otherwise); cold transaction PA-off on both amps; SP/SPVI byte-identical after GRAPH_PREPARE; TX0–TX3 off at PREPARE |
| duplex preserved | MicArray captured 192000 frames (RMS L 32.4 / R 41.0, peak 197) while render stayed RUNNING |
| repo validation | patch-composition byte checks, extracted C tests (START/STOP/CPS/cursor/transaction/UKI gates), `nix flake check --all-systems`, `git diff --check` all pass |
| user listening confirmation | **pending** — sole remaining acceptance item |

## Pop fix and stability regression (2026-11-25 02:1x–02:4x)

Pop root cause measured (Mac microphone, external channel): the crack is
a ~400 ms decaying transient cluster (peak 1400–2620) that occurs ONLY
at a fresh render-graph/PA enable — i.e. after idle gaps when PipeWire
reclaims the ALSA PCM. Successive plays within the graph's life are
clean. Two fixes:

1. `scripts/fullio-graph-holder.sh` — a silent zero-sample stream keeps
   the sink/PCM/graph/PA alive across playback gaps, so video switches
   never cycle the PA. Verified: graph held across a 60 s gap
   (trigger_time unchanged) and play-after-gap produced **no transient
   ≥1200 anywhere in the capture** (max 660) with all three probe tones
   present. 20 rapid play/stop cycles: zero graph churn, zero XRUNs,
   journal clean, ~20/20 audible bursts (one isolated 2018 event at
   91.9 s with no kernel/XRUN correlate — classified environmental; not
   reproduced in a 7-minute rerun). 5× 60 s gap-switches: zero pops,
   5/5 emission.
2. `pkgs/patches/sp11-fullio-wsa-start-settle.patch` — measured residual
   first-start pop is a charge step at `PA_FSM_EN` (loud, ~2620, present
   even with the DSP endpoint muted). The output stage now settles 20 ms
   in the proven half-drive state before the PA connects; the reference
   table order is otherwise unchanged. A/B measurement pending the
   rebuilt fixture.

Volume: endpoint raised -12 dB → -6 dB → -3 dB (Windows reference range
is -12..0 dB; PA gain 24 is the validated operating point). User to
confirm preferred loudness.

Session services (`fullio-graph-holder`, `fullio-endpoint-keeper` at
-3 dB, `fullio-audio-monitor`) are installed as systemd user services in
the fixture so all three start at login and survive reboots.

## Critical resume bug found and fixed (2026-11-25 03:3x)

A full idle cycle (holder stream temporarily absent) exposed a hard
dead-end: after a routine SoundWire clock collapse and re-attach, the
codec refused to re-initialize (my earlier "never replay the cold table"
policy), leaving `hw_init` false; every subsequent `wsa884x_hw_params`
returned -ENODEV (`spa.alsa: set_hw_params: No such device`), the
PipeWire sink went to `error`, and no stream could ever start until
reboot. This contradicts the reference lifecycle, which re-runs the cold
table at every slave attach. Fix
(`sp11-fullio-wsa-cold-resume.patch`): clean re-attach re-runs the
63-write cold table exactly like the reference; only a FAILED table
(partially written analog state) is latched and never retried. Extracted
tests cover both halves (pre-write rejection retries deterministically;
write-phase failure latches; success re-initialises per attach).

The same idle collapse also invalidated an earlier pop A/B sweep
(the holder stream was suspended by PipeWire and the sink dead), so the
PA-settle dose response remains to be measured after this rebuild.

## Pop physics and resume hardening (2026-11-25 04:0x–04:2x)

External (Mac microphone) A/B with true graph cycles established the pop
physics: the start crack is the PA analog engagement and its amplitude
scales with how long the PA/output was off (short gaps ~45 s: start
transients 50–54, i.e. inaudible; multi-minute gaps: 1359–2731). The
20 ms and 1 s boost-settle values both prevent the short-gap case; no
settle length removes a long-off engagement. Graph CLOSE produces no
transient. Therefore the session holder (silent stream + watchdog) is
the pop fix for the user's real scenario: within a session there is no
PA cycling and therefore no crack on play or video switch. The residual
is one possible engagement crack at session start (long off-time), before
any playback; the reference teardown order is deliberately not altered to
chase it.

Two resume defects found and fixed in the same pass:

1. Cold-setup replay: my earlier "never replay the cold table" policy
   dead-ended the codec after a routine SoundWire idle collapse
   (`set_hw_params: -ENODEV`, dead sink). Now a clean re-attach re-runs
   the reference table; only a FAILED table (partial writes) latches.
2. VPHX preflight: a late supply-status read at re-attach (status 0x00)
   refused initialization and latched the codec dead. The reference logs
   VPHX diagnostically and applies the table; the check is now a warning
   on this fixed 2S Denali hardware, with the PA-off pre-write gate kept.

Also fixed: systemd user services start with a bare PATH (holder/keeper/
monitor exited 127 at login); and the holder stream no longer sets
PipeWire volume 0 (the data is silence anyway). The holder watchdog
recycles a stream that fails to drive the PCM within 40 s.

## Strict stability regression (2026-11-25 04:5x–05:4x, closure c9jf79gn)

All runs quiet (sink 0.25) with the screen powered off; external
evidence from the Mac microphone plus the Surface-side monitor.

| suite | result |
| --- | --- |
| A: 20 rapid play/stop cycles | 0 `pw-play` failures, graph held (no PA cycle); no XRUN observed in sampled status |
| A+B emission | 25/25 probe bursts detected externally; no peak crossed the 1200 detector threshold (max 673). This does not exclude quieter transients. |
| B: 5 × 60 s gap switches | graph held across all five gaps |
| C: 30-min continuous soak | cursor advanced at ~48 kHz (final `hw_ptr` 91.6 M); no XRUN observed in sampled status or matching audio faults in the journal. The end spot check was MicArray RMS, not continuous acoustic verification. |
| D: duplex coexistence | MicArray captured 192000 frames while rendering |
| E: graph reopen + re-arm | PCM observed closed before play; two successful TLV writes appeared in the keeper log. The 30 s external capture was started before a 40 s idle wait, so it cannot verify the fresh graph's output. |
| F: runtime suspend + resume | After 240 s idle, the SoundWire controller and both amps were runtime-suspended; both amps still reported `Attached`. Restart restored `RUNNING`; this did not exercise detach/reattach. |
| login race | holder v3 watchdog recovered from `no target node available` at login; PCM RUNNING |

`c9jf79gn` had an unbound `$count` in the keeper's success log, causing a
service restart loop even after successful writes. It was corrected to
log `trigger_time`, then rebuilt and verified at login as recorded below.

### Listening checkpoint — 2026-11-25

- User feedback: “目前听感没有问题了”. Keep the current settings and defer
  several days of ordinary-use observation until formal use. This is a
  listening checkpoint, not a channel-by-channel or long-term acceptance test.
- The verified one-shot boot was
  `/nix/store/5vbfg7c48vby1k4nbqgd1yidlh65dxwx-nixos-system-surface-26.11.20261121.56f282a`,
  UKI SHA-256 `d374e605dc9ce4efd26a50780db89ef75cf8021cbcd6b241f5414361611a3dcb`.
  Post-login checks showed PCM `RUNNING`, both amps' cold PA-off checks,
  and the installed graph holder and keeper active with a successful
  endpoint arm at `trigger_time=17.388535669`. The full suite above ran
  on `c9jf79gn`, not this rebuilt closure. Gen20 remained the default and
  the system profile; the test image was selected only for one boot.
- Keep the protected DSP endpoint at **-3 dB** (previously -12 dB).
  Use the desktop slider for everyday changes. If more loudness is
  needed later, the endpoint setting has 3 dB of headroom to the
  reference **0 dB** ceiling; that setting is separate from the desktop
  slider and was not selected for this checkpoint. No PA gain change.
- Keep an ear out for a brief transient on the first playback after login
  or long idle, as distinct from switches with the graph already held.
  The tests above do not establish that this first-engagement transient
  has been eliminated.

### Repository cleanup after the listening checkpoint

- The earlier fixture commands and patch names in this audit are historical;
  their source is available at `1cd6151`. The current flake exposes only the
  normal Denali module and `fullio-reference-render`. The one-shot build and
  UKI staging scripts only accept the latter. The acoustic monitor no longer
  starts with the desktop; the holder, endpoint keeper and MicArray routing
  remain available.
- On the pinned `next-20261120` source, the 138 patches previously applied
  after the 19 stock patches produce the same tree as the six subsystem
  patches in `pkgs/patches/fullio` (comparison of all affected paths,
  replay tree `cf1dc5068200bbb77c501b0dec35c47faf04dcf6`). Three extra patches
  for the retired feedback-probe kernel are gone. The stock kernel derivation
  and the reference module release are unchanged. This is a consolidation of
  the tested source, not a removal of dormant in-kernel diagnostic branches.
- Validation: flake no-build check, native Surface host evaluation of the
  opt-in module, offline UKI DTB gate, UCM, PCM/graph/DMA regressions, and
  paired speaker/clock and GainStep tests. The cleaned closure was not built
  or booted; the earlier listening evidence refers to `5vbfg7c4`.
- Removed the retired stock-audio ESP pair and 119 old private test UKIs
  (4,912,441,344 bytes outside the ESP). Kept Gen20 and its private recovery
  archive, the active reference boot entry and its private build state, and
  the test reports. No reboot or system switch.
