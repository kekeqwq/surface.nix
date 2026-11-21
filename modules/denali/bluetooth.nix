{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.surface.devices.denali;
  btmgmt = lib.getExe' config.hardware.bluetooth.package "btmgmt";
  setupAddress = pkgs.writeShellApplication {
    name = "denali-bluetooth-address";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.gnugrep
    ];
    text = ''
      controller=$1
      address=$2
      [[ $controller =~ ^hci[0-9]+$ ]]
      for ((i=0; i<30; i++)); do
        # Address assignment transitions the controller from the unconfigured
        # index list to the regular list asynchronously. Never overwrite an
        # already configured controller, and let BlueZ's AutoEnable policy
        # decide whether it powers up.
        info=$(timeout 2 ${btmgmt} -i "$controller" info 2>&1 || true)
        if grep -qE '^[[:space:]]*addr [[:xdigit:]:]+ version' <<< "$info"; then
          exit 0
        fi
        opts=$(timeout 2 ${btmgmt} -i "$controller" config 2>&1 || true)
        if grep -qE 'missing options:.*public-address' <<< "$opts"; then
          timeout 2 ${btmgmt} -i "$controller" public-addr "$address" || true
        fi
        sleep 0.5
      done
      echo "Denali $controller did not become configured" >&2
      exit 1
    '';
  };
in
{
  options.surface.devices.denali.bluetoothAddress = lib.mkOption {
    type = lib.types.nullOr (lib.types.strMatching "[0-9a-fA-F][02468aAcCeE](:[0-9a-fA-F]{2}){5}");
    default = null;
    example = "02:00:00:00:12:34";
    description = "Per-device WCN7850 public address (prefer the factory address); a distinct locally administered address can be used on a test installation. Leave null to disable assignment.";
  };

  config = lib.mkIf (cfg.enable && config.hardware.bluetooth.enable && cfg.bluetoothAddress != null) {
    assertions = [
      {
        assertion =
          !(builtins.elem (lib.toLower cfg.bluetoothAddress) [
            "00:00:00:00:00:00"
            "00:00:00:00:5a:ad"
          ]);
        message = "Denali Bluetooth needs a real per-device address, not the Qualcomm placeholder.";
      }
    ];
    # Match the built-in WCN7850's UART, not a plugged-in USB adapter.
    services.udev.extraRules = ''
      ACTION=="add", SUBSYSTEM=="bluetooth", KERNEL=="hci[0-9]*", KERNELS=="a98000.serial", TAG+="systemd", ENV{SYSTEMD_WANTS}+="surface-bluetooth-address@%k.service"
    '';
    systemd.services."surface-bluetooth-address@" = {
      description = "Assign an address to Denali Bluetooth controller %I";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${lib.getExe setupAddress} %I ${cfg.bluetoothAddress}";
        TimeoutStartSec = "25s";
      };
    };
  };
}
