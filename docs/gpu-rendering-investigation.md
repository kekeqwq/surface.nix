# Denali OLED: accepted GPU initialization route

## Hardware and result

Surface Pro 11 Denali OLED (Samsung SDC4195), X1E80100 Adreno X1-85, native
2880×1920 at 120 Hz, scale 2. The validated diagnostic kernel was `next-20261119`
plus the isolated touch queue and read-only register logging. No GPU register
experiments, disabled compression/tiling, or desktop style workarounds were
needed for the successful run. The release omits tracing.

The initial GPU request occurred **after switch-root and before ordinary
services**: switch-root at 2.535 s, missing zap at 4.606 s, runtime firmware
service at 5.487 s. Repacking the initrd alone did not close this gap. Preparing
private firmware during activation (after NixOS sets its public firmware path,
before root coldplug) made the same original zap available at 3.739 s, before
GPU initialization at 4.668 s. No missing-zap, GPU `-2`, or GMU OOB errors were
seen in that boot. No change to the GPU firmware version was required.

Direct KMS at native 120 Hz with Adreno and Mesa 26.3.1 then produced matching
linear and UBWC CRC in all 238 compressed frames for each test:

| Pattern | Render request | CRC pair |
| --- | --- | --- |
| 16×16 multicolor | default | `0710fa20,8438e792` |
| 8×8 multicolor | default | `0f627144,6f727a25` |
| Per-pixel gradient | default | `c341fdb7,ede31bc1` |
| 8×8 multicolor | GMEM diagnostic | `0f627144,6f727a25` |

SSPP error fields were zero. The user confirmed a clean, smooth **physical**
desktop at 120 Hz, including a stronger per-window Ghostty transparency test;
shared Ghostty opacity stays 0.95. This validates the route on this device,
not all suspend/refresh/boot combinations. A clean screenshot alone never
established scanout correctness. Earlier register candidates did not fix it,
and those tests did not establish a hardware defect or exclude coherency.
The cold-link color-depth issue was fixed separately: the eDP RGB stream depth
is recomputed from the EDID and the negotiated link after successful training,
without forcing 30 bpp or bypassing link-capacity checks. A first cold boot of
the candidate selected 30 bpp directly, retained 2880×1920@120 and UBWC, and
passed the user’s physical color check at the shared 0.95 Ghostty opacity.
The shared Linux Ghostty default was then changed to 0.70; macOS keeps its
separate private default. External DP and YCbCr follow the existing code path.

## Firmware provenance

The accepted GPU zap was provisioned privately from a WOA Surface driver CAB:
`f2f6dd1d7b2dc6e8019f85d9a17a16bb3bc3605fb0bebc632ec615c1b404b86b`.
Microsoft's `SurfacePro11_ARM_Win11_26100_26.094.41119.0.msi` was also extracted
without running Windows. Its GPU INF version `31.0.137.0`, zap SHA-256
`c89711a60240f29cb5df13f7b904642b78b7d9d6e614473751f7bf4049fab137`, matches
`turbineBMW/surface-pro-11-linux@15e590c3c3298dd75a0b79256efa815c15dc0897`.
Its ADSP pair matches the installed files. CDSP and video firmware are not
used by this configuration. The public SQE and GMU matched that project's
files. The public generic zap is not the Microsoft-specific file requested by
the Denali DTB.

### MSI hardware regression (2026-11-25)

The owner-held MSI SHA-256 is
`8b299016027a4a87f50cf168f69ca1fb8dedc9a0612fcd6cff89b9bc64135ec2`.
On the non-5G Denali OLED, a private one-shot using the Gen25 kernel, initrd
components, and desktop configuration booted with all three files extracted
from that MSI. Only the private firmware directory changed in the closure.
The candidate initrd's zap and all three runtime file hashes matched
`scripts/surface-install-usb.py`'s verified list. The original firmware was
backed up; Gen25 remained the default and Gen20 was available for recovery.

- Niri/greetd and SSH came up; OLED mode was 2880×1920 at 120 Hz, scale 2.
- Adreno X1-85 (Mesa 26.3.1) passed 1,024 offscreen GLES pixel readbacks.
- Three FullIO idle/close/runtime-suspend/reopen rounds kept both amps
  attached, re-armed on the new trigger and preserved it through each
  192,000-frame stereo MicArray duplex capture.
- MicArray picked up the three timed speaker tones at 30.5, 32.1 and
  39.4 dB above the nonmatching windows/sidebands. These are not SPL values.
