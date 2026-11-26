# Denali magnetic keyboard: opt-in HHKB prototype

`surface.devices.denali.keyboard.hhkb.enable = true;` selects an experimental
Surface HID transport patch. The hardware option defaults off; `flakes#surface`
may explicitly enable it. The Live image keeps it off. On the 2026-11-26
native evaluation, leaving it off yielded the exact deployed daily closure. See the [PFU Studio US Fn table][pfu] for
macOS Profile 2, adapted to keep the physical Surface top row and number row
(including grave, minus, equals and Backspace) in place.

The verified device is Surface Aggregator UID `01:15:02:01:00`, HID
`0019:045e:09ae`, with `microsoft,denali-oled` and a byte-for-byte matching
263-byte report descriptor (SHA-256
`11dda0c14d12e6acd6b1ec2c60a77debac8f93802f44f7c7932e132c74d6d596`). It
reports ID 1: one modifier byte and ten simultaneous keyboard usages. A
short read-only capture confirmed physical Right (`0x4f`) alongside
semicolon (`0x33`) and apostrophe (`0x34`), with independent releases. The
patch preserves the original keyboard input path, translating the keyboard
array and the verified auxiliary reports for the physical top row. The
synthetic array has room for all translated usages without displacing other
held keys. Eject uses a separate added Consumer HID report. The touchpad,
generic USB/BT keyboards, and xremap configuration are unchanged.

- Physical Right is Fn, and standalone Fn has no evdev output. Physical
  Left/Up/Down and left Ctrl do not emit. Caps becomes real left Ctrl;
  Fn+Tab is Caps Lock. The two left Alt/Super positions are exchanged.
- Studio Fn mappings include the four directions, Home/End/Page Up/Page
  Down, F1–F12 on the number keys and `-`/`=`, keypad operations, Print
  Screen/Scroll Lock/Pause, Insert, Forward Delete, volume, Eject, and Power.
  The output of a key held across a layer change remains fixed until its
  physical release. Rollover or an invalid slot does not invent releases.
- Right-Fn + physical top row emits F1–F12. The matched magnetic keyboard's
  firmware-generated F1–F12 usages represent those same physical positions;
  normalize them to the captured base actions unless Right-Fn selected the
  alternate at make time. This makes the mapping independent of the firmware
  Fn Lock mode. Clear only bit 0 of report `5b` (the observed old Fn event),
  preserving adjacent system bits. This does **not** stop the firmware from
  driving its Fn LED or handling any firmware-local behavior.
- Right Alt and Copilot/Menu remain stock. Fn+Esc is the intentional Studio
  Power shortcut. Linux handles that key according to its own power policy.
  No Studio hardware pairing/profile controls exist.

## Verification

Use the official pinned Next24 source. The 2026-11-26 tags check found stable
`v7.3`, mainline `v7.4-rc4`, and `next-20261125`; the existing audio comparison
found no relevant change to justify mixing a new kernel baseline into this
experiment. Apply `pkgs/patches/denali-hhkb.patch` to a scratch copy of the
source, then run the same translator used by the module in the host model:

```sh
cc -std=c11 -Wall -Wextra -Werror \
  -I "$patched_linux/drivers/hid/surface-hid" tests/denali-hhkb.c -o /tmp/denali-hhkb-test
/tmp/denali-hhkb-test
```

The translator model passed with Clang ASan/UBSan and natively on AArch64.
Both modified HID objects compiled against the exact Gen27 build headers.
Deploy through the locked `flakes#surface` configuration with ordinary
`nixos-rebuild switch --flake .#surface` and reboot normally. Keep an
independent USB keyboard, the previous working generation, and the
independent recovery entry. Check the booted closure and the module
parameter, then TTY and Niri, original Caps and left Ctrl, both Fn release
orders, arrow repeat, the number and top rows, and xremap's Emacs left-Shift
tap/hold behavior. Repeat with the Surface keyboard reattached and after
resume, and verify that the USB keyboard and audio path are unchanged.
These are run-time acceptance requirements, not results of the model.

2026-11-26 installed-boot feedback: the candidate booted with
`surface_hid_core.denali_hhkb=1`, and the loaded module reported `Y`.
The owner confirmed physical Caps works as Ctrl without lighting the Caps
LED, and Right works as Fn. Right-Fn plus a physical top-row function/media
key does not yet produce its F-key alternate; the original Fn still does and
its light still responds. This was separate from Studio Fn+number F1–F12.

Follow-up read-only captures from both `09ae` and `09b0` found all relevant
reports on `09ae`. Physical F1/F9 with the old Fn produced keyboard usages
`3a`/`42`, bracketed by `5b01` and `5b00`; with the new Fn they produced
the same base reports as without Fn. With no Fn, the F1–F12 positions in
order produced `5e01`, `03e200`, `03ea00`, `03e900`, `d501`, `037000`,
`036f00`, and keyboard usages `46`, `4a`, `4d`, `4b`, `4e`. The revised
model checks all twelve positions, make-time mapping in both release
orders, deduplication with Fn+number, and unrelated Consumer pass-through.
The revised model passed ASan/UBSan and native AArch64; all three Surface
HID/KBD modules compiled and linked against the running build headers.
Physical TTY and desktop regression remain to be verified after deployment.

[pfu]: https://happyhackingkb.com/manual/studio/ug-us/en/ug/topic/use_fnkeys_fn1.html
