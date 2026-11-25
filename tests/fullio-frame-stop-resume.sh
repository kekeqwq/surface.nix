#!/usr/bin/env bash
# One ordinary runtime-PM vote on the controller or left codec. No PCM, reset, or retry.
set -euo pipefail
s=${1:?pass exact native build state directory}
mode=${2:-controller}
case $mode in controller|left) ;; *) exit 64 ;; esac
repo=$s/hardware
master=/sys/bus/platform/devices/6b10000.soundwire
macro=/sys/bus/platform/devices/6b00000.codec
swr=/sys/firmware/devicetree/base/soc@0/soundwire@6b10000
left=/sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:0
right=/sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:1
[[ $EUID == 0 && -e $swr/qcom,denali-fullio-wait-frame-stop ]]
[[ $(<"$master/supplier:platform:6b00000.codec/runtime_pm") == 1 ]]
boot_id=$(</proc/sys/kernel/random/boot_id)
[[ $boot_id =~ ^[0-9a-f-]{36}$ ]]
if [[ $mode == controller ]]; then
    target=$master
    bash "$repo/tests/fullio-frame-stop-smoke.sh" "$s"
else
    target=$left
    [[ -d $s/controller-vote-$boot_id ]]
    bash "$repo/tests/fullio-boot-preflight.sh" "$s" passive-link
    prior=$(journalctl -kb --no-pager -o cat)
    [[ $(grep -Fc 'FullIO PM transition after-exit-clock-stop: clash=0 frame=1 result=0 slaves=0x00000014' <<< "$prior") == 1 ]]
    for d in "$master" "$macro" "$left" "$right"; do
        [[ $(<"$d/power/control") == auto && $(<"$d/power/runtime_status") == suspended ]]
    done
fi
mkdir "$s/$mode-vote-$boot_id"
cursor=$(journalctl -kb -n 0 --show-cursor --no-pager | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
inst=/sys/kernel/tracing/instances/fullio-rpm-vote-$$
mkdir "$inst"
cleanup() {
    local rc=$?
    printf '0\n' > "$inst/tracing_on" || rc=1
    rmdir "$inst" || rc=1
    if ((rc)); then printf 'Observation failed; no PM recovery or retry.\n' >&2; fi
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '0\n' > "$inst/tracing_on"
printf 'mono\n' > "$inst/trace_clock"
printf '64\n' > "$inst/buffer_size_kb"
for e in rpm_resume rpm_status; do
    printf 'name == "%s" || name == "%s" || name == "%s" || name == "%s"\n' \
        "${master##*/}" "${macro##*/}" "${left##*/}" "${right##*/}" > "$inst/events/rpm/$e/filter"
    printf '1\n' > "$inst/events/rpm/$e/enable"
done
for e in regcache_sync regmap_reg_write; do
    printf 'name == "%s" || name == "%s"\n' "${left##*/}" "${right##*/}" > "$inst/events/regmap/$e/filter"
    printf '1\n' > "$inst/events/regmap/$e/enable"
done
printf '1\n' > "$inst/tracing_on"
printf 'FullIO %s PM vote begin\n' "$mode" > "$inst/trace_marker"
printf 'on\n' > "$target/power/control"
printf 'FullIO %s PM vote returned\n' "$mode" > "$inst/trace_marker"
# Collect post-exit hardware status dispatch, not just synchronous PM return.
sleep 0.2
printf '0\n' > "$inst/tracing_on"
trace=$(<"$inst/trace")
# Keep register contents private; retain timestamps and counts to localize replay.
printf '%s\n' "$trace" | awk '/regmap_reg_write:/ {sub(/ reg=.*/, " [register/value omitted]")} {print}'
log=$(journalctl -kb --after-cursor "$cursor" --no-pager -o short-monotonic)
printf '%s\n' "$log"
if grep -Eq 'new streams locked|clash snapshot|SWR bus clsh|MAX_RETRY|failed to exit clock stop|link failed to connect|Oops:|BUG:|Kernel panic' <<< "$log"; then exit 2; fi
awk -v mode="$mode" -v left="${left##*/}" -v right="${right##*/}" '
    /^# entries-in-buffer\/entries-written:/ {split($3,n,"/"); complete=(n[1] == n[2])}
    /rpm_status: 6b00000\.codec status=RPM_ACTIVE/ {++macro; m=NR}
    /rpm_status: 6b10000\.soundwire status=RPM_ACTIVE/ {++master; c=NR}
    /rpm_status:|rpm_resume:|regmap_reg_write:|regcache_sync:/ && index($0,right) {++unexpected}
    /rpm_status:|rpm_resume:|regmap_reg_write:|regcache_sync:/ && index($0,left) {
        if (mode == "controller") ++unexpected
        if (/regcache_sync:.*status=start$/) {++starts; s=NR}
        if (/regcache_sync:.*status=stop$/) {++stops; t=NR}
        if (/rpm_status:.*status=RPM_ACTIVE$/) {++pairstate; a=NR}
        if (/regmap_reg_write:/) {++writes; if (starts != 1 || stops) ++unexpected}
    }
    END {
        print "Left codec regcache sections:", starts+0, stops+0, "hardware write events:", writes+0
        exit !(complete && macro == 1 && master == 1 && m < c && !unexpected &&
               (mode == "controller" || (starts == 1 && stops == 1 && pairstate == 1 && c < s && s < t && t < a)))
    }
' <<< "$trace"
awk '
    /FullIO PM transition before-exit-clock-stop: .*clash=0 frame=1 result=0 slaves=0x00000014/ {++before; a=NR}
    /FullIO PM transition after-exit-clock-stop: .*clash=0 frame=1 result=0 slaves=0x00000014/ {++after; b=NR}
    END {exit !(before == 1 && after == 1 && a < b)}
' <<< "$log"
[[ $(<"$master/power/runtime_status") == active && $(<"$macro/power/runtime_status") == active ]]
for d in "$left" "$right"; do
    expected=suspended
    [[ $d != "$target" ]] || expected=active
    [[ $(<"$d/power/runtime_status") == "$expected" && $(<"$d/status") == Attached ]]
done
bash "$repo/tests/fullio-boot-preflight.sh" "$s" passive-link
printf 'auto\n' > "$target/power/control"
printf '%s PM vote passed; normal auto policy restored. No PCM opened.\n' "$mode"
