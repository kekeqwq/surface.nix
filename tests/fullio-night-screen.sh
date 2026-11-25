#!/usr/bin/env bash
# Shut off displays in the existing Niri session of an exact one-shot FullIO boot.
# No services, configuration, backlight or kernel state are installed/edited.
set -euo pipefail
s=${1:?pass exact native build state directory}
[[ $(id -u) == 0 && $(hostname -s) == surface && $s == /home/keke/.local/state/fullio-* ]]
[[ -L $s/system && $(<"$s/status") == 0 ]]
expected=$(readlink -e "$s/system")
base=$(readlink -e /nix/var/nix/profiles/system-20-link)
[[ $(readlink /nix/var/nix/profiles/system) == system-20-link && $expected != "$base" ]]
[[ $(readlink -e /run/booted-system) == "$expected" && $(readlink -e /run/current-system) == "$expected" ]]
[[ $(uname -r) == *-surface-fullio ]]
dt=/sys/firmware/devicetree/base
[[ -e $dt/sound/microsoft,denali-fullio-reference-render &&
   -e $dt/soc@0/soundwire@6b10000/speaker@0,0/qcom,denali-fullio-reference-codec &&
   -e $dt/soc@0/soundwire@6b10000/speaker@0,1/qcom,denali-fullio-reference-codec ]]
for service in sshd greetd; do systemctl is-active --quiet "$service"; done
niri=/run/current-system/sw/bin/niri
[[ -x $niri ]]
uid=$(id -u keke)
runtime=/run/user/$uid
shopt -s nullglob
for ((attempt=0; attempt<30; attempt++)); do
    active=()
    for sock in "$runtime"/niri.*.sock; do
        [[ -S $sock && ! -L $sock && $(stat -c %u "$sock") == "$uid" ]] || continue
        [[ ${sock##*/} =~ ^niri\.[[:alnum:]_-]+\.([0-9]+)\.sock$ ]] || continue
        pid=${BASH_REMATCH[1]}
        if [[ $(ps -o uid= -p "$pid" | tr -d ' ') == "$uid" && $(<"/proc/$pid/comm") == niri ]]; then
            active+=("$sock")
        fi
    done
    if ((${#active[@]} > 1)); then
        echo 'Night screen: multiple live Niri sessions; no action sent.' >&2
        exit 2
    fi
    if ((${#active[@]} == 1)) &&
       timeout 2 runuser -u keke -- env XDG_RUNTIME_DIR="$runtime" NIRI_SOCKET="${active[0]}" "$niri" msg outputs >/dev/null; then
        timeout 5 runuser -u keke -- env XDG_RUNTIME_DIR="$runtime" NIRI_SOCKET="${active[0]}" "$niri" msg action power-off-monitors
        printf 'Night screen: Niri accepted power-off on the verified FullIO fixture; Gen20 untouched.\n'
        exit 0
    fi
    sleep 1
done
printf 'Night screen: no ready Niri session; display policy unchanged.\n' >&2
exit 2
