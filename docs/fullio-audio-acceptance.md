# Denali FullIO: 0 dB recovery and listening acceptance

**Status: open. 0 dB / GainStep 30 is the only acceptance setting.**
The earlier graph retirement fix and shorter passing probes are not
acceptance of the reported level sag or crack. Use the protected v19c
route and unity DSP endpoint (not PA gain or >100% PipeWire amplification).
−3 dB is only a comparator or fallback, never a passing result. Do not disable SP/SPVI, change PA gain,
restart an active application, or replay an ambiguous endpoint transaction.

| Requirement | Evidence needed before completion |
| --- | --- |
| Fix audible crack | Start a timestamped acoustic capture **before** hardware initialization, include digital silence, and distinguish PA START from the keeper's unmute. Use an independent recorder or validate that the Surface MicArray was already recording continuously and that opening it does not change the initialization path under test; otherwise MicArray evidence is diagnostic only. On identical quiet source also verify sustained-graph pause, seek and natural long-idle reopen. Compare the transient against digital output; invalid/clipped/missing capture cannot pass. The synthetic envelope is not a driver fix. |
| Fix changing loudness | Reproduce with a constant source and repeatable real content. Compare matched frequency/level against a known-good interval and independently exclude MicArray capture artifacts; a stable PCM pointer or healthy PA FSM does not prove acoustic level. |
| 0 dB stays stable | Observe GainStep 30 ACK and repeat the failing 600 s stimulus on the fixed candidate with verified acoustic pickup. If using the Surface MicArray instead of an independent recorder, validate it on the exact candidate with a known stable external acoustic reference monitored through the replay; reject runs with reference drift, clipping, or missing frames. Because MicArray is part of the trigger, it cannot establish the mic-closed control or the pre-open half of the late-open test. Require both lanes, fixed graph/capture provenance, no XRUN, and no >3 dB sustained drop in resolved band measurements versus a healthy reference. Repeat on real content. |
| Preserve full audio | Check real left/right output and test MicArray duplex, desktop volume/mute, ordinary pause/seek and idle/reopen. Do not substitute silent PCM progress or a single channel. |
| Final deployment regression | After fixing and verifying a candidate, perform the ordinary pinned `nixos-rebuild switch --flake .#surface` and default reboot, verify exact UKI/closure and protected audio on that default; retain Gen20 recovery. |

Existing evidence and the private log directory are indexed in
[`gpu-rendering-investigation.md`](gpu-rendering-investigation.md).
`tests/fullio-level-replay.sh` checks a held playback **and** capture
trigger, digital stimulus continuity and the acoustic loss on a bounded
periodic probe. The replay requires coherent measurements on both stereo
lanes, rejects clipped windows, and evaluates the worst resolved band in
each approximately 10-second block; the other lane cannot average away a
failure. This is only a reproduction check until acoustic pickup and
GainStep 30 are verified independently. `tests/fullio-acoustic-sustain.sh` separately reports the
boundaries of two short playback streams. Neither identifies the cause
of a crack in real program material or measures physical speaker voltage.
The external input must first demonstrate nonzero capture and tone-to-noise
contrast on the exact test; reject an all-zero or duplicate stream.
`ffmpeg … -ac 2 -ar 48000 -f s16le - | python3 scripts/fullio-external-levels.py LOG`
converts a verified **independent** microphone input into time-stamped
scalar measurements without writing audio. The frontend must be configured
for the actual acoustic device, not a digital sink monitor.

## Opt-in LPASS audit candidate

Layer `inputs.surface.nixosModules.fullio-reference-clock-audit` on an
existing `fullio-reference-render` system in an isolated copy of the
consuming flake. Build the exact diagnostic closure natively, stage a
private one-shot UKI, and preserve the installed profile and recovery
entries. Do not load/unload this module on a running system. Ordinary
FullIO does not take this extra patch or set the module flag.

When the genuine FullIO clock owner already holds runtime PM active,
root can read `/sys/bus/platform/devices/6b00000.codec/fullio_clock_snapshot`.
It reports uncached TX0–TX3 protection path controls and the two RX path
controls; it does not wake the hardware or write any register. Sample
at intervals alongside both PCM triggers and acoustic levels; `EAGAIN`
is a rejected snapshot, not “clocks off”. Inspect TX clock-enable bit 4
and RX mute bit 4, comparing complete readings before, during and after
acoustic changes. Even stable readbacks do not prove the presence of VI or
CPS samples or pin a fault on DSP processing. Kernel.org tag check for
this candidate: `v7.4-rc4` and `next-20261124` unchanged; native AArch64
object compiled against the exact current candidate's development output.
Do not promote the audit module to the installed configuration.
`tests/fullio-clock-snapshot.py PATH/TO/PATCHED/lpass-wsa-macro.c`
exercises denial without clock ownership or active runtime PM and
checks each read failure leaves the PM vote balanced. Model success
and object compilation do not prove the audio path fixes either symptom.

### Non-Mac independent pickup

The Surface enumerated only the built-in capture PCM (`card0/device2`)
and USB root hubs; no independent USB audio device was connected. A
class-compliant USB microphone on a separate stand can provide a second
acoustic path without needing a Mac. Connect it to the Surface, verify its
placement and fixed gain (no device AGC/limiter), then identify its numeric
capture card/device using `arecord -l`. With `alsa-utils` available:

```sh
bash scripts/fullio-usb-pickup.sh CARD,DEVICE "$HOME/private-usb-levels.jsonl" 650
```

This selects `hw:` directly only after checking `snd-usb-audio` ancestry;
it does not change the default source or open MicArray or playback. It
requires native 48 kHz stereo S16_LE and a new private path. Discard an
interrupted run or any run with nonzero status, hotplug, gain changes, or
an unverified mic. For an incompatible recorder, export from its native
format privately rather than letting this runner fall back. Capture room
baseline before stimulus and continue after it; keep the recorder setup
unchanged across mic-closed, mic-open and late-open controls. Mark the tone
edges on both captures to check time alignment. The scalar runner only
addresses sustained levels: its receipt timestamps are **not** ADC
timestamps, and one-second windows are **not** startup transient evidence.
For startup, use continuous independent PCM spanning pre-init, muted START
and separate unmute, with a no-render control and verified timing. The USB
runner has not yet been validated with real hardware.

A phone or standalone recorder is another option for the **startup**
trace. Record continuously with fixed gain/no AGC to a private file,
include at least 0.5 s of clean flank on either side of each event, and
keep the independent recorder in the same place for a matched no-render
control. Keep the original file for continuity review: decoding a
container into WAV alone cannot prove that the recorder dropped no
packets. Use two observed synchronization cues bracketing the test,
outside the event/flank windows. Do not use file creation time or the
Surface's pipe receipt stamps as ADC timing. If anchor uncertainty
cannot separate muted START from unmute or other sounds, the capture is
diagnostic only. Decode privately to PCM S16 WAV preserving sample rate
and channels (no normalization, filtering, gap fill or time stretch).
Then report per-lane peaks with:

```sh
python3 tests/fullio-independent-startup.py private.wav \
  --anchor MONO_A FRAME_A --anchor MONO_B FRAME_B \
  --event muted-start BEGIN END --event unmute BEGIN END
```

Choose windows that cover the known event-time uncertainty and do not
include another action. The offline analyzer rejects bad anchor geometry,
missing samples, zero lanes and full-scale clipping in the selected
windows. It cannot authenticate the anchors, gain, physical placement,
continuity of the original recording, or acoustic origin by itself.
The analyzer has synthetic unit coverage only, not a new acoustic result.

## First bounded 0 dB long replay

2026-11-25 21:52:25 (+08): `unity-bounded.log` in the private stop-test
state directory records a 224-byte acknowledged GainStep 30 transaction,
without a mute write. The fixed −31 dBFS stimulus lost over 18 dB in some
matched MicArray windows, with playback and capture triggers unchanged
in those early windows and both PAs reading `0x2f` when sampled. The
full 600 s gate also failed separately: PipeWire logged `Broken pipe`
at monotonic `10452.343887` and the playback graph re-armed at
`10453.150891330`. The normal keeper restored −3 dB / GainStep 26 on that
new graph; the bounded trial did not send another TLV. Do not attribute
the earlier same-trigger attenuation to this later XRUN. The native
kernel build had begun during the replay; its CPU load is a confounder
for the XRUN and should not overlap the next acceptance attempt.

The clock-audit candidate built natively (private state
`~/.local/state/denali-clock-audit-06dhJe`) and booted once into
`/nix/store/qckd104lvmrbv1hhy8agdvklzbn4vzf2-nixos-system-surface-26.11.20261124.52a9386`.
Both recovery UKI and Gen26 UKI hashes passed before staging; Gen26 remained
installed and selected by default. SSH and greetd were active, Niri received
the night-screen command, and no newly unsafe boot fault was found. With
playback running the new root-only snapshot emitted `tx=10,10,10,10
rx=24,24` and both amps had FSM `0x2f`. This confirms the probe is live and
establishes the expected control snapshot, not speaker protection data
flow or a fix.

The 22:07:25 **600 s 0 dB replay failed without an XRUN**. Both PCM
triggers held (`16.466356711` playback, `52.815715343` capture); the
fixed digital stimulus stayed near −31.09 dBFS. The short-window acoustic
loss reached −12.59 dB and remained at −7.85 to −13.80 dB across the
four reported tags in the last window. All 125 in-session snapshots
read `tx=10,10,10,10 rx=24,24`; all 250 PA observations read FSM `0x2f`,
zero error bits and raw VPHX status `0x02`. This rules out a persistent
change of those clock/mute bits as the cause of the loss. It does not
rule out intermittent transport faults, bad VI/CPS sample data, DSP
attenuation or a MicArray transfer change. The trial acknowledged a
same-trigger return to −3 dB with no mute write. Evidence: `unity-bounded.log`,
`levels-audit.jsonl`, `amps-and-clocks.jsonl`, and `clock-join-600.log`.
`tests/fullio-level-clock-join.py` reproduces the time-aligned summary.

The next discriminator is an independently verified acoustic pickup
paired with a fixed-signal run **without MicArray**. Compare both time
series once with and once without capture, keeping the playback trigger
and ambient geometry unchanged. If that isolates playback, a validated
post-SP RX0 level tap would be the next DSP-versus-hardware boundary;
do not repurpose the existing PA-off-only DIAG collector or treat its
ambiguous tap-1 format as proof. Until then neither the intermittent
crack nor stable 0 dB satisfies the acceptance checklist.

The Mac was found in clamshell mode (`AppleClamshellState=Yes`) while
its built-in microphone returned all zeros; that input is unavailable
for acceptance until it passes a nonzero tone check. An alternative is
an independent USB acoustic mic. `tests/fullio-mic-isolation.sh` was
verified on the one-shot clock closure with only the silent holder:
MicArray closed and reopened (`52.815715343 → 796.953771817`) with the
same playback trigger `16.466356711`, no new kernel events and no bus
or protection writes. With an independent acoustic mic, run it during
the fixed 0 dB probe instead of the silent holder check. Only the two
links used by the test probe are disconnected, and the script refuses
any other capture consumer. The scalar probe also has a `--monitor-only`
mode for a playback-only recording from the beginning of a test.

## XRUN/RTKit contrast (not a level-sag fix)

The NixOS host had no RTKit service, `LimitRTPRIO=0` and a ordinary
`TS` PipeWire data thread feeding a 960-frame/20 ms ALSA buffer. Built
an isolated consumer flake with exactly `security.rtkit.enable = true`
added; the kernel bytes match the clock-audit candidate. It booted once
into `/nix/store/7hwbv4a0vn8x0hzxi0v2zd6pwxrbnz5b-nixos-system-surface-26.11.20261124.52a9386`.
RTKit was active, but the original PipeWire thread **still** had `TS` at
first login. After an ordinary idle service restart, the actual PipeWire
`data-loop.0` became `RR` at priority 20. The holder initially raced node
creation after the restart and was restarted only after the speaker sink
appeared. Use the thread scheduler class, not just service state, for a
meaningful comparison. This is not evidence that XRUN caused the reported
crack, and cannot explain the clock-audit replay's XRUN-free level sag.
With RT verified, the 180 s 0 dB replay still failed by 10.75 dB, without
an XRUN. Both symptoms remain open.

## Silent initialization and PA cache replay

Mac input became nonzero with the lid open. One shutdown/reopen run
captured before initialization and held the endpoint muted for six
seconds after PCM START. A second run used audible timing markers only
outside the silent interval, but clipping in the Mac capture already
predated the reopen; neither is a clean startup transient acceptance.
A packet-timestamp-preserving capture at 22:35:47 also failed quality
checks (203 ms missing in the startup window).

That last reopen exposed a separate hard failure: right WSA884x
reported `FullIO reference cold setup unverified` / `-EBUSY` after
VPHX status `0x21`, followed by `hw_params -ENODEV`. The holder and
keeper were stopped to prevent further attempts. The PA-off predicate
was not bypassed. Cached PA-enable replay is a plausible path, not yet
a proven explanation of the hardware reading. The Denali-only candidate
marks `PA_FSM_EN` volatile so paired START cannot cache an enabled
value, and checks the actual enable bit before reattach cache
synchronization. The Maple cache can still seed its static `0x00`
default; this change rules out replaying a cached `0x01`, not every
write to the PA control register during sync. It leaves the
Golden 63-write table and PA start/stop proofs unchanged. Validate the
next boot, natural long-idle reopen, synchronized Mac startup capture,
and 0 dB regressions before promoting it.

The native PA-cache one-shot (`k6fsibsn1d7cizggmi57mw9cvsfgn18v`,
private build `denali-pa-cache-fFlST5`) booted normally with healthy
PCM/clock readbacks and unchanged Gen26 default and Gen20 recovery. Mac
recording started before reboot, but the boot-PCM event window had 213 ms
missing, including an 11 ms local packet gap, so it did not pass.
At 22:55:40 a subsequent natural idle reopen failed: SoundWire MASTER_CLASH
was logged before right-amp cold initialization, the right amp completed
its PA-off table, and left `SPKR` failed `hw_params -ENODEV`. This rules
out stale PA-enable replay as a complete fix. The holder and keeper were
stopped; do not repeat the failed hardware operation on this boot. No gain,
reset, bus injection or unbind was used. The external startup window also
had gaps and the PCM never reached START: this is not a crack acceptance.
The live DT has `qcom,denali-fullio-feedback` but not the separate
`qcom,denali-fullio-link-gate`, which explains why the logged clash did
not latch new-stream admission on this closure. Audit the clock-stop
entry/exit and per-amp reattach ordering next; don't merely mask the IRQ.
The Windows-reference v27 retention branch is a useful discriminator,
but blindly retaining init after an unresolved MASTER_CLASH would skip
the current transport/PA proofs.

Built a DT-only diagnostic contrast with `surface.fullio.swrResumeAudit`
(default off). The native output `faddcfnaps4h162lc56vbqgh3dkrn64b` has
identical kernel bytes to the failed PA-cache candidate; its DT adds
only the existing read-only PM transition snapshots and fail-closed
link gate on `6b10000.soundwire` (no synthetic fault flag). The actual
patched Next24 controller passes `fullio-resume-admission.py`,
`fullio-pm-preconditions.py`, `fullio-detach-latch.py` and
`fullio-resume-boundaries.py`; models explicitly exercise single-master.
This contrast has not been booted, and the running faulted closure was
not asked to retry the bus or open a speaker PCM. Option enablement is
containment/diagnostics, not a resume fix.

### SoundWire master word-length candidate

The archived PA-cache boot (`a4c91221d109416298cce06af75d6809`) shows a
WARN from `qcom_swrm_port_target()` at 22:52:56.265 during WirePlumber
`sdw_prepare_stream()`: `x1=0` at the port check and `x3=0x112c`. The
22:55:40 MASTER_CLASH is a later event, not the same transaction. On
Denali the runtime DT supplies master word-length overrides only for
DP7 and DP13; the other entries are `0xff` (absent). The driver's
`qcom_swrm_compute_params()` leaves the separate master `port_params`
zero-initialized for those ports while populating `transport_params`.
The core calls both programming callbacks. The old word-length callback
therefore computes a DP0 register address and `bps - 1` for an absent
override, and `qcom_swrm_port_target()` warns but allows the write.

The candidate skips only this absent override in the master word-length
callback; it rejects incomplete or out-of-range overrides. DP7/DP13
register addresses, values and propagated write failures are preserved.
No SoundWire transport values, feedback clocks, PA proof or gain changed.
The extracted callback test fails on the former implementation (unexpected
write) and passes on the candidate, as does the existing master-port bound
test. Native AArch64 `qcom.o` compiled against the running Next24 kernel's
matching dev output (SHA-256 `77af21177f36879b09f5c4532a0df92caa551493d4420b2a574fb23b7c9d028e`);
this is an object, not a built/deployed kernel or hardware pass.

