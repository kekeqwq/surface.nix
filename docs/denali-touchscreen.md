# Denali touchscreen startup

The SPI touchscreen/stylus (`001C:045E:0C83`) uses the pinned NixOS `iptsd` package. It is separate from the SSAM magnetic keyboard and its `09AF` touchpad. On the HHKB top-row regression boot, the touchpad initially got `/dev/hidraw3`; the touchscreen later got that number, and the touchpad reappeared as `hidraw4`. The numbered `iptsd@dev-hidraw3.service` attached to the correct touchscreen but systemd stopped it in the same startup window. The preceding boot also stopped that service once before starting it again. Starting the numbered service after device enumeration restored both virtual input devices and the owner confirmed touch worked.

`modules/denali/touchscreen.nix` keeps the stock service/configuration package but changes automatic startup for this SPI HID ID on Denali. A late udev rule creates `/dev/surface/denali/ipts` and replaces the packaged numbered startup for that device with `denali-iptsd.service`. The service is ordered after and bound to the stable device unit, not a recycled number. The rule does not match the touchpad or change its settings. No fixed `hidraw` number or locally staged binary is needed.

Before physical reboot validation: the generated udev rule passed `udevadm verify` on the native target; `iptsd-check-device` accepted a symlink to the verified touchscreen. After an ordinary locked switch and reboot, check:

```sh
udevadm info -q property -n /dev/surface/denali/ipts
systemctl status denali-iptsd.service
journalctl -b -u denali-iptsd.service
```

The alias must resolve to `001C:045E:0C83` and only the dedicated service should own the touchscreen. Check virtual touch/stylus registration, touch taps and swipes, touchpad independence, and retained HHKB behavior. A test of the userspace service on an already enumerated device is not a boot test.
