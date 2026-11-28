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

On 2026-11-26 the refreshed private image was written to USB and the
entire image range read back byte-for-byte (SHA-256
`0e53bdba6bb1ee7a5e612bd07584c8aa3966538ff2478cdd069897f0577b40d6`).
The owner later reached the boot menu on the Denali OLED, but selecting
Live left a black screen and did not expose a usable TTY. **This image
is not a verified bootable baseline.** The menu, ISO/ESP inspection and
USB readback do not distinguish early kernel failure, Live root mount
failure and display/console handoff failure. On the next image, retain a
visible boot log and verify the real device reaches a legible local TTY
with working input and the Live root mounted before attempting any disk
installation. Keep the failure investigation separate from the installed
system and do not repartition the internal disk to test it. Keep subsequent
private candidates outside Git, the Nix store, and iCloud while testing.
Archive a copy in the owner's iCloud only after the owner confirms real
USB boot and use of the Live TTY. The failed candidate is not a baseline.

### Live root mount fix

The old Live configuration evaluated `/nix/.ro-store` with `loop,threads=multi`.
The actual Next24 Live kernel build config has `SQUASHFS_COMPILE_DECOMP_SINGLE=y`
and no `SQUASHFS_CHOICE_DECOMP_BY_MOUNT`; its `squashfs_parse_param_threads_str()`
rejects `multi` with `EINVAL`. This is a concrete blocker for reaching stage 2,
independent of whether there is a second display problem. Keep the same
kernel and override the Live read-only store mount to use its compiled
SquashFS default, leaving ISO discovery and overlay unchanged. The native
configuration gate checks the effective mount flags, `SURFACE_LIVE` label,
and visible stage-1 status; an initial sub-option override that still left
`threads=multi` was rejected by the gate before packaging.

### Denali USB boot qualification

The Wi-Fi/HHKB candidate (`c7dbb7a`, 1,679,294,464 bytes, private ISO SHA-256
`05bbdeb12d62583c3114564b897c456ccc806034d9df1bf598d0c403b8825b73`)
passed a complete post-write USB readback. The owner booted it and used
the local text console; the running system showed the USB-backed ISO9660,
SquashFS and overlay mounts, HHKB enabled, Wi-Fi connected under
NetworkManager, and working Live-only root SSH. Both Git repositories
were reachable and all three embedded firmware hashes matched. The
internal NVMe was not mounted or modified. The prior run had USB disconnect
before SquashFS I/O errors; with USB left attached, the repeat boot had
no matching kernel faults. Keep the stick connected throughout use and
remove it only after shutdown (or select the installed system at reboot).

The booted medium's full hash differed from the preboot image; the same
new hash was observed locally on Surface and in a separate readback to
Mac. Do not archive that disk dump as the original ISO. This qualifies
Live boot and network/install-tool availability; LUKS enrollment and
first boot from a blank-disk installation have not been performed.

### Private r4 remaster for a fresh install

To add only the local fresh-install enrollment script to the verified r4,
run on the Mac; use new output paths outside the repo and Nix store:

```sh
nix shell \
  github:NixOS/nixpkgs/5e50e88b70dff025f88e08f2b56de55137a13fe3#xorriso \
  github:NixOS/nixpkgs/5e50e88b70dff025f88e08f2b56de55137a13fe3#mtools \
  -c python3 scripts/remaster-live-enrollment.py \
  --r4 /private/path/to/original-r4.iso --out /private/path/to/r4-fresh-key.iso
```

The remaster tool accepts only the recorded original r4 SHA-256 above and
checks that the ESP, loader, UKI, SquashFS and three firmware files are
unchanged. The first Mac remaster had SHA-256
`5e579db768902e40c6593a44c23414dfbe487c7dac9ffcc6034c8a7d9e1bdd48`.
This is an image-structure check, not a USB boot qualification. Do not
replace the archived r4 image with this remaster.

On the Live console, run `sudo bash /iso/surface-install/enroll-key.sh`
only when the target data is backed up or disposable. It checks the internal
Samsung NVMe and asks for explicit confirmation before replacing GPT, the ESP
and LUKS2. It does not reuse an old LUKS header, passphrase, key registration
or filesystem, and does not perform a whole-drive secure erase. The new
recovery passphrase is entered only on the local console. The script stops
with the new `cryptroot` mapping open; Btrfs and the normal GitHub-based
NixOS install follow separately.
