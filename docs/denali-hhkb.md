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
patch preserves the original keyboard input path and only translates that
report. Eject uses a separate added Consumer HID report; all physical
consumer/system reports pass as before. The touchpad, generic USB/BT
keyboards, and xremap configuration are unchanged.

- Physical Right is Fn, and standalone Fn has no evdev output. Physical
  Left/Up/Down and left Ctrl do not emit. Caps becomes real left Ctrl;
  Fn+Tab is Caps Lock. The two left Alt/Super positions are exchanged.
- Studio Fn mappings include the four directions, Home/End/Page Up/Page
  Down, F1–F12 on the number keys and `-`/`=`, keypad operations, Print
  Screen/Scroll Lock/Pause, Insert, Forward Delete, volume, Eject, and Power.
  The output of a key held across a layer change remains fixed until its
  physical release. Rollover or an invalid slot does not invent releases.
- The original left Fn had no reliable independent make/break in the captured
  reports. This implementation does **not** claim to disable firmware-side
  behavior. The unrelated system control report must not be deleted on the
  assumption that it means Fn. Right Alt and the Copilot/Menu behavior remain
  stock until the latter's own reports can be distinguished without stealing
  a genuine chord. The top row's base behavior remains stock; Fn+Esc is
  the intentional Studio Power shortcut. Linux handles that key according to
  its own power policy. No Studio hardware pairing/profile controls exist.

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

[pfu]: https://happyhackingkb.com/manual/studio/ug-us/en/ug/topic/use_fnkeys_fn1.html