2026-11-26 upstream check: `v7.4-rc4` still writes with the absent
parameters. Next24 (`3dd8c790a7b7027abdd568e36db5e82ffaea7c77`) and
Next25 (`9437046953b2fb3bf55b36582450ea0267df82a7`) have byte-identical
`qcom.c` and `stream.c`. Keep the pinned baseline for this isolated
candidate; there is no SoundWire benefit from changing those tags for
this test. Verify warning removal and a natural idle reopen on a
recovery-preflighted one-shot before judging any relationship to the
crack or later clash. Neither is fixed by the object-build evidence.

The native full build exited 0; exact one-shot closure `8kj74jhgcbp4n2m0waknhngcq31d3rkh`
booted with the same DTB as the resume-audit parent (link gate and PM
snapshots on; no separate frame-stop opt-in). Gen26 default and Gen20
rescue UKI hashes verified; SSH/greetd were healthy and the display was
turned off through the exact test Niri session. Both amps proved PA-off
cold setup, the graph reached RUNNING and the comparator armed at −3 dB.
The `qcom_swrm_port_target` warning was absent on this cold boot; no
acoustic claim follows from that.

After the confirmed idle shutdown (clock-off, CLOSE and UNMAP ACKs,
runtime-suspended; 75 seconds), reopen **failed** and did not reach START.
On resume the sampled status stayed `0x14` through CGCR reset and clock
start, then became `0x00` before IRQ restore. The IRQ-side slot observer
latched first `-ENODEV` while `clash=0`; subsequent re-enumeration reached
`0x14` again, but transfer/PA-off reattach checks failed and new streams
remained quarantined. This is not evidence of a MASTER_CLASH on this
boot, nor does the eventual bit pattern prove a valid recovery. Kernel
windows: `boot-kernel.log` and `idle-kernel.log` in the private native
candidate state. Holder/keeper were stopped, playback and capture closed,
SSH/greetd remained up, and no reopen or reboot was retried. Investigate
whether the clock-exit sequence itself loses enumeration before a valid
paired reattach can be proven; do not remove the detach latch or admit
streams based only on the recovered slot bitmap.

**Frame-stop DT-only contrast.** The failing boot had frame=1 both
at ClockStop ACK and on entry to resume; it did not wait for physical
frame stop. Earlier PA-off tests documented in `audio-protection-audit.md`
showed why a second read matters. Built a fresh one-shot
`cxa4khhab82vfl9b8wg3pgqd7lqmb9c1` with the exact same kernel/modules
and exactly one added DTS property, `qcom,denali-fullio-wait-frame-stop`
on `6b10000.soundwire`. No change to link admission or reattach proof.
The private UKI verified as
`7b6b524f7c37b2781fb267061a638c13b09e0420e2f3bbafb1acd1f533fd4bdf`;
Gen26 default and Gen20 rescue remained untouched. Exact boot, SSH,
greetd and Niri screen-off verified; cold attach and initial render
trigger succeeded without the DP0 warning.

Three consecutive natural 75-second idle reopens passed with the keeper
stopped and the new graphs DSP-muted. Each stop proved frame-off on the
second read before gating. Wake retained `0x14` through ClockStop exit,
without a clash, invalid slot, or latched link error. Fresh RUNNING
triggers: `16.530536762 → 133.244841927 → 253.021356536 → 347.917556758`.
Round 1 specifically observed frame=0 through IRQ restore, then the
clock-stop-finished IRQ and frame=1 before exit. The contrast supports
the wait-before-gate correction on this board. It does not prove a
crack fix, active-capture duplex, or behavior at 0 dB. Evidence:
`idle-round{1,2,3}-kernel.log` in the private frame-gate state.

**0 dB duplex on that exact frame-gate closure — still failing.** The
pinned endpoint accepted Q28 `0x10000000`, GainStep 30, then unmute; desktop
sink and source were unity, all six MicArray decimators still at 84, the
keeper was stopped, and no other stream was feeding the speakers. The
600-second peak-4608 test produced 598 usable active monitor windows,
unchanged playback/capture triggers (`347.917556758` and `491.893673165`),
no clipping, and no new kernel entries. The first >3 dB short-window
block began about 74 seconds after playback began (−8.0 to −11.9 dB in
all six bands), the worst block was −19.09 dB at 449 Hz, and all bands
remained down about 8–13 dB in the final block. The monitor tone held
steady. This is a MicArray-only diagnostic that matches the previously
independently recorded failure, not a new independent acoustic result.
Frame-stop admission fixed the tested reopen, not the observed duplex
loss. The acknowledged comparator (`−3 dB`, step 26) was restored once,
MicArray closed, the playback trigger remained unchanged, and SSH/greetd
stayed up. Logs under `micarray-0db.lkv40A` in the private frame-gate state.

The fresh-graph −3 dB comparator (`micarray--3db.6huMtw`) was aborted
before its tone began: opening MicArray on the just-started graph
coincided with PipeWire `snd_pcm_avail after recover: Broken pipe` and
several new muted GRAPH_PREPAREs. The original −3 dB ACK applied only
to trigger `2025.018705835`; playback subsequently reached trigger
`2027.628678496`. Do not use the abandoned comparator to make any
−3 dB acoustic claim from that attempt. The watcher stopped both keepers,
with no retry; SSH/greetd remained up. The replay now requires five fresh
silent samples on unchanged RUNNING playback and capture triggers.

The subsequent −3 dB comparator **did reproduce the sustained drop**
(`micarray--3db.OlMQiz`). Both streams settled with DSP mute before a
single step-26 gain/unmute transaction; fixed triggers `3997.685401978`
and `3998.154346493`, host unity, all six capture decimators at 84,
600 s peak-4608 stimulus, 599 active sampled windows, no clipping or
PipeWire errors. The digital monitor held within the band stability gate.
All six pickups by frequency were near baseline through the block
starting ~225 s, then down 8–12 dB in the block starting ~235 s and
stayed down to the end. Worst short-band drop: 203 Hz, −12.317 dB.
The 0 dB diagnostic had failed earlier (~74 s) in a separate run; the
latency difference is not a controlled estimate of gain dependence.
The comparator rules out a failure that requires unity/step 30 under
these conditions, not protection or GainStep involvement. It used the
triggering onboard MicArray without external calibration, not independent
acoustic acceptance. Both PCMs closed and SSH/greetd stayed healthy.

**0 dB silent preconditioning.** On the same closure the initial attempt
(`micarray-0db.xM35VZ`) retired its playback epoch as the capture probe
linked; no gain/unmute or tones were sent. With three seconds of stable
muted playback before linking capture, a fresh run (`micarray-0db.gXGid7`)
confirmed step 30/unmute once, held both PCMs at triggers
`5070.471063120`/`5074.023409590`, then waited 300 s with live MicArray
and digital-zero render before the 160 s peak-4608 stimulus. All 307
pre-stimulus scalar windows had zero monitor peaks. Initial measured
MicArray tone amplitudes were within ~1.5 dB of the previous immediate
0 dB diagnostic's initial bands, and stayed level until the short-band
block starting ~115 s of audible tone; that block lost 8–12 dB across
all six bands. Worst: 449 Hz, −12.234 dB. No monitor-level fall, clipping,
PCM epoch replacement or logged XRUN. Step 26 restore ACKed, both
PCMs closed, SSH/greetd up. Thus on this run elapsed duplex time with an
armed endpoint and ambient mic payload was not sufficient to produce an
already-attenuated first tone. A render/feedback-dependent state or the
speaker tone in the mic payload remains possible; digital silence does
not distinguish them. This is uncalibrated MicArray diagnostic evidence,
not proof of intact startup acoustics or reproducible onset latency.

**Same-epoch silence recovery contrast.** Generated a
bounded same-stream stimulus using `tests/fullio-level-stimulus.py
--seconds 520 --peak 4608 --silent-gap 300 120`: 300 s of tones, 120 s
of exact zero and 100 s of tones, with 150 ms ramps. Offline inspection
verified frame counts, hard zero and the peak bound. Both attempted
starts (`micarray-0db.tYhL90` and `micarray-0db.rExnqa`) retired the
playback graph as the dual scalar probe linked. Ring release followed
CLOSE and both UNMAP ACKs; no endpoint write or tone was sent. Short
muted profiled contrasts with a direct player (`NuNXch`) and the holder
(`X5fd4W`) did not churn; therefore those traces cannot explain the
failed starts. Do not keep retrying the same launcher. Trace the actual
launcher across linking, or separate monitor attachment from capture
start and verify a stable mute+epoch before arming. An additional staged
attempt (`BXrt74`) held the playback trigger through monitor-only attach,
then recycled playback after MicArray linked, before endpoint writes.
This narrows that failure to the mic-attach window, not its cause.

On the staged, traced run `micarray-0db.q90scq` / `gap-trace.anAvLm`,
playback held trigger `6030.691125844`; capture initially stopped with
ALSA state 4 (XRUN) in a kworker during mic bring-up, then settled at
`6037.674345576` before step 30/unmute ACKs. The two settled triggers
held for the entire 520 s stimulus, with no logged PipeWire errors.
All 111 interior gap windows had exactly zero monitor peaks. Relative
to the initial tone, six bands were down 27–40 dB just before the gap
and 28–42 dB immediately after the gap. They were still 24–36 dB down
later. Neither stream was restarted and no gain transaction ran through
the gap. Thus a 120 s pause in program audio did **not** clear the fault
with both PCM streams still active. Onboard scalar measurements are
diagnostic only; the pre-arm XRUN also precludes a clean startup pass.

A distinct follow-up for the loudness defect is to retire only the capture
PCM after the drop, keep the 0 dB render trigger and tone unchanged, and
record before/during/after capture close with the independent pickup. The
historical 300 s capture-close run did not first demonstrate a drop, so it
cannot test recovery. A rise after closing capture would demonstrate that
capture must remain active to maintain the loss; no rise would show that
capture-close alone does not clear it within the observation window. A
failed close, another capture client, a playback epoch change, any gain
write during the contrast or a recorder discontinuity invalidates it.
This is a localization test, not a proposed capture-off workaround.
Use a continuously running `--monitor-only --stimulus-tones` probe
and a separate capture-only client so closing it cannot kill the monitor.
With separate stimulus-edge markers in each clock, run:

```sh
python3 tests/fullio-capture-close-recovery.py external.jsonl monitor.jsonl \
  --external-start EXT_EDGE --surface-start SURFACE_EDGE \
  --capture-closed SURFACE_MONO --duration 600
```

The checker requires a pre-close drop on both lanes, a fixed playback
trigger, continuous digital tone and explicit capture close. It reports
an early post-close window (2–12 s) by default. Keep the Mac recording
and tone running long enough to check a later window with `--post-delay 30`
(+30 to +40 s) from the same run. Delayed analysis still verifies digital
monitor stability through the intervening interval. Neither window proves
indefinite recovery or excludes a still slower change. Confirm endpoint ACK, no intervening gain
writes/PCM XRUN, recorder independence and edge alignment separately.
The only capture PCM currently enumerated on the test Surface is the
built-in MicArray; the contrast has not been run with external pickup.

**Onset fingerprints for the loudness track.** Replayed four archived
scalar logs with `tests/fullio-sag-onset.py`: first five consecutive
~1 s windows with all six transfers down >5 dB, stable paired digital
monitor and fixed triggers. Immediate 0 dB (`lkv40A`), 300 s zero-primed
0 dB (`gXGid7`) and −3 dB (`OlMQiz`) cross at 76.20, 110.29 and
230.62 s of tone, respectively. Despite variable latency and GainStep,
the following 10-window medians agree: ~12 dB down at 203–454 Hz and
~8 dB down at 1009/1017 Hz. The gap diagnostic (`q90scq`) is different:
~9 dB across all six bands after the 158.41 s crossing, then a much
deeper drop. Do not fit all records to a single fixed shelf or invert the
shape at the endpoint; the observed patterns are discriminators for a
future post-SP observation, not a safe correction curve. Capture here
is still the uncalibrated onboard MicArray, and the one-second bins do
not give exact event timestamps.
Traces removed, both PCMs closed, SSH/greetd healthy.

**Capture reads before ALSA START.** On `duplex-profiler-staged.XgFaKB`,
scoped PREPARE/trigger/read probes confirmed eight initial `q6apm_read()`
submissions from the capture prepare at `6706.230421–.230473`. Eight
more submissions came from the `DATA_READ_DONE` callback before the
capture q6apm START at `6706.242669` (~12 ms after priming). All observed
sends returned 56 (accepted by transport, not DSP completion status).
A source cross-check found that `q6apm.c` publishes the READ_DONE token
as a hardware pointer and invokes the PCM callback on a matching buffer
address even if the returned `status` is nonzero or `data_size` is zero.
Therefore the eight early callbacks cannot be taken as eight valid
periods. The first five 32-bit fields agree between the composed kernel
and public `rd_sh_mem_ep_api.h`, but the kernel declaration has an extra
`offset` word before the timestamp. Do not decode timestamps/flags using
that struct until the shipped firmware layout is verified. A targeted
next diagnostic is to record only the length-checked common prefix
(status, size and token; no PCM payload) around ordinary MicArray START,
then determine whether valid full periods actually precede START. This
can be investigated entirely on the Surface; it is not evidence that
capture accounting causes the sustained acoustic drop.

On `duplex-profiler-staged.5mNt4Q`, a temporary READ_DONE callback probe
read only those common metadata fields. The eight pre-START notifications
(tokens 0–7 at `8812.473046–.473108`) all reported status 0 and **zero
bytes**. Capture START occurred at `8812.477951`; all 82 observed later
completions reported 7680 bytes, the negotiated full period. No PCM
payload was captured by the trace. The player was muted and neither PCM
changed epoch after startup. Thus the burst was a ring of empty returns,
not eight early audio periods. A candidate must return/requeue these
buffers without publishing a hardware period; skipping only the period
notification while still advancing the token-derived pointer is not
sufficient. Preserve one outstanding submission per slot and do not
change protection or DSP gain. This trace does not reproduce the
intermittent XRUN or explain the long 0 dB attenuation.

`tests/fullio-capture-start-completions.py` models the observed eight
empty returns followed by 82 full periods. It keeps the ALSA position
unchanged during priming and rejects a partial empty lap, reordered or
duplicate tokens, errors, short periods and empty steady-state returns.
A partial empty lap is not equivalent to a full lap: publishing slot 1 as
logical period 0 would expose the wrong samples. The kernel integration
also needs a submission fix: `q6apm_read()` currently snapshots the token
for packet allocation **before** `graph->lock`, then selects the DMA
address and advances the same cursor **inside** it, while sending after
unlock. Prepare and completion requeue are separate callers. Establish
serialized token/address/queue ordering and no cursor advance on a failed
send before trusting the completion model. The opt-in review patch
`pkgs/patches/sp11-fullio-capture-read-order.patch` is the submission half:
it takes the token from the address's slot under the same mutex, holds
that mutex through the nonblocking `gpr_send_port_pkt()` / `rpmsg_trysend`,
and leaves the cursor unchanged on send failure. It rejects a missing
or invalid slot. `git apply --check` on the composed Next24 tree and
`tests/fullio-capture-read-order.py` passed; the extracted unpatched
function fails the mock's send-serialization assertion. The patch is
not in the kernel stack yet. It does not change how returned payloads
are admitted or how upper layers handle submission failure, and it is
not a deployed fix for either acoustic symptom.

The separate `pkgs/patches/sp11-fullio-capture-read-prefix.patch` checks
READ_DONE admission before any hardware-pointer update: the response must
contain the common prefix through `data_size`, its token must be in the
mapped ring, and both address halves must match the slot. Without a map,
no ALSA notification is sent. The callback runs after releasing the graph
mutex because it may submit another read. The extracted C regression
`tests/fullio-capture-read-prefix.py` covers missing/truncated prefix,
out-of-range token, mismatched address, unmapped and valid buffers.
These are offline checks, not a native build or deployment. The prefix
gate does not yet treat a zero-byte return as a period-free reclaim.
Dropping the callback would starve the ring; forwarding the existing
callback would still publish progress. The reclaim event and its
submission/lifecycle ownership have to be implemented together.

