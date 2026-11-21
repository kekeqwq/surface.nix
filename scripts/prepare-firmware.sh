# Invoked as root by the generated NixOS activation script, before root coldplug.
set -euo pipefail
public=$1
private=$2
state=/run/surface
zap=qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn
test -f "$private/$zap"
install -d -m 0700 "$state"
work=$(mktemp -d "$state/.firmware.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
cp -rLs "$public/." "$work/"
cp -rL --remove-destination "$private/." "$work/"
# Atomically replace the lookup link; retain previous trees until reboot so
# an in-flight firmware request cannot lose its pathname during a switch.
ln -s "$(basename "$work")" "$work.link"
mv -Tf "$work.link" "$state/firmware"
printf %s "$state/firmware" > /sys/module/firmware_class/parameters/path
trap - EXIT
printf '<6>surface-firmware: private runtime firmware ready before coldplug\n' > /dev/kmsg