- Twenty play/stop cycles and five minutes of low-volume playback held one
  graph with approximately 2.88 million frames of progress per minute. No
  matching kernel/GPU/ASoC or PipeWire recovery faults were found.

The same day, the normal `flakes#surface` at `0414cb9` (hardware `3fbc19a`)
built natively and passed two ordinary `nixos-rebuild switch --flake .#surface`
invocations. Both selected the same stock entry automatically; the second
switch kept its exact UKI. The default boot came up as Gen26,
`/nix/store/vgah550lp9wr8bhfkrsmrcl9467xnrmq-nixos-system-surface-26.11.20261124.52a9386`,
with Current and Default both
`nixos-f13f8559f20376e71cac05b1dcc76ebbe78f29338946d84cc0a25ddb91c822ca.conf`.
The installed UKI and runtime firmware matched the MSI. Gen26 independently
passed the same GPU check, three idle/reopen + duplex rounds, speaker probes
(27.8/28.2/26.2 dB contrast), 20 short cycles and five minutes of progress on
one graph. No failed system or user units were reported. The original firmware
and ESP were archived privately, and the verified Gen20 image was preserved
as an independent rescue entry outside normal generation retention.

These results verify the firmware identities and the standard switch path,
not USB installation, long-term listening, or a physical SoundWire detach.
Matching hashes are an informational check for user-supplied packages, not a
flake input pin.

### Gen26 ordinary-use audio regression (2026-11-25)

Ordinary listening did **not** pass: after about two seconds paused, playback
resumes briefly, then fades to near silence. Do not treat the earlier
five-minute PCM progress test as five minutes of acoustic output. In a
low-volume tone/silence/tone test on the long-held graph, the explicitly
linked PipeWire speaker monitor held about 500 PCM counts at 1193 Hz on both
channels during both five-second tones. An independent MicArray link did not
show sustained matching acoustic output, despite unchanged ALSA trigger time.
This bounds the problem below the software monitor; it does not distinguish
ALSA/DSP transport, DSP protection/gain, or the amplifiers. A separate duplex
probe also hit PipeWire's `snd_pcm_avail after recover: Broken pipe`, followed
by a new trigger and endpoint re-arm; that is distinct from the long-held
fade observation. Boot logs contain a SoundWire `qcom_swrm_port_target`
warning on both Gen25 and Gen26, not yet tied to this symptom. No increase in
DSP or PA gain was made. Keep USB/fresh-install acceptance pending.

A follow-up run used two separate five-second playback streams with a
three-second gap (`tests/fullio-acoustic-sustain.sh`). On Gen26 the trigger
stayed at `10070.469340614`; both software tones were present, but the
correlated MicArray signal stayed at the noise floor. Targeted, read-only
samples of the volatile PA FSM status registers showed `0x00` on both amps
throughout both tones, with no FSM error bits. ALSA `RUNNING` alone did not
mean the paired PAs were still on.

The WSA playback backend controls mute at trigger time. A STOP can turn off
both PAs without `hw_free`, but the FE's `fullio_reference_started` guard used
to treat a later START of that graph as a duplicate. The FE now marks that
started graph for retirement on STOP/SUSPEND/PAUSE_PUSH. It leaves STOP
non-blocking with respect to DSP transactions and notifier drain. PREPARE
uses the existing paired PA-off and clock-off checks, scoped STOP/CLOSE/UNMAP
and quarantine before starting a fresh graph. This fixes the stale-start
path without changing the gain curve or protection. It does not claim to
prevent the initial XRUN or explain every possible fade.

Kernel.org mainline and linux-next annotated tags were checked on 2026-11-25:
latest mainline candidate `v7.4-rc4`, latest integration tag `next-20261124`
(tag object `ecfab21e114b19a8425356b5b7547c471bd6ebb2`). Retained the audited
Next24 pin and built natively on AArch64. The one-shot candidate booted
`/nix/store/zbxcyhc346h3v46iwa3bwqxr6i0zy1hk-nixos-system-surface-26.11.20261124.52a9386`;
Gen26 remained default and Gen20 recovery was verified before boot. Results:

- Two same-FD ALSA `DROP → PREPARE → START` cycles caused fresh, armed triggers.
- A further desktop run changed trigger once. Logs show the old ring was
  released after CLOSE/UNMAP ACKs and the replacement graph armed. Its tone
  envelopes stayed above noise; this run does **not** count as same-graph.