The offline ring model now couples every reclaim to one accepted read,
checks that failed submission does not consume a slot, and refuses to
publish late returns after retirement. The composed source exposes a
second integration constraint: `q6apm_alloc_fragments()` resets `dsp_buf`
and `hw_ptr` **before** its existing-map check, and ordinary PREPARE can
invoke it again on the same graph. The token is only a slot number; the
ordered model can reject unexpected slots but cannot distinguish a
stale reply from a new read with the same token/address after wrap or
reprepare. Do not reset the new ownership counters there until retirement
is proven; use a drained protocol boundary or a fresh GPR port with
verified old-port retirement. The model does not certify DMA release.
The submit, common-prefix and ownership tests all passed offline.

**Actual same-fd capture retirement.** `tests/fullio-capture-same-fd.py`
ran capture-only on the exact frame-gate one-shot (`capture-reprepare.vDkjiL`),
with speaker PCM closed and no gain or DSP changes. Two 7680-frame reads
succeeded across DROP→PREPARE→START on one ALSA handle. With this direct
ALSA geometry the full completion was 15360 bytes (not the earlier
PipeWire 7680). After DROP at `9400.335035`, the old lap returned token 2
with **960 bytes** during BE STOP, then tokens 3/0/1 with **0 bytes**
during FE STOP. All four arrived before FE STOP returned at `9400.339793`,
then the driver freed/reallocated host descriptors and started again.
No explicit GRAPH_FLUSH appeared. This is positive evidence for a
possible drain boundary on this normal transition, not proof that STOP
always drains or even that this trace's STOPs ACKed (no return values were
probed). A future candidate must turn off requeue first, accept in-flight
partial/empty returns as retirement accounting only (never PCM progress),
require the STOP result and zero outstanding reads, and refuse reuse if
either proof fails. Partial data while *draining* is not the same as a
partial active period. No persistent changes or saved PCM.

**Checked capture implementation candidate.** Apply
`sp11-fullio-capture-read-order.patch`, `sp11-fullio-capture-read-prefix.patch`,
then `sp11-fullio-checked-capture.patch`. The new behavior requires
`microsoft,denali-fullio-checked-capture` on the sound card, Denali queued
MicArray graph 2, and no feedback-probe mode. Requests use a monotonically
increasing GPR token until retirement of the port (no wrap/reuse); replies
must match the outstanding token, address and map handle. An initial empty
lap only recycles slots. Full periods advance the cursor; invalid active
completions cause an XRUN instead of publishing bad data. Retirement gates
submission under the same mutex, consumes partial/empty returns without
notifying ALSA, and requires an actual token-scoped STOP ACK plus zero
outstanding reads before same-fd PREPARE can reuse the descriptors. A
shared/no-op STOP, missing completion or missing ACK denies reuse. This
checks ordered completion; the production DSP still has to demonstrate
that it echoes non-slot tokens, retains reply order, and drains with
requeue disabled under the actual PipeWire geometry. The patch does not
establish DMA release after a failed CLOSE or change the playback path.

The three patches apply to the driver files fetched at official
`next-20261124` after the current FullIO AudioReach and gain patches.
`tests/fullio-checked-capture.py` ran the extracted C completion/retirement
functions with a mocked GPR STOP for empty/full laps, wrong/stale token,
partial priming, partial/empty retire, shared/no-op STOP, incomplete drain
and timeout. Native Surface AArch64 object compile on that composition
passed: `q6apm.o` SHA-256 `a5adcb47ed39cf6ce11e7ea2a4cb7faf81cf5405422ab5ca09e86f38aeb1dabb`,
`q6apm-dai.o` `a92ef5b53d3cc2369a04ad888e2f7671616980d2263a13136e67e432ceab6d35`.
This did not link or boot a new kernel. Before the object build, official
tag queries confirmed mainline v7.3 / v7.4-rc4 and next-20261125; keep the
already compared Next24 pin for this isolated test (no proven relevant
benefit from changing the baseline at the same time). `q6apm.c`,
`q6apm-dai.c`, and `wsa884x.c` are byte-identical at those two next tags.

**First exact one-shot (checked capture v1).** Enable
`surface.fullio.checkedCapture` alongside the existing render and clock
readback modules. The audit module must extend the *selected* capture
kernel, not silently replace it with the ordinary FullIO kernel. Native
evaluation confirmed enabled and disabled release suffixes. Standalone
UKI preparation requires both `--checked-capture` and a matching DT
marker/release. The v1 build used the exact frame-gate fixture sources
plus the experimental drivers only, without the separate local gain
snapshot and keeper changes. The normalized DT differed only by the new
marker. `/nix/store/n07zy76gxrj6y1q602qs3v0clprhr1k6-nixos-system-surface-26.11.20261124.52a9386`
booted from UKI SHA-256 `132c543f814749f1f7dc8126e48f738adb74fc6d01fea8e6d475203fda62ffe7`;
Gen26 default and Gen20 rescue verified, sshd/greetd active, Niri screen
turned off on the exact closure. Both PCMs closed after stopping the
fixture holder/keeper.

In `capture-reprepare.VgHmiq`, the first capture delivered 7680 frames,
with two valid 15360-byte completions. Same-fd PREPARE then failed
`-EIO` without Oops: FE ALSA DROP at `72.664816` was followed by BE
`q6apm_graph_stop` at `72.664837`; token 2 returned 192 bytes at
`72.666353`, before FE `q6apm_capture_retire` at `72.667978`. It was
misclassified as an *active* short period and latched the fault. This
is a real v1 regression. v2 adds `sp11-fullio-capture-early-drain.patch`:
close admission in the FE STOP trigger before that BE can return the
buffer, without waiting or sending a DSP command in trigger. PREPARE
still requires the distinct single scoped STOP and zero outstanding
reads. The C test now injects the observed 192-byte reply before FE
retirement, checks no cursor change, and checks that a second STOP is
not issued.

**Checked capture v2 on the Surface.** Native closure
`/nix/store/s3hhfal6x0jxr3719hkf99xw896yv27k-nixos-system-surface-26.11.20261124.52a9386`,
private UKI SHA-256 `f4761c96c4a811373d89189d684c474b3bdbb3258e60e6f85803d06d908e21c5`,
booted one-shot with exact closure, sshd/greetd and Niri screen-off
verified. Persistent Gen26 and recovery Gen20 remained unchanged.
Capture-only `capture-reprepare.r6ylkS` (3840-frame periods) and
`capture-reprepare.9RVJXS` (1920-frame periods) each delivered two
7680-frame epochs through same-fd DROP/PREPARE. Metadata and
`tests/fullio-checked-capture-trace.py` confirmed both STOP ACKs in each
trial, four outstanding returns retired after DROP, and first tokens 6
and 8 respectively on the re-prepared epoch. In the 3840-frame case
one old token returned 576 bytes, followed by three empty returns, and
none published a period. No XRUN or kernel fault in those trials.

**Separate startup diagnostic on v2.** `muted-pa-start.8WPjTz` started
from 180 seconds closed and frame-gated, with a MicArray epoch already
running, exact-zero playback and DSP mute verified. PA START entry/return
`293.975900→294.084325`, with unchanged MicArray epoch. The capture
showed raw peaks 2769 and 1787 within the vicinity of the event, but the
strict analyzer **rejected** it: maximum adjacent pipe receipt gap
152.308 ms exceeded the existing 150 ms bound. There were no sample-index
gaps in the 504 analyzed blocks; this does not fix receipt-to-ADC timing
or establish the acoustic source. The analyzer had first rejected the
new explicit `{'state': 'closed'}` schema; fixing that presentation case
and rerunning on the same data retained the timing rejection. This is not
a startup-crack pass.

**0 dB v2 replay reproduced the fault.** `micarray-0db.kLeLYI` used
GainStep 30/Q28 unity with gain and unmute ACKs, both normal capture
paths at 84, 4608 peak stimulus, and fixed playback/MicArray triggers
`394.452829601`/`398.237483917`. The pane/SSH lifetime interrupted the
intended 600 s run after about 290 s of tones; both PCMs closed and no
kernel or PipeWire errors were logged. The valid prefix is already a
failure: `fullio-sag-onset.py` found a sustained post-monitor drop at
82.229 s, first-window losses 7.86–12.56 dB across all six bands with
stable monitor. The earlier capture accounting bug is not required for
this reproduction. Do not arm another unchanged 600 s playback as an
attempt at acceptance.

**Direct ALSA MicArray / 80 ms differential.** Added the opt-in
`fullio-level-probe.py --direct-mic-80ms`: monitor still uses PipeWire,
but `arecord` owns MicArray `hw:0,2` in S16_LE/48000/stereo with verified
3840/15360-frame periods/buffer and fatal-error handling. No PipeWire
capture node or capture XRUN recovery was involved. In the exact v2
closure `micarray-0db.LNBplJ` completed the intended 240 s of tones at
Step 30 with both capture routes at 84 and gain/unmute ACKs. The replay
passed provenance/frame/clipping checks and failed the level gate:
82.229 s in the earlier PipeWire capture run versus 224.616 s here;
fixed render/capture triggers `2237.365191050`/`2241.132422701`, no error
entries in kernel, PipeWire or arecord logs, −12.08 dB worst 10 s band.
The first sustained post-crossing six-band profile was within 0.33 dB
per band of the earlier 40 ms/PipeWire run. Onset delay is not explained
by a single trial per geometry; the failure itself does not require the
PipeWire MicArray node or the 40 ms host capture periods. This narrows
where to look; it does not identify the first changing post-monitor
signal or qualify 0 dB stability.

**DSP timestamp lead for startup observation.** In capture-only
`capture-reprepare.rbSKX4`, all eight full 7680-byte/56-byte replies had
public-layout word 7 `0x80000000`, word 8 = 40, and words 5/6 advanced
by 40000 µs exactly across all six contiguous in-epoch intervals.
Empty drain replies retained old words 5/6 but cleared validity and
frame count. Do not interpret the kernel struct's undocumented `offset`
slot as a timestamp. `tests/fullio-capture-dsp-clock.py` checks the wire
length, valid flag, nonzero frame count, consecutive tokens and cadence.
A native `tests/fullio-arm-counter-anchor.c` read 19.2 MHz CNTVCT and
estimated a counter-to-host monotonic offset of 21.540331 s on the same
boot. If the DSP words share that origin, the callback trails the first
sample time by 44.62–44.84 ms for the measured 40 ms periods. That is
plausibility, not proof of ADC origin or an acoustic conclusion; check
80 ms geometry and join independent direct PCM period metadata before
using this for PA-event localization.

`capture-reprepare.kby6LK` also gave exactly 80000 µs at 15360 bytes
(six intervals). Two separated CNTVCT anchors drifted 8.4 ms against
Linux CLOCK_MONOTONIC across ~66 s; use short, same-run anchors rather
than a fixed boot offset. `fullio-capture-period-peaks.py` takes bounded
direct 1920-frame MicArray reads and keeps only peak scalars;
`fullio-capture-period-join.py` matched 396 10 ms peak blocks to valid DSP
periods in the capture-only `ygWeLw` trial. Anchored READ_DONE receipt
trailed the calculated end of each 40 ms period by 0.099–2.985 ms.

**DSP-timed muted START versus direct no-render control.** After 180 s
closed/frame-gated, `capture-reprepare.fUWsGP` took 996 joined peak
blocks, no gain/unmute, exact-zero render, verified DSP mute, one PA pair
`1309.627752→1309.736586` and no capture XRUN; callback lag after each
period end was 0.096–2.157 ms. The no-render `u1QkVG` had 996 blocks
and the same geometry (0.112–4.239 ms lag). At matched offsets from first
capture sample, maxima before entry, during PA START, and at 0–100,
100–500, and 500–1500 ms after return were respectively
`127/652/287/2701/195` vs `87/49/63/74/69` for no-render. The strongest
blocks start +150.509 ms (2701), +350.586 ms (1731), and +220.540 ms
(1665) after paired START returns, not at the synchronous register-write
or readiness window. This points to delayed render-engagement effects in
this trial. It does not identify where the signal entered the MicArray,
measure mic-closed acoustics or justify undoing PA or clock proofs.

**Exploratory live DIAG, not a localization proof.** Private 0x1586
archives `live-diag.J6eomR` and `fade-diag.oyV73D` contain tap-1 records
with 8 kHz/32-bit/640 B and 48 kHz/16-bit/192 B formats consistent with
candidate VI and post-SP loggers. Tap ID alone does not establish logger
identity. The latter archive shows changing payload statistics around an
acoustically measured fade with stable render monitor, but the original
analysis used coarse receipt windows and incomplete 192 B payloads. Raw
signed word-sum/difference ratios are not physical V/I measurements;
packing, continuity, logger provenance, and alignment are not established.
The Golden topology configures `0x4003/0x4025/0x402a` for tap IDs
1/2/3 respectively, not a shared tap ID. The private collector retained
only records with a value of 1–4 at byte offset 52. In `oyV73D`, it
rejected 264,820 of 274,967 structurally valid records at this filter;
all retained records had value 1, and none had a 24 kHz header. The
reference `2026-08-20-postpa-offset2-cpswake-tap3.json` places tag 3 at
byte offset 60 (`0x3c`), not 52. The retained `oyV73D` packets split at
that offset into 8,634 tag-1/48 kHz and 1,513 tag-2/8 kHz records.

On the exact checked-capture v2 boot, a 12 s protected zero-input
render with MicArray closed counted all 13,181 structurally valid
0x1586 frames, without archiving payload or filtering by any tag.
Offset 60 classified every frame consistently: 11,981 tag-1/48 kHz and
1,200 tag-2/8 kHz, matching the RX0 and VI logger configuration. The
old filter would discard 9,178 frames in this same run. No tag-3 or
24 kHz records in either 192 B or 1920 B geometry were observed in
this window. DIAG-ID negotiation was incomplete, so the result does not
prove an inactive CPS transport or a missing CPS input to protection.
Zero mask was sent (no exposed ACK); both PCMs closed on cleanup and
no matching faults or XRUNs were logged. The parser and the existing
PA-off collector now use offset 60.

Reanalysis of `oyV73D` used recorded monotonic arm origin 4523.858314 s
and acoustic onset 4677.794 s. The full 192 B payloads in receipt windows
−40 to −10 s and +20 to +50 s (600 packets each), interpreted as
interleaved stereo S16, gave 744.6/744.8 and 314.6/314.9 RMS counts
(about −7.5 dB). Only 600 ms of candidate PCM was retained per 30 s
window, with receipt gaps up to 210 ms over the run; only 2492/8633
adjacent 48 kHz records advanced the candidate sequence by one. This
is a decrease in the retained samples, not a continuous measurement or
proof that attenuation originates in SP or MicArray data aliases into
feedback.

**Receipt-time onset cross-check.** `tests/fullio-rx0-sag-join.py` joins
corrected tap-1 RX0 PCM to the MicArray/host-monitor scalar onset in
five-second bins. In `oyV73D`, the bin beginning at acoustic onset
measured −7.71 dB on both RX0 lanes (98 packets) and −10.80 dB in mean
six-band acoustic transfer. The equivalent bins in `KluWuO` (rejected
map, 0 dB) and `gXqnQq` (rejected map, −3 dB) measured −7.58/−7.57 and
−7.79/−7.79 dB respectively on RX0. All three stayed depressed in the
following bins. Small declines in the preceding RX0 bins are not a
lead-time measurement: old archives are sparse and selection-biased;
DIAG receipt and MicArray scalar readout are not sample clocks. This
supports a DSP-output component to the sag, not an analog-only explanation,
but cannot identify the first DSP stage that attenuates.

The pinned graph provides two existing upstream checkpoints:
`0x47e9` (code `0x1531`) before final `VOL_CTRL 0x4a63`, and
`0x467a` (code `0x19b0`) after the two MSIIR stages but before
`SAL 0x4001 → channel mixer 0x402c → SP 0x4027`. Their exact edges
are now verified in `tests/fullio-topology.py`, including SAL input
port 12. Neither upstream stream was observed in those 0x1586-only
archives.

**Same-run three-tap bracket (checked-capture v2, unchanged topology).**
A four-second protected zero-input qualification first observed both
upstream codes, each tag 1, stereo 48 kHz S16 with 1920 B payloads,
398 packets per code, all zero. A temporary collector then enabled only
`0x1531`, `0x19b0`, and `0x1586` together for a 240 s 0 dB replay, saving
one-second counts and sums of squares only, not PCM. Exact closure
`s3hhfal6…`, trial `denali-checked-capture-boot.upstream.09G4fP` /
`micarray-0db.vIAhkj`; Step 30, Q28 `0x10000000`, direct MicArray with
fixed START epochs. The acoustic sag reproduced at 223.616 s from first
active stimulus (worst 10 s band −12.448 dB). At acoustic onset,
`tests/fullio-dsp-sag-bracket.py` compares both lanes over five receipt
bins against the −40 to −20 s reference; every bin had ≥90% nominal
frame coverage. Pre-volume stayed at 0.0000 dB, pre-SAL at +0.0001 dB,
and RX0 fell −7.3393 dB on both lanes. Both PCMs closed, no matching
kernel faults/XRUNs, and zero-mask send succeeded (no firmware ACK).

