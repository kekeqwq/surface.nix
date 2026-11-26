#!/usr/bin/env bash
# 0 dB scalar-only desktop duplex regression after the ordinary boot gate.
# Run as the desktop user, in a quiet room with no other playback/capture.
# Never restarts the holder/keeper, changes volume, or saves microphone PCM.
set -euo pipefail
umask 077
expected=${1:?expected boot closure}
output=${2:?new private output directory}
[[ $(readlink -e /run/booted-system) == "$expected" ]]
[[ $(readlink -e /run/current-system) == "$expected" ]]
[[ $(readlink -e /nix/var/nix/profiles/system) == "$expected" ]]
root=$(cd "$(dirname "$0")/.." && pwd)
export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
keeper=fullio-endpoint-keeper.service
holder=fullio-graph-holder.service
render=/proc/asound/card0/pcm0p/sub0/status
capture=/proc/asound/card0/pcm2c/sub0/status
trigger() { awk '/^state:/ {running=$2=="RUNNING"} /^trigger_time:/ {t=$2} END {if(running && t+0>0)print t}' "$render"; }
unit_property() { systemctl --user show "$keeper" --property="$1" --value; }
check_ready() {
    systemctl --user is-active --quiet "$holder"
    systemctl --user is-active --quiet "$keeper"
    [[ -z $(unit_property DropInPaths) ]]
    [[ $(readlink -e "$(unit_property FragmentPath)") == "$(readlink -e "$expected/etc/systemd/user/$keeper")" ]]
    [[ $(wpctl get-volume @DEFAULT_AUDIO_SINK@) == 'Volume: 1.00' ]]
    [[ $(<"$capture") == closed ]]
}
check_ready
mkdir -m 700 -- "$output"
play=$(trigger)
[[ -n $play ]]
invocation=$(unit_property InvocationID)
[[ $invocation =~ ^[0-9a-f]{32}$ && $invocation != 00000000000000000000000000000000 ]]
journalctl --user -b --no-pager -o cat "_SYSTEMD_INVOCATION_ID=$invocation" > "$output/keeper.log"
python3 - "$output/keeper.log" "$play" <<'PY'
import sys
from pathlib import Path
lines = Path(sys.argv[1]).read_text().splitlines()
trigger = sys.argv[2]
attempt = f'Endpoint arm attempt for trigger_time={trigger}'
armed = f'Endpoint armed for trigger_time={trigger}'
if lines.count(attempt) != 1 or lines.count(armed) != 1:
    raise SystemExit('not exactly one completed keeper transaction for the current playback epoch')
body = lines[lines.index(attempt)+1:lines.index(armed)]
for prefix in ('endpoint_db=0 q28=268435456 (0x10000000) gainstep=30',
               'Endpoint gain/GainStep: ACK', 'Endpoint unmute: ACK'):
    if sum(line.startswith(prefix) for line in body) != 1:
        raise SystemExit(f'missing or duplicate unity endpoint evidence: {prefix}')
PY
start=$(date '+%Y-%m-%d %H:%M:%S')
probe=
cleanup() {
    if [[ -n $probe ]]; then
        kill -TERM "$probe" 2>/dev/null || true
        wait "$probe" || true
    fi
}
trap cleanup EXIT
python3 "$root/scripts/fullio-level-probe.py" "$expected" "$output/levels.jsonl" --stimulus-tones > "$output/probe.log" 2>&1 &
probe=$!
# The replay itself requires 5 fresh, silent scalar windows and no other
# audio link to the speaker. Allow the capture path enough time to settle.
for ((i=0; i<25; i++)); do
    kill -0 "$probe"
    if [[ -f $output/levels.jsonl ]] && (( $(grep -c '"short_tone_amplitudes"' "$output/levels.jsonl" || true) >= 8 )); then break; fi
    sleep 1
done
(( i < 25 ))
bash "$root/tests/fullio-level-replay.sh" "$expected" "$output/levels.jsonl" 120 | tee "$output/replay.log"
kill -0 "$probe"
kill -TERM "$probe"
wait "$probe"
probe=
for ((i=0; i<20; i++)); do
    [[ $(<"$capture") != closed ]] || break
    sleep 1
done
check_ready
[[ $(trigger) == "$play" && $(unit_property InvocationID) == "$invocation" ]]
sudo -n journalctl -k -b --since "$start" --no-pager -o short-monotonic > "$output/kernel.log"
if grep -Ein 'Oops:|BUG:|WARNING:|Call trace:|XRUN|Broken pipe|CMD timeout|fatal|drain.*(fail|timeout)|wake.*(fail|timeout)' "$output/kernel.log"; then
    echo "Review kernel log in $output before qualifying desktop duplex" >&2
    exit 1
fi
printf 'Normal services, once-per-epoch unity ACK, 120 s scalar duplex and cleanup verified: %s\n' "$output"