- Three ordinary close/runtime-idle/reopen rounds passed 192,000-frame
  MicArray duplex each. This is not a physical SoundWire detach test.
- On the last reopened graph, two 30-second tones with a three-second gap
  held trigger `357.837264592`. Late-window peak-channel amplitudes were
  28.92 and 19.65 counts vs noise floors of 0.42 and 0.29. Both PA FSMs read
  `0x2f` at the end, with no FSM error bits or matching new kernel faults.
  A second pair of 30-second tones on that same trigger had no quiet window
  in either tone's measured interior and no matching new kernel faults.

Private test evidence: `~/.local/state/denali-fullio-stop-xUjFn9/` on the
Surface. Still pending: pinned ordinary switch/default boot and daily
listening. Do not treat the one-shot as the standard deployment regression.

### Protected endpoint loudness (2026-11-25)

A session-only keeper override tested the pinned Windows endpoint ceiling
of **0 dB** (Q28 `0x10000000`, GainStep 30), instead of −3 dB (GainStep 26).
This was unity at the DSP endpoint, not added PA gain or desktop
amplification. The desktop volume slider and mute were not changed.

At unchanged desktop volume and trigger `981.050508991`, low-level
997/1499 Hz probes measured late-window amplitudes of 43.99/31.49 counts
at −3 dB and 62.39/42.17 counts at 0 dB (roughly +3.0/+2.5 dB relative;
not calibrated SPL). The return-to-−3 dB pass had a noisy 1499 Hz floor
and did not qualify as a clean repeat. With the revised keeper running
in a session-only systemd override, two 30-second tones separated by
three seconds passed the sustained acoustic gate with no quiet window.
Three further runtime-idle/reopen cycles each armed GainStep 30 and
passed 192,000-frame duplex. No change to PA/WSA controls or protection
admission. The session override was not an installed generation. Private
evidence is in the same directory above (`loudness-*`).

Daily listening subsequently reported that playback still gets quieter
with time. This supersedes the short-probe acceptance. A read-only snapshot
shortly after the report found the last armed 0 dB trigger still running,
sink volume unchanged and both PA FSMs at `0x2f`, with no FSM error bits.
The snapshot was taken after the user's playback had ended: it cannot prove
what the DSP or PAs were doing at the onset of attenuation. Do not classify
this as the earlier PA-off failure, assume normal thermal limiting, raise
any gains further, or promote the 0 dB candidate on this evidence.
`tests/fullio-acoustic-sustain.sh` now also checks for partial attenuation:
for longer probes it divides the MicArray tone amplitude by the concurrent
software monitor amplitude and rejects a loss exceeding 3 dB in a 10 s
window. This catches a sustained quieter plateau even when still well
above the acoustic noise floor. Two 90 s low-level tones, separated by
3 s, passed on unchanged trigger `1327.451658626`. The lowest / final
acoustic-to-digital changes were −2.79/−0.59 dB at 997 Hz and
−0.31/+1.87 dB at 1499 Hz. Both PAs were `0x2f` throughout the sampled
interval, with no matching new kernel faults. The dip at 997 Hz did not
persist. This does not reproduce or rule out the reported decrease on
ordinary content; the next comparison needs the same repeatable passage
and onset timing, without increasing gain or bypassing protection.

The user then reproduced the fade in Chrome at around 20:27 (+08:00),
near video position 2:27, and heard recovery in the 20:29 minute. The
session probe (`scripts/fullio-level-probe.py`) saved only one-second
level statistics and PCM state, not audio. The 10-second medians align
with the report (dBFS, channels L/R):

| Window start | PipeWire monitor | MicArray |
| --- | --- | --- |
| 20:27:00 | −24.15 / −25.39 | −46.28 / −46.41 |
| 20:28:50 | −24.51 / −24.63 | −56.28 / −56.48 |
| 20:29:30 | −23.48 / −24.23 | −45.82 / −46.12 |

All 169 samples in the interval held ALSA `RUNNING`, trigger
`1327.451658626`, desktop volume `1.00`, and at least 47,104 frames per
capture per sample. No logged audio error or keeper re-arm coincided
with it. The acoustic drop on both MicArray channels is not explained by
a matching overall drop at the digital monitor. Program spectrum,
MicArray pickup, and DSP/hardware behavior are not independently isolated
by broadband level statistics. After playback ended, at 20:31 the
session-only 0 dB override was removed. The original −3 dB / GainStep
26 re-armed on the same graph; the probe was left running for a repeat of
the same Chrome passage. Do not promote the 0 dB setting.