This brackets the measured level change **after the pre-SAL logger and
at or before RX0**: `SAL → CHMIXER → SP → SPLITTER → RX0 logger`.
It excludes an upstream broadband drop in this run, not every upstream
spectral or feedback change. It does not distinguish SAL from SP or
identify the trigger, and is not evidence that startup is fixed. No
24 kHz CPS records were seen in this run either. Do not bypass or
retune SAL/SP; a next localization needs a qualified observation at the
CHMIXER→SP boundary or a supported dynamic readback for that segment.

**Offline pre-SP logger fixture.** `tests/fullio-pre-sp-fixture.py`
accepts only the hash-pinned compiled Golden topology (`e7bb06a0…`). It
moves the existing `0x19b0` logger `0x467a` from upstream of SAL into
SP's container, so `0x48a1 → SAL:12` and
`CHMIXER → 0x467a → SP:2`. It recycles the logger IID and calibration
instead of adding another module or changing logger code, SP/SAL
parameters, control links, or feedback routes. Only three widgets'
placement/edge values and three corresponding DAPM routes change; the
inverse must reconstruct Golden byte-for-byte. Independently editing
the pinned text source and compiling with native AArch64 `alsatplg`
produced an identical binary, SHA-256
`86cc8afb4100c4713d077bbb0c3d71ebab910c25e75f2e29dbffcaec26a73a6c`.

**Native pre-SP one-shot and reproduction.** The opt-in
`surface.fullio.preSpLoggerAudit` adds a distinct DT marker and disables
holder/keeper autostart on this diagnostic only. UKI staging requires
both checked-capture and pre-SP flags and verifies the selected topology
hash. Native closure `kddj969k3azm2nplmm0xqk03b8lx1hbm` reused the exact
checked-capture v2 kernel; after removing the marker, the normalized DT
matched v2. Verified the exact boot, Niri screen-off, SSH/greetd and the
hash of the runtime firmware path. Gen26 stayed default and Gen20 and the
v2 recovery UKI matched their preflight hashes. Four-second zero-input
qualification had stereo PCM, mute/SP/SPVI PREPARE readbacks, RX0 and VI
logs, and 396 zero packets on each upstream logger. Both PCMs closed
without matching faults; this does not qualify protection under all loads.

In matched 240 s replay `denali-checked-capture-boot.pre-sp.Jpdxix` /
`micarray-0db.p896FQ` (0 dB, Step 30, live direct MicArray), acoustic loss
reproduced at **87.243 s**, worst ten-second band **−17.477 dB**. At onset,
`0x1531` and relocated `0x19b0` both stayed at **0.0000 dB relative to
reference** on both lanes, while RX0 fell **−5.3874 dB**. In later bins
RX0 was about −8.2 dB while the pre-SP logger stayed flat. No PCM payload
saved, no matching fault/XRUN, zero mask sent without firmware ACK, both
PCMs closed. This places the measured drop after CHMIXER, in the
**SP → splitter → RX0 logger** segment on the diagnostic graph. The
public AudioReach splitter (`0x07001011`, source `d416046c…`) copies PCM,
which makes SP the leading candidate, not a proof about the proprietary
firmware or its trigger. The fixture changes scheduling and onset varies;
it is not a fix and does not validate startup or 0 dB acceptance.

**Feedback-parity candidate.** Re-decoding archive
VI by the corrected tag at byte 60, the four 16-bit positions in each
8-byte transport unit all show the same extreme pattern. In prior
zero-input/mic-closed `live-diag.J6eomR` (1,017 packets), exact
`−32768` occupies 26.27–26.33% and `+32767` 26.60–26.66% per position.
In Golden-map replay `oyV73D`, the `−32768` rate is 16.33–17.58% before
and 23.81–25.45% after (30 s windows offset 15 s from onset; 100 packets
per window). The clean reference's forced-tap-2 silence reports no
`−32768`, median absolute 178 and peak 891. Different logger mode and
historical sampling bias prevent quantitative equivalence; this is a
feedback-integrity lead already present before sag and without mic, not
proof of MicArray aliasing or of a physical lane's scaling.

Running WSA DT contained `0xff` configured Offset2 for DP10/11/13 and
no active-parity marker. The quiet start trace proved transport-param
and enable callbacks plus the paired PA return, but recorded **no**
`qcom_swrm_cpu_reg_write` events, so it does not prove active register
values. Golden v33's launch explicitly enables both active Offset2
and CPS route/PCM wake. The existing kernel already implements the
scoped parity path under `qcom,denali-fullio-sidechain-audit` with
readback and CPS restoration. `surface.fullio.feedbackParityAudit`
opts in only with checked capture, frame-stop admission and the
unmodified Golden topology. The private UKI gate independently checks
those markers and the stock topology hash. Neither the default path nor
kernel code changes.

Native one-shot `3wa0xinlhavkyfjw1zfs9cpw6w2s59nw` uses the same v2
kernel and byte-exact Golden topology; normalized DT differs from v2
only by the sidechain marker. Exact boot, SSH/greetd and Niri screen-off
verified. Gen26 default unchanged; Gen20 and v2 UKI hashes checked.
Protected zero-input qualification reported DP10/11/13 Offset2=0
readbacks in both banks, CPS wake and restored originals; DIAG counted
398 tag-3 24 kHz CPS frames (1920 B) where the prior control had none.

The 240 s instrumented 0 dB trial `feedback-parity.Xp88gI` registered
25,498 CPS frames, passed with worst acoustic band −0.166 dB, and closed
both PCMs. The independent **600 s** replay without a DIAG collector
`feedback-600.VbCpAb/micarray-0db.TqitQC` passed with live direct MicArray
(TX/VA controls all 84), Step 30, Q28 unity, fixed PCM epochs, and worst
10 s six-band change **−0.466 dB**. Both PCMs closed; no matched XRUN,
wake restoration failure or kernel fault in the wrapper journal gate.
These results support the combined feedback-parity candidate for sag;
they do not distinguish the contributions of active Offset2 and CPS
wake. Startup transient, program listening, and strict regression /
normal deployment remain unverified.

**Practical startup gate, feedback-parity one-shot.** After continuous
180 s with both PCMs closed and SoundWire suspended, the protected
zero-render trial `capture-reprepare.TSLr5P` returned paired START 0 and
joined 996 MicArray scalar blocks. The largest nearby peak was 174
(−89.353 ms relative to paired START return), versus historical peaks
1759–3085. In the historical delayed-transient window the candidate max
was 73 against 74 in the retained no-render control. Thus the old large
spike did not reproduce in this run; about 109 ms paired START latency
remained and is not, by itself, a listening failure. Same-fd MicArray
DROP/PREPARE passed for 3840- and 1920-frame periods, two 7680-frame
epochs each. These are diagnostic results; judge daily suitability on
ordinary program playback/first sound, volume and mute, and duplex at
0 dB, not on eliminating every scalar transient.

**Desktop-path regression and owner listening handoff.** A 120 s
PipeWire render + ordinary PipeWire MicArray replay at unity recorded
`replay.status=0`, worst ten-second band −0.124 dB and empty fault logs
(`parity-desktop.zKUXNW/micarray-0db.fLWOyk`). The wrapper's immediate
post-stop closure check exited early; a subsequent read confirmed both
PCMs closed. `desktop-acoustic-controls.gaSkHk` held the playback epoch
and measured two acoustic tone bands: desktop 50% reduced both by
18.0–18.4 dB, mute by 34.9–37.7 dB, and return to unity was within
0.05 dB. A monitor-only test did not see these downstream changes and
was not used as control evidence.

The keeper now accepts explicit `0` or the unchanged default `-3`,
with the same once-per-epoch and no-retry-on-failed-ACK rules. On the
exact parity one-shot, an ephemeral user-unit drop-in selected 0 dB
for listening only. Three close/runtime-suspend/reopen cycles armed
three distinct epochs exactly once with Step 30/Q28 unity and no
matching kernel faults. The first attempt's 12.5 s suspend allowance
was too short; the 45 s allowance qualified all three transitions.
Third graph left armed on silence; MicArray closed until an application
opens it. No change to Gen26 or Gen20, no persistent user drop-in, and
no claim of user listening or ordinary-switch acceptance yet.

**Prepared daily closure without disturbing listening.** The explicit
`surface.fullio.feedbackParityRender` option uses the same feedback DT
as the manual-start audit, rejects mixing the audit variants, and starts
the holder and once-per-epoch keeper automatically at endpoint 0 dB.
The checked-capture package excludes the unrelated gain-snapshot patch
so it reuses the exact tested v2 kernel. In an isolated consuming-flake
copy with the existing pinned inputs, native closure `0q3k9z43…` built
successfully. Its kernel, boot DTB and compressed Golden topology were
byte-identical to the listening one-shot; generated service links and
`ExecStart … 0` / `Restart=no` were checked. Keeper and repeat-UKI
unit tests passed. The closure was not switched or selected; this has
not updated the committed consumer lock. Next verify owner playback,
then the synchronized input and ordinary switch/default reboot with
Gen20 recovery preserved.

The read-only post-reboot gate is
`sudo -n python3 tests/fullio-daily-boot.py "$expected_toplevel"` from
`surface.nix`. It checks the bootctl JSON default and selected entry,
all three closure symlinks, the actual PE init/kernel/DTB rather than
its sidecar, booted feedback markers, runtime Golden topology, Gen20
hash, SSH and greetd. The checker validated the real Gen26 PE sections
and rejected the current one-shot as a default boot. Its offline
negative tests also cover wrong DTB and duplicate entry/cmdline fields.
This is a deployment check, not a substitute for audible regression.

**Locked native rehearsal, no activation.** A clean private Git consumer
snapshot `9f99d35…` locks hardware snapshot `498afef…` with a local Git
URL (bundles, no push). Only the `surface` lock node differs from
`flakes` base `0414cb9`; nixpkgs remains the locked unstable-small
`52a93865f031ba894c0d19121dda6b75c0f2b2b8`, evaluated release `26.11`,
existing `system.stateVersion = "26.05"` unchanged. Native offline build
from the lock, without an input override, produced `lifk8l96…`.
Kernel store path is the exact tested v2 `8c9110hy…`; DTB, initrd and
Golden firmware match `0q3k9z43…` byte for byte. Both autostart links
and unit contents match aside from the tools derivation path; keeper
and volume scripts match byte for byte, and the holder only changes
comments. RTKit and the frame-stop gate stay as tested. The snapshots
are a private rehearsal, not a portable release lock or proof of
ordinary `switch` / default boot.

Consumer rehearsal `9bbedc5…` adds the corresponding assertions to
`flakes/tests/surface.nix` and still evaluates to exactly `lifk8l96…`.
The native `checks.aarch64-linux.surface-boundaries` build passed for
both the old locked configuration and the unity candidate. In an
isolated negative test, forcing the keeper to restart on failure was
rejected by the unity assertion. The check also requires holder/keeper
autostart, the checked-capture kernel, frame-stop admission, RTKit,
explicit unity, and no diagnostic-only mode. It is not a runtime check.

Before changing the ESP, a root-only backup was made on the Surface
(outside the store). `tar --compare` and the archive SHA-256 check
passed; both archived Gen26 and Gen20 images matched their known
hashes. After each ordinary `sudo nixos-rebuild switch --flake .#surface`,
run `sudo -n python3 tests/fullio-daily-switch-check.py "$expected_toplevel"`.
Save the reported default ID and UKI SHA-256 from the first switch; pass
`--repeat-entry ID` after the second and compare the hashes. The checker
rejects an unswitched candidate (verified on the live one-shot), verifies
the real UKI rather than the generation sidecar, checks Gen20 and recovery
services, and refuses to qualify a pending `LoaderEntryOneShot` EFI
variable. The initrd gate checks the exact expected initrd prefix and
parses the appended archive to compare the early GPU zap with the
locally provisioned private input. The actual Gen26 image passed this
check; malformed, duplicate, and mismatched payloads failed offline.
Only the post-reboot gate checks the actually selected entry.

The exact candidate `surface-install-ukis` hook ran twice natively in a
private mount namespace against an off-ESP ext4 fixture. It produced a
candidate UKI and accepted the rewritten entry on the second run with an
unchanged image digest (`064c0542…`). The PE, private initrd and Gen20
checks passed, and the copied Gen26 and Gen20 entries were unchanged.
This exercises the real hook with a synthetic stock BLS entry; it does
not exercise systemd-boot selecting an ordinary default on the physical ESP.

### Remaining acceptance gates

| Requirement | Current evidence | Still required |
|---|---|---|
| Reproduce startup distortion | Historical DSP-aligned peaks of 1759–3085 versus 74 no-render; previous owner reported audible defect | At 0 dB, listen to first ordinary audio after login/idle and after pause, resume and seek. Parity scalar result (delayed peak 73) does not establish audibility. |
| Reproduce and remove audible level fluctuation | Prior 0 dB loss around 12 dB; parity 240 s DIAG and independent 600 s non-DIAG with at most 0.466 dB worst-band loss | Ordinary program audio on the deployed path, with MicArray open as well as closed. |
| Full 0 dB desktop regression | Gen27 default boot: 120 s PipeWire duplex, −0.267 dB worst band, and mpv pause/seek/resume with volume/mute controls; prior one-shot: same-fd 40/80 ms, acoustic volume/mute and three trigger epochs | Owner's ordinary-content listening on Gen27; representative long-idle reopen if not covered by that session. |
| Ordinary deploy and recovery | Two real switches, default reboot with exact selected UKI/closure, SSH/greetd/Niri/GPU and preserved Gen20 | Verified on the private locked rehearsal; portable two-repo release lock remains separate. |

For the default-boot desktop duplex check, run the boot gate first, then as
`keke` run `bash tests/fullio-daily-desktop.sh "$expected_toplevel" "$new_private_dir"`
in an otherwise idle session. It rejects a different boot before opening
MicArray (checked on the listening one-shot), rejects a keeper drop-in,
and requires exactly one 0 dB gain/unmute ACK pair for the live playback
trigger. It uses the existing 120 s scalar replay, preserves the holder
and keeper, and checks that only the probe closes its capture afterward.
No mic PCM is written. The positive path still needs the ordinary boot;
passing it will not count as a listening verdict.

**2026-11-26 ordinary deployment rehearsal, with owner permission.** Ran
`sudo -n nixos-rebuild switch --flake .#surface` twice from the clean locked
consumer `9bbedc5…`. Both installed/selected the same Gen27 default entry
`nixos-f41dc407…`, UKI SHA-256
`7662d524581e88ceb03c3959ddaefcd4c4af8d8cd360e5a58ac87d58cc229852`.
Ordinary reboot (no one-shot) selected exactly `lifk8l96…`; the actual
PE/kernel/DTB/initrd and private zap, booted Golden topology, SSH/greetd,
Gen20, and Niri eDP-1 2880×1920@120 Hz were verified. Adreno X1-85
passed 1024 offscreen GLES clears with pixel readback. On that default
boot the unmodified installed units supplied a once-per-trigger 0 dB
ACK pair. The 120 s desktop PipeWire duplex replay passed: worst acoustic
band −0.267 dB long / −0.230 dB short, no matching kernel fault and
MicArray closed afterward. A separate quiet mpv PCM playback
simulation exercised pause, exact seek and resume, desktop 50%, mute
and restoration to 100% at the same protected render trigger, with no
matched kernel fault. These application and control checks are not a
subjective listening verdict. Gen27 is left ready at 0 dB, desktop
100% unmuted, with no test player and capture closed.

These gates are separate from any USB or blank-storage work.

**Rejected two-lane map experiment.** One-shot closure
`mxa8mlhnsq3nnvf7g24il5g7800kz9p1` changed the SP_VI logical map from
four entries to two. In `fade-diag.KluWuO` / `micarray-0db.odfd1k`, the
0 dB fade still started 90.245 s after first active audio, reaching
−12.55 dB at 454 Hz. The −3 dB diagnostic control
`fade-diag.gXqnQq` / `micarray--3db.gQbYHg` also failed (−12.598 dB at
206 Hz); it is not an acceptance run. Changed raw word statistics do
not identify a mechanism. The four logical sense lanes and two transport
words are also present in the Golden configuration; they do not establish
an overread. Speaker-2 feedback and protection were not qualified under
the experimental map. The patch is no longer selected in `flake.nix`;
retain the Golden map and do not replay on this closure. The machine
was returned to the exact checked-capture v2 one-shot `s3hhfal6…` with
SSH/greetd active and Niri monitors off. Gen26 stayed default; its UKI
and Gen20 recovery both matched the recorded hashes before reboot.

