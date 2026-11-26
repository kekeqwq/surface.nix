#!/usr/bin/env bash
# Reproduce a same-graph level sag with the running scalar-only session probe.
set -euo pipefail
umask 077
closure=${1:?expected boot closure}
log=${2:?private level-probe JSONL path}
duration=${3:-120}
[[ $(readlink -e /run/booted-system) == "$closure" ]]
[[ $duration =~ ^[1-9][0-9]{0,2}$ ]] && (( duration >= 32 && duration <= 600 && duration % 4 == 0 ))
export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
sink=alsa_output.platform-sound.HiFi__Speaker__sink
name=denali-repeat-probe-$$
# Don't start over any other program or mix it into the result if it resumes.
exclusive() {
    pw-link -l | awk -v sink="$sink" -v own="$1" '
        $0 !~ /^ / {play = ($0 == sink ":playback_FL" || $0 == sink ":playback_FR")}
        play && $1 == "|<-" {if ($2 ~ /^fullio-graph-holder:output_F[RL]$/) held++;
                             else if (own == "" || index($2, own ":output_") != 1) bad=1}
        END {exit (bad || held != 2)}'
}
work=$(mktemp -d "$XDG_RUNTIME_DIR/denali-repeat-probe.XXXXXX")
pid=
cleanup() {
    if [[ -n $pid ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
    rm -rf -- "$work"
}
trap cleanup EXIT
stim=(--seconds "$duration")
[[ -z ${STIMULUS_PEAK:-} ]] || stim+=(--peak "$STIMULUS_PEAK")
python3 "$(dirname "$0")/fullio-level-stimulus.py" "$work/probe.wav" "${stim[@]}"
exclusive ''
lo=$(python3 - "$log" <<'PY'
from collections import deque
import json, sys, time
with open(sys.argv[1]) as stream:
    rows = deque((r for line in stream if 'monitor' in (r := json.loads(line))), maxlen=5)
now = time.monotonic()
assert len(rows) == 5 and now - rows[-1]['mono'] < 2, 'probe not writing fresh samples'
assert all(max(r['monitor']['peak']) == 0 and 'tone_amplitudes' in r['mic'] for r in rows), 'tone probe not idle'
for key in ('pcm', 'capture_pcm'):
    states = [row.get(key, {}) for row in rows]
    triggers = {state.get('trigger_time') for state in states}
    assert len(triggers) == 1 and None not in triggers and '' not in triggers, f'{key} epoch not settled'
    assert all(state.get('state') == 'RUNNING' for state in states), f'{key} not settled in RUNNING'
print(now)
PY
)
printf 'Start: %s mono=%s\n' "$(date -Iseconds)" "$lo"
timeout "$((duration+5))" pw-play --target "$sink" -P "node.name=$name" --volume 1 "$work/probe.wav" & pid=$!
while kill -0 "$pid" 2>/dev/null; do
    exclusive "$name" || { echo 'Another program appeared; stopping only the test player' >&2; exit 1; }
    sleep 2
done
wait "$pid"
pid=
sleep 2
hi=$(python3 -c 'import time; print(time.monotonic())')
python3 - "$log" "$lo" "$hi" "$duration" "$(dirname "$0")" <<'PY'
import json, math, statistics as stats, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[5]).resolve()))
from fullio_replay_bands import band_gate
lo, hi, duration = map(float, sys.argv[2:5])
with open(sys.argv[1]) as stream:
    rows = [r for line in stream if 'monitor' in (r := json.loads(line)) and lo - 6 < r['mono'] < hi]
test = [r for r in rows if lo < r['mono'] < hi]
assert test and len({r['pcm'].get('trigger_time') for r in test}) == 1
assert all(r['pcm'].get('state') == 'RUNNING' for r in test)
assert all(r.get('capture_pcm', {}).get('state') == 'RUNNING' for r in test), 'capture PCM not continuously running'
assert len({r['capture_pcm'].get('trigger_time') for r in test}) == 1, 'capture PCM trigger changed'
full = [r for r in test if all(x is not None and x > -33 for x in r['monitor']['rms_dbfs'])]
# JSON windows are slightly longer than one second; allow that drift,
# not silence or a discontinuity inside the active stimulus.
assert abs(len(full) - duration) <= max(4, int(duration / 60)), ('incomplete tone', len(full))
assert all(b['mono'] - a['mono'] < 1.5 for a, b in zip(full, full[1:])), 'gap in stimulus'
assert all(r[key]['frames'] > 40000 for r in full for key in ('monitor', 'mic')), 'lost frames'
assert all(max(r[key]['peak']) < 32767 for r in rows for key in ('monitor', 'mic')), 'clipped PCM window'
# Each tone is unique to one of the output channels. MicArray channels
# are two pickups of the mixed acoustic field, not speaker terminals.
frequencies = ('203', '206', '449', '454', '1009', '1017')
def analyze(metric):
    changes = {}
    for j, f in enumerate(frequencies):
        ch = j % 2
        amp = lambda row, key: row[key][metric][f]
        before = [max(amp(r,'mic')) for r in rows if r['mono'] < lo and metric in r['mic']]
        base = full[2:12]
        mic_ref = stats.median(max(amp(r,'mic')) for r in base)
        monitor_ref = stats.median(amp(r,'monitor')[ch] for r in base)
        if not before or mic_ref < 4 * max(.1, stats.median(before)) or monitor_ref < 10:
            continue
        if not all(abs(20 * math.log10(max(.01,amp(r,'monitor')[ch]) / monitor_ref)) < 1 for r in full[2:-2]):
            continue
        transfer = lambda r: 20 * math.log10(max(.01, max(amp(r,'mic'))) / amp(r,'monitor')[ch])
        reference = stats.median(map(transfer, base))
        # Skip two transition windows on either edge; include every
        # complete block in between (including the final full block).
        changes[f] = [stats.median(map(transfer, full[i:i+10])) - reference
                      for i in range(2, len(full) - 11, 10)]
    for i, values in enumerate(zip(*changes.values())):
        print(metric, full[2+10*i]['time'], {f: round(v, 2) for f, v in zip(changes, values)})
    try:
        f, window, worst = band_gate(frequencies, changes)
    except ValueError as exc:
        print(metric, exc, changes)
        return None
    print(metric, 'worst band in a ~10-second block:', f, 'Hz, block', window, ':', round(worst, 3), 'dB')
    return worst

long = analyze('tone_amplitudes')
short = analyze('short_tone_amplitudes')
assert short is not None, 'insufficient short-window measurement'
assert short >= -3, 'short-window acoustic attenuation reproduced'
assert long is not None and long >= -3, 'long-window-only uncertainty; check phase/rate'
PY
