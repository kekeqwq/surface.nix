#!/usr/bin/env bash
# A single PA-off supply observation. No DSP START or PA/rail/gain writes.
set -euo pipefail
s=${1:?pass exact native build state directory}
repo=$s/hardware
bash "$repo/tests/fullio-boot-preflight.sh" "$s" vphx
prior=$(journalctl -kb --no-pager -o cat)
if grep -Fq 'FullIO PA-off VPHX_STATUS=' <<< "$prior"; then
    echo 'VPHX probe already ran in this boot; not retrying.' >&2
    exit 2
fi
cursor=$(journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
al=/nix/store/90kcqvgk6gak7riqymc2sswa9bnmx7p9-alsa-utils-1.2.16/bin
lib=/nix/store/hs142rv75ssn0g6di4ivp94ii7kgywdp-alsa-lib-1.2.16.1/lib/libasound.so.2
rc=0
runuser -u keke -- bash "$repo/tests/fullio-mute-smoke.sh" "$al" "$lib" || rc=$?
log=$(journalctl -kb --no-pager -o short-monotonic --after-cursor "$cursor")
grep -E 'FullIO PA-off VPHX_STATUS|FullIO mute survived|ASoC error|Oops:|SWR bus clsh' <<< "$log" || true
((rc == 0))
! grep -Eq 'FullIO .*START/STOP|FullIO start audit|GRAPH_START|PA shutdown not fully verified' <<< "$log"
for amp in 0 1; do
    values=$(awk -F= -v amp="$amp" '$0 ~ "sdw:1:0:0217:0204:00:" amp ": FullIO PA-off VPHX_STATUS=" {print $NF}' <<< "$log" | sort -u)
    [[ $values =~ ^(0x[0-9a-f]+|0)$ ]]
    printf 'WSA UID %s: stable VPHX status %s (reference expected 0x2).\n' "$amp" "$values"
done
bash "$repo/tests/fullio-boot-preflight.sh" "$s" vphx