**Offline CPS tracking control.** The hash-pinned Golden topology
passed `tests/fullio-topology.py --self-test`. Its existing
`--retag-rx0-out … --rx0-log-off --feedback-log-off --keep-cps-log`
variant changes logger configuration only, leaving the CPS 0x1586
logger enabled. Output SHA-256:
`147254e051a0e3d3bd15b278bb172511a8323a746dfed62814d395881b15b9f3`.
This fixture was not installed. A source-discrimination test needs a
bounded, metadata-only census of all structurally valid records before
any assumed tap filter, with CPS geometry checked against the Golden
reference. A single logger control is not a sag fix or an acceptance
configuration.

A second DSP-timed 180 s idle trial (`capture-reprepare.wIoW9v`) added
passive WSA regmap, clock-proof, endpoint mute, and PCM watermark
probes. With 1000 joined blocks (0.055–2.643 ms after-period callback
lag), the largest peak was **3085** in the block starting 24.459 ms
before PA pair return (`1718.954242`), inside the protection-clock proof
call (`1718.906742–1718.954240`), and ~36 ms after the last PA-enable
regmap write (`1718.893710`). A second peak (**1107**) started 155.444 ms
*after* return, consistent with the delayed window in `fUWsGP`. No
traced PA/power-stage register writes or endpoint mute callback occurred
in the first 500 ms after return. Watermark work started +7.480 ms and
ran 50 times at 9.826–10.295 ms cadence in that interval, with no missed
10 ms slot. These observations distinguish an in-proof burst and a
later burst and rule out a host re-write of the **traced** controls for
the later burst in this run. They do not identify the exact clock edge,
exclude autonomous DSP/codec behavior, or prove acoustic origin.

A third 180 s idle trial `capture-reprepare.2Rrr95` added a passive
regmap filter for LPASS TX0–TX3 protection path controls and producer
`TOP_CFG1` (no change to the write sequence). Both pairs went from
reset/clock-off `0x20` to reset/clock-on `0x30` and finally `0x10`.
TX0/TX1 reset release was at `2030.776342–.776345`, TX2/TX3 at
`2030.788219–.788221`, PA pair return at `2030.800091`. The strongest
10 ms MicArray block (1759) starts `2030.778688`: about 2.34 ms after
TX0/TX1 release and overlaps TX2/TX3 release near its end. Another
block (1006) starts 1.409 ms before PA return. The prior large +150 ms
burst did not repeat in this trial. This is closer timing evidence for
the earlier in-proof burst, but a 10 ms block and the unresolved
ADC/physical path cannot assign it to a single register edge. Preserve
paired protection admission; do not add dwell or reorder TX lanes
based on this correlation.
The capture buffer is eight 1920-frame periods. The generic prepare path
starts the DSP graph, queues the entire capture ring, and marks its private
state RUNNING independently of ALSA START. ALSA's period notification
skips pointer updates while not RUNNING, but the q6apm callback still
requeues. This proves that the capture ring can complete a lap before
ALSA START; it does **not** prove an overrun at START or explain the long
acoustic fall. That muted trial and the preceding staged stack-trace
trial (`3dlEGT`) had no XRUN/epoch replacement, so no failed-start stack
was captured. Next compare ALSA stream identity and pointer state at a
natural XRUN with its preceding read completion cadence; do not move DSP
start, add data-flow delays or change protection based on the clean trace.

`duplex-profiler-staged.eDfDqm` additionally correlated ALSA substream
identity with q6apm pointer and capture completion tokens. Tokens 0–7
arrived in **58 µs** before capture START (not eight real-time 40 ms
intervals). Initial capture pointer returns were 0; the next completion
advanced it to 1920 at START+41.5 ms, then 3840 at +81.4 ms. Subsequent
completions arrived at about 40 ms intervals. No state-4 stop or
`-EPIPE` update was seen. Thus the early burst alone is not sufficient for
the failure, and callback receipt alone does not establish the contents
or DSP timestamps of those early buffers. Private trace addresses were
used only to correlate substreams; hooks were removed and both PCMs
closed. This was a muted diagnostic, not startup acoustic evidence.
A subsequent trace of the non-staged launcher (`gap-trace.DRyyFR`,
18,715/18,715 events retained) also did not reproduce the state-4 stop or
`-EPIPE` and must not be read as a repaired opening path. Do not treat
repeated successful muted traces as evidence for the acoustic fix.

**PA START source audit.** Compared the ten START writes in
`pkgs/patches/fullio/wsa-speaker-protection.patch` with the pinned
Windows `2026-08-17-windows-wsa8845-complete-state-machine-oracle.json`:
address order and values match, including `PDRV_HS_CTL 0x52`,
`PA_FSM_EN 0x01`, `PWRSTG_DBG 0x0c`, `PDRV_HS_CTL 0x5a`. The KD
reference explicitly establishes order, not delays; its WPP summary is
for the clock-stop policy, not a per-write acoustic timing baseline.
Updated the local source comments to remove the unsupported assertion
that the crack is a charge step at `PA_FSM_EN`; no write, delay, check,
error path or runtime state was changed. The paired START model passed
on the composed Next24 source. For source attribution, the missing
observable is independent continuous pickup across a long-off **muted**
start and isolated unmute, not another already-quiet PCM smoke test.

**Newer reference branches, not a baseline switch.** `SP11X1e-audio`
`main` still points at `3232e1d`; audited `sp11/7.3-driver-maintenance`
`4a52ccc`, `sp11/7.3-host-integration` `aa14181` and the release `1261677`.
The reference reports clear first sound on two 7.3 maintenance boots,
not microphone qualification or a long 0 dB duplex control. Its linked
2026-10-30 write-up reports a specific difference on the earlier recovered
7.1 stack: distro UCM had stopped enabling the **LPASS macro**
`WSA WSA_COMP1/2 Switch`; restoring both was followed by clear cold
slider checks, but prior on/off tone comparison was inconclusive and
upstream UCM removed those enables for attack distortion on X Elite.
The pinned Surface-next fixture has both macro switches **off** by
read-only `amixer -D hw:0 cget` on the closed PCM fixture (numids 31/32).
Its `SpkrLeft/Right COMP Switch` UCM entries are separate amp controls and
are not evidence of macro parity. Next24 already has MAPLE cache and
versioned COMP1 CTL3/7 selection in `lpass-wsa-macro.c`. Turning on the
macro companders changes real RX gain behavior; do not import the UCM
as a harmless startup change or enable it at 0 dB without establishing
its transfer and protection margins on this stack first.

The control writes only `comp_enabled[]`; on a subsequent interpolator
DAPM power-up, this enables the compander clock, pulses reset and inserts
the block at `RX{0,1}_PATH_CFG0` bit 1, and invokes the configured PGA
offset path. The driver's ear-speaker compensation comment (−12/−15 dB)
is specific to the ear gain branch, not a stereo speaker gain bound.
`2026-08-15-wsa-runtime-producer-state.json` confirms these clock, insert
and half-dB select transitions on the older CPS-v3 Linux binary, whereas
`2026-08-15-wsa-macro-compander-provenance.json` does not establish the
Windows or this Next24 effective curve. A low-amplitude test would not
establish the applicable upper gain bound by itself. The UCM regression
now rejects importing a macro enable into the qualified route; the
existing external `SpkrLeft/Right COMP Switch` writes are unaffected.
Baseline and a one-line mutation were checked offline. No device change.

The maintenance path also removes an early APM readiness RPC from GPR
probe. Next24 still performs it and this exact boot logs opcode
`0x01001021` timeout at 8.672 s. Useful separate boot integration finding;
it is not evidence for the PA startup transient or the 600 s fade. No
reference input changed, no build or deployment, no control writes.

**Offline tap cadence check.** The archived reference
`runtime-20260820-rx-core-tx-mclk/canonical-baseline-capture/packets.bin`
(SHA-256 `da7056a46871a9bad6be12e390a84f34d9803a2753a11fa60d3127e0b4cb989b`)
contains 391 render-shaped tap-1 records (48 kHz stereo S16, 1 ms of
samples per record) over 20.234539 s of recorded host receipt time.
All 390 successive sequence advances are non-unit; no VI or CPS records.
That is 391 ms of sample bytes spread across 20.23 s, not a contiguous
20 s waveform. Do not concatenate this stream to time-align it to the
0 dB fade or infer lost frames from sequence steps without a firmware
contract. `tests/fullio-feedback-samples.py` now reports receipt span
and non-unit sequence advances separately; the reference's historical
timestamps are wall-clock, not a Linux ALSA trigger clock. The legacy
wire tap number is not enough for graph identity: the separate PA-off
CPS-only contrast produced wire tap 1 with a different shape. No live
logging or graph changes were made. The v19c checkpoint's 7.232 s
simultaneous capture is compatibility evidence, not a long 0 dB control.

The session advertises default graph quantum 1024 at 48 kHz and permits
up to 2048; FullIO playback only admits 960 total frames (two 480-frame
periods). That is a size mismatch worth testing, not proof of the active
quantum at the failed transition. In PipeWire 1.6.11 `alsa-pcm.c`, the
ALSA node advertises `node.max-latency` as half the formatted buffer
only with timer scheduling enabled. Measure effective quantum for both
nodes across capture start before concluding the default runs unchecked.
Only then contrast an isolated bounded quantum before proposing a shipped
PipeWire policy; the 1.6.11 `stream.c` env `PIPEWIRE_QUANTUM` maps to
node force-rate/quantum, not a persistent daemon setting. This startup
issue is distinct from the 600-second 0 dB fade on a held graph with no
XRUN.

**Actual duplex scheduler cycles.** Used `pw-profiler -J` on the exact
frame-gate one-shot with one muted `/dev/zero` player and no endpoint
writes. Two distinct capture consumers: direct `pw-cat` at first playback
RUNNING, and the monitor+MicArray scalar probe after a 0.8 s settling
interval. Neither trial replaced the running PCM epoch or logged a new
Broken pipe. Playback negotiated ALSA 480/960 frames (period/buffer);
MicArray negotiated 1920/15360. In both profiles **every** speaker cycle
was 256 frames at 48 kHz, before and after mic start. Every microphone
driver cycle was 1024 frames, in a distinct graph. The advertised 1024
therefore does not by itself explain the playback failure.

The speaker's initial driver activation took 108.629 / 108.990 ms
against a 5.33 ms cycle; its profiler xrun counter increased before mic
start in both trials. After the settling interval, the maximum speaker
busy time was 0.045 / 0.052 ms and steady duplex counters did not
increase. The previous muted PA kprobe interval was 108.947 ms on a
different start. PipeWire's `alsa-pcm.c` calls `snd_pcm_start()`
synchronously; the FullIO trigger calls paired PA setup synchronously.
The timing is consistent with a start-path stall but a **same-run**
profile and PA trace is needed to attribute the interval. Do not enlarge
quantum or move PA enable before its proofs on this evidence. The failed
−3 dB run was not itself profiled, and no acoustic run is accepted here.
Raw profile and marks: `duplex-profiler-default.OtuOWf` and
`duplex-profiler-dualprobe.nu5CvM`; `tests/fullio-pw-cycle-summary.py`
replays the per-driver counts and durations.

**Same-start attribution.** `duplex-profiler-dualprobe.YHgrF6` joined
`pw-profiler -J` to scoped monotonic kprobes on the same muted start.
The speaker driver activation ran from `3873.596079305` to
`3873.704829518` (108.750 ms). Inside it, `data-loop.0` was in
`wsa884x_fullio_start_pair()` from `3873.596118` to `3873.704800`
(108.682 ms, >99.9% of the activation). The two per-amp START bodies
took 21.645 and 21.421 ms. Pair readiness was checked five times at
11.89–11.92 ms each, including four checks around PM/feedback-clock
transitions. The driver xrun counter increased 24→26 before the mic
open, then stayed 26. No PCM epoch churn or kernel/daemon errors during
this trial. Only scoped trace hooks were added and removed; no endpoint
writes or schedule changes. This attributes the deadline miss, **not**
the acoustic transient or the sustained 0 dB fade. Neither deleting
readiness proofs nor increasing global quantum can be justified by
this result. Any later startup scheduling change must keep PA/feedback
ordering and suppress program data until success, and must distinguish
startup-RT isolation from acoustic crack removal.

### Endpoint arm: failure containment and timing

The keeper used to retry the whole gain/GainStep + unmute sequence up to
six times, even after an ambiguous DSP error. The local candidate makes
one attempt per new running PCM trigger, checks the trigger again after
completion, and leaves the unit failed (no automatic restart) if the
transaction fails or the trigger changes during the write. The helper
logs separate submit/ACK lines for gain/GainStep and unmute. Use
`journalctl --user -u fullio-endpoint-keeper.service -o short-monotonic`
with the matching kernel PA START timestamps and acoustic capture. A
submit without ACK does not establish either that the write applied or
that the endpoint is still muted. Do not restart the failed keeper just
to retry the transaction.

Offline mocks exercise a lost ACK, a trigger changing before/after the
helper, a normal new epoch, and prevention of unmute after a failed gain
write. These changes do not alter either gain setting, DSP payload, or
PA state machine; they are not a crack fix or an acoustic test result.

**Isolated digital-silence unmute, 0 dB.** Added `--transient-blocks`
to `scripts/fullio-level-probe.py`: 480-frame (10 ms) MicArray and monitor
peak pairs, absolute stream frame indices and monotonic pipe receipt
marks, no waveform storage. `tests/fullio-isolated-unmute.py` checks the
exact closure, continuous triggers, zero digital monitor, live ambient
input, contiguous frame indices, receipt jitter/coverage and clipping.
Its broad time bracket allows for batching; pipe receipt is not an ADC
timestamp. Unit tests cover split reads, boundary placement, wrong
closure, changed trigger, a missing block and clipping.

On the exact frame-gate fixture the playback trigger stayed
`347.917556758`, capture `1450.464764819`. Muted the endpoint, set gain
and GainStep 30 while PCM was silent, waited four seconds, then submitted
only the unmute write. ACK interval was 3.24 ms. The 64 blocks in the
receipt-time event window had MicArray maximum 139 (S16 units), below
the nearby pre/post maxima 240/419; the monitor was exactly zero. No
near-event spike above background was observed in this one isolated
unmute. The comparator GainStep 26 was restored with ACK, and capture
was closed. Private logs: `isolated-unmute.87fRz5`. This neither tests
PA START nor rules out an intermittent crack, a combined transition,
or real-content clipping. Do not use it as the init-crack acceptance.

**One normal PA-start transient with the endpoint kept muted.** On the
same frame-gate one-shot, stopped the holder, proved frame-off before
iface gate, then opened only MicArray (`--mic-only --transient-blocks`).
Confirmed playback remained closed and the WSA bus suspended while the
MicArray was running. Then started one explicit `/dev/zero` player, no
other speaker links and no keeper, gain or unmute write. The kernel
verified DSP mute through GRAPH_PREPARE. The short-lived root-only trace
instance contained exactly one `wsa884x_fullio_start_pair` entry at
monotonic `1686.417290` and return 0 at `1686.526237`; playback reached
RUNNING (`1686.526252325`) and capture kept its previous trigger
`1681.943366781`. The instance and both trace events were removed.

Within the receipt-time window bracketing startup, the MicArray peaked
at 2867 S16 (~−21.2 dBFS), versus 108 and 115 in the flanking reference
windows. The first large block was received at `1686.611669`, the
second burst peaked at 1809 in blocks received at `1686.823859`.
These are **receipt** times (+85 and +298 ms after return), not ADC
sample times; they do not establish which specific write or event made
the transient. This one trial produces a start-associated MicArray
transient without endpoint unmute or program samples. It does not prove
speaker acoustic origin vs electrical pickup in the MicArray, explain
intermittency, or qualify init crack acceptance. Seek an independent
pickup before assigning the transient to the PA itself. Private
scalar/trace evidence: `muted-pa-start.GQAjLf`.

A separate MicArray-only no-render control (`pa-no-render.uWRxub`) had
1,329 contiguous blocks with playback closed and one capture trigger.
Its matched receipt window peaked at 102; the largest ambient peak
anywhere in the control was 935. This argues against an obligatory
MicArray-only startup sound at this offset, but does not exclude
start-induced electrical coupling. Both PCMs subsequently closed,
keeper/holder inactive, SSH/greetd active; no speaker-start retry.

### Independent recording preflight

