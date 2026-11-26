{
  config,
  lib,
  pkgs,
  ...
}:
let
  node = "/dev/surface/denali/ipts";
  deviceUnit = "dev-surface-denali-ipts.device";
  service = "denali-iptsd";
in
{
  config = lib.mkIf config.surface.devices.denali.enable {
    services.iptsd.enable = lib.mkDefault true;

    services.udev.extraRules = lib.mkIf config.services.iptsd.enable ''
      # Run after the package's 50-iptsd.rules. Replace its numbered launch
      # only for the Denali touchscreen, not other IPTS or Surface HID devices.
      ACTION=="add|change", SUBSYSTEM=="hidraw", KERNELS=="001C:045E:0C83.*", \
        SYMLINK+="surface/denali/ipts", TAG+="systemd", \
        ENV{SYSTEMD_ALIAS}+="${node}", ENV{SYSTEMD_WANTS}="${service}.service"
    '';

    systemd.services.${service} = lib.mkIf config.services.iptsd.enable {
      description = "Denali touchscreen and stylus (IPTSD)";
      # The raw numeric node can be briefly assigned to the magnetic touchpad
      # during boot. Order against and follow only the verified touchscreen.
      bindsTo = [ deviceUnit ];
      after = [ deviceUnit ];
      restartTriggers = [ config.environment.etc."iptsd.conf".source ];
      serviceConfig.ExecStart = "${lib.getExe' pkgs.iptsd "iptsd"} ${node}";
    };
  };
}
