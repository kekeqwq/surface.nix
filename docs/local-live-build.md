# Local Denali installation media

The `surface-live` development shell uses this repository's `flake.lock` for
its tools. Build the non-private AArch64 Linux base on a native AArch64 Linux
machine; the final remaster can also run on a Mac using `--base-iso`. Provide
one official MSI explicitly. Do not place the MSI, extracted firmware, or
output image in the source tree or Nix store. No disk is written by `build.py`.

## Baseline selection (2026-11-25)

Both official kernel.org tag queries succeeded. The latest reported mainline
RC was v7.4-rc4 (`a4d7daea…`, tag object), formal v7.3 was `091b0638…`, and
the latest reported integration tag was next-20261124 (`ecfab21e…`, peeled
`3dd8c790…`). Retain the current next pin and Denali patch stack for this
image: the other tags were already compared for the
[Next24 baseline](denali-next24-baseline.md), and there is no newer candidate
in this query to justify changing the tested Surface boot/driver baseline.

The 2026-11-26 recheck found the same formal and RC tags and
`next-20261125` (tag `47588e4c…`, peeled `94370469…`). The earlier
[Next25 source comparison](fullio-audio-acceptance.md) found the relevant
audio paths unchanged. This refresh keeps the already tested Next24
`fetchgit` pin and introduces no kernel or patch-stack change for Live.
The ISO derivation includes only its two inspection scripts, so edits to
unrelated FullIO tools no longer invalidate it.

The Live environment uses the text installer kernel/configuration; the
installed `flakes#surface` selects the Niri desktop and protected FullIO
configuration separately. The Live `system.stateVersion` is 26.11 for the
locked 26.11 release; this does not change the installed host's state version.

## Local build verification (2026-11-25)

The native AArch64 base and local private remaster passed inspection. The
examined private artifact had SHA-256
`40f93873f47f6d9b63a6125025e6a8a3752194d3aadbd8f6e237a2069aad4528`.
The base and remaster had the same EFI partition digest, Denali ARM64 zboot
UKI, and Live squashfs; the embedded three-file firmware payload matched the
hardware-tested MSI. No USB was written. Do not treat verified ISO contents
as a USB boot or an acceptance test of a freshly installed instance.
