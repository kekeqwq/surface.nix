#!/usr/bin/env bash
# PA-off observation only. Keep raw DIAG data private and transient.
set -euo pipefail
umask 077
s=${1:?pass exact native build state}
collector=${2:?pass reviewed native fullio-qrtr-lpass-discovery binary}
repo=$s/hardware
bash "$repo/tests/fullio-boot-preflight.sh" "$s" ring-dma-taps
[[ -x $collector ]]
prior=$(journalctl -kb --no-pager -o cat)
if grep -Eq 'FullIO independent ring|FullIO attached ring|PCM ring quarantined|snd_soc_pcm_component_prepare\(' <<< "$prior"; then
    echo 'Audit may have run already; not retrying.' >&2
    exit 2
fi
work=$(mktemp -d /run/fullio-dma-taps.XXXXXX)
pid=
cleanup() {
    if [[ -n $pid ]]; then kill -TERM "$pid" 2>/dev/null || true; wait "$pid" || true; fi
    rm -rf -- "$work"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
cursor=$(journalctl -kb -n 0 --show-cursor --no-pager | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
"$collector" --capture-1586 "$work/packets" >"$work/collector.log" 2>&1 &
pid=$!
for ((i=0; i<120; ++i)); do
    grep -q 'capture armed.*monotonic origin=' "$work/collector.log" && break
    kill -0 "$pid" 2>/dev/null || break
    sleep .05
done
if ! grep -q 'capture armed.*monotonic origin=' "$work/collector.log" || ! kill -0 "$pid" 2>/dev/null; then
    head -100 "$work/collector.log"
    exit 2
fi
rc=0
bash "$repo/tests/fullio-ring-map-smoke.sh" "$s" ring-dma-taps || rc=$?
collector_rc=0
wait "$pid" || collector_rc=$?
pid=
head -100 "$work/collector.log"
bash "$repo/tests/fullio-boot-preflight.sh" "$s" ring-dma-taps
((rc == 0 && collector_rc == 0))
grep -Fq 'zero mask sent' "$work/collector.log"
# On a logger isolation contrast, zero 0x1586 traffic can be a
# meaningful negative. Retain the positive precondition elsewhere.
sound=/sys/firmware/devicetree/base/sound
records='[1-9][0-9]*'
if [[ -e $sound/microsoft,denali-fullio-feedback-log-off-audit ]]; then
    [[ -e $sound/microsoft,denali-fullio-rx0-tag-audit && -e $sound/microsoft,denali-fullio-rx0-log-off-audit ]]
    records='[0-9]+'
fi
grep -Eq "LPASS data datagrams=[0-9]+, .*0x1586=$records, .*invalid=0, unmatched=0, oversize=0\$" "$work/collector.log"
! grep -Fq 'LPASS data datagrams=4096,' "$work/collector.log"
origin=$(awk -F= '/capture armed.*monotonic origin=/{print $NF}' "$work/collector.log")
read -r start stop < <(journalctl -kb --after-cursor "$cursor" --no-pager -o cat | awk '
    /FullIO tap host window:/ { for (i=1; i<=NF; i++) {
        if ($i ~ /^start_ack_ns=/) { split($i,a,"="); start=a[2] }
        if ($i ~ /^stop_begin_ns=/) { split($i,a,"="); stop=a[2] }
    } }
    END { if (start && stop) print start,stop }')
read -r begin end < <(python3 - "$origin" "$start" "$stop" <<'PY'
from decimal import Decimal
import sys
origin, start, stop = map(Decimal, sys.argv[1:])
start, stop = (v / 1_000_000_000 for v in (start, stop))
if not origin <= start < stop <= origin + 4:
    raise SystemExit('collector did not cover the complete DSP audit window')
print(start, stop)
PY
)
read_count() {
    local count
    count=$(awk -v key="$1" '/^LPASS data datagrams=/ {
        for (i=1; i<=NF; i++) {
            split($i,v,"[=,]"); if (v[1] == key && v[2] ~ /^[0-9]+$/) print v[2]
        }
    }' "$work/collector.log")
    [[ $count =~ ^[0-9]+$ ]] || return 1
    printf '%s\n' "$count"
}
rx_args=()
rx0_count=$(read_count tap1)
if [[ -e $sound/microsoft,denali-fullio-rx0-tag-audit ]]; then
    rx_args+=(--rx0-tag-audit --expected-legacy-records "$rx0_count")
    rx0_count=$(read_count tap4)
fi
python3 "$repo/tests/fullio-feedback-samples.py" --archive "$work/packets" \
    --allow-empty-archive --report-rx0 --expected-rx0-records "$rx0_count" "${rx_args[@]}" \
    --receive-window "$origin" "$begin" "$end"
