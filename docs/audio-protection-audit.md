# Denali speaker loudness/protection audit

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
