#!/usr/bin/env bash
# Native build only. Never changes a profile, switch or running system.
set -euo pipefail
s=${1:?pass native fixture work directory}
fixture=${2:-fullio-link-gate-test}
[[ $(hostname -s) == surface && $(uname -m) == aarch64 && $(id -un) == keke ]]
[[ $s =~ ^/home/keke/\.local/state/fullio-[a-zA-Z0-9-]+$ && -f $s/hardware/flake.nix && $fixture =~ ^fullio-[a-z0-9-]+$ ]]
[[ ! -e $s/status && ! -e $s/system ]]
[[ $(id -un) == keke && -d $HOME/Repos/flakes && -f $s/booted-system ]]
trap 'rc=$?; printf "%s\n" "$rc" > "$s/status"; exit "$rc"' EXIT
sudo_run() { sudo -n -- "$@"; }
expected=$(<"$s/booted-system")
[[ $expected == /nix/store/*-nixos-system-surface-* ]]
[[ $expected == "$(readlink -f /run/booted-system)" ]]
original=$expected
[[ $original == "$(readlink -f /run/current-system)" &&
   $(readlink -f /nix/var/nix/profiles/system) == "$(readlink -e /nix/var/nix/profiles/system-20-link)" ]]
gen20=/nix/var/nix/profiles/system-20-link
profile_before=$(readlink "$gen20")
default_before=$(sudo_run bootctl status --no-pager | awk '/^Default Boot Loader Entry:/ {d=1;next} d&&$1=="id:" {print $2;d=0}')
[[ $default_before == nixos-3aae9950e05724a6f75ac7703476b7b4d3ceb0f8ea5bba8665aace82d3a98a62.conf ]]
src=$(readlink -e "$s/hardware")
[[ $src =~ ^/home/keke/\.local/state/fullio-[a-zA-Z0-9-]+/hardware$ ]]
apply="c: (c.extendModules { modules = [ (builtins.getFlake \"path:$src\").nixosModules.$fixture ]; }).config.system.build.toplevel.drvPath"
drv=$(nix eval "path:$HOME/Repos/flakes#nixosConfigurations.surface" --no-write-lock-file --impure --apply "$apply" --raw)
printf 'Native %s derivation: %s\n' "$fixture" "$drv"
[[ $drv =~ ^/nix/store/[a-z0-9]{32}-nixos-system-surface-[a-zA-Z0-9._-]+\.drv$ ]]
nix build -L -v "$drv^out" --out-link "$s/system"
sys=$(readlink -e "$s/system")
[[ $sys != "$original" && $(readlink -f /run/booted-system) == "$original" &&
   $(readlink -f /run/current-system) == "$original" &&
   $(readlink -f /nix/var/nix/profiles/system) == "$(readlink -e "$gen20")" &&
   $(readlink "$gen20") == "$profile_before" ]]
default_after=$(sudo_run bootctl status --no-pager | awk '/^Default Boot Loader Entry:/ {d=1;next} d&&$1=="id:" {print $2;d=0}')
[[ $default_after == "$default_before" ]]
printf 'Native build complete: %s (no switch, profile change, or default boot change)\n' "$sys"
