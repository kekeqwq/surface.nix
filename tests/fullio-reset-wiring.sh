#!/usr/bin/env bash
# Read-only audit of Denali's two codec shutdown GPIO consumers. No sysfs writes.
set -euo pipefail
s=${1:?pass exact healthy FullIO boot state directory}
[[ $(id -u) == 0 && $(hostname -s) == surface && $s == /home/keke/.local/state/fullio-* ]]
[[ $(<"$s/status") == 0 && $(readlink -e /run/booted-system) == $(readlink -e "$s/system") &&
   $(readlink /nix/var/nix/profiles/system) == system-20-link && $(uname -r) == *-surface-fullio-muted-test ]]
for svc in sshd greetd; do systemctl is-active --quiet "$svc"; done
dt=/sys/firmware/devicetree/base
[[ -e $dt/sound/microsoft,denali-fullio-muted-test && ! -e $dt/sound/microsoft,denali-fullio-post-pa-test ]]
shopt -s nullglob
pcm=(/proc/asound/card*/pcm*/sub*/status)
((${#pcm[@]} >= 2))
for f in "${pcm[@]}"; do [[ $(<"$f") == closed ]]; done
install_check() {
    local dev=$1 node=$2
    [[ $(readlink -e "$dev/of_node") == "$node" && $(<"$dev/status") == Attached ]]
    [[ $(readlink -e "$dev/driver") == /sys/bus/soundwire/drivers/wsa884x-codec ]]
    printf '%s attached/%s: %s\n' "${dev##*/}" "$(<"$dev/power/runtime_status")" "${node##*/}"
}
ctrl=$dt/soc@0/soundwire@6b10000
left=$ctrl/speaker@0,0
right=$ctrl/speaker@0,1
provider=$dt/soc@0/pinctrl@6e80000
install_check /sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:0 "$left"
install_check /sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:1 "$right"
python3 - "$left/reset-gpios" "$right/reset-gpios" "$provider" <<'PY'
from pathlib import Path
import struct, sys
left, right, provider = map(Path, sys.argv[1:])
expected = struct.unpack(">I", (provider / "phandle").read_bytes())[0]
assert (provider / "gpio-controller").is_file()
assert (provider / "#gpio-cells").read_bytes() == struct.pack(">I", 2)
for path in (left, right):
    assert struct.unpack(">III", path.read_bytes()) == (expected, 12, 1)
print("Both WSA consumers reference the same LPASS pinctrl GPIO12, GPIO_ACTIVE_LOW.")
PY
pin=$(awk '/^gpiochip/ {lpass=($0 ~ /platform\/6e80000.pinctrl/)} lpass&&$1=="gpio12" {print; count++} END{exit count!=1}' /sys/kernel/debug/gpio)
printf 'Read-only LPASS pin observation: %s\n' "$pin"
[[ $pin == *'out high func0'* ]]
printf 'Shared SD_N wiring matched; no shared votes dropped, shutdown assertion not tested.\n'
