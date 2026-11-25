#!/usr/bin/env bash
# Observe APSS GPIO204/205 only. Never claim, mux, write or pulse a GPIO.
set -euo pipefail
s=${1:?pass exact FullIO boot directory}
repo=$(dirname -- "${BASH_SOURCE[0]}")
bash "$repo/fullio-boot-preflight.sh" "$s" "${2:-start-audit}"
node=/sys/firmware/devicetree/base/soc@0/pinctrl@f100000
dev=/sys/bus/platform/devices/f100000.pinctrl
[[ $(tr -d '\0' < "$node/compatible") == qcom,x1e80100-tlmm ]]
[[ -e $node/gpio-controller && $(readlink -e "$dev/driver") == /sys/bus/platform/drivers/x1e80100-tlmm ]]
python3 - "$node" <<'PY'
from pathlib import Path
import struct, sys
node = Path(sys.argv[1])
read = lambda name: [v for (v,) in struct.iter_unpack('>I', (node / name).read_bytes())]
provider, offset, pin, count = read('gpio-ranges')
assert [provider] == read('phandle') and offset == pin == 0 and count > 205
reserved = read('gpio-reserved-ranges')
assert len(reserved) % 2 == 0
assert not any(start <= n < start + size for start, size in zip(reserved[::2], reserved[1::2]) for n in (204, 205))
print('GPIO204/205 are within the APSS range and not reserved by this DT.')
PY
for p in clocks power-domains; do [[ ! -e $node/$p ]]; done
printf 'APSS provider runtime status: %s\n' "$(<"$dev/power/runtime_status")"
pins=$(awk '/^gpiochip/ {apss=($0 ~ /platform\/f100000\.pinctrl/)}
    apss&&($1=="gpio204" || $1=="gpio205") {print; count++}
    END {exit count!=2}' /sys/kernel/debug/gpio)
printf '%s\n' "$pins"
mux=/sys/kernel/debug/pinctrl/f100000.pinctrl/pinmux-pins
for n in 204 205; do grep -E "^pin $n \(GPIO_$n\): UNCLAIMED$" "$mux"; done
printf 'No GPIO changed. Board connectivity, polarity and cutoff timing remain unverified.\n'
