{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.surface.devices.denali;
in
{
  options.surface.devices.denali.privateFirmwareDirectory = lib.mkOption {
    type = lib.types.nullOr lib.types.str;
    default = null;
    description = "Privately provisioned runtime firmware directory; never copied into the Nix store.";
  };

  config = lib.mkIf cfg.enable (
    lib.mkMerge [
      {
        hardware.firmware = [
          (lib.hiPrio pkgs.surfacePackages.wifiBoard)
          pkgs.linux-firmware
          pkgs.wireless-regdb
        ];
      }
      (lib.mkIf (cfg.privateFirmwareDirectory != null) {
        assertions = [
          {
            assertion = lib.hasPrefix "/" cfg.privateFirmwareDirectory;
            message = "surface.devices.denali.privateFirmwareDirectory must be absolute.";
          }
        ];
        systemd.services.surface-private-firmware = {
          description = "Expose privately provisioned Surface firmware";
          wantedBy = [ "multi-user.target" ];
          before = [
            "display-manager.service"
            "greetd.service"
          ];
          unitConfig.ConditionPathIsDirectory = cfg.privateFirmwareDirectory;
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
            RuntimeDirectory = "surface-firmware";
          };
          script = ''
            cp -rLs ${config.hardware.firmware}/lib/firmware/. /run/surface-firmware/
            cp -rL --remove-destination ${lib.escapeShellArg cfg.privateFirmwareDirectory}/. /run/surface-firmware/
            printf %s /run/surface-firmware > /sys/module/firmware_class/parameters/path
          '';
        };
        system.activationScripts.surfacePrivateFirmware = {
          deps = [ "udevd" ];
          text = ''
            if [ -d /run/surface-firmware ]; then
              printf %s /run/surface-firmware > /sys/module/firmware_class/parameters/path
            fi
          '';
        };
      })
    ]
  );
}