On that −3 dB replay, the user marked video 0:49 in the 20:33 minute.
Audio began at 20:32:44.697, placing the mark near 20:33:33. Aligning the
one-second digital RMS envelopes over 20:33:00–20:33:39 against the
prior 0 dB run estimated a 446 s offset with correlation 0.977. Near
20:33:30–20:33:39, matched-window digital medians were −28.13 dBFS at
−3 dB and −27.88 dBFS in the earlier run; acoustic medians were −56.03
and −49.97 dBFS respectively. The median paired residual after allowing
for the nominal −3 dB setting was −3.15 dB. This is evidence that lowering
the endpoint did not eliminate the reported behavior, not an isolated
comparison of gain steps: the runs were sequential with no cold reset,
content alignment is based on statistical envelopes, and there is no
in-event hardware snapshot. The ALSA trigger and desktop volume stayed
unchanged; both PAs read `0x2f` when sampled after the marked interval.

The user left Chrome playing at −3 dB, so no manual recovery marker is
needed. At comparable digital level (−24 to −22 dBFS), median MicArray
minus monitor level moved from −28.8 dB at 20:34 to −22.5 dB at 20:37,
then to −28.5 dB at 20:41, with one uninterrupted ALSA trigger. Matching
broadband level helps reject simple input level changes but cannot match
the program spectrum. `scripts/fullio-pa-level-state.py` was started at
20:42:35 for 15 minutes, five-second intervals, without interrupting
Chrome. In its first 31 snapshots both FSMs stayed `0x2f`, with no error
bits and raw VPHX status `0x02`. The ADC output bytes are recorded raw;
this is not a calibrated coil temperature or proof that the DSP is not
attenuating. No new kernel fault matched the interval.

`tests/fullio-level-stimulus.py` prepares a deterministic periodic
voice-band stereo stimulus for a controlled test once the sink is idle.
The generated repeated waveform checked at −31.09 dBFS RMS per channel,
peak 3477 counts, and zero at the file boundaries. Use the existing
level probe and hardware snapshots with identical early/late repeats;
do not layer this test over the user's ongoing Chrome stream. Do not
alter PA gain, VI/CPS clocks, protection calibration or protection
admission based on the current broadband correlation.

With Chrome idle, three repetitions of the same 120 s file on the
long-held −3 dB graph (`1327.451658626`) established a regression test:

- 20:48:54: digital level stayed −31.09 dBFS; both mic RMS channels fell
  by 4.0–4.22 dB in the 20:49:57 window and recovered in the next one.
- 20:52:58: the median coherent acoustic-to-digital change across five
  resolved stimulus tones reached −17.94 dB. The ALSA read/write
  pointers still advanced at approximately 48,000 frames/s. WSA raw PA
  status, error bits and VPHX matched the beginning of the replay.
- 20:56:51: the 250 ms magnitude measurement (which does not cancel
  phase across a whole second) still showed a −17.14 dB median dip
  on the two resolved tags, 449 Hz on left and 454 Hz on right. The
  whole-second tone measurements were below the required contrast on
  this run; do not combine the two metrics into one threshold.

`tests/fullio-level-replay.sh <closure> <probe-log> 120` requires a
probe started with `--stimulus-tones`. It refuses other clients on the
speaker and terminates only its own player if another stream appears.
No raw captures are stored by the telemetry. A result below −3 dB
is a regression, not an instruction to restart an active application.
Logs: `controlled-level.log`, `coherent-level.log` and
`short-coherent-analysis.log` in the private Surface state directory.

After normal PCM close and SoundWire runtime suspend, the graph reopened
with trigger `6786.250028391` at the same −3 dB setting. The old CLOSE
and ring/GainStep-page release were acknowledged. The first identical
120 s replay on the new graph passed: worst one-second/250 ms 10-second
median changes of −0.38/−0.90 dB. All sampled PA states still matched.
The subsequent 180 s replay on the same new trigger (no intermediate
refresh) also passed at −0.14/−0.50 dB with no new kernel events.
This is a recovery observation, not proof of the failed component:
ordinary reopen also reinitialized DSP state, went through SoundWire
runtime PM, and restarted the microphone capture. It is not permission
to recycle a graph while an application is playing or to remove the
speaker protection path.

