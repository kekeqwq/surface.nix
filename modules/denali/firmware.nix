{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.surface.devices.denali;
  prepare = pkgs.writeShellScript "surface-prepare-firmware" (
    ''
      export PATH=${lib.makeBinPath [ pkgs.coreutils ]}
    ''
    + builtins.readFile ../../scripts/prepare-firmware.sh
  );
  runtime = "/run/surface/firmware";
in
{
  options.surface.devices.denali.privateFirmwareDirectory = lib.mkOption {
    type = lib.types.nullOr lib.types.str;
    default = null;
    description = "Owner-supplied firmware on the root filesystem, available during activation. Bytes never enter Nix store outputs.";
  };

  config = lib.mkIf cfg.enable (
    lib.mkMerge [
      {
        hardware.firmware = [
          (lib.hiPrio pkgs.surfacePackages.wifiBoard)
          pkgs.surfacePackages.audioTopology
          pkgs.linux-firmware
          pkgs.wireless-regdb
        ];
        # Keep the shared UCM definition and conservative speaker behavior.
        systemd.user.services.wireplumber.environment.ALSA_CONFIG_UCM2 =
          "${pkgs.surfacePackages.alsaUcm}/share/alsa/ucm2";
        services.pipewire.wireplumber.extraConfig."51-surface-speaker" = {
          "monitor.alsa.rules" = [
            {
              matches = [ { "device.name" = "alsa_card.platform-sound"; } ];
              actions.update-props."device.profile" = "HiFi (Mic, Speaker)";
            }
            {
              matches = [ { "node.name" = "alsa_output.platform-sound.HiFi__Speaker__sink"; } ];
              actions.update-props = {
                "api.alsa.soft-mixer" = true;
                "api.alsa.disable-mmap" = true;
              };
            }
          ];
        };
      }
      (lib.mkIf (cfg.privateFirmwareDirectory != null) {
        assertions = [
          {
            assertion =
              lib.hasPrefix "/" cfg.privateFirmwareDirectory
              && !(lib.hasPrefix "/nix/store/" cfg.privateFirmwareDirectory);
            message = "Denali privateFirmwareDirectory must be an absolute, privately provisioned path outside the Nix store.";
          }
        ];
        # The first GPU request was measured AFTER switch-root, BEFORE ordinary
        # services. Preparing firmware only in a later oneshot or only inside an
        # initrd leaves a gap and can poison initial GPU state.
        system.activationScripts.surfacePrivateFirmware = {
          deps = [ "udevd" ];
          text = ''
            ${prepare} ${lib.escapeShellArg "${config.hardware.firmware}/lib/firmware"} ${lib.escapeShellArg cfg.privateFirmwareDirectory}
          '';
        };
        systemd.services.surface-private-firmware = {
          description = "Verify early Surface private firmware";
          wantedBy = [ "multi-user.target" ];
          before = [
            "display-manager.service"
            "greetd.service"
          ];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
            RuntimeDirectory = "surface";
            RuntimeDirectoryMode = "0700";
            RuntimeDirectoryPreserve = "yes";
          };
          script = ''
            ${pkgs.diffutils}/bin/cmp ${runtime}/qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn ${lib.escapeShellArg cfg.privateFirmwareDirectory}/qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn
            printf %s ${runtime} > /sys/module/firmware_class/parameters/path
          '';
        };
        systemd.services.surface-adsp = {
          description = "Start Surface ADSP after private firmware is ready";
          after = [ "surface-private-firmware.service" ];
          requires = [ "surface-private-firmware.service" ];
          wantedBy = [ "multi-user.target" ];
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
          };
          script = ''
            for remote in /sys/class/remoteproc/remoteproc*; do
              [ "$(${pkgs.coreutils}/bin/cat "$remote/name")" = adsp ] || continue
              if [ "$(${pkgs.coreutils}/bin/cat "$remote/state")" != running ]; then
                echo start > "$remote/state"
              fi
            done
            echo sound > /sys/bus/platform/drivers_probe || true
          '';
        };
      })
    ]
  );
}