The Mac AVFoundation/FFmpeg capture frontend lost 0.725 s of packets
in a 6 s silent-device preflight even with an enlarged input queue.
`swiftc -swift-version 5 scripts/fullio-mac-capture.swift -o CAPTURE`
uses AVAudioEngine and records the first packet wall time plus sample
clock continuity. In an 8 s and a 12 s quiet-room preflight the native
44.1 kHz input was nonzero, unclipped and contiguous. A 24 s run had
zero gaps but was rejected for overload; do not promote it. Run
`CAPTURE NEW_PRIVATE_CAF SECONDS` in a private directory; use
`ffmpeg -i CAF -c:a copy -f nut NUT` and pass `firstWall` from the capture
log to `tests/fullio-init-transient.py --first-wall`. This only qualifies
the instrument; actual audio startup still requires a clean capture
bracketing initialization and separately logged unmute.

## Decisive 0 dB fade localization (2026-11-25/26)

**The fade is real acoustic output loss, not a capture artifact.** On the
frame-stop/link-gate one-shot (`dxghbxi490m4z0pxl79g6syq1ir68brr`, kernel
byte-identical to the PA-cache candidate, Gen26 default and Gen20 recovery
verified before staging) a 360 s fixed-tone replay at 0 dB / GainStep 30 was
recorded simultaneously by the Surface MicArray and by an independent Mac
CoreAudio microphone (`scripts/fullio-mac-capture.swift`, sample-accurate
`firstWall`, no gaps).

Both recorders show the same progressive fall from the same onset:

| offset | Mac independent (dB) | Surface MicArray (dB) |
| --- | --- | --- |
| 60–90 s | 37…44 | −24 |
| 120–180 s | 21…30 | −24 |
| 210 s | 10…20 | −36 |
| 240–390 s | −8…−18 | −52…−70 |

The digital sink monitor stayed flat, ALSA `hw_ptr` advanced at 48 kHz, and
the graph was not reopened during the measured window. `tests/fullio-external-vs-surface.py`
reproduces the aligned trend; `scripts/fullio-external-levels.py --first-wall`
turns the independent capture into scalar time series without storing PCM.

The comparison tool now accepts separate `--external-start` and
`--surface-start` edges; an external sample-derived wall timestamp is not
comparable directly to Surface monotonic time. It rejects a clipped,
zero-lane, incomplete, duplicate, or gapped selected interval. A re-audit
of the historical independent log found one saturated second at
23:43:23.567; the full run does not pass the strict capture gate. A
separately reported **diagnostic excerpt**, from 23:43:25.644 for 240 s
(external `1795621405.644`, Surface `1143.146`), spans the transition
without that second. At 200 s into this excerpt the four measured bands
are down 48–53 dB on the independent recorder and 39–47 dB on MicArray,
while the pre-DSP monitor measurements differ by at most 0.01 dB in that
block. Together these observations corroborate a physical output drop
in the old run, not a MicArray-only artifact. This excerpt is neither an
acceptance run nor new evidence about startup crack origin.

**WSA gain registers do not change during the fade.** A targeted, sparse
regmap sampler (`denali-gain-state.py`, no writes, no PM wake) read both
devices every 5 s across a separate 300 s 0 dB run in which the mic fell
~12 dB. Every sample was identical before, during and after:

- `WSA884X_PA_FSM_STA0 = 0x2f`, `ERR0/ERR1 = 0`, `PDM_WD_CTL = 0x01`
- `WSA884X_DRE_CTL_0 = 0xf0`, `WSA884X_DRE_CTL_1 = 0x0e` (live, volatile)
- WSA macro `RX0/RX1 PATH_CTL = 0x24`, `VOL_CTL = 0xfd` (−3 dB),
  `MIX_CTL = 0x04`, `MIX_VOL = 0x00`

This rules out a PA FSM fault/cutoff, DRE gain drift, and any host write to
the macro RX digital volume/mute as the cause. Combined with the flat PipeWire
monitor, the attenuation is inside the AudioReach graph (VOL_CTRL / SP
protection / compander) or in analog behavior that leaves these registers
unchanged. Do not claim which without a live DSP gain/VI-CPS readback.

### Next discriminator: level dependence

A thermal/protection derating is level- and duration-dependent; a DSP logic
fault is not. `tests/fullio-level-stimulus.py --peak N` now scales the fixed
stimulus; `tests/fullio-level-replay.sh` honours `STIMULUS_PEAK`. Compare
fade onset at the default peak (3477 counts) against a 12 dB lower peak
(1152) on the same graph. Lower-level survival points at load/thermal/power;
identical fade points at DSP state. Neither result authorizes a gain or
protection change.

### Level dependence confirms load-driven DSP derating

Same graph (trigger `107.329737908`), same 300 s duration, same four
resolved tags, only the fixed stimulus peak changed:

| stimulus peak | Surface mic transfer over 300 s | result |
| --- | --- | --- |
| 3477 counts (default) | −23.5 dB flat to 240 s, then −35.6 dB | fade reproduced |
| 1152 counts (−9.6 dB) | −23.8 → −24.0 dB, no fade | stable |

`WSA884X_DRE_CTL_1 = 0x0e` and macro `RX VOL_CTL = 0xfd` were constant in
both runs (66 samples in the low-level run). A protection/derating model
that integrates delivered power predicts exactly this: a 9.6 dB lower drive
pushes the threshold out by roughly an order of magnitude in time, so no
fade inside the same window. A DSP control-logic bug would fade at any level.

This does **not** yet tell whether the derating is correct protection or a
fault. The remaining discriminator is the AudioReach SP/VI/CPS feedback
path: if the SP module receives absent or invalid VI/CPS frames it may ramp
toward maximum attenuation instead of holding gain. Earlier PA-off
diagnostics never proved live VI/CPS samples; do not infer them from TX
clock-enable bits or from logger configuration readbacks. Verifying live
feedback during a *played* graph is the next step, and must not reuse the
PA-off-only DIAG collector as if it were an RX0 audio proof.

### Duplex requirement: the fade needs the MicArray open

Repeating the identical 300 s, peak-4608 stimulus while the MicArray was
**fully closed** (probe stopped, `/proc/asound/card0/pcm2c/sub0/status == closed`,
only the silent holder connected), measured with the independent Mac
recorder only:

| condition | independent acoustic level over 300 s |
| --- | --- |
| MicArray open (duplex) | 37…44 dB, then falls (see table above) |
| MicArray closed | 37.87 → 37.65 dB (0.2 dB drift) — **no fade** |

So the attenuation requires simultaneous capture and playback. It is not
inherent to the render path and not caused by the tone alone.

A clock-tree diff taken with the MicArray closed versus open (`clk-mic-closed.txt`
vs `clk-mic-open.txt`) is **identical**: `fsgen` 19.2 MHz enable_count 4,
`WSA_CORE_TX_MCLK` 19.2 MHz count 2 with `mclk` 9.6 MHz, `TX_CORE_MCLK`
count 3. No shared-clock enable or rate change explains the fade.

**Current localization:** real, level-dependent acoustic loss that appears
only while a capture graph is active, with all WSA codec/macro gain registers
and LPASS clocks unchanged. The remaining candidates are inside AudioReach
on the ADSP: shared graph heap/cycle pressure, the SP protection module's
VI/CPS feedback being invalid or zeroed when duplex runs, or a shared module
(PCM_CNV/MFC) misbehaving under concurrent graphs. Do not raise DSP or PA
gain, and do not disable protection, to mask this.

### Concrete next step

Verify live VI/CPS feedback *during played duplex audio* and compare the SP
module's live master gain (`0x4a63/0x08001035`, already readable via
`q6apm_fullio_verify_gain_bounds`) with capture open versus closed. If the SP
gain ramps down only when the capture graph is present, the fault is the
protection consumer reacting to absent/invalid feedback rather than a real
excursion/thermal event. Any such readback is diagnostic only: it must not
write, retry, or relax the fail-closed admission and PA lifecycle.

### Duplex requirement confirmed (600 s control)

The earlier "MicArray closed → no fade" run was only 300 s and therefore
inconclusive against an onset of 210–300 s. A full 600 s run with the
MicArray **closed the whole time**, peak 4608 stimulus, 0 dB endpoint,
measured only by the independent Mac recorder, was completely stable:

```
 150s  [37.04, 40.07, 28.08, 35.37]
 ...
 570s  [36.94, 40.06, 27.60, 35.20]
 600s  (tone ended)
```

(0.1 dB drift over seven minutes.) Together with three mic-open runs that
all faded between 210 s and 300 s, the fade now requires **an active capture
graph**. A 300 s run in which the mic was closed at t=245 s stayed healthy
until the (stale 300 s) stimulus ended, consistent with the capture path
being the trigger rather than playback time alone.

Test-infrastructure defect fixed along the way: `tests/fullio-level-stimulus.py`
creates its output exclusively, so a stale shorter probe was silently reused
by `denali-micdrop.sh`. It now takes `--force`, and the runner deletes old
probe files first. Never replay a probe of unknown duration.

**Refined root-cause statement:** progressive/abrupt acoustic output loss
that appears only while a capture graph runs alongside protected render,
gets stronger at higher render level, and leaves every WSA codec/macro gain
register and every LPASS clock unchanged. This is an AudioReach/ADSP duplex
interaction in the protected render graph — most plausibly the SP protection
consumer seeing invalid VI/CPS feedback while capture is resident — not a
host volume, PA, DRE or clock problem.

### Next step

Inspect the v19c merged topology for any module/IID/port shared between the
capture graph (FE `MultiMedia3`, high graph-object namespace `0xb0000203` /
`0xe0000203`) and the protected render graph's VI/CPS consumers
(`0x4026→0x4025→0x4024` and `0x402b→0x402a→0x4029→0x4028`). The 2026-08-26
checkpoint fixed an instance-ID alias at that boundary; verify the compiled
`X1E80100-…-FullIO-v19c0-tplg.bin` in use has disjoint allocations and that
the SP module's VI/CPS input ports stay bound when graph 2 opens. Then read
the SP master gain (`0x4a63/0x08001035`) with capture open versus closed
during playback. Any fix must keep the fail-closed PA lifecycle, the −3 dB
comparator and protection admission unchanged.

### The trigger is the DMIC actually capturing, not the capture graph

Topology is not the problem: the installed topology is the pinned v19c
artifact (`e7bb06a03e7bd9b869825a51775355a6743477d1579d78eb09fad5881cfb20f0`),
and a full inventory of every widget shows graph 0 (render, 29 modules),
graph 2 (capture FE, 5 modules) and graph 120 (capture BE, 2 modules) with
**no cross-graph IID collisions**. The 2026-08-26 instance-ID fix holds.

A raw `arecord -D hw:0,2` opens the capture PCM and instantiates the capture
graphs, but captures **peak 96 / RMS 21** — the MicArray is not UCM-routed, so
the DMIC is not actually active. With that as the only capture client the
600 s probe stayed at 36.9 dB. That was not a fair "capture graph" control.

Applying `api.alsa.disable-mmap` to the MicArray capture node (verified
`access: RW_INTERLEAVED`, mic peak nonzero, so actually routed) did **not**
help: the 600 s probe faded from ~240 s and reached −8 dB by 600 s. So the
ALSA access mode (MMAP versus RW) is not the trigger either.

Therefore the fade requires the **DMIC hardware path to be active** — the
VA/TX macro DMIC clock-and-divider path that `lpass-micarray.patch` wires
through `lpass_macro_dmic_clk_request()` → `va_dmic_clk_enable()`, which is
the only new code path that runs when capture begins. A full `clk_summary`
diff between capture-active and capture-idle showed **only GPU clocks**
differing; no LPASS audio clock enable or rate changed.

Remaining candidates, in order:
1. `va_dmic_clk_enable()` / the shared DMIC divider disturbs state the WSA
   render path depends on without showing in `clk_summary`.
2. The AudioReach SP protection consumer (`0x4027`) sees invalid VI/CPS
   while the capture graph is resident and ramps the render gain down. This
   fits the level dependence and the ~200–300 s integrator.
3. A DSP shared-resource (heap/cycle) effect only under both graphs.

Discriminate with a live read of the SP master gain
(`0x4a63/0x08001035`) during the fade: if it falls, the fault is (2) and the
fix belongs to the VI/CPS feedback binding or the SP gain policy; if it stays
at unity, look at (1)/(3). No such userspace readback exists today (the three
`SP11 Windows …` controls are write-only), so it needs a small gated,
read-only addition. Do not weaken the fail-closed PA lifecycle, protection
admission or the −3 dB comparator while doing it.

### Register sweep during the fade

A full dump of all three register spaces (WSA macro, both WSA884x codecs)
taken before and 340 s into a 400 s 0 dB replay with the MicArray active
shows **no digital gain change anywhere**:

- `WSA884X_DRE_CTL_1 = 0x0e`, `PA_FSM_STA0 = 0x2f`, error bits 0
- macro `RX0/RX1 PATH_CTL = 0x24`, `VOL_CTL = 0xfd`, `MIX_CTL = 0x04`
- macro `TX0..TX3 SPKR_PROT_PATH_CTL = 0x10` — the VI/CPS feedback clock
  enable bit (bit 4) stays **on** for the whole fade

The only differing bytes are in the WSA884x analog sensor/ADC block
(`WSA884X_VBAT_SNS` region `0x3015/0x3016`, and the `TEMP_DIN/TEMP_DOUT`
and `VBAT_DIN/VBAT_CAL` LSB bytes at `0x3453/0x3455/0x345b/0x345f`). A
follow-up 1 s sampling shows those LSB bytes jump between consecutive reads,
so they are conversion-phase noise, not a measured trend. The MSBs
(`TEMP_*_MSB`, `VBAT_*_MSB`) are stable. **No conclusion about thermal or
VBAT derating is justified from these bytes.** They are not evidence of a
temperature rise or supply sag.

What is now certain: the attenuation is not in any host-visible digital gain
control, not in the PA FSM, not in the VI/CPS feedback clock enable, and not
in a LPASS clock. It is inside AudioReach on the ADSP (or analog behavior
that leaves every readable register unchanged), and it is triggered by the
DMIC hardware path being active.

The remaining discriminating measurement is a live read of the protected
graph's gain state during the fade. The final VOL_CTRL is `0x4a63` with
`0x08001035` (master gain, Q13) and `0x08001038/0x08001039` (final gain/mute);
`q6apm_fullio_get_cfg()` already validates exactly `0x4a63/0x08001035`. The
three `SP11 Windows …` ALSA controls are write-only, so a small gated,
read-only accessor is required. Read it with the MicArray open versus closed
during playback: a ramp-down localises the fault to the SP/VOL_CTRL consumer
(and points at the VI/CPS feedback binding when capture is resident); a
steady unity gain moves the search to the WSA analog/transport side.

### Codec-DMA interface sharing is the next concrete check

All three feedback/capture endpoints use the same AudioReach module class
`0x07001024` (codec DMA): render VI `0x4026`, render CPS `0x402b`, and the
capture backend `device120.codec_dma_tx1` (`0x6090`, graph 120). The
static endpoint configurations in the pinned topology are:

| endpoint | EP_MEDIA (rate, bits) | EP_INTF |
| --- | --- | --- |
| `0x4157` speaker RX0 | 48000, 16 | (2, **1**, 3) |
| `0x4026` WSA VI | 8000, 32 | (2, **1**, 3) |
| `0x402b` WSA CPS | 24000, 32 | (2, **3**, 3) |

The capture backend `0x6090` has **no static EP_INTF frame anywhere in the
topology** — its codec-DMA interface is chosen at run time when graph 120
opens. If that runtime assignment lands on interface 1 or 3 it would compete
with the VI/CPS feedback lanes, which is exactly the shape of this bug: the
feedback becomes invalid only while the capture graph is resident, the SP
consumer then ramps the render gain down over a couple of minutes, and every
WSA/PA/clock register stays unchanged.

Next action: read the runtime codec-DMA interface/SID assigned to `0x6090`
while capture is active and compare it with `0x4026`/`0x402b`. If they
collide, the fix is a disjoint interface allocation for the capture backend
(analogous to the 2026-08-26 graph-object IID split), keeping the VI/CPS
lanes exclusively owned by the protected render graph. If they are already
disjoint, fall back to a live SP gain readback (`0x4a63/0x08001035`) to
decide between DSP gain ramp and analog behaviour.

### Static topology confirms the interface split, capture side is dynamic

Raw scan of the pinned topology finds exactly three `PARAM_ID_CODEC_DMA_INTF_CFG`
frames:

```
0x4026  (VI)   (2, 1, 3)   WSA codec-DMA type, interface 1, both DMA slots
0x402b  (CPS)  (2, 3, 3)   WSA codec-DMA type, interface 3, both DMA slots
0x4157  (RX)   (2, 1, 3)   WSA codec-DMA type, interface 1, both DMA slots
```

