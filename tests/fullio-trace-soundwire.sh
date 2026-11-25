#!/usr/bin/env bash
# Observe an already booted FullIO diagnostic fixture. No register writes.
set -euo pipefail
[[ $EUID == 0 ]]
case $(tr -d '\0' </sys/firmware/devicetree/base/sound/model) in
    Denali-FullIO-VI-Probe) kind=VI ;;
    Denali-FullIO-CPS-Probe) kind=CPS ;;
    X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0)
        [[ $(uname -r) == *-surface-fullio-muted-test ]]
        [[ ! -e /sys/firmware/devicetree/base/sound/microsoft,denali-fullio-post-pa-test ]]
        kind=MUTE
        ;;
    *) exit 1 ;;
esac
user=${1:?pass the unprivileged test user}
probe=${2:?pass the unprivileged sidechain smoke script}
alsa=${3:?pass the alsa-utils bin directory}
[[ $(id -u "$user") != 0 ]]
trace=/sys/kernel/tracing
[[ $(findmnt -n -o FSTYPE --mountpoint "$trace") == tracefs ]]
name=fullio_sdw_$$
instance=$trace/instances/$name
mkdir -- "$instance"
registered=()
cleanup() {
    printf '0\n' > "$instance/tracing_on" || true
    rmdir -- "$instance" || true
    local event
    for event in "${registered[@]}"; do
        printf -- '-:%s/%s\n' "$name" "$event" >> "$trace/kprobe_events" || true
    done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '0\n' > "$instance/tracing_on"
add_probe() {
    local kind=$1 event=$2 symbol=$3 args=${4:-}
    if printf '%s:%s/%s %s %s\n' "$kind" "$name" "$event" "$symbol" "$args" >> "$trace/kprobe_events"; then
        registered+=("$event")
        printf '1\n' > "$instance/events/$name/$event/enable"
    else
        printf 'Trace symbol unavailable: %s\n' "$symbol" >&2
    fi
}
for symbol in qcom_snd_sdw_prepare sdw_prepare_stream sdw_enable_stream sdw_disable_stream sdw_deprepare_stream q6apm_graph_start q6apm_read; do
    add_probe p "$symbol" "$symbol"
    add_probe r "${symbol}_ret" "$symbol" 'rc=$retval:s32'
done
for symbol in wsa884x_port_prep wsa_macro_enable_vi_feedback; do
    add_probe p "$symbol" "$symbol"
done
# In this arm64 kernel, gpr_resp_pkt begins with the packed 24-byte GPR header.
# Record header fields only; don't dereference the payload pointer.
if [[ $(uname -m) == aarch64 ]]; then
    add_probe p feedback_gpr_rx graph_callback 'opcode=+20($arg1):x32 token=+16($arg1):u32 bytes=+32($arg1):s32'
fi
if ((${#registered[@]} == 0)); then
    echo 'No SoundWire probes available.' >&2
    exit 1
fi
printf '1\n' > "$instance/tracing_on"
printf '%s test begin\n' "$kind" > "$instance/trace_marker"
result=0
if [[ $kind == MUTE ]]; then
    runuser -u "$user" -- bash "$probe" "$alsa" "${4:?pass the pinned libasound.so.2}" || result=$?
else
    runuser -u "$user" -- bash "$probe" "$alsa" || result=$?
fi
printf '%s test end\n' "$kind" > "$instance/trace_marker"
printf '0\n' > "$instance/tracing_on"
# Strip instruction pointers and other unrelated trace lines; retain return codes.
awk '
    /[A-Z]+ test (begin|end)/ { print; next }
    /: feedback_gpr_rx:/ {
        if (match($0, /opcode=0x[[:xdigit:]]+ token=[0-9]+ bytes=-?[0-9]+/)) {
            split($0, a, ": ");
            print a[1] ": feedback_gpr_rx: " substr($0, RSTART, RLENGTH);
        }
        next;
    }
    /fullio_sdw_/ || /: (qcom_snd_sdw_|sdw_(prepare|enable|disable|deprepare)_stream|wsa884x_port_prep|wsa_macro_enable_vi_feedback|q6apm_graph_start|q6apm_read)/ {
        n = split($0, a, ": ");
        if (n < 3) next;
        printf "%s: %s:", a[1], a[2];
        if (match($0, /rc=-?[0-9]+/)) printf " %s", substr($0, RSTART, RLENGTH);
        print "";
    }
' "$instance/trace"
exit "$result"
