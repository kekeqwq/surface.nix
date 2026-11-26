# Denali touchscreen startup

The SPI touchscreen/stylus (`001C:045E:0C83`) uses the pinned NixOS `iptsd` package. It is separate from the SSAM magnetic keyboard and its `09AF` touchpad. On the HHKB top-row regression boot, the touchpad initially got `/dev/hidraw3`; the touchscreen later got that number, and the touchpad reappeared as `hidraw4`. The numbered `iptsd@dev-hidraw3.service` attached to the correct touchscreen but systemd stopped it in the same startup window. The preceding boot also stopped that service once before starting it again. Starting the numbered service after device enumeration restored both virtual input devices and the owner confirmed touch worked.

The first stable-alias candidate booted with both the dedicated service and the old numbered service opening `045E:0C83` within the same 7 ms window. The old daemon then exited and the touchscreen was unusable despite the dedicated daemon remaining active. The final udev database contained only the dedicated service request, so replacing the wants property in a late rule was insufficient: an older event can probe the reused number and already queue the numbered service.

`modules/denali/touchscreen.nix` keeps the stock service/configuration package but wraps `50-iptsd.rules` so the generic numeric probe is skipped before it executes. The Denali SPI touchscreen creates `/dev/surface/denali/ipts` and starts only `denali-iptsd.service`; the magnetic touchpad skips the IPTSD probe entirely so its earlier event cannot accidentally open the SPI touchscreen by number. This does not change its own driver or udev settings. Other devices use the original packaged rules. The dedicated service is ordered after and bound to the stable device unit, not a recycled number. No fixed `hidraw` number or locally staged binary is needed.

Before physical reboot validation: the generated udev rule passed `udevadm verify` on the native target; `iptsd-check-device` accepted a symlink to the verified touchscreen. After an ordinary locked switch and reboot, check:

```sh
udevadm info -q property -n /dev/surface/denali/ipts
systemctl status denali-iptsd.service
journalctl -b -u denali-iptsd.service
```

The alias must resolve to `001C:045E:0C83` and only the dedicated service should own the touchscreen. Check virtual touch/stylus registration, touch taps and swipes, touchpad independence, and retained HHKB behavior. A test of the userspace service on an already enumerated device is not a boot test.