RX and VI intentionally share WSA interface 1 in opposite directions; CPS
owns interface 3. The capture widgets (`device120.codec_dma_tx1`,
`device120.logger1`, `stream2.rdsh_ep1`) carry **only widget tuples and no
calibration frames at all**, so the capture backend's codec-DMA interface is
chosen when `MultiMedia3 Capture` opens, not by the static topology. That is
the one allocation this investigation has not yet observed.

It must be checked before any fix: a capture backend landing on WSA interface
1 or 3 would corrupt the VI/CPS feedback while capture is resident and would
explain every observation (mic-dependent, level-dependent, delay, no
register/clock change). Obtain it from the live DSP/graph configuration —
the kernel already sends `PARAM_ID_CODEC_DMA_INTF_CFG` for the render path
and validates it in `q6apm_fullio_verify_sink()`; expose the equivalent
read-only value for the capture graph, or read the LPASS codec-DMA interface
registers while capture is active. Keep it strictly read-only.

### Configured Codec-DMA interfaces are disjoint

Decoding the topology module tokens (`snd_ar_tokens.h`:
`AR_TKN_U32_MODULE_HW_IF_IDX = 250`, `HW_IF_TYPE = 251`) against the
`PARAM_ID_CODEC_DMA_INTF_CFG` semantics in `audioreach.h`:

```
lpaif_type: 1=RXTX  2=WSA  3=VA  4=AXI
intf_index: RX0|TX0=1, RX1|TX1=2, RX2|TX2=3, ...
```

| endpoint | lpaif_type | intf_index | peripheral |
| --- | --- | --- | --- |
| `0x4157` speaker RX | 2 (WSA) | 1 | WSA RX0/TX0 |
| `0x4026` VI feedback | 2 (WSA) | 1 | WSA TX0 (shares WSA pair 1 with RX, opposite direction) |
| `0x402b` CPS feedback | 2 (WSA) | 3 | WSA TX2 |
| `0x6090` capture BE | 1 (RXTX) | 4 | RXTX TX4/RX4 |

The pinned capture token is not just a static label: in the composed
Next24 source, `q6dma_hw_params()` prepares ordinary capture media and
`audioreach_codec_dma_set_media_format()` emits `lpaif_type` and
`intf_index` directly from that capture module's topology tokens. The
active channel mask is formed separately from the nonzero `channel_map`
positions; neither the default capture channel map nor its bit width
reassigns the peripheral or interface index. This rules out identical
**host-configured** interfaces, not hidden DSP slot aliasing or a hardware
routing defect. The generic capture serializer is not evidence of the
internal layout of the protected graph's VI input.

The independent recording confirms acoustic loss, and subsequent unity
readbacks exclude changes to the measured VOL_CTRL settings. Static SP
calibration readback does not measure the processor's time-varying gain.
The reference's `2026-08-14-existing-windows-protection-telemetry-corpus.md`
also rules out reusing its historical TMax/XMax query as a live substitute:
`0x4027/0x080011f2` has Windows outbound request records, not saved successful
response samples. The exact Linux query already returned command/module
failure with a zero-filled body. Do not interpret that body as zero
excursion, poll the same unsupported parameter, or alter gain based on it.
The first divergent signal is still unobserved: a qualified post-SP DSP
measurement or a downstream output measurement is needed to distinguish
DSP attenuation from output-stage behavior. Do not reallocate interfaces,
edit the VI map or compensate with gain on this evidence.

### Thermal and supply derating ruled out

A 400 s 0 dB replay with the MicArray active sampled the WSA884x
temperature and battery ADCs every 2 s alongside the acoustic probe. The
fade reproduced fast this time (mic fell from −59.8 to −78 dB within 50 s
and stayed there) while the PipeWire monitor stayed exactly −31.08 dBFS
throughout. The sensor registers were **flat for the entire run**:

```
t(s)  TEMP_DIN  TEMP_DOUT  VBAT_DIN  VBAT_CAL
  0    27904     27904      49344     49792
...
400    27904     27904      49344     49792
```

TEMP is bit-identical for 400 s and VBAT_DIN varies only ±64 counts of
conversion noise around 49344. There is **no temperature rise and no supply
sag**. Combined with the earlier full register sweep (no digital gain, PA,
DRE, RX/TX or interface change) this removes thermal protection and
VBAT/BCL derating from the candidate list.

The fade onset is also variable across runs: 50 s here, 150–300 s earlier.
It is not a fixed timer.

**Conclusion: the attenuation is generated inside AudioReach on the ADSP.**
Every readable hardware/control register stays constant while the acoustic
output falls by 18–45 dB. The only remaining discriminator is a live read
of the protected graph's own gain state (`0x4a63/0x08001035`, and ideally the
SP module's state) with capture open versus closed. That requires the small
gated read-only accessor; it is now the single blocking measurement.

### Live DSP gain readback: VOL_CTRL holds unity while output falls

The gated read-only accessor (`snd_q6apm.fullio_gain_audit`, admin-only
`/sys/.../gprsvc:service:2:1/fullio_master_gain`) was implemented, built
natively and booted once
(`rsfl55dvjahgm3pvl7id8399l5lhg0va-nixos-system-surface-26.11.20261124.52a9386`,
Gen26 default and Gen20 recovery verified before staging). It reports the
protected graph's own `PARAM_ID_VOL_CTRL_MASTER_GAIN` (`0x4a63/0x08001035`,
Q13) and performs exactly one bounded 4-byte `GET_CFG` per read.

During a 400 s 0 dB replay with the MicArray active, all **214** samples read
`q13=0x2000 reserved=0x0` — Q13 unity, unchanged — while the acoustic
transfer fell from −25 dB to −73 dB. So the final DSP volume stage is not
the attenuator.

**Graph order is the reason.** Decoding the 26 render edges from the pinned
topology gives the data chain:

```
0x4660 pull → 0x465c log → 0x465f pcm_cnv → 0x4663 vol → 0x4662 swr_sink
→ 0x4664 EQ → 0x4669 vol → 0x466a mfc → 0x466b soft_pause → 0x412b spr
→ 0x47e9 log → 0x4a63 VOL_CTRL  → 0x4675 swr_sink → 0x489e/0x48a1 MSIIR
→ 0x467a log → 0x4001 SAL → 0x402c CHMIXER → 0x4027 SPEAKER_PROTECTION
→ 0x4002 splitter → 0x4003 log → 0x4157 codec_dma_sink
```

`0x4027` (AudioReach speaker protection) sits **downstream of the final
VOL_CTRL**, immediately before the DAC sink. Its internal attenuation is
invisible to every readback taken so far and to every WSA/PA register. It is
also exactly the module class that is level-dependent and consumes the
VI/CPS feedback (`0x4026 → 0x4025 → 0x4024` and `0x402b → 0x402a → 0x4029 →
0x4028`), which would explain the capture-dependence.

**Refined root cause:** the AudioReach speaker-protection module attenuates
the render output when the capture graph is resident, most plausibly because
its VI/CPS feedback becomes invalid/absent in that condition, so it ramps
toward maximum protection. Not host volume, not VOL_CTRL, not PA/DRE/clock,
not thermal, not VBAT.

Next: observe the SP/VI feedback state while the fade is active. The
existing `GET_CFG` allowlist already permits `0x4027/0x080011e8` (68 bytes)
and `0x4024/0x080011f6` (44 bytes); extend the accessor to dump them and
compare capture-open versus capture-closed. If they are static while the
output falls, the decision is inside the SP's protection algorithm and the
fix belongs to the VI/CPS feedback delivery, not to any gain setting. Do not
disable speaker protection or raise gain to mask it.

### SP/SPVI/SAL configuration is unchanged during the fade

The accessor was extended to hash the speaker-protection, SP-VI and SAL
configurations through the already allow-listed `GET_CFG` payloads, and to
read the SAL limiter configuration. On
`2aar4wzk9s5n7c9if7d96887sn4l6h56-nixos-system-surface-26.11.20261124.52a9386`
(Gen26 default and Gen20 recovery verified before staging) a 400 s 0 dB
replay with the MicArray active produced **210 identical readings**:

```
vol=0x2000,0x0  sp=0xcadd338e  spvi=0xaa318ee5  sal=0x8c61
```

while the acoustic transfer fell from −24.6 to −48.8 dB. Every stage between
the final volume control and the DAC sink — the SP protection config, the
SP-VI config and the SAL limiter config — is byte-identical throughout.

**Root cause, stated as narrowly as the evidence allows:** a dynamic
attenuation generated inside the AudioReach render chain downstream of
`0x4a63` (VOL_CTRL), driven by the SP protection consumer's VI/CPS inputs,
appears only while the MicArray capture graph is resident and scales with
render level. It is not a host volume change, a VOL_CTRL change, a PA/DRE
change, an LPASS clock change, a codec-DMA interface collision, a thermal
limit or a VBAT sag, and it is not a rewritten module configuration.

The fix therefore belongs to the VI/CPS feedback delivery into `0x4027`
while a capture graph is resident, or to the SP's handling of absent/invalid
feedback — **not** to any gain value. Disabling speaker protection, raising
gain or periodically re-asserting the endpoint transaction would mask the
fault and is not acceptable.

Remaining work to a fix: determine why the VI/CPS inputs
(`0x4026 → 0x4025 → 0x4024`, `0x402b → 0x402a → 0x4029 → 0x4028`) go bad
only when capture is resident — e.g. capture-stale DMA, a shared DSP
resource or an uninitialised feedback stream — then correct that delivery
and rerun the 0 dB reproduction plus the full regression. No fix, no
reproduction pass and no strict regression pass is claimed yet.

### All three volume stages hold unity; the fade is low-frequency heavy

The accessor was extended to the two upstream `vol_ctrl` modules as well as
the final one. On `fk84rin12cf60psif6cf53gpbw396bc2-nixos-system-surface-26.11.20261124.52a9386`
(Gen26 default and Gen20 recovery verified before staging) a 400 s 0 dB
replay with the MicArray active produced **210 identical readings**:

```
vol=0x2000,0x0  sp=0xcadd338e  spvi=0xaa318ee5  sal=0x8c61  vol1=0x8820  vol2=0x8820
```

`0x4a63`, `0x4663` and `0x4669` are all Q13 unity (`0x2000`, CRC `0x8820`)
for the whole run. The acoustic transfer still fell −24.6 → −37.1 dB.

The fall is **not spectrally flat**:

| tag | before | after | change |
| --- | --- | --- | --- |
| 449 Hz | −24.58 | −36.54 | −11.96 dB |
| 454 Hz | −22.59 | −34.49 | −11.90 dB |
| 1009 Hz | −15.91 | −24.12 | −8.21 dB |
| 1017 Hz | −26.82 | −34.71 | −7.89 dB |

Low-frequency loss is ~4 dB larger than high-frequency loss. That is the
signature of **cone-excursion protection**, not a flat gain stage, a digital
mute or a codec volume register. It strongly favours the AudioReach
speaker-protection module (`0x4027`) acting on its VI feedback over the
equalizer, soft-pause, MSIIR, SAL or channel mixer.

So the working root cause is: the speaker-protection module over-attenuates
in a low-frequency-weighted, level-dependent way while the MicArray capture
graph is resident, because its VI (Vsense/Isense) feedback becomes invalid
or absent under that condition. Every gain/config register in the DSP and
in the WSA hardware stays constant, which is consistent with protection
running on bad feedback rather than with a control being changed.

To fix it, verify the VI feedback delivery into `0x4024` while capture is
resident (the codec-DMA lanes, the SP-VI calibration/R0-T0 selection, and
the `0x4025` tap between `0x4026` and `0x4024`) and correct that delivery.
Do **not** disable the excursion protection, raise the level or change the
GainStep ceiling to hide it. No fix, reproduction pass or strict regression
pass is claimed.

### The capture graph's start triggers the fade, ~60–120 s later

A timing experiment played the fixed 0 dB stimulus for 600 s with the
MicArray **closed for the first 180 s** and opened only afterwards. The
independent Mac recorder shows the switch unambiguously:

```
  0..150s  MIC_CLOSED  449 Hz ≈ 35.3 dB   (flat)
 180s      MIC_OPEN    35.41
 210s      MIC_OPEN    35.38
 240s      MIC_OPEN    33.20             (60 s after open: onset)
 270s      MIC_OPEN     5.45
 300s      MIC_OPEN    -9.91             (120 s after open)
 330s..    MIC_OPEN   ≈ -11 dB           (stabilised)
```

With the mic closed for 180 s the output never moved; once capture started,
the fall began about **60 s later**, deepened for another ~60 s and then
held. So the trigger is the capture graph **starting**, not elapsed playback
time, and the delay is an estimator/integrator, not a timer.

Combined with the earlier results this is now:

- capture graph resident **and** render level high → low-frequency-weighted
  acoustic loss of 12–48 dB;
- every readable gain/config register constant (three VOL_CTRL stages,
  SP/SPVI/SAL configs, WSA DRE/RX/TX/PA, LPASS clocks, codec-DMA mapping,
  temperature and VBAT);
- independent Mac and Surface microphones agree;
- reopening the playback graph resets it.

This is the AudioReach speaker-protection consumer ramping on bad/absent VI
feedback roughly a minute after capture begins. The fix is in the VI
feedback delivery into `0x4024`/`0x4027` while a capture graph is resident —
for example a codec-DMA lane, buffer or calibration path shared with, or
disturbed by, the capture side. Disabling excursion protection or raising
gain to hide it is not acceptable.

To close the fix: identify the exact VI/CPS lane or buffer that degrades at
capture start, correct it, then rerun this 180 s timing experiment (fade
must not appear), the 600 s 0 dB reproduction, and the strict regression.

### Capture start changes no WSA configuration register

A targeted before/after sweep dumped all three register spaces (WSA macro and
both WSA884x codecs) immediately before and 4 s after the MicArray capture
started, with playback already held. The only differing bytes were the
already-established VBAT/temperature ADC LSBs (`0x3016`, `0x345a/0x345d/
0x345f`) — conversion noise. **No TX path, RX path, DRE, PA, compander or
clock register changes when capture begins.** So the capture graph's effect
is not a WSA reconfiguration; it is either DSP-internal or analog coupling
that leaves every readable register unchanged.

For completeness, the capture backend's codec-DMA declaration decodes as
`AR_TKN_U32_MODULE_HW_IF_TYPE = 1 (LPAIF_RXTX)`, `HW_IF_IDX = 4` — RXTX
pair 4 (`snd_ar_tokens.h`: 0=LPAIF, 1=RXTX, 2=WSA, 3=VA, 4=AXI). The speaker
feedback runs on WSA pairs 1 and 3, so the two are disjoint on paper. That
is the one remaining static claim this investigation has not confirmed at
run time: whether RXTX pair 4 is the correct codec-DMA lane for the Denali
DMIC array, and whether activating it disturbs the WSA TX lanes that carry
VI/CPS.

**Next concrete step:** confirm the actual LPASS codec-DMA lane used by the
MicArray at run time and compare it with the WSA VI/CPS lanes while capture
is active. If RXTX pair 4 is wrong or overlaps a shared DMA resource, the
fix is a disjoint lane assignment for the capture backend; if the lanes are
truly disjoint and clean, the remaining discriminator is the VI sample
content delivered to `0x4024`, which needs a validated live tap and must not
reuse the PA-off-only DIAG collector. No fix has been implemented yet.

### Topology stream names confirm disjoint codec-DMA peripherals

The pinned v19c reference configuration names the endpoints explicitly:

- render: `WSA_CODEC_DMA_RX_0 Playback`, mixer `MultiMedia1`
- capture: `TX_CODEC_DMA_TX_3 Capture`, mixer `TX_CODEC_DMA_TX_3`

So playback and capture use **different LPASS codec-DMA blocks** (WSA RX0
versus TX3), matching the earlier token decode (WSA pair 1/3 versus RXTX
pair 4). The VI/CPS feedback occupies WSA **TX0/TX2** on the same WSA block
as the render's **RX0**. That leaves one precise question: does starting the
TX3 capture disturb the WSA RX0/TX0 pair that simultaneously carries render
data and VI feedback?

The capture backend's token tuple is `HW_IF_TYPE=1 (LPAIF_RXTX)`,
`HW_IF_IDX=4`, `FMT_DATA=1`, while its named stream is `TX_CODEC_DMA_TX_3`.
Whether "pair 4" and "TX_3" denote the same physical lane has not been
checked against the LPASS hardware definition; a mismatch there would be a
concrete, fixable allocation error rather than a DSP-algorithm problem.

