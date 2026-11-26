#!/usr/bin/env bash
# Independent acoustic pickup, recorded on Surface via an explicit USB ALSA device.
# Does not touch the built-in render/MicArray graph or mixer.
set -euo pipefail
umask 077
pcm=${1:?supply ALSA capture device as CARD,DEVICE (numeric)}
log=${2:?new private scalar output path}
secs=${3:?seconds of capture}
[[ $pcm =~ ^([0-9]{1,2}),([0-9]{1,2})$ && $secs =~ ^[0-9]{1,3}$ ]] || exit 2
card=$((10#${pcm%,*}))
dev=$((10#${pcm#*,}))
secs=$((10#$secs))
((secs >= 5 && secs <= 900)) || exit 2
id=pcmC${card}D${dev}c
sys=$(readlink -e "/sys/class/sound/$id")
[[ -e /dev/snd/$id && $sys == /sys/devices/* ]]
usb_card() {
  local node=$1 subsystem driver found_driver=0
  while [[ $node == /sys/devices/* ]]; do
    subsystem=$(readlink -f "$node/subsystem") || return 1
    driver=$(readlink -f "$node/driver") || return 1
    if [[ $subsystem == /sys/bus/usb && ${driver##*/} == snd-usb-audio ]]; then
      found_driver=1
    fi
    if ((found_driver)) && [[ $subsystem == /sys/bus/usb && -r $node/idVendor && -r $node/idProduct ]]; then
      printf '%s vid=%s pid=%s\n' "$node" "$(<"$node/idVendor")" "$(<"$node/idProduct")"
      return
    fi
    node=${node%/*}
  done
  return 1
}
identity=$(usb_card "$sys") || { echo 'Refusing non-USB or unverified sound device' >&2; exit 1; }
printf 'Independent pickup: %s %s (verify physical placement and fixed gain)\n' "$id" "$identity" >&2
# hw: forbids ALSA plug conversion or automatic fallback; require native stereo.
# A fixed-duration reader and ALSA overrun fatal errors bound the test.
"${ARECORD:-arecord}" --fatal-errors -q -D "hw:$card,$dev" -t raw -f S16_LE -c 2 -r 48000 -d "$secs" |
  python3 "$(dirname "$0")/fullio-external-levels.py" "$log" --seconds "$secs" --strict
[[ $(readlink -e "/sys/class/sound/$id") == "$sys" && $(usb_card "$sys") == "$identity" ]]
