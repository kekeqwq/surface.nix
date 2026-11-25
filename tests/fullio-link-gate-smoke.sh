#!/usr/bin/env bash
# Verify a seeded policy latch rejects new WSA streams without a real bus fault.
set -euo pipefail
s=${1:?pass exact native build state directory}
mode=${2:-startup}
[[ $mode == startup || $mode == pre-pm ]]
[[ $(readlink -e /run/current-system) == $(readlink -e /run/booted-system) ]]
[[ $(id -u) == 0 && $(hostname -s) == surface && $s == /home/keke/.local/state/fullio-* ]]
[[ $(<"$s/status") == 0 && $(readlink -e /run/booted-system) == $(readlink -e "$s/system") &&
   $(readlink /nix/var/nix/profiles/system) == system-20-link && $(uname -r) == *-surface-fullio-muted-test ]]
for svc in sshd greetd; do systemctl is-active --quiet "$svc"; done
sound=/sys/firmware/devicetree/base/sound
swr=/sys/firmware/devicetree/base/soc@0/soundwire@6b10000
[[ -e $sound/microsoft,denali-fullio-muted-test && -e $sound/microsoft,denali-fullio-clock-off-audit &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test && ! -e $sound/microsoft,denali-fullio-dsp-start-audit &&
   -e $swr/qcom,denali-fullio-link-gate && -e $swr/qcom,denali-fullio-link-gate-test ]]
log=$(journalctl -kb --no-pager -o cat)
grep -Fq 'FullIO test: seed new-stream denial without a hardware fault' <<< "$log"
[[ $(grep -Fc 'FullIO SoundWire new streams locked: first link error -125' <<< "$log") == 1 ]]
! grep -Eq 'SWR bus clsh|Oops:|BUG:|Kernel panic|MAX_RETRY' <<< "$log"
shopt -s nullglob
pcms=(/proc/asound/card*/pcm*/sub*/status)
((${#pcms[@]} >= 2))
check_idle() {
    local f d
    for f in "${pcms[@]}"; do [[ $(<"$f") == closed ]] || return 2; done
    for d in /sys/bus/platform/devices/{6b00000.codec,6b10000.soundwire} /sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:{0,1}; do
        [[ $(<"$d/power/control") == auto ]] || return 2
        [[ ! -f $d/status || $(<"$d/status") == Attached ]] || return 2
    done
    for d in /sys/bus/platform/devices/{6b00000.codec,6b10000.soundwire} /sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:{0,1}; do
        [[ $(<"$d/power/runtime_status") == suspended ]] || return 1
    done
}
check_idle
inst=
cleanup() {
    local rc=$?
    if [[ -n $inst ]]; then
        printf '0\n' > "$inst/tracing_on" || rc=1
        rmdir "$inst" || rc=1
    fi
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ $mode == pre-pm ]]; then
    path=/sys/kernel/tracing/instances/fullio-link-gate-$$
    mkdir "$path"
    inst=$path
    printf '0\n' > "$inst/tracing_on"
    ev=$inst/events/rpm/rpm_status
    printf '%s\n' 'name == "6b00000.codec" || name == "6b10000.soundwire" || name == "sdw:1:0:0217:0204:00:0" || name == "sdw:1:0:0217:0204:00:1"' > "$ev/filter"
    printf '1\n' > "$ev/enable"
    printf '1\n' > "$inst/tracing_on"
    check_idle
fi
cursor=$(journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
al=/nix/store/90kcqvgk6gak7riqymc2sswa9bnmx7p9-alsa-utils-1.2.16/bin
lib=/nix/store/hs142rv75ssn0g6di4ivp94ii7kgywdp-alsa-lib-1.2.16.1/lib/libasound.so.2
for pass in 1 2; do
    runuser -u keke -- bash "$s/hardware/tests/fullio-mute-smoke.sh" "$al" "$lib" link-gate
    if [[ $mode == pre-pm ]]; then
        grep 'rpm_status:' "$inst/trace" && exit 2
        check_idle
        continue
    fi
    # ASoC takes component PM refs before calling DAI startup. Require
    # natural autosuspend, not uninterrupted runtime suspension.
    deadline=$((SECONDS + 15))
    while :; do
        log=$(journalctl -kb --no-pager -o cat --after-cursor "$cursor")
        if grep -Eq 'SWR bus clsh|Oops:|BUG:|Kernel panic|MAX_RETRY' <<< "$log"; then exit 2; fi
        rc=0
        check_idle || rc=$?
        ((rc == 0)) && break
        ((rc == 1 && SECONDS < deadline)) || exit 2
        sleep .25
    done
done
log=$(journalctl -kb --no-pager -o short-monotonic --after-cursor "$cursor")
printf '%s\n' "$log"
! grep -Eq 'GRAPH_START|FullIO PCM_CNV|SWR bus clsh|Oops:|BUG:|Kernel panic|MAX_RETRY' <<< "$log"
if [[ $mode == pre-pm ]]; then
    [[ $(grep -Ec 'WSA Playback:.*ASoC error \(-131\).*__soc_pcm_open' <<< "$log") == 2 ]]
    ! grep -Eq '6b10000\.soundwire:.*snd_soc_dai_startup' <<< "$log"
    printf '0\n' > "$inst/tracing_on"
    ! grep -q 'rpm_status:' "$inst/trace"
    printf 'Two fresh requests rejected before component PM; no WSA runtime-PM transition or DSP START.\n'
else
    [[ $(grep -Ec '6b10000\.soundwire:.*ASoC error \(-131\).*snd_soc_dai_startup' <<< "$log") == 2 ]]
    printf 'Two fresh requests rejected at WSA startup; no DSP START, attachment preserved, normal autosuspend restored.\n'
fi