**Next action:** resolve the LPASS codec-DMA lane numbering (`TX_CODEC_DMA_TX_3`
versus `hw_interface_idx = 4`) from the SoC hardware description, and check
for a shared DMA channel/IRQ between TX3 and the WSA RX0/TX0 pair. If they
overlap, the fix is a disjoint lane for the capture backend and can be
verified by the 180 s timing experiment. If they are genuinely disjoint,
the remaining suspect is the adaptive VI calibration in `0x4024`, which
would need a validated live tap of the V/I samples during the 60 s ramp.

### AFE port IDs confirm the capture and feedback are on different hardware

Decoding `q6afe.c` gives the actual LPASS AFE port identifiers:

| path | AFE port | block |
| --- | --- | --- |
| render `WSA_CODEC_DMA_RX_0` | `0xB000` | WSA RX0 |
| VI `WSA_CODEC_DMA_TX_0` | `0xB001` | WSA TX0 |
| CPS `WSA_CODEC_DMA_TX_1` | `0xB003` | WSA TX1 |
| capture `TX_CODEC_DMA_TX_3` | `0xB037` | TX block TX3 |

The capture and the speaker feedback therefore occupy **different codec-DMA
blocks and distinct AFE ports**. There is no codec-DMA lane, AFE port or
static interface collision. Combined with the earlier findings this removes
resource-collision at the transport/mapping layer from the candidate list.

What remains is between the DSP and the amplifier sense lines:

1. **Analog coupling.** The DMIC PDM clock/data could couple into the WSA
   Vsense/Isense lines. The ~60 s delay fits an estimator integrating a
   slowly biased VI measurement; the low-frequency weighting fits excursion
   estimation; the absence of any register change fits a purely analog
   disturbance.
2. **DSP resource starvation of the SP's VI processing** when the capture
   graph runs. This would normally be immediate, not delayed by 60 s.
3. **Adaptive VI calibration** in `0x4024` converging to a wrong R0/T0 while
   capture is resident. Reopening the render graph resets it, which fits.

Discriminate (1) from (2)/(3) by capturing the VI samples delivered to
`0x4024` while the fade ramps: if the V/I waveforms themselves acquire a
bias/noise the capture correlates with, it is analog/transport; if they are
clean but the SP still attenuates, the fault is the SP's calibration or
protection policy and must be corrected there. That measurement needs a
validated live tap of the VI data and must not reuse the PA-off-only DIAG
collector. No fix is claimed.

### The captured microphone data, not the capture hardware, triggers the fade

The MicArray decimator gains (`VA_DEC0..3 Volume`, `TX_DEC0..1 Volume`, all
84 = 0 dB) were set to **0 (−84 dB)** so the capture graph, DMIC clock and
codec-DMA stayed live but carried only silence. With that, an independent
Mac recording of a 600 s 0 dB tone was **flat for the whole run**:

```
   0s  [35.18, 39.81, 25.21, 32.90]
  ...
 570s  [35.01, 39.70, 26.18, 32.97]
```

with only ~0.2 dB drift. The same run with live mic data faded 12–48 dB.
The capture PCM was confirmed `RUNNING` in both cases, so this is not "the
capture graph is closed".

This removes the analog-PDM-crosstalk and DSP-resource-starvation
hypotheses, which would persist regardless of the captured content. What
remains is a **routing/calibration coupling between the MicArray capture
data and the speaker-protection input**: the SP's excursion/thermal
estimate is being driven by something derived from the microphone signal.
That is exactly consistent with the observed shape — the mic picks up the
speakers, so the louder the render the more "excursion" the SP infers, and
the low frequencies dominate the room pickup.

**Next action:** find where microphone data reaches the protected render
path — a shared buffer, a module/IID alias between `0x6090` (capture
codec-DMA) / `0x6024` (capture rdsh endpoint) and `0x4024`/`0x4027` (SP-VI
and SP), or an incorrect VI channel map (`PARAM_ID_SP_VI_CHANNEL_MAP_CFG`,
`0x08001203`) that points at the capture lane. Because the effect scales
with the mic's captured content, compare the graph's static wiring first
(cheap, offline) before any live tap.

The MicArray decimator gains were restored to 84 after the test. No fix is
claimed; the reproduction and regression gates remain unmet.

### SP-VI channel-map discrepancy found in the pinned topology

The reference configuration's `sp11.speaker_protection_vi.4024:viep` block
settles the VI endpoint exactly:

```
0x4026  EP_MEDIA 0x08001017 : rate=8000, bits=32, num_channels=2, fmt=1
0x4026  EP_INTF  0x08001063 : lpaif_type=2 (WSA), intf_index=1, chan_mask=3
```

so the VI source delivers **2 channels** (Vsense/Isense pair) on WSA pair 1.
The SP-VI's own `PARAM_ID_SP_VI_CHANNEL_MAP_CFG` (`0x08001203`) however
declares `num_channels = 4` with `channel_mapping = [1, 2, 3, 4]`.

That 4-versus-2 discrepancy is the first concrete static inconsistency found
in the protected feedback path. If the SP-VI reads four sense channels from
a two-channel stream, its upper two channels come from whatever memory
follows the VI buffer — which is exactly the shape of a bug that would make
the protection consumer respond to unrelated data, including a capture
buffer that becomes populated only while the MicArray is running.

This is consistent with the live discriminator (muted mic data ⇒ no fade)
and with the observed low-frequency weighting and level scaling. It is not
yet proven to be the cause: the reference model may use `num_channels=4`
for two physical pairs in a way the endpoint format represents as 2.

**Next action:** resolve the SP-VI `num_channels`/`channel_mapping` semantics
against the reference model and the endpoint format. If it is a genuine
4-channel read from a 2-channel source, the fix is a correct VI channel map
or an explicitly sized VI buffer, and the 600 s 0 dB reproduction plus the
strict regression become the acceptance gates. If the semantics are
legitimate, the remaining leak is a shared/aliased buffer between the
capture graph (`0x6090`/`0x6024`) and `0x4024`/`0x4027`, which needs the
static wiring walk. Do not disable protection or change any gain to test it.

### Dose response: the microphone data level drives the attenuation

The MicArray decimator gain (`VA_DEC0..3`/`TX_DEC0..1`, normal value 84 =
0 dB) was run at three levels with the capture graph and DMIC clock held
live and the same 0 dB speaker stimulus. Measured independently by the Mac
recorder over 600 s:

| mic decimator | mic data | result |
| --- | --- | --- |
| 84 (0 dB) | normal | fades 12–48 dB (5 of 5 runs) |
| 40 (−44 dB) | 44 dB down | **flat**, 34.62 → 34.56 dB |
| 0 (−84 dB) | silent | **flat** (2 of 2 runs) |

The intermediate level rules out "setting the volume to zero disabled a DSP
path"; this is a genuine **dose effect on the captured data level**, not a
state change caused by the control.

Combined with the earlier evidence this is now:

- the speaker-protection consumer over-attenuates in a low-frequency
  weighted, level-dependent way;
- the attenuation is absent when the capture graph is closed;
- it is absent when the capture is active but its data is attenuated 44 dB;
- it is present whenever the capture carries real, full-level microphone
  data;
- no readable gain/config register changes at any point.

Because the MicArray picks up the speakers, its data level tracks the
speaker output; a leak of that data into `0x4024` (SP-VI) would make the
protection infer excursion from room pickup and attenuate accordingly,
which fits the observed shape and the ~60 s estimator ramp.

**Next action:** find the leak of capture data into the SP-VI input. Compare
the VI source `0x4026` per-frame byte count and DMA buffer length with the
SP-VI's per-frame read of four sense signals (`channel_map = [1,2,3,4]`),
and check for a shared/aliased buffer between `0x6090`/`0x6024` and
`0x4024`/`0x4027`. Both the pinned v19c and the cps-lab reference use the
same 2-channel VI endpoint with the 4-sense map, so resolve the semantics
before editing anything. Once the leak is corrected, the gates are the
600 s 0 dB reproduction (must stay flat with live mic data) and the strict
regression. Do not disable protection or alter any gain.

### Which decimator is muted does not matter — all mic data must be silenced

Complementary runs at 0 dB with the capture graph live, each 600 s,
measured by the Mac recorder:

| VA_DEC (52–55) | TX_DEC (35,36) | result |
| --- | --- | --- |
| 0 (muted) | 0 (muted) | flat (2 of 2) |
| 0 (muted) | 84 (normal) | **fades**, onset ~540 s |
| 84 (normal) | 0 (muted) | **fades**, onset ~150 s |
| 40 (−44 dB) | 40 (−44 dB) | flat |

So the earlier inference that the TX macro alone was implicated is wrong:
**either decimator carrying real microphone data is enough to trigger the
fade**; only silencing every mic path stops it. The trigger is the
capture data in aggregate, not one macro's stream.

The onset time remains variable across runs (150 s, 210 s, 240 s, 540 s),
which is consistent with an estimator reacting to the room pickup rather
than a fixed resource timer.

This narrows the defect to the coupling between **any live microphone
sample data** and the speaker-protection input. It is not a specific
codec-DMA lane, not the decimator's gain register, and not the capture
graph's existence. The plausible mechanisms remain:

- the SP-VI input buffer/stream is aliased or adjacent to capture data, so
  non-zero mic samples perturb the protection estimate;
- a shared DSP processing/buffer resource whose state is driven by the
  capture payload;
- an incorrect VI channel/buffer size that samples capture memory.

All mic decimators were restored to 84. No fix is claimed; the 600 s 0 dB
reproduction and strict regression gates remain unmet.

### External acoustic content makes the fade worse — the microphone's acoustic pickup is the driver

A loud 3 kHz tone played from the Mac speaker near the Surface microphone,
while the Surface played the usual 600 s 0 dB stimulus, produced a fade
that began earlier (~270–300 s instead of ~540 s) and was deeper (449 Hz
reaching −11 dB). The external tone was at a frequency outside the
measured stimulus bands, so it did not contaminate the measurement; it
changed only what the microphone captures.

This is consistent with the acoustic-coupling reading of the dose effect:
the microphone's picked-up sound, not the microphone gain control itself,
is what drives the speaker protection into over-attenuation. It is
supportive rather than conclusive (the recording is noisier with the
external source active), but it removes "the gain register has some other
side effect" as a plausible explanation.

Combined evidence for the coupling between live microphone sample data and
the speaker-protection input:

- microphone closed → flat 600 s
- microphone open, all mic decimators muted → flat 600 s (2 of 2)
- microphone open, decimators at −44 dB → flat 300 s
- microphone open, decimators at 0 dB → fades 8 of 8 runs
- louder external acoustic content near the microphone → earlier, deeper fade
- render ring and capture DMA are separately allocated
- no host-visible gain, config, clock, port or thermal change accompanies the fade

The exact route by which microphone samples reach the SP-VI input is still
unidentified; that is the remaining work before any fix.

### Cross-object instance-ID alias is ruled out

The 2026-08-26 FullIO v19c checkpoint records a prior microphone-collision
defect: the capture graph's subgraph/container IDs aliased a protected
render module IID, so SPF rejected graph 2 whenever the Golden render was
resident. That fix moved capture graph-object IDs into disjoint high
namespaces and added a builder collision gate.

Checked against the current reviewed structural model and the capture
module set used at runtime:

- render subgraph IDs `0xb0000001`, `0xb000007e`, `0xb000007f`
- render container IDs `0xe0000001`, `0xe0000005`, `0xe0000006`,
  `0xe0000007`, `0xe000004c`, `0xe0000066`, `0xe0000114`
- capture module IIDs `0x6020`–`0x6024`, `0x6090`, `0x6091`
- capture graph objects `0xB0000203`, `0xE0000203`, `0xB0000209`, `0xE0000209`

Render subgraph ∩ capture IIDs = empty; render container ∩ capture IIDs =
empty; capture graph objects ∩ render IIDs = empty. The four cross-class
sets are disjoint, so the historical alias is not the present defect.

Combined with the earlier graph-0/2/120 IID inventory (no cross-graph IID
collision), this closes the object-ID-family explanations for the
microphone-to-protection coupling. The remaining candidates are data-plane
aliasing (VI input buffer/stream sharing capture payload), incorrect VI
channel/buffer sizing, or a DSP processing resource whose state is driven
by the capture payload.

### The protection consumer is a vendor module, not the stock SPR

Crash-artifact text identifies the SP stage as `graph0, iid: 0x4027,
mid: 0x10007, module: msPP`, i.e. a Microsoft protection-processor module,
while `0x412b` in the render chain is the stock AudioReach SPR. The
engine tree at `fwk/spf/modules/spr` implements only the stock SPR
(single physical input port, internal circular buffer, path-delay and
av-sync helpers); the `msPP` stage that consumes the VI and CPS streams
has no source here.

Consequences for the remaining investigation:

- the VI/CPS data-plane semantics cannot be settled from the stock SPR
  code; the coupling lives in `msPP` or in how the VI stream is presented
  to it;
- the static channel-map question (`SP_VI_CHANNEL_MAP_CFG` declares
  `num_channels=4` against a 2-channel VI endpoint) must be answered
  against `msPP`'s contract, not against `cps-lab-topology.conf`, since
  the two agree with each other and both are Windows-derived.

Next decisive steps, in order:

1. runtime VI configuration readback — extend the read-only allowlist to
   the VI source `0x4026` `EP_MEDIA`/`EP_INTF` and compare with the
   topology values, to prove which codec-DMA channel the DSP actually
   binds for the VI;
2. if the binding is correct, the defect is data-plane aliasing inside
   `msPP`'s input presentation, which needs a live VI sample tap or a
   bounded per-frame checksum to confirm;
3. only after the route is proven should any VI channel-map or buffer
   sizing be changed.

### Runtime VI source configuration is not readable

The read-only allowlist was extended to the VI source `0x4026`
`EP_MEDIA` (`0x08001017`) and `EP_INTF` (`0x08001063`), keeping the
accessor admin-only, read-only, no write, no retry and no wake. On the
one-shot diagnostic kernel the snapshot reports:

```text
vol=0x2000,0x0 sp=0xcadd338e spvi=0xaa318ee5 sal=0x8c61 vol1=0x8820 vol2=0x8820 vimedia=err-5 viintf=err-5
```

Every other allow-listed object reads back normally, including the
render's codec-DMA sink `0x4157`, but the VI source returns `-EIO` for
both endpoint parameters. So the DSP does not serve the VI source's
endpoint configuration through GET_CFG.

This is an asymmetry worth noting rather than a diagnosis: either `0x4026`
is not instantiated as a GET-capable endpoint, or its endpoint
configuration is held elsewhere (the codec-DMA port setup is owned by the
device route, not the module). It means the "which codec-DMA channel does
the VI actually bind" question cannot be settled by GET_CFG alone, and a
different readback is needed — for example the codec-DMA port registers
for `WSA_CODEC_DMA_TX_0`, or a per-frame checksum on the VI stream.

No change to the protected render, the PA lifecycle or any fail-closed
path was made. The default entry, the Gen20 recovery entry and the stock
generation identity remain untouched.

### VI sensing hardware path (reference route)

`wsa_macro_enable_disable_vi_feedback()` in `lpass-wsa-macro.c` programs
`CDC_WSA_TX0/TX1_SPKR_PROT_PATH_CTL` for VI mask bit `WSA_MACRO_TX0`
and `CDC_WSA_TX2/TX3_SPKR_PROT_PATH_CTL` for VI mask bit `WSA_MACRO_TX1`.
Both register pairs are VI sense paths in this handler; the separate CPS
DAI is described as carrying the WSA8845 DP6 source to `WSA_CODEC_DMA_TX_1`.
The VI sense enable routine asserts SPKR_PROT reset, programs PCM rate,
enables the SPKR_PROT clock and then releases reset.

Under the reference route that DAPM handler is deliberately bypassed —
`wsa_macro_fullio_post_pa_probe()`, `wsa_macro_fullio_clock_audit()` and
`wsa_macro_fullio_reference_route()` all short-circuit it — because the
paired PA lifecycle owns the protection clocks. That is the fail-closed
behaviour this work preserves.

`get_channel_map()` returns the VI DAI's active mask and count;
`wsa_macro_hw_params()` records `pcm_rate_vi`. These describe the host
DAI, not the DSP's sample packing or the `msPP` map contract. The WSA
macro registers describe sense-clock/rate state, not the ADSP codec-DMA
routing. Thus neither the two-channel endpoint declaration nor the four
macro registers establishes what `num_channels=4` means to `msPP`.
Keep the map unchanged. Data-plane aliasing into VI is a hypothesis,
not a finding; a validated passive live tap could distinguish it from a
shared DSP resource driven by capture payload.
