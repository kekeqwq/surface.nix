# Denali OLED touchscreen candidate

## Priority and baseline

Higher-gain internal audio/protection work is deferred until the other hardware
bring-up tasks are done. Keep the accepted zero-local-patch linux-next desktop
and original downstream rescue UKI. Do not overwrite either while testing touch.

## Gap in next-20261118

The pinned kernel.org snapshot has no generic `drivers/hid/spi-hid/` transport,
GENI QSPI extensions, or Denali digitizer DT node. This is not resolved by
installing iptsd or enabling the existing HID_MULTITOUCH symbol alone.

`surface-next-touch` retains the kernel.org source and adds the dependency-ordered
SPI-HID v7 / GENI+GPI QSPI / digitizer queue from
`dwhinham/linux-sp11@46bb6beace94874a3ec602bfb83e6f87995bc5d0`. The 18 pinned
commits include the shared SPI-HID infrastructure, binding schemas, PM/reset
fixes and QSPI protocol support. The Romulus compatible precedes Denali because
the latter commit builds directly on it; no Romulus host/device is enabled.
There are no audio gain, modem, power-policy or graphics changes in the queue.
See `pkgs/touch-patches.nix` for exact commits and hashes.

The GENI patch required a source rebase: next added panic-notifier/ready-GPIO
fields and replaced direct DMA callback assignment with
`dmaengine_desc_set_callback()`. The local adapted patch retains those upstream
fields and uses the new helper for RX completion. Original attribution and
source commit are recorded in its header. The rest of the queue applied without
fuzz in a scratch source tree (some line offsets were required).

## Isolated host candidate

The standalone test flake's `denali-next-touch` selects this kernel, keeps the
accepted Niri graphics configuration, and enables Nixpkgs iptsd 3.1.1. It does
not import the audio experiment. The kernel release has a distinct
`-surface-touch` suffix, with `SPI_HID=m` and `SPI_HID_OF=m`.

The native Nix kernel/system/UKI build completed with `BUILD_EXIT=0`.
Module vermagic matches `7.4.0-rc3-next-20261118-surface-touch`. UKI sections
match the intended kernel, initrd, DTB and command line byte-for-byte.
UKI SHA-256: `d4278a751eec4474b3edfc7d6265dbed1cf065508281a0e65c6905f0e0f0e651`.

A one-shot reboot reached the installed system (SSH at 192.168.2.194):
`spi0.0` bound through SPI-HID, device `045E:0C83` appeared, and
`iptsd@dev-hidraw0.service` is active in Touchscreen mode. Virtual touchscreen
and stylus input devices were created. Niri is running on a real VT, with
Adreno X1-85 EGL and 2880x1920 @ 120 Hz retained.

Startup logged one `Unknown input report version (v 0x0)` and one
`ignoring report --> -16`; their impact has not been established. Do not call
these harmless merely because enumeration succeeded. The user subsequently
confirmed finger touch works in Niri. Detailed edge/coordinate, multitouch,
pen and suspend/resume tests remain separate gates; do not infer them from the
general finger-touch confirmation.

The touch candidate is GC-rooted and installed under its own UKI filename.
The standalone flake's `denali` now selects the accepted touch desktop. The
zero-local-patch next desktop and original downstream configuration remain
explicit alternatives. Flake selection and the machine's manually deployed
boot default are separate: promotion requires updating that boot selection.

## Incremental iteration

`nix develop .#surface-next-touch -c bash scripts/surface-next-workbench.sh build`
provides a writable patched source tree, persistent Kbuild output and ccache.
Its initial build still needs compilation. Subsequent source edits reuse the
same output directory; do not clean it for each patch. If the tracked patch
queue changes, the script refuses to silently reuse a stale source seed: review
and reconcile the source delta, then update `patch-seed` explicitly. Workbench
artifacts remain diagnostic; final acceptance uses the Nix-built candidate UKI.

## Acceptance gates

1. Verify final Kconfig, affected modules, Denali touch DT node and matching UKI.
2. Pin candidate closure/UKI and deploy under a new filename, never over baseline.
3. One-shot boot; confirm kernel release, NVMe root, Wi-Fi, SSH and Niri 120 Hz.
4. Confirm SPI device binds, hidraw appears and iptsd creates a touch input device.
5. Human test: coordinate alignment, all panel edges, taps, drag and multitouch.
   Pen and suspend/resume need separate tests, not inferred from finger input.