A further discriminator kept that graph open. About ten minutes after
its start, the 21:11:00 replay failed again: worst short-window change
within the replay −22.05 dB, and −13.03 dB versus an absolute fresh-graph
reference (floor-limited, common stimulus tones). Normal playback PCM
close and reopen recovered it **without SoundWire runtime suspend or
MicArray restart**. Four already-active devices were held active only
for this bounded contrast; suspended-time counters remained exactly
`3131/2275/55102/55115` ms. Playback trigger changed
`6786.250028391 → 7608.014041534`, mic trigger stayed `6789.364824913`.
All four policies returned to `auto`. At unchanged −3 dB the new graph
passed 120 s (worst short-window drop −0.59 dB); the absolute matched
comparison was within the healthy reference range. This rules out
requiring runtime suspend, but normal PCM close still resets DSP state
and cycles the paired PA/feedback lifecycle, so it does not distinguish
the two.

In an uninterrupted periodic-stimulus run beginning at 21:17:25,
attenuation was present before 21:19, with no pause, no trigger change
and no corresponding limit change in the software signal. Two explicit
live diagnostics on this low-level synthetic input used the same
−3 dB setting and the helper's new `--mute keep` mode: one 8-byte
endpoint-gain-only TLV at 21:19:48, and one 224-byte gain plus pinned
GainStep 26 delta at 21:20:29. Both returned success; neither restored
sustained acoustic output to reference. Individual tones briefly
improved after the second write, but that was neither complete nor
lasting. No automatic retransmission or mute operation. Do not infer
that these controls' ACKs prove live protection or output.

The pinned route's `0x4003` logger is downstream of SP on the path to
RX0 and could distinguish DSP output from LPASS/SoundWire/amp output.
The available collector is explicitly guarded for a PA-off diagnostic;
older captures also had ambiguous provenance and wrong media format.
Do not reuse it on the live protected graph by removing the guard, or
call legacy tap 1 a valid RX0 signal. A useful next boundary measurement
needs separately validated routing, format and protection-safe access.

The 600 s replay ultimately lost 27.94 dB in the worst short-window
median despite the intervention. A second no-runtime-suspend reopen
then failed its 120 s replay by 9.07 dB; reopen is not a dependable
mitigation. Later the same playback trigger `8417.334278609` passed
120 s (−1.52 dB), confirming the variation can also recover without
another playback reopen. In the 21:42:45 replay, short-window levels on
four tags sagged by 5–6 dB relative to the start. At 21:43:48 the two
MicArray probe links alone were disconnected until capture PCM closed,
then restored. Capture trigger changed `6789.364824913 → 9374.350335266`;
playback trigger stayed `8417.334278609`. About 13 seconds later three
of four tags were back within 0.6 dB of their starting ratios, the other
within 1.8 dB. This single intervention cannot distinguish recovery
caused by capture reopen from coincident spontaneous recovery, or a
capture-side effect from DSP graph coexistence. Both PA states were
stable, and the external Mac input returned only zeros and was rejected.
The level probe now records the capture PCM state and trigger separately;
`fullio-level-replay.sh` rejects any capture reopen during a normal trial.
The user's audible fade remains an open failure; these evidence limits
preclude a speculative runtime gain, PA or protection change.

The user also heard an occasional crack during test playback. Past
external recordings identified a separate PA-engagement transient, but
that does not identify the new report. Both synthetic generators now
use 150 ms raised-cosine edges. `fullio-acoustic-sustain.sh` reports peak
and adjacent-sample jumps for onset, release and an interior window
rather than excluding every boundary from analysis. On the held
`8417.334278609` graph, a single low-level 997/1499 Hz pair passed, with
unchanged trigger and no corresponding audio-service or kernel event.
The sink peak was 500 counts at both frequencies; the MicArray boundary
peaks were 151–214 counts. A larger mic-only adjacent-sample jump (365
counts at the 1499 Hz onset versus 242 in that tone's interior) was
observed, but its source is unverified. This run does not clear the
intermittent crack. Before changing PA timing or applying a system-wide
ramp, distinguish a crack within the held graph from one coincident
with a new PCM trigger; qualify it with an independent acoustic pickup.

Private blobs and firmware-bearing UKIs must not enter Git or the Nix store.
The diagnostic kernels, old boot scripts and their experiment documents are
historical only; there is one maintained kernel and one installed boot path.
