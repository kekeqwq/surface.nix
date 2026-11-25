#!/usr/bin/env bash
# Verify the real PipeWire MicArray profile of the exact capture-only fixture.
# No playback device or stream may succeed. Capture analysis is local and temporary.
set -euo pipefail
s=${1:?pass exact native build state directory}
lib=${2:?pass pinned libasound.so.2}
[[ $(hostname -s) == surface && $(id -un) == keke && $s == /home/keke/.local/state/fullio-* ]]
[[ $(readlink -e /run/booted-system) == $(readlink -e "$s/system") &&
   $(readlink /nix/var/nix/profiles/system) == system-20-link && $(<"$s/status") == 0 ]]
[[ $(uname -r) == *-surface-fullio-muted-test && $lib == /nix/store/*/lib/libasound.so.2 ]]
for svc in sshd greetd; do systemctl is-active --quiet "$svc"; done
systemctl --user is-active --quiet wireplumber
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-muted-test && -e $sound/microsoft,denali-fullio-capture-only &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test && ! -e $sound/microsoft,denali-fullio-dsp-start-audit ]]
[[ $(tr -d '\0' < "$sound/model") == X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0 ]]
wp=$(systemctl --user show -p MainPID --value wireplumber)
[[ $wp =~ ^[1-9][0-9]*$ ]]
tr '\0' '\n' < "/proc/$wp/environ" | grep -Fx "XDG_STATE_HOME=/run/user/$(id -u)/fullio-mic-state" >/dev/null
node=alsa_input.platform-sound.HiFi__Mic__source
mode=${3:-verify-render-denial}
[[ $mode == verify-render-denial || $mode == capture-only ]]
if [[ $mode == verify-render-denial ]]; then
playback=$(awk '/MultiMedia1 Playback/ && /playback [1-9]/ {print $1}' /proc/asound/pcm)
[[ $playback =~ ^([0-9]+)-([0-9]+):$ ]]
printf -v pcm 'hw:%d,%d' "$((10#${BASH_REMATCH[1]}))" "$((10#${BASH_REMATCH[2]}))"
python3 - "$lib" "$pcm" <<'PY'
import ctypes, errno, sys
alsa = ctypes.CDLL(sys.argv[1])
pcm = ctypes.c_void_p()
rc = alsa.snd_pcm_open(ctypes.byref(pcm), sys.argv[2].encode(), 0, 1)
if rc == 0:
    alsa.snd_pcm_close(pcm)
    sys.exit("Playback open unexpectedly succeeded; no params or writes attempted")
if rc != -errno.EOPNOTSUPP:
    sys.exit(f"Unexpected playback open error {rc}")
print("Capture-only kernel rejects render PCM open with -EOPNOTSUPP before hw_params.")
PY
fi
umask 077
work=$(mktemp -d "${XDG_RUNTIME_DIR:?}/fullio-mic-desktop.XXXXXX")
cleanup() { rm -rf -- "$work"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for _ in {1..25}; do
    timeout 4 pw-dump > "$work/objects.json"
    grep -Fq "$node" "$work/objects.json" && break
    sleep .3
done
python3 - "$work/objects.json" "$node" <<'PY'
import json,sys
props = [x.get("info", {}).get("props", {}) for x in json.load(open(sys.argv[1]))]
src = [p for p in props if p.get("node.name") == sys.argv[2] and p.get("media.class") == "Audio/Source"]
if len(src) != 1:
    sys.exit(f"Mic-only UCM source missing: {[(p.get('node.name'), p.get('media.class')) for p in props if p.get('media.class', '').startswith('Audio/')]}")
if any(p.get("media.class") == "Audio/Sink" and p.get("node.name", "").startswith("alsa_output.") for p in props):
    sys.exit("Unexpected hardware audio sink; capture not started")
pos = src[0].get("audio.position")
if isinstance(pos, str):
    pos = pos.strip(" []").replace(",", " ").split()
if pos != ["FL", "FR"] or str(src[0].get("audio.channels")) != "2":
    sys.exit(f"Unexpected Mic channel format: {pos}")
print("Desktop PipeWire exposes the native MicArray as [FL, FR] and no hardware sink.")
PY
for pass in 1 2; do
    rc=0
    timeout -s INT -k 2s 5s pw-record --target "$node" --rate 48000 --channels 2 --channel-map FL,FR --format s16 "$work/mic.wav" >"$work/record.log" 2>&1 || rc=$?
    if [[ $rc != 124 || ! -s $work/mic.wav || -s $work/record.log ]]; then
        printf 'pw-record pass %s failed, rc=%s; no data left behind.\n' "$pass" "$rc" >&2
        head -15 "$work/record.log" >&2
        exit 1
    fi
    python3 "$s/hardware/tests/fullio-micarray.py" "$work/mic.wav"
    rm -f -- "$work/mic.wav"
    printf 'Desktop stereo MicArray capture/close pass %s complete.\n' "$pass"
    sleep .3
done
printf 'Desktop native MicArray delivered varying stereo twice; no clips retained or speaker playback tested.\n'
