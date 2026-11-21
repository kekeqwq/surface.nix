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
The cold-link color-depth issue remains separate.

## Firmware provenance

The accepted GPU zap was provisioned privately from a WOA Surface driver CAB:
`f2f6dd1d7b2dc6e8019f85d9a17a16bb3bc3605fb0bebc632ec615c1b404b86b`.
Microsoft's `SurfacePro11_ARM_Win11_26100_26.094.41119.0.msi` was also extracted
without running Windows. Its GPU INF version `31.0.137.0`, zap SHA-256
`c89711a60240f29cb5df13f7b904642b78b7d9d6e614473751f7bf4049fab137`, matches
`turbineBMW/surface-pro-11-linux@15e590c3c3298dd75a0b79256efa815c15dc0897`.
Its ADSP pair matches the installed files. CDSP and video firmware were
collected but not deployed in the accepted run. ELF/manifest checks of the
five private files are structural checks, not hardware acceptance. The public
SQE and GMU matched that project's files. The public generic zap is not the
Microsoft-specific file requested by the Denali DTB.

Private blobs and firmware-bearing UKIs must not enter Git or the Nix store.
The diagnostic kernels, old boot scripts and their experiment documents are
historical only; there is one maintained kernel and one installed boot path.
